from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_hidden_free_movement_resolution import context as free_context
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.hidden_attack_models import HiddenAttackOpportunityLossReason
from towr.domain.hidden_give_ground_models import HiddenGiveGroundLossRequest
from towr.domain.hidden_lifecycle_models import HiddenLifecycleApplicationRequest
from towr.domain.resolution_models import GiveGroundRequest, GiveGroundResolutionRequest
from towr.domain.spatial_models import ZoneConnection
from towr.rules import hidden_lifecycle_resolution as lifecycle
from towr.rules.hidden_give_ground_resolution import lose_hidden_opportunity_after_give_ground
from towr.rules.move_quietly_resolution import execute_move_quietly_action
from towr.rules.spatial_resolution import resolve_give_ground, start_next_spatial_round


def context(*, later=False, same_zone=False, enemy=False):
    state, _, _ = free_context(same_zone=same_zone)
    quietly = state.active_move_quietly
    spatial = start_next_spatial_round(quietly.spatial_state) if later else quietly.spatial_state
    movement_request = GiveGroundResolutionRequest(
        source=GiveGroundRequest("reaction:give-ground"), state=spatial,
        mover_id="hero", destination_zone_id="zone:b" if same_zone else (
            "zone:c" if enemy else "zone:a"), mover_conditions=ConditionState(),
    )
    movement = resolve_give_ground(movement_request)
    return state, HiddenGiveGroundLossRequest(
        "hidden:give-ground", quietly, movement, state.consumed_opportunity_ids,
    ), movement_request


