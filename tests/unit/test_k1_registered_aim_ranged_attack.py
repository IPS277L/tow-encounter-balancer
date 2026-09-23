from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_ranged_weapon_attack_resolution import aimed_ranged_request
from tests.unit.test_k1_aim_consumption_resolution import request as loss_request
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from towr.domain.aim_consumption_models import AimConsumptionState, RegisteredAimRangedAttackExecutionRequest
from towr.domain.attack_models import AttackOutcome
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.reload_models import create_initial_ranged_weapon_reload_state
from towr.rules import aim_consumption_resolution as consumption
from towr.rules.aim_resolution import execute_aim_action, resolve_aim_follow_up
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack_with_aim_history


def request(*, weapon_id=RangedWeaponId.CROSSBOW, aim_values=(1, 2, 10), renamed=False):
    history = AimConsumptionState("hero", ("aim:older",), ("follow:older", "follow:prior"))
    attack = aimed_ranged_request(
        create_initial_ranged_weapon_reload_state("hero:weapon", weapon_id), aim_values=aim_values,
        next_cycle_id="reload:1" if weapon_id is RangedWeaponId.CROSSBOW else None,
        consumed=history.consumed_aim_follow_up_ids,
    )
    if renamed:
        original = attack.aim_follow_up.source_request
        action = replace(original.attack, id="attack:new")
        follow_up = resolve_aim_follow_up(replace(original, id="follow:new", attack=action, next_action_id=action.id))
        attack = replace(attack, id="execute:new", aim_follow_up=follow_up,
                         ranged_attack=replace(attack.ranged_attack, id="ranged:new", attack=follow_up.attack))
    return RegisteredAimRangedAttackExecutionRequest("registered:aim", history, attack)


