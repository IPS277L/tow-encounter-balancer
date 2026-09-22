from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_hidden_attack_resolution import loss_request
from tests.unit.test_k1_move_quietly_resolution import request as quietly_request
from towr.domain.hidden_lifecycle_models import HiddenLifecycleApplicationRequest, HiddenLifecycleState
from towr.domain.hiding_position_models import HidingPositionState
from towr.domain.move_quietly_models import MoveQuietlyHidingChoice, MoveQuietlyOutcome
from towr.rules import hidden_lifecycle_resolution as lifecycle
from towr.rules.move_quietly_resolution import execute_move_quietly_action
from towr.rules.opposed_test import resolve_opposed_test


def context(**options):
    state = HiddenLifecycleState(
        HidingPositionState("hero", ("hiding:older",), ("attack:older",)),
        consumed_opportunity_ids=("hidden:older",),
    )
    request = quietly_request(used_hiding_position_ids=state.hiding_positions.used_hiding_position_ids,
                              **options)
    return state, request


class K1MoveQuietlyHiddenLifecycleTests(unittest.TestCase):
    def test_all_outcomes_execute_one_test_and_receipt_with_exact_history(self):
        cases = (
            ({}, [1, 10, 10], MoveQuietlyOutcome.HIDDEN),
            ({"include_movement": False, "hiding_choice": MoveQuietlyHidingChoice.HIDE_IN_CURRENT_ZONE},
             [1, 10, 10], MoveQuietlyOutcome.HIDDEN),
            ({}, [10, 10, 1], MoveQuietlyOutcome.FAILED),
            ({}, [10, 10, 10], MoveQuietlyOutcome.FAILED),
            ({"include_movement": False}, [1, 10, 10], MoveQuietlyOutcome.SUCCEEDED_WITHOUT_HIDING),
            ({"include_movement": False}, [10, 10, 1], MoveQuietlyOutcome.FAILED),
        )
        for options, values, outcome in cases:
            with self.subTest(options=options, outcome=outcome, values=values):
                state, request = context(**options)
                rng, decisions = SequenceRandom([*values, 7]), Mock()
                with (
                    patch.object(lifecycle, "execute_move_quietly_action", wraps=execute_move_quietly_action) as execute,
                    patch("towr.rules.move_quietly_resolution.resolve_opposed_test", wraps=resolve_opposed_test) as contest,
                ):
                    result = lifecycle.execute_hidden_lifecycle_move_quietly(state, request, rng, decisions=decisions)
                execute.assert_called_once_with(request, rng, decisions=decisions)
                contest.assert_called_once()
                self.assertEqual(rng.randint(1, 10), 7)
                action = result.completed
                self.assertIs(action.source_request, request)
                self.assertIs(action.outcome, outcome)
                self.assertTrue(action.slot.executed)
                self.assertEqual(action.slot.execution.id, request.id)
                self.assertEqual(len(action.round_state.active_turn.action_slots), 1)
                self.assertIs(result.state.hiding_positions, state.hiding_positions)
                self.assertEqual(result.state.consumed_opportunity_ids, state.consumed_opportunity_ids)
                self.assertTrue(set(action.applied_rule_ids) <= set(result.applied_rule_ids))
                if outcome is MoveQuietlyOutcome.HIDDEN:
                    self.assertIs(result.state.active_move_quietly, action)
                    self.assertIs(result.state.opportunity, action.hidden_attack_opportunity)
                    self.assertIn("hero", action.spatial_state.free_move_used_entity_ids)
                else:
                    self.assertIs(result.state, state)
                    self.assertIsNone(result.state.opportunity)
                    self.assertEqual(action.spatial_state, request.spatial_state)
                self.assertFalse(request.round_state.active_turn.action_slots[0].executed)

    def test_actor_stale_history_and_consumed_source_fail_before_executor_or_rng(self):
        state, request = context()
        for changed, message in (
            (replace(state, hiding_positions=HidingPositionState("ally", ("hiding:older",))), "another actor"),
            (replace(state, hiding_positions=HidingPositionState("hero")), "stale hiding"),
            (replace(state, hiding_positions=HidingPositionState("hero", ("hiding:older", "hiding:other"))), "stale hiding"),
            (replace(state, consumed_opportunity_ids=(f"{request.id}:hidden",)), "already consumed"),
        ):
            with self.subTest(message=message):
                rng, decisions = Mock(), Mock()
                with patch.object(lifecycle, "execute_move_quietly_action") as execute:
                    with self.assertRaisesRegex(ValueError, message):
                        lifecycle.execute_hidden_lifecycle_move_quietly(changed, request, rng, decisions=decisions)
                execute.assert_not_called()
                self.assertEqual(rng.mock_calls, [])
                self.assertEqual(decisions.mock_calls, [])

    def test_active_opportunity_cannot_be_replaced_even_when_hiding_is_declined(self):
        state, request = context()
        active = lifecycle.execute_hidden_lifecycle_move_quietly(state, request, SequenceRandom([1, 10, 10])).state
        for candidate in (replace(request, id="quietly:new"), context(include_movement=False)[1]):
            with self.subTest(choice=candidate.hiding_choice), patch.object(lifecycle, "execute_move_quietly_action") as execute:
                with self.assertRaisesRegex(ValueError, "resolve the active"):
                    lifecycle.execute_hidden_lifecycle_move_quietly(active, candidate, Mock())
                execute.assert_not_called()

    def test_result_feeds_loss_and_consumed_source_cannot_roll_again(self):
        state, request = context()
        result = lifecycle.execute_hidden_lifecycle_move_quietly(state, request, SequenceRandom([1, 10, 10]))
        lost = lifecycle.lose_hidden_lifecycle_opportunity(result.state, loss_request(
            move_quietly=result.completed, consumed=result.state.consumed_opportunity_ids,
        ))
        self.assertIsNone(lost.state.opportunity)
        self.assertIs(lost.state.hiding_positions, state.hiding_positions)
        for candidate in (request, replace(context(include_movement=False)[1], id=request.id)):
            with self.subTest(choice=candidate.hiding_choice), patch.object(lifecycle, "execute_move_quietly_action") as execute:
                with self.assertRaisesRegex(ValueError, "already consumed"):
                    lifecycle.execute_hidden_lifecycle_move_quietly(lost.state, candidate, Mock())
                execute.assert_not_called()

    def test_failed_or_declined_action_still_has_a_completed_slot_that_cannot_reroll(self):
        for options, values in (({}, [10, 10, 1]), ({"include_movement": False}, [1, 10, 10])):
            options = {**options, "include_movement": False}
            state, request = context(**options)
            result = lifecycle.execute_hidden_lifecycle_move_quietly(state, request, SequenceRandom(values))
            self.assertIs(result.state, state)
            # Lifecycle is unchanged, but caller must retain the returned action state.
            already_executed = replace(request, round_state=result.completed.round_state)
            rng = Mock()
            with self.assertRaisesRegex(ValueError, "already been executed"):
                lifecycle.execute_hidden_lifecycle_move_quietly(result.state, already_executed, rng)
            rng.randint.assert_not_called()

    def test_completed_non_hidden_results_keep_actor_history_and_replay_checks(self):
        for values in ([1, 10, 10], [10, 10, 1]):
            state, request = context(include_movement=False)
            completed = execute_move_quietly_action(request, SequenceRandom(values))
            for changed in (
                replace(state, hiding_positions=HidingPositionState("ally", ("hiding:older",))),
                replace(state, hiding_positions=HidingPositionState("hero")),
                replace(state, consumed_opportunity_ids=(f"{request.id}:hidden",)),
            ):
                with self.subTest(outcome=completed.outcome, state=changed), self.assertRaises(ValueError):
                    HiddenLifecycleApplicationRequest("apply", changed, completed)

    def test_rng_failure_leaves_turn_spatial_and_lifecycle_unchanged(self):
        state, request = context()
        before = deepcopy((state, request))
        rng = Mock()
        rng.randint.side_effect = [1, RuntimeError("RNG failed")]
        with patch.object(lifecycle, "apply_hidden_lifecycle_result") as apply:
            with self.assertRaisesRegex(RuntimeError, "RNG failed"):
                lifecycle.execute_hidden_lifecycle_move_quietly(state, request, rng)
        apply.assert_not_called()
        self.assertEqual((state, request), before)

    def test_non_hidden_result_cannot_change_history_or_invent_active_source(self):
        state, request = context(include_movement=False)
        result = lifecycle.execute_hidden_lifecycle_move_quietly(state, request, SequenceRandom([1, 10, 10]))
        active = lifecycle.execute_hidden_lifecycle_move_quietly(state, context()[1], SequenceRandom([1, 10, 10])).state
        for changed in (active, replace(state, consumed_opportunity_ids=()),
                        replace(state, hiding_positions=HidingPositionState("hero"))):
            with self.subTest(state=changed), self.assertRaisesRegex(ValueError, "stale provenance or state"):
                replace(result, state=changed)

    def test_invalid_types_and_unknown_source_rule_are_rejected_before_rng(self):
        state, request = context()
        for changed_state, candidate, error in ((None, request, TypeError), (state, None, TypeError),
                                                (state, replace(request, rule_id="foreign"), ValueError)):
            rng = Mock()
            with self.subTest(error=error), self.assertRaises(error):
                lifecycle.execute_hidden_lifecycle_move_quietly(changed_state, candidate, rng)
            rng.randint.assert_not_called()
