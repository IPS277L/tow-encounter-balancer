from copy import deepcopy
from dataclasses import replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.unit.test_m2_npc_round_coordinator import Candidates, request as round_request, resume
from tests.unit.test_m2_npc_roster_attack_execution import change_participant
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.npc_attack_selection_models import NpcAttackSelectionBlock as Block
from towr.domain.npc_round_models import NpcRoundOutcome
from towr.domain.resolution_models import GiveGroundRequest
from towr.engine import npc_attack_controller as controller
from towr.engine.npc_round_coordinator import run_npc_round
from towr.rules import npc_roster_attack_execution as executor


CASES = (
    ((Condition.BROKEN,), Block.ACTOR_BROKEN, "broken"),
    ((Condition.DEFENCELESS,), Block.ACTOR_DEFENCELESS, "defenceless"),
    ((Condition.BROKEN, Condition.DEFENCELESS), Block.ACTOR_DEFENCELESS, "defenceless"),
)


def source_round(opposition_first=False):
    source = round_request()
    if opposition_first:
        source = replace(source, round_state=replace(source.round_state,
                         side_order=source.round_state.side_order[::-1]))
    return source


def with_conditions(state, actor_id, conditions):
    index = next(i for i, member in enumerate(state.roster.participants) if member.state.actor_id == actor_id)
    injury = state.roster.participants[index].state.injury
    return change_participant(state, index, injury=replace(injury, conditions=ConditionState(frozenset(conditions))))


def selection(opposition_first=False):
    stopped = run_npc_round(source_round(opposition_first), Candidates(empty=True), Mock())
    return Candidates().get_candidates(stopped.blocked_selection.source_request)


