from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import Mock

from tests.helpers import SequenceRandom
from tests.unit.test_k1_kernel import FixedKernelDecisions
from tests.unit.test_m2_npc_attack_controller import candidate, request as selection_request
from tests.unit.test_m2_npc_roster_attack_execution import change_participant
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.injury_models import ProfileInjuryState, ProfileStateChangeRequest
from towr.domain.npc_attack_selection_models import NpcAttackSelectionBlock, NpcAttackSelectionResult
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_round_models import NpcRoundOutcome, NpcRoundRequest
from towr.domain.resolution_models import GiveGroundRequest, TargetInjuryPolicy
from towr.domain.turn_models import (
    CombatActionDeclaration, CombatActionKind, CombatActionSlotResult, CombatRoundState,
    CombatTurnEndResult, CombatTurnStartResult,
)
from towr.engine.npc_round_coordinator import run_npc_round


def request():
    source = selection_request()
    combat_round = CombatRoundState(1, source.state.roster.turn_participants)
    return NpcRoundRequest("round:test", source.state, combat_round,
                           tuple(p.entity_id for p in combat_round.participants), ())


class Candidates:
    def __init__(self, *, empty=False):
        self.contexts = []
        self.empty = empty

    def get_candidates(self, context):
        self.contexts.append(context)
        if self.empty:
            return context
        target = {"brigand:0": "brigand:2", "brigand:1": "brigand:3",
                  "brigand:2": "brigand:0", "brigand:3": "brigand:1"}[context.actor_id]
        proposed = candidate(context.state, context.id + ":candidate", target_id=target)
        return replace(context, candidates=(proposed,))


def resume(source, result, *, pending=None):
    return replace(source, state=result.state, round_state=result.round_state,
                   pending_follow_ups=result.pending_follow_ups if pending is None else pending)