class K1RegisteredAimRangedAttackTests(unittest.TestCase):
    def test_one_executor_kernel_receipt_and_registration_for_all_outcomes(self):
        for weapon in (RangedWeaponId.LONGBOW, RangedWeaponId.CROSSBOW):
            for aim_values in ((1, 2, 10), (10, 10, 10)):
                for hit in (False, True):
                    with self.subTest(weapon=weapon, aim=aim_values, hit=hit):
                        source = request(weapon_id=weapon, aim_values=aim_values)
                        before = deepcopy(source)
                        dice = 2 + sum(value <= 5 for value in aim_values)
                        rng, decisions = SequenceRandom([1 if hit else 10, *([10] * (dice - 1)), 7]), Mock()
                        with (
                            patch.object(consumption, "execute_aim_ranged_weapon_attack", wraps=consumption.execute_aim_ranged_weapon_attack) as execute,
                            patch.object(consumption, "register_aim_ranged_attack", wraps=consumption.register_aim_ranged_attack) as register,
                            patch("towr.rules.attack_action_execution.resolve_kernel_attack", wraps=resolve_kernel_attack) as kernel,
                        ):
                            result = consumption.execute_registered_aim_ranged_attack(source, rng, decisions=decisions)
                        execute.assert_called_once_with(source.attack, rng, decisions=decisions)
                        kernel.assert_called_once()
                        register.assert_called_once_with(result.registration.source_request)
                        self.assertEqual(rng.randint(1, 10), 7)
                        self.assertIs(result.execution, result.registration.source_request.execution)
                        self.assertIs(result.state, result.registration.state)
                        self.assertIs(result.registration.previous_state, source.state)
                        self.assertEqual(result.state.consumed_aim_source_ids, ("aim:older", "aim:execute"))
                        self.assertEqual(result.state.consumed_aim_follow_up_ids, result.execution.consumed_aim_follow_up_ids)
                        shot = result.execution.ranged_attack
                        self.assertEqual(shot.attack.resolution.attack.outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
                        self.assertEqual(shot.attack.slot.execution.id, source.attack.ranged_attack.attack.id)
                        self.assertEqual(shot.attack.state.active_turn.action_slots[0], source.attack.ranged_attack.attack.state.active_turn.action_slots[0])
                        self.assertTrue(shot.attack.slot.executed)
                        self.assertTrue(set(result.registration.applied_rule_ids) <= set(result.applied_rule_ids))
                        if weapon is RangedWeaponId.CROSSBOW:
                            self.assertFalse(shot.weapon_state.loaded)
                            self.assertEqual(shot.weapon_state.reload_cycle_id, "reload:1")
                        else:
                            self.assertIs(shot.weapon_state, source.attack.ranged_attack.weapon_state)
                        self.assertEqual(source, before)

    def test_replay_and_renamed_source_fail_before_executor_rng_or_decisions(self):
        source = request()
        completed = consumption.execute_registered_aim_ranged_attack(source, SequenceRandom([10] * 4))
        for candidate in (source, request(renamed=True)):
            rng, decisions = Mock(), Mock()
            with self.subTest(id=candidate.attack.id), patch.object(consumption, "execute_aim_ranged_weapon_attack") as execute:
                with self.assertRaisesRegex(ValueError, "source was already consumed"):
                    updated = replace(candidate, id="wrapper:new", state=completed.state)
                    consumption.execute_registered_aim_ranged_attack(updated, rng, decisions=decisions)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])
            self.assertEqual(decisions.mock_calls, [])

    def test_actor_prefix_and_lost_source_preflight(self):
        source = request()
        histories = (
            replace(source.state, actor_id="other"),
            replace(source.state, consumed_aim_follow_up_ids=()),
            replace(source.state, consumed_aim_follow_up_ids=tuple(reversed(source.state.consumed_aim_follow_up_ids))),
            consumption.consume_lost_aim(loss_request()).state,
        )
        for history in histories:
            rng = Mock()
            with self.subTest(history=history), patch.object(consumption, "execute_aim_ranged_weapon_attack") as execute:
                with self.assertRaises(ValueError):
                    candidate = replace(source, state=history)
                    consumption.execute_registered_aim_ranged_attack(candidate, rng)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])

    def test_attack_before_aim_and_second_slot_in_later_turn_fail_before_execution(self):
        source = request()
        pending = source.attack.aim_follow_up.source_request.aim.source_request
        future = execute_aim_action(replace(pending, round_state=replace(pending.round_state, round_number=2)), SequenceRandom([1, 2, 10]))
        future_follow = resolve_aim_follow_up(replace(source.attack.aim_follow_up.source_request, aim=future))
        later_base = source.attack.aim_follow_up.source_request.attack
        later_base = replace(later_base, state=future.round_state)
        later_follow = resolve_aim_follow_up(replace(source.attack.aim_follow_up.source_request, attack=later_base))
        candidates = (
            replace(source.attack, aim_follow_up=future_follow),
            replace(source.attack, aim_follow_up=later_follow,
                    ranged_attack=replace(source.attack.ranged_attack, attack=later_follow.attack)),
        )
        for attack in candidates:
            with self.subTest(attack=attack.id), patch.object(consumption, "execute_aim_ranged_weapon_attack") as execute:
                with self.assertRaises(ValueError):
                    replace(source, attack=attack)
            execute.assert_not_called()

    def test_runtime_preflight_is_repeated_before_rng(self):
        source, rng = request(), Mock()
        with patch.object(consumption, "_validate_aim_attack_preflight", side_effect=ValueError("preflight failed")) as check, \
             patch.object(consumption, "execute_aim_ranged_weapon_attack") as execute:
            with self.assertRaisesRegex(ValueError, "preflight failed"):
                consumption.execute_registered_aim_ranged_attack(source, rng)
        check.assert_called_once_with(source.state, source.attack)
        execute.assert_not_called()
        self.assertEqual(rng.mock_calls, [])

    def test_rng_failure_keeps_input_snapshots_and_skips_registration(self):
        source = request()
        before = deepcopy(source)
        rng = Mock()
        rng.randint.side_effect = [1, RuntimeError("RNG failed")]
        with patch.object(consumption, "register_aim_ranged_attack") as register:
            with self.assertRaisesRegex(RuntimeError, "RNG failed"):
                consumption.execute_registered_aim_ranged_attack(source, rng)
        register.assert_not_called()
        self.assertEqual(rng.randint.call_count, 2)
        self.assertEqual(source, before)

    def test_registration_or_result_failure_keeps_inputs_without_rolling_back_rng(self):
        for stage in ("register_aim_ranged_attack", "RegisteredAimRangedAttackExecutionResult"):
            source, rng = request(), SequenceRandom([10, 10, 10, 10, 7])
            before = deepcopy(source)
            with self.subTest(stage=stage), patch.object(consumption, stage, side_effect=RuntimeError("stage failed")):
                with self.assertRaisesRegex(RuntimeError, "stage failed"):
                    consumption.execute_registered_aim_ranged_attack(source, rng)
            self.assertEqual(rng.randint(1, 10), 7)
            self.assertEqual(source, before)

    def test_result_source_registration_and_trace_cannot_be_rebound(self):
        source = request()
        result = consumption.execute_registered_aim_ranged_attack(source, SequenceRandom([10] * 4))
        other = consumption.execute_registered_aim_ranged_attack(request(renamed=True), SequenceRandom([10] * 4))
        for changes in (
            {"request_id": "other"}, {"rule_id": "other"}, {"source_request": None},
            {"registration": None}, {"registration": other.registration},
            {"source_request": replace(source, id="other")}, {"applied_rule_ids": ()},
            {"applied_rule_ids": (*result.applied_rule_ids, "extra")},
        ):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(result, **changes)

    def test_result_history_blocks_next_preparation_and_bad_types_are_rejected(self):
        source = request()
        result = consumption.execute_registered_aim_ranged_attack(source, SequenceRandom([10] * 4))
        aim_follow = source.attack.aim_follow_up.source_request
        candidate = preparation_request(RangedWeaponId.CROSSBOW, attack=aim_follow.attack, aim=aim_follow.aim, next_cycle="reload:2")
        with self.assertRaisesRegex(ValueError, "source was already consumed"):
            prepare_ranged_weapon_attack_with_aim_history(result.state, candidate)
        for changes in ({"state": None}, {"attack": None}, {"rule_id": "foreign"}, {"id": ""}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(source, **changes)
        with self.assertRaises(TypeError):
            consumption.execute_registered_aim_ranged_attack(None, Mock())