class K1HiddenGiveGroundResolutionTests(unittest.TestCase):
    def test_same_and_later_round_loss_keeps_history_and_completed_movement(self):
        for later, same_zone, enemy in ((False, False, False), (False, True, True),
                                       (True, False, False), (True, False, True)):
            with self.subTest(later=later, same_zone=same_zone, enemy=enemy):
                state, request, _ = context(later=later, same_zone=same_zone, enemy=enemy)
                before = deepcopy((state, request))
                with (
                    patch.object(lifecycle, "lose_hidden_opportunity_after_give_ground",
                                 wraps=lose_hidden_opportunity_after_give_ground) as lose,
                    patch("towr.rules.spatial_resolution.resolve_give_ground") as move,
                    patch.object(lifecycle, "execute_registered_hidden_attack") as attack,
                ):
                    result = lifecycle.apply_hidden_lifecycle_give_ground(state, request)
                lose.assert_called_once_with(request)
                move.assert_not_called()
                attack.assert_not_called()
                self.assertIs(result.completed.source_request.movement, request.movement)
                self.assertIs(result.completed.reason, HiddenAttackOpportunityLossReason.LEFT_HIDING_POSITION)
                self.assertIsNone(result.state.opportunity)
                self.assertIs(result.state.hiding_positions, state.hiding_positions)
                self.assertEqual(result.state.consumed_opportunity_ids,
                                 (*state.consumed_opportunity_ids, state.opportunity.id))
                self.assertEqual(request.movement.conditions.has(Condition.BROKEN), enemy)
                self.assertEqual(request.movement.state.free_move_used_entity_ids,
                                 request.movement.previous_state.free_move_used_entity_ids)
                if not later:
                    self.assertIn("hero", request.movement.state.free_move_used_entity_ids)
                self.assertTrue(set(request.movement.applied_rule_ids) <= set(result.applied_rule_ids))
                self.assertEqual((state, request), before)

    def test_same_round_requires_exact_post_hiding_snapshot(self):
        _, request, movement_request = context(same_zone=True)
        # Same-Zone hiding changed only usage; matching placement alone is insufficient.
        for spatial in (
            request.move_quietly.previous_spatial_state,
            replace(movement_request.state, free_move_used_entity_ids=()),
            replace(movement_request.state, gave_ground_entity_ids=()),
            replace(movement_request.state, placements=tuple(
                replace(item, zone_id="zone:d") if item.entity_id == "guard" else item
                for item in movement_request.state.placements)),
        ):
            movement = resolve_give_ground(replace(movement_request, state=spatial))
            with self.subTest(spatial=spatial), self.assertRaisesRegex(ValueError, "exact post-hiding"):
                replace(request, movement=movement)

    def test_later_round_allows_changed_other_actors_but_not_earlier_movement(self):
        state, request, movement_request = context(later=True)
        changed = replace(movement_request.state, placements=tuple(
            replace(item, zone_id="zone:d") if item.entity_id == "guard" else item
            for item in movement_request.state.placements))
        movement = resolve_give_ground(replace(movement_request, state=changed))
        result = lifecycle.apply_hidden_lifecycle_give_ground(state, replace(request, movement=movement))
        self.assertIsNone(result.state.opportunity)
        source = request.move_quietly.source_request
        late_round = replace(source.round_state, round_number=3)
        late_spatial = replace(source.spatial_state, round_number=3)
        late = execute_move_quietly_action(replace(source, round_state=late_round,
            spatial_state=late_spatial, free_movement=replace(source.free_movement,
                round_state=late_round, state=late_spatial)), SequenceRandom([1, 10, 10]))
        with self.assertRaisesRegex(ValueError, "must follow"):
            replace(request, move_quietly=late)

    def test_foreign_actor_origin_side_and_graph_are_rejected(self):
        _, request, movement_request = context(later=True)
        foreign = replace(movement_request, mover_id="scout")
        origin = replace(movement_request, state=replace(movement_request.state, placements=tuple(
            replace(item, zone_id="zone:c") if item.entity_id == "hero" else item
            for item in movement_request.state.placements)), destination_zone_id="zone:b")
        side = replace(movement_request, state=replace(movement_request.state, placements=tuple(
            replace(item, side_id="other") if item.entity_id == "hero" else item
            for item in movement_request.state.placements)))
        graph = replace(movement_request, state=replace(movement_request.state, graph=replace(
            movement_request.state.graph, connections=(*movement_request.state.graph.connections,
                                                      ZoneConnection("zone:c", "zone:d")))))
        for candidate, message in ((foreign, "another actor"), (origin, "hidden placement"),
                                   (side, "hidden placement"), (graph, "Zone graph")):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                replace(request, movement=resolve_give_ground(candidate))

    def test_stale_source_or_chain_fails_before_consumer(self):
        state, request, _ = context()
        other = execute_move_quietly_action(request.move_quietly.source_request, SequenceRandom([1, 1, 10]))
        for changed in (replace(state, active_move_quietly=other),
                        replace(state, active_move_quietly=None),
                        replace(state, consumed_opportunity_ids=()),
                        replace(state, consumed_opportunity_ids=("hidden:new", "hidden:older"))):
            with self.subTest(state=changed), patch.object(lifecycle, "lose_hidden_opportunity_after_give_ground") as lose:
                with self.assertRaises(ValueError):
                    lifecycle.apply_hidden_lifecycle_give_ground(changed, request)
                lose.assert_not_called()

    def test_ready_result_accepts_structural_equality_without_reexecution(self):
        state, request, _ = context()
        completed = lose_hidden_opportunity_after_give_ground(deepcopy(request))
        with patch.object(lifecycle, "lose_hidden_opportunity_after_give_ground") as lose:
            result = lifecycle.apply_hidden_lifecycle_result(HiddenLifecycleApplicationRequest(
                "apply:ready", state, completed))
        lose.assert_not_called()
        self.assertIs(result.completed, completed)
        with self.assertRaises(ValueError):
            HiddenLifecycleApplicationRequest("apply:stale", replace(state, consumed_opportunity_ids=()), completed)

    def test_replay_and_reactivation_fail_with_new_ids(self):
        state, request, _ = context()
        result = lifecycle.apply_hidden_lifecycle_give_ground(state, request)
        with self.assertRaisesRegex(ValueError, "no active"):
            lifecycle.apply_hidden_lifecycle_give_ground(result.state, replace(request, id="again"))
        with self.assertRaisesRegex(ValueError, "no active"):
            HiddenLifecycleApplicationRequest("apply:again", result.state, result.completed)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            HiddenLifecycleApplicationRequest("activate:again", result.state, request.move_quietly)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            replace(request, consumed_opportunity_ids=result.state.consumed_opportunity_ids)

    def test_result_cannot_forge_reason_history_consumption_or_trace(self):
        state, request, _ = context(enemy=True)
        result = lifecycle.apply_hidden_lifecycle_give_ground(state, request)
        for changes in ({"reason": HiddenAttackOpportunityLossReason.TARGET_AWARE},
                        {"request_id": "wrong"}, {"consumed_opportunity_ids": ()},
                        {"applied_rule_ids": (request.rule_id,)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(result.completed, **changes)
        with self.assertRaises(ValueError):
            replace(result, state=replace(result.state, hiding_positions=replace(state.hiding_positions,
                used_hiding_position_ids=(*state.hiding_positions.used_hiding_position_ids, "hiding:wall"))))
        with self.assertRaises(FrozenInstanceError):
            result.completed.reason = HiddenAttackOpportunityLossReason.TARGET_AWARE

    def test_bad_types_rules_source_and_missing_movement_trace_are_rejected(self):
        state, request, _ = context()
        failed = execute_move_quietly_action(request.move_quietly.source_request, SequenceRandom([10, 10, 1]))
        for changes in ({"move_quietly": failed}, {"move_quietly": None}, {"movement": None},
                        {"rule_id": "unknown"}, {"consumed_opportunity_ids": "string"},
                        {"consumed_opportunity_ids": ("dup", "dup")},
                        {"movement": replace(request.movement, applied_rule_ids=(request.movement.source.rule_id,))},
                        {"movement": replace(request.movement, source=replace(request.movement.source,
                            resolution_id=request.move_quietly.request_id))}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(request, **changes)
        with self.assertRaises(TypeError):
            lifecycle.apply_hidden_lifecycle_give_ground(state, request.movement)
        with self.assertRaises(TypeError):
            lose_hidden_opportunity_after_give_ground(request.movement)

    def test_consumer_failure_preserves_inputs_and_skips_application(self):
        state, request, _ = context()
        before = deepcopy((state, request))
        with (
            patch.object(lifecycle, "lose_hidden_opportunity_after_give_ground", side_effect=RuntimeError("failed")),
            patch.object(lifecycle, "apply_hidden_lifecycle_result") as apply,
        ):
            with self.assertRaisesRegex(RuntimeError, "failed"):
                lifecycle.apply_hidden_lifecycle_give_ground(state, request)
        apply.assert_not_called()
        self.assertEqual((state, request), before)
