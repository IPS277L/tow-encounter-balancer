from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_resolution import aim_request, reserve_action
from tests.unit.test_k1_hidden_free_movement_resolution import context as completed_context
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.hidden_lifecycle_models import HiddenLifecycleApplicationRequest
from towr.domain.hidden_movement_models import HiddenFreeMovementExecutionRequest
from towr.domain.spatial_models import ZoneConnection
from towr.domain.turn_models import CombatActionKind, CombatSide
from towr.rules import hidden_lifecycle_resolution as lifecycle
from towr.rules.aim_resolution import execute_aim_action
from towr.rules.free_movement_resolution import resolve_free_movement
from towr.rules.hidden_movement_resolution import lose_hidden_opportunity_after_free_movement
from towr.rules.move_quietly_resolution import execute_move_quietly_action


def context(**options):
    state, loss, movement = completed_context(**options)
    return state, HiddenFreeMovementExecutionRequest(
        "hidden:move", loss.move_quietly, movement, state.consumed_opportunity_ids,
    )


class K1HiddenFreeMovementExecutionTests(unittest.TestCase):
    def test_one_movement_and_loss_return_consistent_spatial_and_hidden_states(self):
        for options in ({}, {"same_zone": True}, {"same_zone": True, "fast": True}):
            with self.subTest(options=options):
                state, request = context(**options)
                expected_movement = resolve_free_movement(request.movement)
                with (
                    patch.object(lifecycle, "resolve_free_movement", return_value=expected_movement) as move,
                    patch.object(lifecycle, "lose_hidden_opportunity_after_free_movement",
                                 wraps=lose_hidden_opportunity_after_free_movement) as lose,
                    patch.object(lifecycle, "execute_registered_hidden_attack") as attack,
                ):
                    result = lifecycle.execute_hidden_lifecycle_free_movement(state, request)
                move.assert_called_once_with(request.movement)
                lose.assert_called_once_with(result.completed.source_request)
                attack.assert_not_called()
                self.assertIs(result.completed.source_request.movement, expected_movement)
                self.assertIs(result.completed.source_request.move_quietly, request.move_quietly)
                self.assertEqual(result.completed.request_id, request.id)
                self.assertIsNone(result.state.opportunity)
                self.assertIs(result.state.hiding_positions, state.hiding_positions)
                self.assertEqual(result.state.consumed_opportunity_ids,
                                 (*state.consumed_opportunity_ids, state.opportunity.id))
                self.assertEqual(expected_movement.state.placement_for("hero").zone_id,
                                 request.movement.destination_zone_id)
                self.assertEqual(expected_movement.state.free_move_used_entity_ids, ("hero",))
                self.assertIs(expected_movement.round_state, request.movement.round_state)
                self.assertTrue(set(expected_movement.applied_rule_ids) <= set(result.applied_rule_ids))
                self.assertIsNotNone(state.opportunity)
                self.assertEqual(request.movement.state.free_move_used_entity_ids, ())

    def test_stale_active_source_chain_and_types_fail_before_movement(self):
        state, request = context()
        other = execute_move_quietly_action(request.move_quietly.source_request, SequenceRandom([1, 1, 10]))
        for changed in (replace(state, active_move_quietly=other),
                        replace(state, active_move_quietly=None),
                        replace(state, consumed_opportunity_ids=()),
                        replace(state, consumed_opportunity_ids=("hidden:new", "hidden:older")), None):
            with self.subTest(state=changed), patch.object(lifecycle, "resolve_free_movement") as move:
                with self.assertRaises((ValueError, TypeError)):
                    lifecycle.execute_hidden_lifecycle_free_movement(changed, request)
                move.assert_not_called()
        with patch.object(lifecycle, "resolve_free_movement") as move:
            with self.assertRaises(TypeError):
                lifecycle.execute_hidden_lifecycle_free_movement(state, request.movement)
            move.assert_not_called()

    def test_actor_placement_graph_and_round_are_checked_before_movement(self):
        state, request = context()
        movement = request.movement
        foreign = replace(movement, actor_id="scout", round_state=replace(movement.round_state,
            completed_turn_entity_ids=("hero",), active_turn=replace(movement.round_state.active_turn,
                actor_id="scout", side=CombatSide.OPPOSITION)))
        origin = replace(movement, state=replace(movement.state, placements=tuple(
            replace(item, zone_id="zone:a") if item.entity_id == "hero" else item
            for item in movement.state.placements
        )), traversed_zone_ids=("zone:b",))
        graph = replace(movement, state=replace(movement.state, graph=replace(movement.state.graph,
            connections=(*movement.state.graph.connections, ZoneConnection("zone:c", "zone:d")))))
        same_round = replace(movement, round_state=request.move_quietly.round_state,
                             state=replace(movement.state, round_number=1))
        for candidate in (foreign, origin, graph, same_round,
                          replace(movement, rule_id="unknown"),
                          replace(movement, id=request.move_quietly.request_id)):
            with self.subTest(movement=candidate), patch.object(lifecycle, "resolve_free_movement") as move:
                with self.assertRaises(ValueError):
                    lifecycle.execute_hidden_lifecycle_free_movement(state, replace(request, movement=candidate))
                move.assert_not_called()

    def test_movement_rules_fail_without_consuming_opportunity(self):
        state, request = context()
        movement = request.movement
        for candidate in (
            replace(movement, state=replace(movement.state, free_move_used_entity_ids=("hero",))),
            replace(movement, actor_conditions=ConditionState((Condition.PRONE,))),
            replace(movement, actor_conditions=ConditionState((Condition.DEFENCELESS,))),
            replace(movement, crosses_obstacle=True),
            replace(movement, crosses_difficult_terrain=True),
            replace(movement, traversed_zone_ids=("zone:d",)),
            replace(movement, path_entity_ids=("guard",)),
        ):
            with self.subTest(movement=candidate):
                selected = replace(request, movement=candidate)
                before = deepcopy((state, selected))
                with patch.object(lifecycle, "apply_hidden_lifecycle_free_movement") as apply:
                    with self.assertRaises(ValueError):
                        lifecycle.execute_hidden_lifecycle_free_movement(state, selected)
                apply.assert_not_called()
                self.assertEqual((state, selected), before)

    def test_exceptions_at_each_stage_preserve_all_inputs(self):
        state, request = context()
        before = deepcopy((state, request))
        for stage in ("resolve_free_movement", "lose_hidden_opportunity_after_free_movement",
                      "apply_hidden_lifecycle_result"):
            with self.subTest(stage=stage), patch.object(lifecycle, stage, side_effect=RuntimeError(stage)):
                with self.assertRaisesRegex(RuntimeError, stage):
                    lifecycle.execute_hidden_lifecycle_free_movement(state, request)
                self.assertEqual((state, request), before)

    def test_replay_and_reactivation_fail_with_new_wrapper_and_movement_ids(self):
        state, request = context()
        result = lifecycle.execute_hidden_lifecycle_free_movement(state, request)
        renamed = replace(request, id="again", movement=replace(request.movement, id="move:again"))
        with patch.object(lifecycle, "resolve_free_movement") as move:
            with self.assertRaisesRegex(ValueError, "no active"):
                lifecycle.execute_hidden_lifecycle_free_movement(result.state, renamed)
            move.assert_not_called()
        with self.assertRaisesRegex(ValueError, "no active"):
            HiddenLifecycleApplicationRequest("apply:again", result.state, result.completed)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            HiddenLifecycleApplicationRequest("activate:again", result.state, request.move_quietly)

    def test_existing_aim_receipt_is_preserved_without_new_action(self):
        state, request = context()
        aim = execute_aim_action(aim_request(reserve_action(
            request.movement.round_state, CombatActionKind.AIM), target_id="scout"), SequenceRandom([1, 5, 10]))
        before = deepcopy(aim)
        request = replace(request, movement=replace(request.movement, round_state=aim.round_state))
        result = lifecycle.execute_hidden_lifecycle_free_movement(state, request)
        round_state = result.completed.source_request.movement.round_state
        self.assertIs(round_state, aim.round_state)
        self.assertEqual(len(round_state.active_turn.action_slots), 1)
        self.assertEqual(aim, before)
        self.assertIsNone(result.state.opportunity)

    def test_request_rejects_invalid_source_consumption_and_remains_immutable(self):
        _, request = context()
        failed = execute_move_quietly_action(request.move_quietly.source_request, SequenceRandom([10, 10, 1]))
        for changes in ({"move_quietly": failed}, {"move_quietly": None}, {"movement": None},
                        {"rule_id": "unknown"}, {"id": ""}, {"consumed_opportunity_ids": "string"},
                        {"consumed_opportunity_ids": ("dup", "dup")},
                        {"consumed_opportunity_ids": (request.move_quietly.hidden_attack_opportunity.id,)}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(request, **changes)
        with self.assertRaises(FrozenInstanceError):
            request.id = "new"