class M2NpcRoundCoordinatorTests(unittest.TestCase):
    def test_no_candidate_keeps_unexecuted_slot_and_resume_does_not_reserve_it_twice(self):
        source = request()
        rng = Mock()
        stopped = run_npc_round(source, Candidates(empty=True), rng)
        rng.randint.assert_not_called()
        self.assertIs(stopped.outcome, NpcRoundOutcome.SELECTION_BLOCKED)
        self.assertIs(stopped.blocked_selection.blocked_reason, NpcAttackSelectionBlock.NO_CANDIDATE)
        self.assertEqual(stopped.state, source.state)
        self.assertEqual(stopped.round_state.active_turn.actor_id, "brigand:0")
        self.assertFalse(stopped.round_state.active_turn.action_slots[0].executed)
        self.assertFalse(any(isinstance(step, CombatTurnEndResult) for step in stopped.steps))
        completed = run_npc_round(resume(source, stopped), Candidates(), SequenceRandom([10] * 24))
        self.assertIs(completed.outcome, NpcRoundOutcome.COMPLETE)
        self.assertIsInstance(completed.steps[0], NpcAttackSelectionResult)
        self.assertEqual(sum(isinstance(step, CombatActionSlotResult) for step in completed.steps), 3)
        self.assertEqual(sum(isinstance(step, NpcRosterAttackExecutionResult) for step in completed.steps), 4)

    def test_wound_stops_before_turn_end_and_pending_is_not_implicitly_acknowledged(self):
        source = request()
        provider = Candidates()
        rng = SequenceRandom([1, 2, 10, 10, 10, 10, 7])
        stopped = run_npc_round(source, provider, rng)
        self.assertIs(stopped.outcome, NpcRoundOutcome.PENDING_FOLLOW_UPS)
        self.assertEqual(len(provider.contexts), 1)
        self.assertEqual(rng.randint(1, 10), 7)
        self.assertTrue(stopped.state.roster.participant("brigand:2").state.injury.defeated)
        self.assertIsInstance(stopped.pending_follow_ups[0], ProfileStateChangeRequest)
        self.assertTrue(stopped.round_state.active_turn.action_slots[0].executed)
        self.assertEqual(stopped.round_state.completed_turn_entity_ids, ())
        again_provider, again_rng = Mock(), Mock()
        again = run_npc_round(resume(source, stopped), again_provider, again_rng)
        self.assertEqual(again.steps, ())
        self.assertEqual(again.pending_follow_ups, stopped.pending_follow_ups)
        again_provider.get_candidates.assert_not_called()
        again_rng.randint.assert_not_called()

    def test_resume_after_external_defeat_acknowledgement_closes_receipt_without_reexecuting(self):
        source = request()
        first = run_npc_round(source, Candidates(), SequenceRandom([1, 2, 10, 10, 10, 10]))
        # Caller/GM has acknowledged the defeat disposition; no automatic acknowledgement is implied.
        provider = Candidates()
        rng = SequenceRandom([10] * 6 + [7])
        later = run_npc_round(resume(source, first, pending=()), provider, rng)
        self.assertIsInstance(later.steps[0], CombatTurnEndResult)
        self.assertEqual(tuple(c.actor_id for c in provider.contexts), ("brigand:1",))
        self.assertEqual(len(later.state.consumed_execution_ids), 2)
        self.assertEqual(later.round_state.completed_turn_entity_ids, ("brigand:0", "brigand:1"))
        self.assertIs(later.outcome, NpcRoundOutcome.DEFEATED_ACTOR)
        self.assertIsNone(later.round_state.active_turn)
        self.assertEqual(later.round_state.participants, source.round_state.participants)
        self.assertEqual(rng.randint(1, 10), 7)

    def test_real_give_ground_remains_pending_and_prevents_later_actor(self):
        source = request()
        target = source.state.roster.participant("brigand:2").state.injury
        state = change_participant(source.state, 2, injury=replace(target,
            conditions=target.conditions.with_condition(Condition.STAGGERED)))
        provider = Candidates()
        stopped = run_npc_round(replace(source, state=state), provider, SequenceRandom([1, 10, 10, 10, 10, 10]),
                                decisions=FixedKernelDecisions(stagger=StaggerChoice.GIVE_GROUND))
        self.assertIs(stopped.outcome, NpcRoundOutcome.PENDING_FOLLOW_UPS)
        self.assertIsInstance(stopped.pending_follow_ups[0], GiveGroundRequest)
        self.assertEqual(len(provider.contexts), 1)
        self.assertEqual(stopped.round_state.completed_turn_entity_ids, ())

    def test_completed_round_noops_and_old_round_with_returned_history_cannot_repeat_attacks(self):
        source = request()
        result = run_npc_round(source, Candidates(), SequenceRandom([10] * 24))
        provider, rng = Mock(), Mock()
        completed = run_npc_round(resume(source, result), provider, rng)
        self.assertIs(completed.outcome, NpcRoundOutcome.COMPLETE)
        self.assertEqual(completed.steps, ())
        provider.get_candidates.assert_not_called()
        rng.randint.assert_not_called()
        rewound_round = replace(source, state=result.state)
        blocked = run_npc_round(rewound_round, Candidates(), rng)
        self.assertIs(blocked.blocked_selection.blocked_reason, NpcAttackSelectionBlock.EXECUTION_CONSUMED)
        rng.randint.assert_not_called()

    def test_provider_must_use_exact_current_context_before_rng(self):
        source = request()
        for field, value in (("id", "other"), ("actor_id", "brigand:1")):
            with self.subTest(field=field):
                provider = Mock()
                provider.get_candidates.side_effect = lambda context: replace(context, **{field: value})
                rng = Mock()
                with self.assertRaisesRegex(ValueError, "changed the current"):
                    run_npc_round(source, provider, rng)
                rng.randint.assert_not_called()
        with self.assertRaises(TypeError):
            run_npc_round(source, Mock(get_candidates=Mock(return_value=())), Mock())

    def test_request_rejects_invalid_order_source_policy_and_unapplied_receipt(self):
        source = request()
        for order in ((), source.actor_order[:-1], source.actor_order + source.actor_order[:1], ("absent",)):
            with self.subTest(order=order), self.assertRaises(ValueError):
                replace(source, actor_order=order)
        participants = list(source.state.roster.participants)
        participant = participants[3]
        participants[3] = replace(participant,
            definition=replace(participant.definition, id="brute", injury_policy=TargetInjuryPolicy.BRUTE, wound_limit=2),
            state=replace(participant.state, definition_id="brute", injury=ProfileInjuryState(0, 2)))
        with self.assertRaisesRegex(ValueError, "Minion participants"):
            replace(source, state=replace(source.state, roster=NpcRoster(tuple(participants))))
        stopped = run_npc_round(source, Candidates(), SequenceRandom([1, 2, 10, 10, 10, 10]))
        with self.assertRaisesRegex(ValueError, "matching consumed"):
            replace(source, round_state=stopped.round_state)
        with self.assertRaises(TypeError):
            replace(source, pending_follow_ups=(object(),))

    def test_unsupported_active_action_is_rejected_without_turn_rewrite(self):
        source = request()
        stopped = run_npc_round(source, Candidates(empty=True), Mock())
        turn = stopped.round_state.active_turn
        turn = replace(turn, action_slots=(replace(turn.action_slots[0],
            declaration=CombatActionDeclaration(CombatActionKind.RECOVER)),))
        with self.assertRaisesRegex(ValueError, "one standard Attack"):
            replace(source, round_state=replace(stopped.round_state, active_turn=turn))

    def test_result_trace_is_bound_to_order_snapshot_and_complete_transitions(self):
        source = request()
        before = deepcopy(source)
        result = run_npc_round(source, Candidates(), SequenceRandom([10] * 24))
        self.assertEqual(source, before)
        with self.assertRaises(FrozenInstanceError):
            result.steps = ()
        with self.assertRaisesRegex(ValueError, "before completion"):
            replace(result, steps=result.steps[:-1])
        with self.assertRaises(ValueError):
            replace(result, steps=(result.steps[0], result.steps[0], *result.steps[1:]))
        with self.assertRaisesRegex(ValueError, "source/order"):
            replace(result, source_request=replace(source, actor_order=("brigand:1", "brigand:0", "brigand:2", "brigand:3")))
        with self.assertRaisesRegex(ValueError, "current roster/round"):
            replace(result, source_request=replace(source,
                state=change_participant(source.state, 3, available_attack_ids=())))

    def test_incoming_defeated_actor_stops_without_provider_slot_or_rng(self):
        source = request()
        source = replace(source, state=change_participant(source.state, 0,
            injury=ProfileInjuryState(1, 1, defeated=True)))
        provider, rng = Mock(), Mock()
        result = run_npc_round(source, provider, rng)
        self.assertIs(result.outcome, NpcRoundOutcome.DEFEATED_ACTOR)
        self.assertEqual(result.steps, ())
        self.assertEqual(result.round_state, source.round_state)
        provider.get_candidates.assert_not_called()
        rng.randint.assert_not_called()
