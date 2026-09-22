from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_hidden_attack_resolution import execution_request
from tests.unit.test_k1_hidden_continuation_resolution import continuation_request
from tests.unit.test_k1_prepared_hidden_ranged_attack_resolution import request as prepared_request
from tests.unit.test_k1_registered_hidden_attack_resolution import branches
from tests.unit.test_k1_move_quietly_resolution import (
    request as quietly_request,
    reserve_action,
    move_quietly_declaration,
)
from towr.domain.hidden_lifecycle_models import (
    HIDDEN_LIFECYCLE_RULE_ID,
    HiddenLifecycleApplicationRequest,
    HiddenLifecycleState,
)
from towr.domain.hiding_position_models import (
    HidingPositionState,
    RegisteredHiddenAttackExecutionRequest,
)
from towr.domain.move_quietly_models import MoveQuietlyHidingChoice
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.turn_models import CombatRoundState, CombatTurnStartRequest
from towr.rules import hidden_lifecycle_resolution as lifecycle
from towr.rules.hiding_position_resolution import (
    execute_registered_hidden_attack,
    prepare_move_quietly_with_hiding_positions,
)
from towr.rules.move_quietly_resolution import execute_move_quietly_action
from towr.rules.turn_resolution import start_combat_turn


def activate(hidden):
    state = HiddenLifecycleState(
        HidingPositionState(hidden.actor_id,
                            hidden.move_quietly.source_request.used_hiding_position_ids),
        consumed_opportunity_ids=hidden.consumed_opportunity_ids,
    )
    return lifecycle.apply_hidden_lifecycle_result(HiddenLifecycleApplicationRequest(
        "adopt:hidden", state, hidden.move_quietly,
    ))


def registered(attack, state):
    return RegisteredHiddenAttackExecutionRequest("registered:hidden", state.hiding_positions, attack)


