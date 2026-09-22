from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import patch

from tests.unit.test_k1_hidden_give_ground_execution import context as execution_context
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.hidden_give_ground_models import HiddenGiveGroundLossRequest
from towr.domain.hidden_lifecycle_models import HiddenLifecycleApplicationRequest
from towr.domain.movement_models import FreeMovementRequest, MovementSpeed
from towr.domain.resolution_models import GiveGroundRequest, GiveGroundResolutionRequest
from towr.domain.spatial_models import ZoneConnection
from towr.domain.turn_models import CombatSide, CombatTurnState
from towr.rules import hidden_lifecycle_resolution as lifecycle
from towr.rules.free_movement_resolution import resolve_free_movement
from towr.rules.spatial_resolution import resolve_give_ground


def free_step(source, before, destination):
    turn = replace(source.round_state, round_number=before.round_number,
                   completed_turn_entity_ids=("hero",),
                   active_turn=CombatTurnState("scout", CombatSide.OPPOSITION))
    return resolve_free_movement(FreeMovementRequest(
        "scout:free", turn, before, "scout", MovementSpeed.NORMAL,
        ConditionState(), (destination,),
    ))


def ground_step(before, actor, destination):
    return resolve_give_ground(GiveGroundResolutionRequest(
        GiveGroundRequest(f"{actor}:give-ground", rule_id="RULE-ABILITY:chain-give-ground"),
        before, actor, destination, ConditionState(),
    ))


def context(kinds=("free", "ground")):
    state, request = execution_context()
    current = request.move_quietly.spatial_state
    chain = []
    for kind in kinds:
        destination = "zone:c" if current.placement_for("scout").zone_id == "zone:b" else "zone:b"
        step = (free_step(request.move_quietly, current, destination) if kind == "free"
                else ground_step(current, "scout", destination))
        chain.append(step)
        current = step.state
    request = replace(request, movement=replace(request.movement, state=current),
                      intervening_movements=tuple(chain))
    return state, request


def loss_request(request):
    return HiddenGiveGroundLossRequest(
        request.id, request.move_quietly, resolve_give_ground(request.movement),
        request.consumed_opportunity_ids, intervening_movements=request.intervening_movements,
    )


