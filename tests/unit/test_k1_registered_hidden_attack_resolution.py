from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_hidden_attack_resolution import execution_request
from tests.unit.test_k1_hidden_ranged_weapon_attack_resolution import combined_request
from tests.unit.test_k1_move_quietly_resolution import request as quietly_request
from tests.unit.test_k1_prepared_hidden_ranged_attack_resolution import (
    request as prepared_request,
)
from towr.domain.hiding_position_models import (
    HidingPositionRegistrationRequest,
    HidingPositionState,
    RegisteredHiddenAttackExecutionRequest,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.reload_models import create_initial_ranged_weapon_reload_state
from towr.rules import hiding_position_resolution as resolution
from towr.rules.kernel import resolve_kernel_attack


def branches():
    return (
        (execution_request(), "execute_move_quietly_hidden_attack"),
        (combined_request(create_initial_ranged_weapon_reload_state(
            "bow:hero", RangedWeaponId.LONGBOW,
        )), "execute_move_quietly_hidden_ranged_attack"),
        (prepared_request(), "execute_prepared_hidden_ranged_attack"),
    )


def request(attack):
    return RegisteredHiddenAttackExecutionRequest(
        "registered:hidden", HidingPositionState("hero"), attack,
    )


class K1RegisteredHiddenAttackResolutionTests(unittest.TestCase):
    def test_each_branch_executes_one_kernel_and_registers_hit_and_miss(self):
        for attack, name in branches():
            for values in ([1, 10], [10, 10]):
                with self.subTest(branch=name, values=values):
                    source = request(attack)
                    rng = SequenceRandom([*values, 7])
                    decisions = Mock()
                    with (
                        patch.object(resolution, name, wraps=getattr(resolution, name)) as execute,
                        patch("towr.rules.attack_action_execution.resolve_kernel_attack",
                              wraps=resolve_kernel_attack) as kernel,
                        patch.object(resolution, "register_revealed_hiding_position",
                                     wraps=resolution.register_revealed_hiding_position) as register,
                    ):
                        result = resolution.execute_registered_hidden_attack(
                            source, rng, decisions=decisions,
                        )
                    execute.assert_called_once_with(attack, rng, decisions=decisions)
                    kernel.assert_called_once()
                    register.assert_called_once()
                    self.assertEqual(rng.randint(1, 10), 7)
                    self.assertIs(result.execution.source_request, attack)
                    self.assertIs(result.execution, result.registration.source_request.execution)
                    self.assertEqual(result.state.used_hiding_position_ids, ("hiding:wall",))
                    self.assertEqual(result.state.consumed_attack_execution_ids,
                                     (source.hidden_request.attack.id,))
                    self.assertIs(result.previous_state, source.state)
                    self.assertTrue(set(result.execution.applied_rule_ids)
                                    <= set(result.applied_rule_ids))
                    executed = (result.execution.attack if name == "execute_move_quietly_hidden_attack"
                                else result.execution.ranged_attack.attack)
                    before = source.hidden_request.attack.state.active_turn.action_slots
                    after = executed.state.active_turn.action_slots
                    self.assertEqual(after[:-1], before[:-1])
                    self.assertTrue(after[-1].executed)
                    self.assertFalse(before[-1].executed)

    def test_history_preflight_blocks_all_branches_before_rng_or_executor(self):
        for attack, name in branches():
            source = request(attack)
            for state, message in (
                (HidingPositionState("ally"), "another actor"),
                (HidingPositionState("hero", ("hiding:older",)), "stale"),
                (HidingPositionState("hero", ("hiding:wall",)), "already used"),
                (HidingPositionState("hero", (), (source.hidden_request.attack.id,)),
                 "already registered"),
            ):
                with self.subTest(branch=name, message=message):
                    rng = Mock()
                    with patch.object(resolution, name) as execute:
                        with self.assertRaisesRegex(ValueError, message):
                            resolution.execute_registered_hidden_attack(
                                replace(source, state=state), rng,
                            )
                    execute.assert_not_called()
                    rng.randint.assert_not_called()

    def test_replay_cannot_change_wrapper_or_registration_id(self):
        first = resolution.execute_registered_hidden_attack(
            request(execution_request()), SequenceRandom([10, 10]),
        )
        for attack, name in branches():
            source = request(attack)
            with self.subTest(branch=name), self.assertRaisesRegex(ValueError, "already registered"):
                replace(source, id="different:wrapper", state=first.state)
        with self.assertRaisesRegex(ValueError, "already registered"):
            HidingPositionRegistrationRequest("different:registration", first.state, first.execution)

    def test_rng_exception_leaves_every_input_unchanged_and_never_registers(self):
        for attack, name in branches():
            with self.subTest(branch=name):
                source = request(attack)
                before = deepcopy(source)
                rng = Mock()
                rng.randint.side_effect = [10, RuntimeError("RNG failed")]
                with patch.object(resolution, "register_revealed_hiding_position") as register:
                    with self.assertRaisesRegex(RuntimeError, "RNG failed"):
                        resolution.execute_registered_hidden_attack(source, rng)
                self.assertEqual(rng.randint.call_count, 2)
                register.assert_not_called()
                self.assertEqual(source, before)

    def test_registration_exception_returns_no_partial_state(self):
        source = request(prepared_request(RangedWeaponId.CROSSBOW))
        before = deepcopy(source)
        with patch.object(resolution, "register_revealed_hiding_position",
                          side_effect=RuntimeError("registration failed")):
            with self.assertRaisesRegex(RuntimeError, "registration failed"):
                resolution.execute_registered_hidden_attack(source, SequenceRandom([10, 10]))
        self.assertEqual(source, before)
        self.assertTrue(source.attack.prepared_attack.preparation.execution.weapon_state.loaded)

    def test_prepared_aim_and_reload_keep_independent_consumption_chains(self):
        for aim_values in ((10, 10, 10), (1, 10, 10)):
            for weapon, bonus in ((RangedWeaponId.CROSSBOW, False),
                                  (RangedWeaponId.REPEATER_PISTOL, True)):
                with self.subTest(aim=aim_values, weapon=weapon):
                    attack = prepared_request(weapon, aim_values=aim_values, repeater_bonus=bonus)
                    count = min(4, 2 + (aim_values[0] == 1) + (2 if bonus else 0))
                    rng = SequenceRandom([10] * count + [7])
                    result = resolution.execute_registered_hidden_attack(request(attack), rng)
                    execution = result.execution
                    self.assertEqual(rng.randint(1, 10), 7)
                    self.assertFalse(execution.ranged_attack.weapon_state.loaded)
                    self.assertEqual(execution.consumed_opportunity_ids,
                                     ("hidden:older", attack.hidden_attack.opportunity.id))
                    self.assertEqual(execution.consumed_aim_follow_up_ids, (
                        "aim:older", attack.prepared_attack.preparation.aim_follow_up.request_id,
                    ))
                    self.assertEqual(len(result.state.consumed_attack_execution_ids), 1)

    def test_result_rejects_unrelated_registration_and_incomplete_trace(self):
        source = request(execution_request())
        result = resolution.execute_registered_hidden_attack(source, SequenceRandom([10, 10]))
        foreign = resolution.execute_registered_hidden_attack(
            request(prepared_request()), SequenceRandom([10, 10]),
        )
        for changes in (
            {"registration": foreign.registration},
            {"request_id": "foreign"},
            {"source_request": replace(source, id="foreign")},
            {"applied_rule_ids": result.registration.applied_rule_ids},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(result, **changes)

    def test_profile_aware_reload_transition_is_preserved(self):
        weapon = create_initial_ranged_weapon_reload_state(
            "crossbow:hero", RangedWeaponId.CROSSBOW,
        )
        attack = combined_request(weapon, next_cycle_id="crossbow:reload:1")
        result = resolution.execute_registered_hidden_attack(
            request(attack), SequenceRandom([10, 10]),
        )
        self.assertFalse(result.execution.ranged_attack.weapon_state.loaded)
        self.assertEqual(result.execution.ranged_attack.weapon_state.reload_cycle_id,
                         "crossbow:reload:1")
        self.assertTrue(weapon.loaded)
        self.assertEqual(result.state.used_hiding_position_ids, ("hiding:wall",))

    def test_result_history_reaches_next_move_quietly_preparation(self):
        result = resolution.execute_registered_hidden_attack(
            request(execution_request()), SequenceRandom([10, 10]),
        )
        with self.assertRaisesRegex(ValueError, "new hiding position"):
            resolution.prepare_move_quietly_with_hiding_positions(result.state, quietly_request())
        prepared = resolution.prepare_move_quietly_with_hiding_positions(
            result.state, quietly_request(hiding_position_id="hiding:tree"),
        )
        self.assertEqual(prepared.used_hiding_position_ids, result.state.used_hiding_position_ids)

    def test_wrong_contract_types_and_unknown_rule_are_rejected(self):
        source = request(execution_request())
        for changes, error in (({"attack": source.hidden_request.attack}, TypeError),
                               ({"state": None}, TypeError),
                               ({"rule_id": "foreign"}, ValueError),
                               ({"id": ""}, ValueError)):
            with self.subTest(changes=changes), self.assertRaises(error):
                replace(source, **changes)
        rng = Mock()
        with self.assertRaises(TypeError):
            resolution.execute_registered_hidden_attack(source.attack, rng)
        rng.randint.assert_not_called()