class M2NpcAttackConditionsTests(unittest.TestCase):
    def test_actor_conditions_block_both_sides_before_preparation_even_without_candidates(self):
        for opposite, (conditions, reason, _), empty in product((False, True), CASES, (False, True)):
            with self.subTest(opposite=opposite, conditions=conditions, empty=empty):
                source = selection(opposite)
                source = replace(source, state=with_conditions(source.state, source.actor_id, conditions),
                                 candidates=() if empty else source.candidates)
                before = deepcopy(source)
                with (patch.object(controller, "prepare_npc_attack") as attack,
                      patch.object(controller, "prepare_npc_attack_protection") as protection):
                    result = controller.select_npc_attack(source)
                attack.assert_not_called()
                protection.assert_not_called()
                self.assertIs(result.blocked_reason, reason)
                self.assertIs(result.source_request, source)
                self.assertIsNone(result.execution_request)
                self.assertIsNone(result.selected_candidate)
                self.assertEqual(result.rejected, ())
                self.assertFalse(source.round_state.active_turn.action_slots[0].executed)
                self.assertEqual(source, before)

    def test_direct_request_and_executor_share_guard_before_rng_and_receipt(self):
        for opposite, (conditions, _, message) in product((False, True), CASES):
            with self.subTest(opposite=opposite, conditions=conditions):
                executable = controller.select_npc_attack(selection(opposite)).execution_request
                state = with_conditions(executable.state, executable.execution.actor_id, conditions)
                before = deepcopy(executable)
                rng, decisions = Mock(), Mock()
                with patch.object(executor, "execute_attack_action") as action:
                    with self.assertRaisesRegex(ValueError, message):
                        replace(executable, state=state)
                    # Simulate an invalid reconstructed object to exercise executor revalidation.
                    invalid = deepcopy(executable)
                    object.__setattr__(invalid, "state", state)
                    with self.assertRaisesRegex(ValueError, message):
                        executor.execute_npc_roster_attack(invalid, rng, decisions=decisions)
                action.assert_not_called()
                self.assertEqual(rng.mock_calls, [])
                self.assertEqual(decisions.mock_calls, [])
                self.assertEqual(executable, before)
                self.assertIs(invalid.state, state)
                self.assertEqual(state.consumed_execution_ids, ())

    def test_pending_and_defeated_keep_priority_over_conditions(self):
        source = selection()
        state = with_conditions(source.state, source.actor_id, (Condition.BROKEN, Condition.DEFENCELESS))
        injury = replace(state.roster.participant(source.actor_id).state.injury, wounds=1, defeated=True)
        defeated = change_participant(state, 0, injury=injury)
        for current in (state, defeated):
            pending = (GiveGroundRequest("unresolved"),)
            result = controller.select_npc_attack(replace(source, state=current, pending_follow_ups=pending))
            self.assertIs(result.blocked_reason, Block.PENDING_FOLLOW_UPS)
            self.assertEqual(result.source_request.pending_follow_ups, pending)
        result = controller.select_npc_attack(replace(source, state=defeated))
        self.assertIs(result.blocked_reason, Block.ACTOR_DEFEATED)

    def test_other_conditions_and_broken_target_do_not_prohibit_actor_attack(self):
        for opposite, condition in product((False, True), (None, Condition.STAGGERED, Condition.PRONE)):
            with self.subTest(opposite=opposite, condition=condition):
                source = selection(opposite)
                state = with_conditions(source.state, source.actor_id, () if condition is None else (condition,))
                state = with_conditions(state, source.candidates[0].target_id, (Condition.BROKEN,))
                result = controller.select_npc_attack(replace(source, state=state))
                self.assertIsNone(result.blocked_reason)
                self.assertIsNotNone(result.execution_request)
                # A Defenceless target is also legal with unopposed Protection.
                state = with_conditions(state, source.candidates[0].target_id, (Condition.DEFENCELESS,))
                candidate = replace(source.candidates[0], protection_skill=None)
                result = controller.select_npc_attack(replace(source, state=state, candidates=(candidate,)))
                self.assertIsNone(result.blocked_reason)
                self.assertIsNone(result.execution_request.preparation.attack.defender_test)

    def test_changed_conditions_invalidate_old_selection_and_fresh_selection_recovers(self):
        source = selection()
        selected = controller.select_npc_attack(source)
        blocked_state = with_conditions(source.state, source.actor_id, (Condition.BROKEN,))
        with self.assertRaisesRegex(ValueError, "stale"):
            controller.require_current_npc_attack_selection(selected, blocked_state, source.round_state,
                                                          pending_follow_ups=())
        blocked = controller.select_npc_attack(replace(source, state=blocked_state))
        self.assertIs(blocked.blocked_reason, Block.ACTOR_BROKEN)
        # Caller supplies the result of external recovery; selection never removes Conditions.
        recovered = with_conditions(blocked_state, source.actor_id, ())
        fresh = controller.select_npc_attack(replace(source, state=recovered))
        self.assertIsNotNone(controller.require_current_npc_attack_selection(
            fresh, recovered, source.round_state, pending_follow_ups=()))
        self.assertTrue(blocked_state.roster.participant(source.actor_id).state.injury.conditions.has(Condition.BROKEN))

    def test_round_stop_and_resume_preserve_unexecuted_slot_and_pending_priority_on_both_sides(self):
        for opposite, (conditions, reason, _) in product((False, True), CASES):
            with self.subTest(opposite=opposite, conditions=conditions):
                source = source_round(opposite)
                actor = source.next_actor(source.round_state)
                source = replace(source, state=with_conditions(source.state, actor, conditions))
                before = deepcopy(source)
                rng, decisions = Mock(), Mock()
                provider = Candidates()
                with patch.object(executor, "execute_attack_action") as action:
                    stopped = run_npc_round(source, provider, rng, decisions=decisions)
                    again = run_npc_round(resume(source, stopped), provider, rng, decisions=decisions)
                    pending = replace(resume(source, again), pending_follow_ups=(GiveGroundRequest("pending"),))
                    unused_provider = Mock()
                    waiting = run_npc_round(pending, unused_provider, rng, decisions=decisions)
                action.assert_not_called()
                unused_provider.get_candidates.assert_not_called()
                self.assertEqual(rng.mock_calls, [])
                self.assertEqual(decisions.mock_calls, [])
                self.assertIs(stopped.outcome, NpcRoundOutcome.SELECTION_BLOCKED)
                self.assertIs(again.blocked_selection.blocked_reason, reason)
                self.assertEqual(len(provider.contexts), 2)
                self.assertTrue(again.blocked_selection.source_request.candidates)
                self.assertEqual(again.round_state, stopped.round_state)
                self.assertEqual(len(again.round_state.active_turn.action_slots), 1)
                self.assertFalse(again.round_state.active_turn.action_slots[0].executed)
                self.assertEqual(again.round_state.completed_turn_entity_ids, ())
                self.assertEqual(again.state, source.state)
                self.assertEqual(waiting.steps, ())
                self.assertIs(waiting.outcome, NpcRoundOutcome.PENDING_FOLLOW_UPS)
                self.assertEqual(waiting.pending_follow_ups, pending.pending_follow_ups)
                self.assertEqual(source, before)