class K1HiddenGiveGroundMovementChainTests(unittest.TestCase):
    def test_each_chain_path_preserves_completed_steps_and_executes_only_owner_movement(self):
        for kinds in (("free",), ("ground",), ("free", "ground"), ("ground", "free")):
            for execute in (False, True):
                with self.subTest(kinds=kinds, execute=execute):
                    state, request = context(kinds)
                    selected = request if execute else loss_request(request)
                    before = deepcopy((state, selected))
                    with (
                        patch.object(lifecycle, "resolve_give_ground", wraps=resolve_give_ground) as move,
                        patch("towr.rules.free_movement_resolution.resolve_free_movement") as free,
                        patch("towr.rules.spatial_resolution.resolve_condition_application") as condition,
                    ):
                        result = (lifecycle.execute_hidden_lifecycle_give_ground(state, selected) if execute
                                  else lifecycle.apply_hidden_lifecycle_give_ground(state, selected))
                    self.assertEqual(move.call_count, int(execute))
                    free.assert_not_called()
                    condition.assert_not_called()  # The owner leaves for a friendly Zone.
                    completed = result.completed.source_request
                    self.assertIs(completed.intervening_movements, selected.intervening_movements)
                    self.assertEqual(completed.movement.previous_state, selected.intervening_movements[-1].state)
                    self.assertIsNone(result.state.opportunity)
                    self.assertIs(result.state.hiding_positions, state.hiding_positions)
                    for step in selected.intervening_movements:
                        self.assertTrue(set(step.applied_rule_ids) <= set(result.applied_rule_ids))
                    if kinds == ("free", "ground"):
                        self.assertTrue(completed.intervening_movements[-1].conditions.has(Condition.BROKEN))
                    self.assertEqual((state, selected), before)

    def test_gaps_reordering_duplicates_and_missing_tail_are_rejected(self):
        state, request = context()
        first, last = request.intervening_movements
        for selected in (request, loss_request(request)):
            for chain in ((), (last,), (first,), (last, first), (first, first, last), (first, last, last)):
                with self.subTest(selected=type(selected), chain=chain):
                    with patch.object(lifecycle, "resolve_give_ground") as move:
                        with self.assertRaises(ValueError):
                            replace(selected, intervening_movements=chain)
                        move.assert_not_called()

    def test_chain_must_begin_at_source_and_use_one_graph_and_round(self):
        _, request = context(("free",))
        source = request.move_quietly
        before = source.spatial_state
        wrong_graph = replace(before, graph=replace(before.graph,
            connections=(*before.graph.connections, ZoneConnection("zone:c", "zone:d"))))
        for initial in (replace(before, free_move_used_entity_ids=()),
                        replace(before, round_number=2), wrong_graph):
            step = free_step(source, initial, "zone:c")
            for selected in (request, loss_request(request)):
                with self.subTest(initial=initial), self.assertRaisesRegex(ValueError, "not continuous"):
                    replace(selected, intervening_movements=(step,))

    def test_chain_cannot_be_used_for_a_later_round(self):
        _, request = context()
        later = replace(request.movement, state=replace(request.movement.state, round_number=2))
        with self.assertRaisesRegex(ValueError, "only support"):
            replace(request, movement=later)
        with self.assertRaisesRegex(ValueError, "only support"):
            replace(loss_request(request), movement=resolve_give_ground(later))

    def test_owner_departure_and_return_cannot_be_hidden_in_chain(self):
        state, request = execution_context()
        before = request.move_quietly.spatial_state
        away = ground_step(before, "hero", "zone:a")
        # A completed free move returns the owner but cannot legitimize the earlier departure.
        # Constructing this result from reset usage models stale input; the chain must reject the owner first.
        reset = replace(away.state, free_move_used_entity_ids=())
        returned = resolve_free_movement(FreeMovementRequest(
            "hero:return", request.move_quietly.round_state, reset, "hero", MovementSpeed.NORMAL,
            ConditionState(), ("zone:b",)))
        with self.assertRaisesRegex(ValueError, "hidden owner"):
            replace(request, movement=replace(request.movement, state=returned.state),
                    intervening_movements=(away, returned))
        self.assertIsNotNone(state.opportunity)

    def test_bad_step_types_and_unrecognised_or_missing_trace_are_rejected(self):
        _, request = context()
        first, last = request.intervening_movements
        for chain in ((request.movement,), (None,), "text", "", b"",
                      (replace(first, rule_id="custom", applied_rule_ids=("custom",)), last),
                      (first, replace(last, applied_rule_ids=(last.source.rule_id,)))):
            for selected in (request, loss_request(request)):
                with self.subTest(chain=chain), self.assertRaises((ValueError, TypeError)):
                    replace(selected, intervening_movements=chain)

    def test_ready_loss_keeps_chain_and_rejects_trace_truncation_and_replay(self):
        state, request = context(("ground",))
        result = lifecycle.execute_hidden_lifecycle_give_ground(state, request)
        with patch.object(lifecycle, "lose_hidden_opportunity_after_give_ground") as lose:
            applied = lifecycle.apply_hidden_lifecycle_result(HiddenLifecycleApplicationRequest(
                "apply:ready", deepcopy(state), result.completed))
        lose.assert_not_called()
        self.assertIs(applied.completed, result.completed)
        rule = "RULE-ABILITY:chain-give-ground"
        self.assertIn(rule, applied.applied_rule_ids)
        with self.assertRaisesRegex(ValueError, "trace"):
            replace(result.completed, applied_rule_ids=tuple(
                item for item in result.completed.applied_rule_ids if item != rule))
        with patch.object(lifecycle, "resolve_give_ground") as move:
            with self.assertRaisesRegex(ValueError, "no active"):
                lifecycle.execute_hidden_lifecycle_give_ground(result.state, replace(request, id="again"))
            move.assert_not_called()
        with self.assertRaisesRegex(ValueError, "no active"):
            HiddenLifecycleApplicationRequest("apply:again", result.state, result.completed)

    def test_list_normalization_and_failures_preserve_snapshots(self):
        state, request = context()
        values = list(deepcopy(request.intervening_movements))
        selected = replace(request, intervening_movements=values)
        values.clear()
        self.assertEqual(selected.intervening_movements, request.intervening_movements)
        with self.assertRaises(FrozenInstanceError):
            selected.intervening_movements = ()
        before = deepcopy((state, selected))
        with patch.object(lifecycle, "lose_hidden_opportunity_after_give_ground", side_effect=RuntimeError("failed")):
            with self.assertRaisesRegex(RuntimeError, "failed"):
                lifecycle.execute_hidden_lifecycle_give_ground(state, selected)
        self.assertEqual((state, selected), before)
