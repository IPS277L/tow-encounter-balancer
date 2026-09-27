from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_spatial_resolution import graph
from tests.unit.test_m2_npc_round_coordinator import Candidates, request, resume
from tests.unit.test_m2_npc_round_exclusion import defeat
from towr.domain.npc_round_advance_models import NpcRoundAdvanceRequest, NpcRoundAdvanceResult
from towr.domain.resolution_models import GiveGroundRequest
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement
from towr.domain.turn_models import CombatSide
from towr.engine.npc_round_coordinator import run_npc_round
from towr.rules import npc_round_advance as advance


def completed_context(*, reversed_sides=False):
    source = request()
    if reversed_sides:
        source = replace(source, round_state=replace(source.round_state, side_order=tuple(reversed(tuple(CombatSide)))))
    result = run_npc_round(source, Candidates(), SequenceRandom([10] * 24))
    current = resume(source, result)
    spatial = SpatialBattleState(graph(), tuple(
        SpatialEntityPlacement(p.entity_id, p.side.value, "zone:a") for p in current.round_state.participants
    ), gave_ground_entity_ids=("brigand:0",), free_move_used_entity_ids=("brigand:1",),
       difficult_terrain_tested_entity_ids=("brigand:2",))
    return NpcRoundAdvanceRequest("next", current, spatial, current.round_state.participants,
                                  tuple(reversed(current.actor_order)))


