from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_move_quietly_hidden_lifecycle import context as quietly_context
from tests.unit.test_k1_move_quietly_resolution import active_round
from towr.domain.condition_models import ConditionState
from towr.domain.hidden_attack_models import HiddenAttackOpportunityLossReason
from towr.domain.hidden_lifecycle_models import HiddenLifecycleApplicationRequest
from towr.domain.hidden_movement_models import HiddenFreeMovementLossRequest
from towr.domain.move_quietly_models import MoveQuietlyHidingChoice
from towr.domain.movement_models import FreeMovementRequest, MovementSpeed
from towr.domain.spatial_models import ZoneConnection
from towr.domain.turn_models import CombatSide
from towr.rules import hidden_lifecycle_resolution as lifecycle
from towr.rules.free_movement_resolution import resolve_free_movement
from towr.rules.hidden_movement_resolution import lose_hidden_opportunity_after_free_movement
from towr.rules.move_quietly_resolution import execute_move_quietly_action
from towr.rules.spatial_resolution import start_next_spatial_round


def context(*, same_zone=False, fast=False):
    options = ({"include_movement": False,
                "hiding_choice": MoveQuietlyHidingChoice.HIDE_IN_CURRENT_ZONE}
               if same_zone else {})
    initial, quietly_request = quietly_context(**options)
    activation = lifecycle.execute_hidden_lifecycle_move_quietly(
        initial, quietly_request, SequenceRandom([1, 10, 10]),
    )
    source = activation.completed
    movement_request = FreeMovementRequest(
        id="movement:leave", round_state=replace(active_round(), round_number=2),
        state=start_next_spatial_round(source.spatial_state), actor_id="hero",
        speed=MovementSpeed.FAST if fast else MovementSpeed.NORMAL,
        actor_conditions=ConditionState(),
        traversed_zone_ids=("zone:b", "zone:c") if fast else (
            "zone:b" if same_zone else "zone:c",
        ),
    )
    movement = resolve_free_movement(movement_request)
    return activation.state, HiddenFreeMovementLossRequest(
        "hidden:leave", source, movement, activation.state.consumed_opportunity_ids,
    ), movement_request


