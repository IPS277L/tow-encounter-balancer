from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_hidden_give_ground_resolution import context as completed_context
from tests.unit.test_k1_hidden_attack_chronology import completed_quietly
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.hidden_give_ground_models import HiddenGiveGroundExecutionRequest
from towr.domain.hidden_lifecycle_models import HiddenLifecycleApplicationRequest
from towr.domain.spatial_models import ZoneConnection
from towr.rules import hidden_lifecycle_resolution as lifecycle
from towr.rules import spatial_resolution as spatial
from towr.rules.hidden_give_ground_resolution import lose_hidden_opportunity_after_give_ground
from towr.rules.move_quietly_resolution import execute_move_quietly_action


def context(**options):
    state, loss, movement = completed_context(**options)
    return state, HiddenGiveGroundExecutionRequest(
        "hidden:execute-give-ground", loss.move_quietly, movement, state.consumed_opportunity_ids,
    )


class K1HiddenGiveGroundExecutionTests(unittest.TestCase):
    def test_executes_one_movement_condition_and_loss_with_consistent_result(self):
        for options, broken in (({}, False), ({"same_zone": True}, True),
                                ({"later": True}, False), ({"later": True, "enemy": True}, True)):
            with self.subTest(options=options):
                state, request = context(**options)
                before = deepcopy((state, request))
                with (
                    patch.object(lifecycle, "resolve_give_ground", wraps=spatial.resolve_give_ground) as move,
                    patch.object(spatial, "resolve_condition_application",
                                 wraps=spatial.resolve_condition_application) as condition,
                    patch.object(lifecycle, "lose_hidden_opportunity_after_give_ground",
                                 wraps=lose_hidden_opportunity_after_give_ground) as lose,
                    patch.object(lifecycle, "execute_registered_hidden_attack") as attack,
                ):
                    result = lifecycle.execute_hidden_lifecycle_give_ground(state, request)
                move.assert_called_once_with(request.movement)
                lose.assert_called_once_with(result.completed.source_request)
                self.assertEqual(condition.call_count, int(broken))
                attack.assert_not_called()
                movement = result.completed.source_request.movement
                self.assertIs(movement.previous_state, request.movement.state)
                self.assertIs(movement.source, request.movement.source)
                self.assertIs(result.completed.source_request.move_quietly, request.move_quietly)
                self.assertEqual(result.completed.request_id, request.id)
                self.assertEqual(movement.state.placement_for("hero").zone_id,
                                 request.movement.destination_zone_id)
                self.assertEqual(movement.state.gave_ground_entity_ids,
                                 (*request.movement.state.gave_ground_entity_ids, "hero"))
                self.assertEqual(movement.state.free_move_used_entity_ids,
                                 request.movement.state.free_move_used_entity_ids)
                self.assertEqual(movement.conditions.has(Condition.BROKEN), broken)
                self.assertIs(result.state.hiding_positions, state.hiding_positions)
                self.assertIsNone(result.state.opportunity)
                self.assertEqual(result.state.consumed_opportunity_ids,
                                 (*state.consumed_opportunity_ids, state.opportunity.id))
                self.assertTrue(set(movement.applied_rule_ids) <= set(result.applied_rule_ids))
                self.assertEqual((state, request), before)

    def test_inactive_stale_source_and_chain_fail_before_movement(self):
        state, request = context()
        other = execute_move_quietly_action(request.move_quietly.source_request, SequenceRandom([1, 1, 10]))
        for changed in (replace(state, active_move_quietly=None),
                        replace(state, active_move_quietly=other),
                        replace(state, consumed_opportunity_ids=()),
                        replace(state, consumed_opportunity_ids=("new", "hidden:older")), None):
            with self.subTest(state=changed), patch.object(lifecycle, "resolve_give_ground") as move:
                with self.assertRaises((ValueError, TypeError)):
                    lifecycle.execute_hidden_lifecycle_give_ground(changed, request)
                move.assert_not_called()

    def test_owner_placement_graph_and_chronology_fail_before_movement(self):
        state, request = context()
        movement = request.movement
        wrong_origin = replace(movement, state=replace(movement.state, placements=tuple(
            replace(item, zone_id="zone:c") if item.entity_id == "hero" else item
            for item in movement.state.placements)))
        wrong_side = replace(movement, state=replace(movement.state, placements=tuple(
            replace(item, side_id="other") if item.entity_id == "hero" else item
            for item in movement.state.placements)))
        graph = replace(movement, state=replace(movement.state, graph=replace(movement.state.graph,
            connections=(*movement.state.graph.connections, ZoneConnection("zone:c", "zone:d")))))
        for changes in (
            {"movement": replace(movement, mover_id="scout")}, {"movement": wrong_origin},
            {"movement": wrong_side}, {"movement": graph},
            {"movement": replace(movement, state=replace(movement.state, free_move_used_entity_ids=()))},
            {"movement": replace(movement, source=replace(movement.source,
                                                         resolution_id=request.move_quietly.request_id))},
            {"move_quietly": completed_quietly(3, 1)},
        ):
            with self.subTest(changes=changes), patch.object(lifecycle, "resolve_give_ground") as move:
                with self.assertRaises(ValueError):
                    lifecycle.execute_hidden_lifecycle_give_ground(state, replace(request, **changes))
                move.assert_not_called()

    def test_movement_restrictions_fail_without_consuming_opportunity(self):
        state, request = context(later=True)
        movement = request.movement
        for candidate in (
            replace(movement, state=replace(movement.state, gave_ground_entity_ids=("hero",))),
            replace(movement, mover_conditions=ConditionState((Condition.PRONE,))),
            replace(movement, mover_conditions=ConditionState((Condition.DEFENCELESS,))),
            replace(movement, crosses_obstacle=True),
            replace(movement, crosses_difficult_terrain=True),
            replace(movement, path_entity_ids=("scout",)),
            replace(movement, destination_zone_id="zone:b"),
            replace(movement, destination_zone_id="zone:d"),
            replace(movement, destination_zone_id="missing"),
            replace(movement, destination_zone_id="zone:c", away_from_entity_id="guard"),
        ):
            with self.subTest(movement=candidate):
                selected = replace(request, movement=candidate)
                before = deepcopy((state, selected))
                with patch.object(lifecycle, "apply_hidden_lifecycle_give_ground") as apply:
                    with self.assertRaises(ValueError):
                        lifecycle.execute_hidden_lifecycle_give_ground(state, selected)
                apply.assert_not_called()
                self.assertEqual((state, selected), before)

    def test_exceptions_including_broken_application_preserve_inputs(self):
        state, request = context(enemy=True)
        before = deepcopy((state, request))
        for module, stage in ((lifecycle, "resolve_give_ground"), (spatial, "resolve_condition_application"),
                              (lifecycle, "lose_hidden_opportunity_after_give_ground"),
                              (lifecycle, "apply_hidden_lifecycle_result")):
            with self.subTest(stage=stage), patch.object(module, stage, side_effect=RuntimeError(stage)):
                with self.assertRaisesRegex(RuntimeError, stage):
                    lifecycle.execute_hidden_lifecycle_give_ground(state, request)
            self.assertEqual((state, request), before)

    def test_replay_and_reactivation_fail_even_with_new_ids(self):
        state, request = context()
        result = lifecycle.execute_hidden_lifecycle_give_ground(state, request)
        renamed = replace(request, id="new", movement=replace(request.movement,
            source=replace(request.movement.source, resolution_id="reaction:new")))
        with patch.object(lifecycle, "resolve_give_ground") as move:
            with self.assertRaisesRegex(ValueError, "no active"):
                lifecycle.execute_hidden_lifecycle_give_ground(result.state, renamed)
            move.assert_not_called()
        with self.assertRaisesRegex(ValueError, "no active"):
            HiddenLifecycleApplicationRequest("apply:again", result.state, result.completed)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            HiddenLifecycleApplicationRequest("activate:again", result.state, request.move_quietly)

    def test_structural_source_equality_and_later_round_context_are_preserved(self):
        state, request = context(later=True)
        movement = request.movement
        request = replace(deepcopy(request), movement=replace(movement,
            source=replace(movement.source, rule_id="RULE-ABILITY:test-give-ground"),
            state=replace(movement.state, placements=tuple(
                replace(item, zone_id="zone:d") if item.entity_id == "guard" else item
                for item in movement.state.placements)),
            mover_conditions=ConditionState((Condition.STAGGERED,))))
        result = lifecycle.execute_hidden_lifecycle_give_ground(state, request)
        completed = result.completed.source_request.movement
        self.assertIs(completed.conditions, request.movement.mover_conditions)
        self.assertEqual(completed.state.placement_for("guard").zone_id, "zone:d")
        self.assertIn("RULE-ABILITY:test-give-ground", result.applied_rule_ids)
        self.assertIsNone(result.state.opportunity)

    def test_invalid_types_rules_failed_source_and_consumption_are_rejected(self):
        state, request = context()
        failed = execute_move_quietly_action(request.move_quietly.source_request, SequenceRandom([10, 10, 1]))
        for changes in ({"move_quietly": failed}, {"move_quietly": None}, {"movement": None},
                        {"rule_id": "unknown"}, {"id": ""}, {"consumed_opportunity_ids": "string"},
                        {"consumed_opportunity_ids": ("dup", "dup")},
                        {"consumed_opportunity_ids": (state.opportunity.id,)}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(request, **changes)
        with patch.object(lifecycle, "resolve_give_ground") as move:
            with self.assertRaises(TypeError):
                lifecycle.execute_hidden_lifecycle_give_ground(state, request.movement)
            move.assert_not_called()
        with self.assertRaises(FrozenInstanceError):
            request.id = "new"