class M2NpcRoundAdvanceTests(unittest.TestCase):
    def test_one_synchronized_advance_preserves_roster_placements_histories_and_side_order(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                source = completed_context(reversed_sides=reverse)
                before = deepcopy(source)
                with (
                    patch.object(advance, "advance_combat_round", wraps=advance.advance_combat_round) as combat,
                    patch.object(advance, "start_next_spatial_round", wraps=advance.start_next_spatial_round) as spatial,
                ):
                    result = advance.advance_npc_round(source)
                combat.assert_called_once_with(source.combat_request)
                spatial.assert_called_once_with(source.spatial_state)
                current, moved = advance.apply_npc_round_advance(source.current, source.spatial_state, result)
                self.assertEqual(source, before)
                self.assertIs(current.state, source.current.state)
                self.assertEqual(current.id, source.current.id)
                self.assertEqual(current.actor_order, source.next_actor_order)
                self.assertEqual(current.round_state.side_order, source.current.round_state.side_order)
                self.assertEqual((current.round_state.round_number, moved.round_number), (2, 2))
                self.assertFalse(current.round_state.round_complete)
                self.assertEqual(current.round_state.completed_turn_entity_ids, ())
                self.assertEqual(current.round_state.excluded_turn_entity_ids, ())
                self.assertIsNone(current.round_state.active_turn)
                self.assertEqual(current.pending_follow_ups, ())
                self.assertEqual(moved.placements, source.spatial_state.placements)
                self.assertEqual(moved.graph, source.spatial_state.graph)
                self.assertEqual((moved.gave_ground_entity_ids, moved.free_move_used_entity_ids,
                                  moved.difficult_terrain_tested_entity_ids), ((), (), ()))
                with self.assertRaises(FrozenInstanceError):
                    result.spatial_state = source.spatial_state

    def test_incomplete_active_and_pending_rounds_fail_before_either_reducer(self):
        source = completed_context()
        active = run_npc_round(request(), Candidates(empty=True), Mock())
        for current in (request(), resume(request(), active),
                        replace(source.current, pending_follow_ups=(GiveGroundRequest("pending"),))):
            with self.subTest(current=current), patch.object(advance, "advance_combat_round") as combat, patch.object(advance, "start_next_spatial_round") as spatial:
                with self.assertRaises(ValueError):
                    advance.advance_npc_round(replace(source, current=current))
                combat.assert_not_called()
                spatial.assert_not_called()

    def test_defeated_cannot_return_and_explicit_two_sided_subset_keeps_whole_roster(self):
        source = completed_context()
        current = defeat(source.current, 3)
        with self.assertRaisesRegex(ValueError, "defeated"):
            replace(source, current=current)
        participants = current.round_state.participants[:3]
        selected = replace(source, current=current, next_round_participants=participants,
                           next_actor_order=tuple(p.entity_id for p in participants))
        result = advance.advance_npc_round(selected)
        self.assertIs(result.continuation.state.roster, current.state.roster)
        self.assertTrue(result.continuation.state.roster.participant("brigand:3").state.injury.defeated)
        self.assertEqual(result.continuation.round_state.participants, participants)

    def test_invalid_composition_order_and_single_or_empty_side_rejected(self):
        source = completed_context()
        for participants in ((), source.next_round_participants[:2],
                             (*source.next_round_participants, source.next_round_participants[0]),
                             (replace(source.next_round_participants[0], entity_id="unknown"), *source.next_round_participants[1:]),
                             (replace(source.next_round_participants[0], side=CombatSide.OPPOSITION), *source.next_round_participants[1:])):
            with self.subTest(participants=participants), self.assertRaises(ValueError):
                replace(source, next_round_participants=participants)
        for order in ((), source.next_actor_order[:-1], source.next_actor_order * 2, ("unknown",)):
            with self.subTest(order=order), self.assertRaises(ValueError):
                replace(source, next_actor_order=order)

    def test_spatial_round_missing_placement_and_wrong_side_rejected(self):
        source = completed_context()
        for spatial in (
            replace(source.spatial_state, round_number=2),
            replace(source.spatial_state, placements=source.spatial_state.placements[:3]),
            replace(source.spatial_state, placements=tuple(replace(p, side_id="wrong") if p.entity_id == "brigand:3" else p
                                                         for p in source.spatial_state.placements)),
        ):
            with self.subTest(spatial=spatial), self.assertRaises(ValueError):
                replace(source, spatial_state=spatial)

    def test_consumer_rejects_replay_and_partial_or_changed_source_snapshots(self):
        source = completed_context()
        result = advance.advance_npc_round(source)
        current, spatial = advance.apply_npc_round_advance(source.current, source.spatial_state, result)
        for candidate, placement in (
            (current, spatial), (current, source.spatial_state), (source.current, spatial),
            (replace(source.current, state=replace(source.current.state,
                acknowledged_defeat_execution_ids=source.current.state.consumed_execution_ids[:1])), source.spatial_state),
            (replace(source.current, pending_follow_ups=(GiveGroundRequest("later"),)), source.spatial_state),
            (source.current, replace(source.spatial_state, free_move_used_entity_ids=())),
        ):
            with self.subTest(candidate=candidate), self.assertRaisesRegex(ValueError, "source differs"):
                advance.apply_npc_round_advance(candidate, placement, result)
        with self.assertRaisesRegex(ValueError, "complete"):
            replace(source, id="new-id", current=current, spatial_state=spatial)

    def test_result_rejects_wrong_transition_number_placements_usage_or_trace(self):
        source = completed_context()
        result = advance.advance_npc_round(source)
        for combat in (replace(result.combat, request_id="other"), replace(result.combat, applied_rule_ids=()),
                       replace(result.combat, state=replace(result.combat.state, round_number=3))):
            with self.subTest(combat=combat), self.assertRaisesRegex(ValueError, "combat round transition"):
                replace(result, combat=combat)
        for spatial in (source.spatial_state, replace(result.spatial_state, gave_ground_entity_ids=("brigand:0",)),
                        replace(result.spatial_state, placements=tuple(replace(p, zone_id="zone:b") for p in result.spatial_state.placements))):
            with self.subTest(spatial=spatial), self.assertRaisesRegex(ValueError, "spatial round transition"):
                replace(result, spatial_state=spatial)

    def test_type_normalization_and_reducer_errors_preserve_inputs(self):
        source = completed_context()
        normalized = replace(source, next_round_participants=list(source.next_round_participants), next_actor_order=list(source.next_actor_order))
        self.assertEqual(normalized, source)
        for change in ({"id": ""}, {"current": object()}, {"spatial_state": object()}, {"next_round_participants": (object(),)}):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                replace(source, **change)
        with self.assertRaises(TypeError):
            advance.advance_npc_round(object())
        with self.assertRaises(TypeError):
            NpcRoundAdvanceResult(source, object(), source.spatial_state)
        with self.assertRaises(TypeError):
            advance.apply_npc_round_advance(source.current, source.spatial_state, object())
        before = deepcopy(source)
        for failure in ("advance_combat_round", "start_next_spatial_round"):
            with self.subTest(failure=failure), patch.object(advance, failure, side_effect=RuntimeError("failure")):
                with self.assertRaises(RuntimeError):
                    advance.advance_npc_round(source)
                self.assertEqual(source, before)
