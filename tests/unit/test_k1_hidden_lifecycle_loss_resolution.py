from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_hidden_attack_resolution import execution_request, loss_request
from tests.unit.test_k1_hidden_lifecycle_resolution import activate
from tests.unit.test_k1_move_quietly_resolution import request as quietly_request
from towr.domain.hidden_attack_models import HiddenAttackOpportunityLossReason
from towr.domain.hidden_lifecycle_models import (
    HIDDEN_LIFECYCLE_RULE_ID,
    HiddenLifecycleApplicationRequest,
)
from towr.domain.spatial_models import SpatialEntityPlacement
from towr.domain.turn_models import CombatActionKind
from towr.rules import hidden_lifecycle_resolution as lifecycle
from towr.rules.hidden_attack_resolution import lose_move_quietly_hidden_attack
from towr.rules.move_quietly_resolution import execute_move_quietly_action


def context():
    quietly = execute_move_quietly_action(
        quietly_request(used_hiding_position_ids=("hiding:older",)),
        SequenceRandom([1, 10, 10]),
    )
    hidden = execution_request(move_quietly=quietly, consumed=("hidden:a", "hidden:b"))
    state = activate(hidden).state
    state = replace(state, hiding_positions=replace(
        state.hiding_positions, consumed_attack_execution_ids=("attack:older",),
    ))
    request = loss_request(move_quietly=quietly, consumed=state.consumed_opportunity_ids)
    return state, request


