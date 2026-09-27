from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import Mock

from tests.helpers import SequenceRandom
from tests.unit.test_k1_retreat_resolution import retreat_declaration, round_state as retreat_round
from tests.unit.test_m2_npc_roster_attack_execution import change_participant
from tests.unit.test_m2_npc_round_coordinator import Candidates, request, resume
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.npc_round_exclusion_models import NpcRoundExclusionRequest, NpcRoundExclusionResult
from towr.domain.npc_round_models import NpcRoundOutcome
from towr.domain.turn_models import CombatRoundAdvanceRequest, CombatSide, CombatTurnStartRequest
from towr.engine.npc_round_coordinator import run_npc_round
from towr.rules.npc_round_exclusion import apply_npc_round_exclusion, exclude_defeated_npc
from towr.rules.turn_resolution import advance_combat_round, start_combat_turn


def defeat(source, *indices):
    for index in indices:
        source = replace(source, state=change_participant(source.state, index,
            injury=ProfileInjuryState(1, 1, defeated=True)))
    return source


def exclude(source, actor_id):
    result = exclude_defeated_npc(NpcRoundExclusionRequest("exclude:" + actor_id, source, actor_id))
    return apply_npc_round_exclusion(source, result)


class M2NpcRoundExclusionTests(unittest.TestCase):
    def test_exclusion_preserves_roster_history_order_and_does_not_complete_a_turn(self):
        source = defeat(request(), 0)
        before = deepcopy(source)
        result = exclude_defeated_npc(NpcRoundExclusionRequest("exclude:0", source, "brigand:0"))
        updated = apply_npc_round_exclusion(source, result)
        self.assertEqual(source, before)
        self.assertIs(updated.state, source.state)
        self.assertEqual(updated.actor_order, source.actor_order)
        self.assertEqual(updated.round_state.participants, source.round_state.participants)
        self.assertEqual(updated.round_state.side_order, source.round_state.side_order)
        self.assertEqual(updated.round_state.excluded_turn_entity_ids, ("brigand:0",))
        self.assertEqual(updated.round_state.completed_turn_entity_ids, ())
        self.assertIsNone(updated.round_state.active_turn)
        self.assertIsNone(result.interrupted_turn)
        self.assertEqual(updated.next_actor(updated.round_state), "brigand:1")
        self.assertIn("RULE-NPC-002", result.applied_rule_ids)
        with self.assertRaises(FrozenInstanceError):
            result.source_request = None

    def test_remaining_sides_and_round_completion_include_exclusions_in_both_orders(self):
        for order in (tuple(CombatSide), tuple(reversed(tuple(CombatSide)))):
            with self.subTest(order=order):
                source = defeat(request(), 0, 1, 2, 3)
                source = replace(source, round_state=replace(source.round_state, side_order=order))
                first_side = [p.entity_id for p in source.round_state.participants if p.side is order[0]]
                for actor in first_side:
                    source = exclude(source, actor)
                self.assertIs(source.round_state.next_side, order[1])
                self.assertFalse(source.round_state.round_complete)
                for actor in source.actor_order:
                    if actor not in first_side:
                        source = exclude(source, actor)
                self.assertIsNone(source.round_state.next_side)
                self.assertTrue(source.round_state.round_complete)
                self.assertEqual(source.round_state.completed_turn_entity_ids, ())
                provider, rng = Mock(), Mock()
                completed = run_npc_round(source, provider, rng)
                self.assertIs(completed.outcome, NpcRoundOutcome.COMPLETE)
                self.assertEqual(completed.steps, ())
                provider.get_candidates.assert_not_called()
                rng.randint.assert_not_called()

    def test_pending_wound_blocks_exclusion_until_external_acknowledgement(self):
        source = request()
        stopped = run_npc_round(source, Candidates(), SequenceRandom([1, 2, 10, 10, 10, 10]))
        current = resume(source, stopped)
        with self.assertRaisesRegex(ValueError, "pending follow-ups"):
            exclude(current, "brigand:2")
        acknowledged = replace(current, pending_follow_ups=())
        result = exclude_defeated_npc(NpcRoundExclusionRequest("exclude:2", acknowledged, "brigand:2"))
        with self.assertRaisesRegex(ValueError, "source differs"):
            apply_npc_round_exclusion(current, result)
        updated = apply_npc_round_exclusion(acknowledged, result)
        self.assertEqual(updated.round_state.active_turn, acknowledged.round_state.active_turn)
        self.assertEqual(updated.state.consumed_execution_ids, stopped.state.consumed_execution_ids)

    def test_rejects_living_unknown_completed_and_already_excluded_actor(self):
        source = defeat(request(), 0)
        for actor in ("brigand:1", "absent"):
            with self.subTest(actor=actor), self.assertRaises(ValueError):
                exclude(source, actor)
        updated = exclude(source, "brigand:0")
        with self.assertRaisesRegex(ValueError, "already excluded"):
            exclude(updated, "brigand:0")
        completed = replace(source, round_state=replace(source.round_state,
            completed_turn_entity_ids=("brigand:0",)))
        with self.assertRaisesRegex(ValueError, "completed turn"):
            exclude(completed, "brigand:0")

    def test_application_rejects_replay_and_changed_roster_history_round_or_context(self):
        source = defeat(request(), 0)
        result = exclude_defeated_npc(NpcRoundExclusionRequest("exclude:0", source, "brigand:0"))
        updated = apply_npc_round_exclusion(source, result)
        changed = (
            updated,
            replace(source, state=change_participant(source.state, 1, available_attack_ids=())),
            replace(source, state=replace(source.state, consumed_execution_ids=("other",))),
            replace(source, round_state=replace(source.round_state, round_number=2)),
            replace(source, actor_order=tuple(reversed(source.actor_order))),
            replace(source, id="other"),
        )
        for current in changed:
            with self.subTest(current=current), self.assertRaisesRegex(ValueError, "source differs"):
                apply_npc_round_exclusion(current, result)

    def test_active_unexecuted_defeated_turn_is_interrupted_without_fake_receipt(self):
        source = request()
        stopped = run_npc_round(source, Candidates(empty=True), Mock())
        current = defeat(resume(source, stopped), 0)
        result = exclude_defeated_npc(NpcRoundExclusionRequest("exclude:0", current, "brigand:0"))
        updated = apply_npc_round_exclusion(current, result)
        self.assertIs(result.interrupted_turn, current.round_state.active_turn)
        self.assertFalse(result.interrupted_turn.action_slots[0].executed)
        self.assertIsNone(updated.round_state.active_turn)
        self.assertEqual(updated.round_state.completed_turn_entity_ids, ())
        self.assertEqual(updated.state.consumed_execution_ids, ())
        self.assertEqual(updated.next_actor(updated.round_state), "brigand:1")

    def test_executed_interrupted_turn_keeps_existing_receipt_and_history_in_source(self):
        source = request()
        stopped = run_npc_round(source, Candidates(), SequenceRandom([1, 2, 10, 10, 10, 10]))
        # External resolved consequence defeats the active actor; retain the already applied Attack.
        current = defeat(resume(source, stopped, pending=()), 0)
        result = exclude_defeated_npc(NpcRoundExclusionRequest("exclude:0", current, "brigand:0"))
        updated = apply_npc_round_exclusion(current, result)
        self.assertTrue(result.interrupted_turn.action_slots[0].executed)
        self.assertIs(updated.state, current.state)
        self.assertEqual(updated.state.consumed_execution_ids, stopped.state.consumed_execution_ids)
        self.assertEqual(updated.round_state.completed_turn_entity_ids, ())
        self.assertIsNone(updated.round_state.active_turn)

    def test_round_rejects_invalid_exclusions_and_active_or_completed_overlap(self):
        source = request()
        for ids in (("brigand:0", "brigand:0"), ("absent",), ("",), (1,)):
            with self.subTest(ids=ids), self.assertRaises((ValueError, TypeError)):
                replace(source.round_state, excluded_turn_entity_ids=ids)
        with self.assertRaisesRegex(ValueError, "completed"):
            replace(source.round_state, completed_turn_entity_ids=("brigand:0",),
                    excluded_turn_entity_ids=("brigand:0",))
        active = start_combat_turn(CombatTurnStartRequest("start", source.round_state, "brigand:0")).state
        with self.assertRaisesRegex(ValueError, "active turn"):
            replace(active, excluded_turn_entity_ids=("brigand:0",))
        with self.assertRaisesRegex(ValueError, "must be defeated"):
            replace(source, round_state=replace(source.round_state, excluded_turn_entity_ids=("brigand:0",)))

    def test_excluded_actor_cannot_start_even_with_remaining_ally_on_same_side(self):
        source = exclude(defeat(request(), 0), "brigand:0")
        with self.assertRaisesRegex(ValueError, "excluded"):
            start_combat_turn(CombatTurnStartRequest("start", source.round_state, "brigand:0"))
        started = start_combat_turn(CombatTurnStartRequest("start", source.round_state, "brigand:1"))
        self.assertEqual(started.turn.actor_id, "brigand:1")

    def test_round_advance_uses_explicit_new_roster_and_does_not_carry_exclusions(self):
        source = defeat(request(), 0, 1, 2, 3)
        for actor in source.actor_order:
            source = exclude(source, actor)
        # Eligibility in a subsequent round is caller-owned; supply a fresh two-sided composition.
        fresh = request().round_state.participants
        result = advance_combat_round(CombatRoundAdvanceRequest("next", source.round_state, fresh))
        self.assertEqual(result.state.round_number, 2)
        self.assertEqual(result.state.excluded_turn_entity_ids, ())
        self.assertEqual(result.state.completed_turn_entity_ids, ())
        self.assertEqual(result.state.side_order, source.round_state.side_order)
        with self.assertRaisesRegex(ValueError, "both sides"):
            advance_combat_round(CombatRoundAdvanceRequest("next", source.round_state, fresh[:2]))

    def test_retreat_does_not_mistake_exclusion_for_start_or_completed_enemy_turns(self):
        for enemies_first in (False, True):
            state = replace(retreat_round(enemies_first=enemies_first), excluded_turn_entity_ids=("enemy:1",))
            with self.subTest(enemies_first=enemies_first), self.assertRaisesRegex(ValueError, "not supported"):
                retreat_declaration(state=state)

    def test_typed_requests_and_results_reject_malformed_inputs(self):
        source = defeat(request(), 0)
        for args in (("", source, "brigand:0"), ("id", source, ""), ("id", object(), "brigand:0")):
            with self.subTest(args=args), self.assertRaises((ValueError, TypeError)):
                NpcRoundExclusionRequest(*args)
        with self.assertRaises(TypeError):
            NpcRoundExclusionResult(object())
        with self.assertRaises(TypeError):
            apply_npc_round_exclusion(source, object())