class K1HiddenLifecycleResolutionTests(unittest.TestCase):
    def test_activation_keeps_exact_source_and_one_opportunity_view(self):
        hidden = execution_request()
        result = activate(hidden)
        self.assertIs(result.completed, hidden.move_quietly)
        self.assertIs(result.state.active_move_quietly, result.completed)
        self.assertIs(result.state.opportunity, hidden.opportunity)
        self.assertEqual(result.state.actor_id, hidden.actor_id)
        self.assertIsNone(result.previous_state.opportunity)
        with self.assertRaisesRegex(ValueError, "resolve the active"):
            replace(result.source_request, state=result.state)
        with self.assertRaises(FrozenInstanceError):
            result.state.active_move_quietly = None

    def test_failed_or_declined_move_quietly_preserves_inactive_state(self):
        initial = HiddenLifecycleState(HidingPositionState("hero"))
        for request, values in ((quietly_request(), [10, 10, 1]),
                                (quietly_request(include_movement=False), [1, 10, 10])):
            completed = execute_move_quietly_action(request, SequenceRandom(values))
            with self.subTest(outcome=completed.outcome):
                result = lifecycle.apply_hidden_lifecycle_result(HiddenLifecycleApplicationRequest(
                    "apply:quietly", initial, completed,
                ))
                self.assertIs(result.state, initial)
                self.assertIs(result.completed, completed)
        self.assertIsNone(initial.opportunity)

    def test_state_rejects_foreign_consumed_or_stale_active_source(self):
        source = execution_request().move_quietly
        for history, consumed, message in (
            (HidingPositionState("ally"), (), "another actor"),
            (HidingPositionState("hero"), (source.hidden_attack_opportunity.id,), "already consumed"),
            (HidingPositionState("hero", ("hiding:wall",)), (), "already used"),
            (HidingPositionState("hero", ("hiding:older",)), (), "stale hiding"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                HiddenLifecycleState(history, source, consumed)
        for invalid in ("string", ("duplicate", "duplicate"), ("",), (1,)):
            with self.subTest(invalid=invalid), self.assertRaises((TypeError, ValueError)):
                HiddenLifecycleState(HidingPositionState("hero"), consumed_opportunity_ids=invalid)
        self.assertEqual(HiddenLifecycleState(HidingPositionState("hero"),
                         consumed_opportunity_ids=["older"]).consumed_opportunity_ids, ("older",))

    def test_continuation_preserves_one_snapshot_and_is_idempotent(self):
        request = continuation_request()
        state = activate(prepared_request(aim_values=(1, 10, 10)).hidden_attack).state
        with patch.object(lifecycle, "continue_move_quietly_hidden_attack",
                          wraps=lifecycle.continue_move_quietly_hidden_attack) as execute:
            result = lifecycle.continue_hidden_lifecycle(state, request)
        execute.assert_called_once_with(request)
        self.assertIs(result.state, state)
        self.assertIs(result.completed.remaining_opportunity, request.opportunity)
        self.assertEqual(lifecycle.continue_hidden_lifecycle(result.state, request), result)

    def test_departure_and_reveal_clear_active_without_registering_an_attack(self):
        request = continuation_request()
        state = activate(prepared_request(aim_values=(1, 10, 10)).hidden_attack).state
        for changes in ({"position_revealed": True}, {"hiding_position_id": "elsewhere"}):
            with self.subTest(changes=changes):
                result = lifecycle.continue_hidden_lifecycle(state, replace(request, **changes))
                self.assertIsNone(result.state.opportunity)
                self.assertEqual(result.state.consumed_opportunity_ids,
                                 (*state.consumed_opportunity_ids, state.opportunity.id))
                self.assertIs(result.state.hiding_positions, state.hiding_positions)
                with self.assertRaisesRegex(ValueError, "no active"):
                    replace(result.source_request, state=result.state)
                with self.assertRaisesRegex(ValueError, "already consumed"):
                    HiddenLifecycleApplicationRequest("reactivate", result.state, state.active_move_quietly)
        self.assertIsNotNone(state.opportunity)

    def test_all_attack_branches_atomically_close_active_and_register_hit_or_miss(self):
        for attack, name in branches():
            hidden = attack if name == "execute_move_quietly_hidden_attack" else attack.hidden_attack
            state = activate(hidden).state
            for values in ([1, 10], [10, 10]):
                with self.subTest(branch=name, values=values):
                    request = registered(attack, state)
                    rng = SequenceRandom([*values, 7])
                    decisions = Mock()
                    with patch.object(lifecycle, "execute_registered_hidden_attack",
                                      wraps=execute_registered_hidden_attack) as execute:
                        result = lifecycle.execute_hidden_lifecycle_attack(state, request, rng, decisions=decisions)
                    execute.assert_called_once_with(request, rng, decisions=decisions)
                    self.assertEqual(rng.randint(1, 10), 7)
                    self.assertIsNone(result.state.active_move_quietly)
                    self.assertEqual(result.state.consumed_opportunity_ids,
                                     (*state.consumed_opportunity_ids, hidden.opportunity.id))
                    self.assertIs(result.state.hiding_positions, result.completed.state)
                    self.assertEqual(result.state.hiding_positions.used_hiding_position_ids, ("hiding:wall",))
                    self.assertEqual(result.state.hiding_positions.consumed_attack_execution_ids, (hidden.attack.id,))
                    self.assertTrue(set(result.completed.applied_rule_ids) <= set(result.applied_rule_ids))
                    with self.assertRaisesRegex(ValueError, "no active"):
                        lifecycle.execute_hidden_lifecycle_attack(result.state, request, Mock())

    def test_stale_source_chain_or_history_is_rejected_before_rng(self):
        attack = prepared_request()
        hidden = attack.hidden_attack
        state = activate(hidden).state
        request = registered(attack, state)
        # Same request/opportunity IDs, but a different completed Stealth result.
        foreign_source = execute_move_quietly_action(hidden.move_quietly.source_request,
                                                     SequenceRandom([1, 1, 10]))
        for changed, message in (
            (replace(state, active_move_quietly=None), "no active"),
            (replace(state, active_move_quietly=foreign_source), "active hidden source"),
            (replace(state, consumed_opportunity_ids=()), "stale opportunity"),
            (replace(state, consumed_opportunity_ids=("hidden:other", "hidden:older")), "stale opportunity"),
            (replace(state, hiding_positions=replace(state.hiding_positions,
                     consumed_attack_execution_ids=("attack:older",))), "stale hiding"),
        ):
            with self.subTest(message=message):
                rng = Mock()
                with patch.object(lifecycle, "execute_registered_hidden_attack") as execute:
                    with self.assertRaisesRegex(ValueError, message):
                        lifecycle.execute_hidden_lifecycle_attack(changed, request, rng)
                execute.assert_not_called()
                rng.randint.assert_not_called()

    def test_stale_continuation_is_rejected_without_calling_reducer(self):
        request = continuation_request()
        state = activate(prepared_request(aim_values=(1, 10, 10)).hidden_attack).state
        foreign = execute_move_quietly_action(request.move_quietly.source_request,
                                             SequenceRandom([1, 1, 10]))
        for changed in (replace(state, consumed_opportunity_ids=()),
                        replace(state, active_move_quietly=foreign)):
            with self.subTest(state=changed), patch.object(lifecycle, "continue_move_quietly_hidden_attack") as execute:
                with self.assertRaises(ValueError):
                    lifecycle.continue_hidden_lifecycle(changed, request)
                execute.assert_not_called()

    def test_completed_result_application_also_rejects_stale_source_or_chain(self):
        attack = prepared_request()
        state = activate(attack.hidden_attack).state
        completed = execute_registered_hidden_attack(registered(attack, state), SequenceRandom([10, 10]))
        for changed in (replace(state, consumed_opportunity_ids=()),
                        replace(state, active_move_quietly=None)):
            with self.subTest(state=changed), self.assertRaises(ValueError):
                HiddenLifecycleApplicationRequest("apply", changed, completed)

    def test_consumed_attack_cannot_be_reapplied_or_reactivated_with_new_ids(self):
        hidden = execution_request()
        state = activate(hidden).state
        result = lifecycle.execute_hidden_lifecycle_attack(
            state, registered(hidden, state), SequenceRandom([10, 10]),
        )
        with self.assertRaisesRegex(ValueError, "no active"):
            HiddenLifecycleApplicationRequest("apply:again", result.state, result.completed)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            HiddenLifecycleApplicationRequest("adopt:again", result.state, hidden.move_quietly)

    def test_rng_exception_leaves_lifecycle_weapon_and_consumption_unchanged(self):
        attack = prepared_request(RangedWeaponId.CROSSBOW, aim_values=(1, 10, 10))
        state = activate(attack.hidden_attack).state
        request = registered(attack, state)
        before = deepcopy((state, request))
        rng = Mock()
        rng.randint.side_effect = [10, RuntimeError("RNG failed")]
        with patch.object(lifecycle, "apply_hidden_lifecycle_result") as apply:
            with self.assertRaisesRegex(RuntimeError, "RNG failed"):
                lifecycle.execute_hidden_lifecycle_attack(state, request, rng)
        apply.assert_not_called()
        self.assertEqual((state, request), before)

    def test_result_rejects_forged_state_and_trace(self):
        attack = execution_request()
        state = activate(attack).state
        result = lifecycle.execute_hidden_lifecycle_attack(state, registered(attack, state), SequenceRandom([10, 10]))
        for changes in ({"state": state}, {"request_id": "foreign"},
                        {"state": replace(result.state, consumed_opportunity_ids=())},
                        {"applied_rule_ids": (HIDDEN_LIFECYCLE_RULE_ID,)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(result, **changes)

    def test_move_quietly_aim_attack_and_second_hiding_cycle_share_one_state(self):
        attack = prepared_request(RangedWeaponId.CROSSBOW, aim_values=(1, 10, 10))
        hidden = attack.hidden_attack
        initial = HiddenLifecycleState(HidingPositionState("hero"),
                                       consumed_opportunity_ids=hidden.consumed_opportunity_ids)
        state = lifecycle.execute_hidden_lifecycle_move_quietly(
            initial, hidden.move_quietly.source_request, SequenceRandom([1, 10, 10]),
        ).state
        state = lifecycle.continue_hidden_lifecycle(state, continuation_request(attack)).state
        result = lifecycle.execute_hidden_lifecycle_attack(state, registered(attack, state), SequenceRandom([10, 10, 10]))
        self.assertFalse(result.completed.execution.ranged_attack.weapon_state.loaded)
        self.assertEqual(len(result.completed.execution.consumed_aim_follow_up_ids), 2)
        state = result.state
        round_state = start_combat_turn(CombatTurnStartRequest(
            "turn:hero:3", CombatRoundState(round_number=3,
                participants=hidden.attack.state.participants), "hero",
        )).state
        round_state = reserve_action(round_state, move_quietly_declaration())
        candidate = replace(quietly_request(
            round_state=round_state,
            state=replace(hidden.spatial_state, round_number=3, free_move_used_entity_ids=()),
            include_movement=False, hiding_choice=MoveQuietlyHidingChoice.HIDE_IN_CURRENT_ZONE,
            hiding_position_id="hiding:tree",
        ), id="quietly:3")
        prepared = prepare_move_quietly_with_hiding_positions(state.hiding_positions, candidate)
        next_hiding = lifecycle.execute_hidden_lifecycle_move_quietly(
            state, prepared, SequenceRandom([1, 10, 10]),
        )
        quietly, state = next_hiding.completed, next_hiding.state
        next_attack = execution_request(move_quietly=quietly, hiding_position_id="hiding:tree",
                                        consumed=state.consumed_opportunity_ids)
        next_attack = replace(next_attack, id="hidden:3", attack=replace(next_attack.attack, id="attack:3"))
        final = lifecycle.execute_hidden_lifecycle_attack(state, registered(next_attack, state), SequenceRandom([10, 10]))
        self.assertEqual(final.state.hiding_positions.used_hiding_position_ids, ("hiding:wall", "hiding:tree"))
        self.assertEqual(final.state.consumed_opportunity_ids,
                         ("hidden:older", hidden.opportunity.id, next_attack.opportunity.id))
        self.assertIsNone(final.state.opportunity)

    def test_wrong_types_and_unknown_rules_fail_explicitly(self):
        state = HiddenLifecycleState(HidingPositionState("hero"))
        for completed in (None, execution_request(), HidingPositionState("hero")):
            with self.subTest(completed=completed), self.assertRaises(TypeError):
                HiddenLifecycleApplicationRequest("bad", state, completed)
        source = execution_request().move_quietly
        with self.assertRaises(ValueError):
            HiddenLifecycleApplicationRequest("bad", state, source, rule_id="foreign")
        with self.assertRaises(TypeError):
            lifecycle.continue_hidden_lifecycle(state, source)
        with self.assertRaises(TypeError):
            lifecycle.execute_hidden_lifecycle_attack(state, source, Mock())