class K1HiddenFreeMovementResolutionTests(unittest.TestCase):
    def test_completed_movement_closes_opportunity_once_without_reexecution(self):
        for same_zone, fast in ((False, False), (True, False), (True, True)):
            with self.subTest(same_zone=same_zone, fast=fast):
                state, request, _ = context(same_zone=same_zone, fast=fast)
                before = deepcopy((state, request))
                with (
                    patch.object(lifecycle, "lose_hidden_opportunity_after_free_movement",
                                 wraps=lose_hidden_opportunity_after_free_movement) as lose,
                    patch("towr.rules.free_movement_resolution.resolve_free_movement") as move,
                    patch.object(lifecycle, "execute_registered_hidden_attack") as attack,
                ):
                    result = lifecycle.apply_hidden_lifecycle_free_movement(state, request)
                lose.assert_called_once_with(request)
                move.assert_not_called()
                attack.assert_not_called()
                self.assertIs(result.completed.source_request, request)
                self.assertIs(result.completed.reason, HiddenAttackOpportunityLossReason.LEFT_HIDING_POSITION)
                self.assertIsNone(result.state.active_move_quietly)
                self.assertIs(result.state.hiding_positions, state.hiding_positions)
                self.assertEqual(result.state.consumed_opportunity_ids,
                                 (*state.consumed_opportunity_ids, state.opportunity.id))
                self.assertEqual(request.movement.round_state.active_turn.action_slots, ())
                self.assertEqual(request.movement.state.free_move_used_entity_ids, ("hero",))
                self.assertEqual((state, request), before)
                for rule in (*request.move_quietly.applied_rule_ids, *request.movement.applied_rule_ids):
                    self.assertIn(rule, result.applied_rule_ids)

    def test_ready_result_application_and_structural_source_equality(self):
        state, request, _ = context()
        completed = lose_hidden_opportunity_after_free_movement(deepcopy(request))
        with patch.object(lifecycle, "lose_hidden_opportunity_after_free_movement") as lose:
            result = lifecycle.apply_hidden_lifecycle_result(HiddenLifecycleApplicationRequest(
                "apply:ready", state, completed,
            ))
        lose.assert_not_called()
        self.assertIs(result.completed, completed)
        self.assertIs(result.state.hiding_positions, state.hiding_positions)

    def test_stale_source_chain_and_inactive_state_fail_before_reducer(self):
        state, request, _ = context()
        other = execute_move_quietly_action(request.move_quietly.source_request, SequenceRandom([1, 1, 10]))
        for changed in (
            replace(state, active_move_quietly=other),
            replace(state, active_move_quietly=None),
            replace(state, consumed_opportunity_ids=()),
            replace(state, consumed_opportunity_ids=("hidden:other", "hidden:older")),
        ):
            with self.subTest(state=changed), patch.object(lifecycle, "lose_hidden_opportunity_after_free_movement") as lose:
                with self.assertRaises(ValueError):
                    lifecycle.apply_hidden_lifecycle_free_movement(changed, request)
                lose.assert_not_called()

    def test_replay_and_reactivation_fail_even_with_new_application_ids(self):
        state, request, _ = context()
        result = lifecycle.apply_hidden_lifecycle_free_movement(state, request)
        with self.assertRaisesRegex(ValueError, "no active"):
            lifecycle.apply_hidden_lifecycle_free_movement(result.state, replace(request, id="new:id"))
        with self.assertRaisesRegex(ValueError, "no active"):
            HiddenLifecycleApplicationRequest("replay", result.state, result.completed)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            HiddenLifecycleApplicationRequest("reactivate", result.state, request.move_quietly)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            replace(request, consumed_opportunity_ids=result.state.consumed_opportunity_ids)

    def test_foreign_actor_changed_origin_or_graph_are_rejected(self):
        _, request, movement_request = context()
        foreign_turn = replace(movement_request.round_state,
            completed_turn_entity_ids=("hero",),
            active_turn=replace(movement_request.round_state.active_turn,
                                actor_id="scout", side=CombatSide.OPPOSITION))
        foreign = replace(movement_request, actor_id="scout", round_state=foreign_turn)
        moved_origin = replace(movement_request, state=replace(movement_request.state, placements=tuple(
            replace(item, zone_id="zone:a") if item.entity_id == "hero" else item
            for item in movement_request.state.placements
        )), traversed_zone_ids=("zone:b",))
        changed_side = replace(movement_request, state=replace(movement_request.state, placements=tuple(
            replace(item, side_id="other") if item.entity_id == "hero" else item
            for item in movement_request.state.placements
        )))
        changed_graph = replace(movement_request, state=replace(movement_request.state, graph=replace(
            movement_request.state.graph, connections=(*movement_request.state.graph.connections,
                                                      ZoneConnection("zone:c", "zone:d")),
        )))
        for candidate, message in ((foreign, "another actor"), (moved_origin, "hidden placement"),
                                   (changed_side, "hidden placement"), (changed_graph, "Zone graph")):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                replace(request, movement=resolve_free_movement(candidate))

    def test_movement_before_or_during_source_round_cannot_consume_opportunity(self):
        _, request, movement_request = context()
        # Even a reset usage list and retained completed receipt cannot grant a second free move.
        forged = replace(movement_request, round_state=request.move_quietly.round_state,
                         state=replace(movement_request.state, round_number=1))
        with self.assertRaisesRegex(ValueError, "already used free movement"):
            replace(request, movement=resolve_free_movement(forged))
        late_source_request = replace(request.move_quietly.source_request,
            round_state=replace(request.move_quietly.source_request.round_state, round_number=3),
            spatial_state=replace(request.move_quietly.previous_spatial_state, round_number=3),
            free_movement=replace(request.move_quietly.source_request.free_movement,
                round_state=replace(request.move_quietly.source_request.round_state, round_number=3),
                state=replace(request.move_quietly.previous_spatial_state, round_number=3)))
        late_source = execute_move_quietly_action(late_source_request, SequenceRandom([1, 10, 10]))
        with self.assertRaisesRegex(ValueError, "must follow"):
            replace(request, move_quietly=late_source)
        with self.assertRaises(ValueError):
            replace(request, movement=request.move_quietly.free_movement_result)

    def test_other_actors_and_later_rounds_do_not_invalidate_hidden_placement(self):
        state, request, movement_request = context()
        spatial = replace(movement_request.state, round_number=4, placements=tuple(
            replace(item, zone_id="zone:a") if item.entity_id == "guard" else item
            for item in movement_request.state.placements
        ))
        movement = resolve_free_movement(replace(movement_request, state=spatial,
            round_state=replace(movement_request.round_state, round_number=4)))
        result = lifecycle.apply_hidden_lifecycle_free_movement(state, replace(request, movement=movement))
        self.assertIsNone(result.state.opportunity)
        self.assertIs(result.completed.source_request.movement, movement)

    def test_result_cannot_forge_history_consumption_reason_or_trace(self):
        state, request, _ = context()
        result = lifecycle.apply_hidden_lifecycle_free_movement(state, request)
        for changes in (
            {"reason": HiddenAttackOpportunityLossReason.TARGET_AWARE},
            {"consumed_opportunity_ids": ()}, {"request_id": "wrong"},
            {"applied_rule_ids": (request.rule_id,)},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(result.completed, **changes)
        for changes in (
            {"state": state},
            {"state": replace(result.state, hiding_positions=replace(state.hiding_positions,
                used_hiding_position_ids=(*state.hiding_positions.used_hiding_position_ids, "hiding:wall")))},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(result, **changes)
        with self.assertRaises(FrozenInstanceError):
            result.completed.reason = HiddenAttackOpportunityLossReason.TARGET_AWARE

    def test_invalid_types_rules_and_failed_sources_are_rejected(self):
        state, request, _ = context()
        failed = execute_move_quietly_action(request.move_quietly.source_request, SequenceRandom([10, 10, 1]))
        for changes in ({"move_quietly": failed}, {"move_quietly": "bad"}, {"movement": None},
                        {"rule_id": "unknown"}, {"consumed_opportunity_ids": "string"},
                        {"consumed_opportunity_ids": ("dup", "dup")},
                        {"movement": replace(request.movement, rule_id="custom",
                                             applied_rule_ids=("custom",))}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(request, **changes)
        with self.assertRaises(TypeError):
            lifecycle.apply_hidden_lifecycle_free_movement(state, request.movement)

    def test_reducer_failure_leaves_inputs_unchanged(self):
        state, request, _ = context()
        before = deepcopy((state, request))
        with (
            patch.object(lifecycle, "lose_hidden_opportunity_after_free_movement", side_effect=RuntimeError("failed")),
            patch.object(lifecycle, "apply_hidden_lifecycle_result") as apply,
        ):
            with self.assertRaisesRegex(RuntimeError, "failed"):
                lifecycle.apply_hidden_lifecycle_free_movement(state, request)
        apply.assert_not_called()
        self.assertEqual((state, request), before)