class K1HiddenLifecycleLossResolutionTests(unittest.TestCase):
    def test_each_loss_reason_closes_opportunity_and_preserves_history(self):
        state, request = context()
        moved = replace(request.spatial_state, placements=tuple(
            replace(item, zone_id="zone:c") if item.entity_id == state.actor_id else item
            for item in request.spatial_state.placements
        ))
        stranger = replace(request.spatial_state, placements=(
            *request.spatial_state.placements,
            SpatialEntityPlacement("stranger", "enemies", "zone:b"),
        ))
        for changes, reason in (
            ({}, HiddenAttackOpportunityLossReason.TARGET_AWARE),
            ({"hiding_position_id": "elsewhere"}, HiddenAttackOpportunityLossReason.LEFT_HIDING_POSITION),
            ({"spatial_state": moved}, HiddenAttackOpportunityLossReason.LEFT_HIDING_POSITION),
            ({"spatial_state": stranger, "target_id": "stranger", "target_is_unaware": True},
             HiddenAttackOpportunityLossReason.DIFFERENT_TARGET),
        ):
            with self.subTest(reason=reason, changes=changes):
                selected = replace(request, **changes)
                with (
                    patch.object(lifecycle, "lose_move_quietly_hidden_attack",
                                 wraps=lose_move_quietly_hidden_attack) as lose,
                    patch.object(lifecycle, "execute_registered_hidden_attack") as attack,
                ):
                    result = lifecycle.lose_hidden_lifecycle_opportunity(state, selected)
                lose.assert_called_once_with(selected)
                attack.assert_not_called()
                self.assertIs(result.completed.source_request, selected)
                self.assertIs(result.completed.reason, reason)
                self.assertIsNone(result.state.opportunity)
                self.assertEqual(result.state.consumed_opportunity_ids,
                                 ("hidden:a", "hidden:b", state.opportunity.id))
                self.assertIs(result.state.hiding_positions, state.hiding_positions)
                self.assertIs(result.previous_state, state)
                self.assertEqual(result.applied_rule_ids, tuple(dict.fromkeys((
                    HIDDEN_LIFECYCLE_RULE_ID, *result.completed.applied_rule_ids,
                ))))
        self.assertIsNotNone(state.opportunity)

    def test_stale_source_and_ordered_chain_fail_before_loss_reducer(self):
        state, request = context()
        other = execute_move_quietly_action(request.move_quietly.source_request,
                                           SequenceRandom([1, 1, 10]))
        for changed in (
            replace(state, active_move_quietly=other),
            replace(state, active_move_quietly=None),
            replace(state, consumed_opportunity_ids=()),
            replace(state, consumed_opportunity_ids=("hidden:b", "hidden:a")),
        ):
            with self.subTest(state=changed), patch.object(lifecycle, "lose_move_quietly_hidden_attack") as lose:
                with self.assertRaises(ValueError):
                    lifecycle.lose_hidden_lifecycle_opportunity(changed, request)
                lose.assert_not_called()

    def test_completed_loss_can_be_applied_without_reexecuting_reducer(self):
        state, request = context()
        completed = lose_move_quietly_hidden_attack(request)
        with patch.object(lifecycle, "lose_move_quietly_hidden_attack") as lose:
            result = lifecycle.apply_hidden_lifecycle_result(HiddenLifecycleApplicationRequest(
                "apply:loss", state, completed,
            ))
        lose.assert_not_called()
        self.assertIs(result.completed, completed)
        self.assertIs(result.state.hiding_positions, state.hiding_positions)
        other = execute_move_quietly_action(request.move_quietly.source_request, SequenceRandom([1, 1, 10]))
        for changed in (replace(state, active_move_quietly=other),
                        replace(state, consumed_opportunity_ids=())):
            with self.subTest(state=changed), self.assertRaises(ValueError):
                HiddenLifecycleApplicationRequest("stale:loss", changed, completed)

    def test_replay_and_reactivation_are_rejected_with_new_request_ids(self):
        state, request = context()
        result = lifecycle.lose_hidden_lifecycle_opportunity(state, request)
        with self.assertRaisesRegex(ValueError, "no active"):
            lifecycle.lose_hidden_lifecycle_opportunity(result.state, replace(request, id="loss:again"))
        with self.assertRaisesRegex(ValueError, "no active"):
            HiddenLifecycleApplicationRequest("apply:again", result.state, result.completed)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            HiddenLifecycleApplicationRequest("reactivate", result.state, state.active_move_quietly)

    def test_loss_result_cannot_mutate_history_or_drop_consumption_trace(self):
        state, request = context()
        result = lifecycle.lose_hidden_lifecycle_opportunity(state, request)
        changed_history = replace(state.hiding_positions,
                                  used_hiding_position_ids=("hiding:older", "hiding:wall"))
        for changes in (
            {"state": state},
            {"state": replace(result.state, hiding_positions=changed_history)},
            {"state": replace(result.state, consumed_opportunity_ids=state.consumed_opportunity_ids)},
            {"applied_rule_ids": (HIDDEN_LIFECYCLE_RULE_ID,)},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(result, **changes)

    def test_loss_errors_preserve_input_and_do_not_apply_partial_result(self):
        state, request = context()
        before = deepcopy((state, request))
        with (
            patch.object(lifecycle, "lose_move_quietly_hidden_attack", side_effect=RuntimeError("loss failed")),
            patch.object(lifecycle, "apply_hidden_lifecycle_result") as apply,
        ):
            with self.assertRaisesRegex(RuntimeError, "loss failed"):
                lifecycle.lose_hidden_lifecycle_opportunity(state, request)
        apply.assert_not_called()
        self.assertEqual((state, request), before)

    def test_eligible_attack_and_stationary_non_attack_still_require_other_paths(self):
        state, _ = context()
        for options, message in (
            ({"target_is_unaware": True}, "execution contract"),
            ({"kind": CombatActionKind.AIM}, "continuation contract"),
        ):
            with self.subTest(options=options), self.assertRaisesRegex(ValueError, message):
                loss_request(move_quietly=state.active_move_quietly,
                             consumed=state.consumed_opportunity_ids, **options)
        with self.assertRaises(TypeError):
            lifecycle.lose_hidden_lifecycle_opportunity(state, state.active_move_quietly)
