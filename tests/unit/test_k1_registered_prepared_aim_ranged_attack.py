from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_prepared_ranged_weapon_attack_resolution import prepared_request
from tests.unit.test_k1_aim_consumption_resolution import request as loss_request
from towr.domain.aim_consumption_models import (
    AimConsumptionState,
    RegisteredPreparedAimRangedAttackExecutionRequest,
)
from towr.domain.attack_models import AttackOutcome
from towr.domain.ranged_weapon_profiles import RangedWeaponId, RangedWeaponRange
from towr.rules import aim_consumption_resolution as consumption
from towr.rules.aim_resolution import execute_aim_action
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.ranged_weapon_attack_preparation import (
    prepare_ranged_weapon_attack,
    prepare_ranged_weapon_attack_with_aim_history,
)


def request(*, weapon=RangedWeaponId.CROSSBOW, aim_values=(1, 2, 10), renamed=False):
    history = AimConsumptionState("hero", ("aim:older",), ("follow:older", "follow:prior"))
    prepared = prepared_request(
        weapon, aim_values=aim_values, consumed=history.consumed_aim_follow_up_ids,
        target_range=RangedWeaponRange.LONG,
        next_cycle="reload:1" if weapon is RangedWeaponId.CROSSBOW else None,
    )
    source = prepared.preparation.source_request
    attack = source.attack
    impact = attack.kernel_request.attack.impact_spec
    # Keep the hit below a Wound threshold so only the Shooting Test needs RNG.
    attack = replace(attack, kernel_request=replace(
        attack.kernel_request, attack=replace(attack.kernel_request.attack,
            impact_spec=replace(impact, resilience=replace(impact.resilience, toughness=100))),
    ))
    if renamed:
        attack = replace(attack, id="attack:new")
        source = replace(source, id="preparation:new")
        prepared = replace(prepared, id="prepared:new")
    prepared = replace(prepared, preparation=prepare_ranged_weapon_attack(replace(source, attack=attack)))
    return RegisteredPreparedAimRangedAttackExecutionRequest("registered:prepared", history, prepared)


class K1RegisteredPreparedAimRangedAttackTests(unittest.TestCase):
    def test_single_execution_registration_receipt_and_profile_trace_for_all_outcomes(self):
        for weapon in (RangedWeaponId.LONGBOW, RangedWeaponId.CROSSBOW):
            for values in ((1, 2, 10), (10, 10, 10)):
                for hit in (False, True):
                    with self.subTest(weapon=weapon, values=values, hit=hit):
                        source = request(weapon=weapon, aim_values=values)
                        before = deepcopy(source)
                        dice = 3 + sum(value <= 5 for value in values)
                        rng = SequenceRandom([1 if hit else 10, *([10] * (dice - 1)), 7])
                        decisions = Mock()
                        with (
                            patch.object(consumption, "execute_prepared_ranged_weapon_attack",
                                         wraps=consumption.execute_prepared_ranged_weapon_attack) as execute,
                            patch.object(consumption, "register_aim_ranged_attack",
                                         wraps=consumption.register_aim_ranged_attack) as register,
                            patch("towr.rules.attack_action_execution.resolve_kernel_attack",
                                  wraps=resolve_kernel_attack) as kernel,
                        ):
                            result = consumption.execute_registered_prepared_aim_ranged_attack(source, rng, decisions=decisions)
                        execute.assert_called_once_with(source.attack, rng, decisions=decisions)
                        kernel.assert_called_once()
                        register.assert_called_once_with(result.registration.source_request)
                        self.assertIs(result.execution.source_request, source.attack)
                        self.assertIs(result.registration.source_request.execution, result.execution.execution)
                        self.assertIs(result.state, result.registration.state)
                        self.assertIs(result.registration.previous_state, source.state)
                        self.assertEqual(result.state.consumed_aim_source_ids, ("aim:older", "aim:execute"))
                        self.assertEqual(result.state.consumed_aim_follow_up_ids,
                                         (*source.state.consumed_aim_follow_up_ids, source.attack.preparation.aim_follow_up.request_id))
                        shot = result.execution.ranged_attack
                        self.assertEqual(shot.attack.resolution.attack.outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
                        self.assertEqual(shot.attack.resolution.attack.attacker_test.trace.rolled_dice, dice)
                        self.assertEqual(shot.attack.slot.execution.id, source.attack.preparation.execution.attack.id)
                        old_slots = source.attack.preparation.execution.attack.state.active_turn.action_slots
                        new_slots = shot.attack.state.active_turn.action_slots
                        self.assertEqual(new_slots[:-1], old_slots[:-1])
                        self.assertEqual(sum(s.executed for s in new_slots), sum(s.executed for s in old_slots) + 1)
                        self.assertTrue(set(source.attack.preparation.applied_rule_ids) <= set(result.applied_rule_ids))
                        self.assertTrue(set(result.registration.applied_rule_ids) <= set(result.applied_rule_ids))
                        if weapon is RangedWeaponId.CROSSBOW:
                            self.assertFalse(shot.weapon_state.loaded)
                            self.assertEqual(shot.weapon_state.reload_cycle_id, "reload:1")
                        else:
                            self.assertIs(shot.weapon_state, source.attack.preparation.execution.weapon_state)
                        self.assertEqual(rng.randint(1, 10), 7)
                        self.assertEqual(source, before)

    def test_replay_with_new_preparation_attack_follow_up_and_wrapper_ids_fails_before_rng(self):
        source = request()
        completed = consumption.execute_registered_prepared_aim_ranged_attack(source, SequenceRandom([10] * 5))
        renamed = request(renamed=True)
        self.assertNotEqual(source.attack.preparation.aim_follow_up.request_id, renamed.attack.preparation.aim_follow_up.request_id)
        for candidate in (source, renamed):
            rng, decisions = Mock(), Mock()
            with self.subTest(id=candidate.attack.id), patch.object(consumption, "execute_prepared_ranged_weapon_attack") as execute:
                with self.assertRaisesRegex(ValueError, "source was already consumed"):
                    candidate = replace(candidate, id="wrapper:new", state=completed.state)
                    consumption.execute_registered_prepared_aim_ranged_attack(candidate, rng, decisions=decisions)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])
            self.assertEqual(decisions.mock_calls, [])

    def test_actor_prefix_and_lost_source_fail_before_execution(self):
        source = request()
        lost = consumption.consume_lost_aim(loss_request()).state
        histories = (
            replace(source.state, actor_id="other"),
            replace(source.state, consumed_aim_follow_up_ids=()),
            replace(source.state, consumed_aim_follow_up_ids=tuple(reversed(source.state.consumed_aim_follow_up_ids))),
            replace(source.state, consumed_aim_source_ids=lost.consumed_aim_source_ids),
        )
        for history in histories:
            with self.subTest(history=history), patch.object(consumption, "execute_prepared_ranged_weapon_attack") as execute:
                with self.assertRaises(ValueError):
                    replace(source, state=history)
            execute.assert_not_called()

    def test_no_aim_and_invalid_types_are_rejected(self):
        source = request()
        for changes in (
            {"state": None}, {"attack": None}, {"id": ""}, {"rule_id": "foreign"},
            {"attack": prepared_request()},
        ):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(source, **changes)
        with self.assertRaises(TypeError):
            consumption.execute_registered_prepared_aim_ranged_attack(None, Mock())

    def test_chronology_preflight_rejects_earlier_attack_and_later_second_slot(self):
        source = request()
        preparation = source.attack.preparation.source_request
        pending = preparation.aim.source_request
        future = execute_aim_action(replace(pending, round_state=replace(pending.round_state, round_number=2)), SequenceRandom([1, 2, 10]))
        for candidate in (
            replace(preparation, aim=future),
            replace(preparation, attack=replace(preparation.attack, state=replace(
                preparation.attack.state, round_number=2,
                active_turn=replace(preparation.attack.state.active_turn,
                    action_slots=(future.slot, preparation.attack.state.active_turn.action_slots[1])),
            ))),
        ):
            attack = replace(source.attack, preparation=prepare_ranged_weapon_attack(candidate))
            with self.subTest(round=candidate.attack.state.round_number), self.assertRaisesRegex(ValueError, "must follow Aim|first slot"):
                replace(source, attack=attack)

    def test_runtime_preflight_rechecks_history_before_executor(self):
        source, rng = request(), Mock()
        with (
            patch.object(consumption, "_validate_prepared_aim_attack_preflight", side_effect=ValueError("preflight failed")) as check,
            patch.object(consumption, "execute_prepared_ranged_weapon_attack") as execute,
        ):
            with self.assertRaisesRegex(ValueError, "preflight failed"):
                consumption.execute_registered_prepared_aim_ranged_attack(source, rng)
        check.assert_called_once_with(source.state, source.attack)
        execute.assert_not_called()
        self.assertEqual(rng.mock_calls, [])

    def test_rng_registration_and_result_failures_preserve_inputs(self):
        source = request()
        before = deepcopy(source)
        rng = Mock()
        rng.randint.side_effect = [1, RuntimeError("RNG failed")]
        with patch.object(consumption, "register_aim_ranged_attack") as register:
            with self.assertRaisesRegex(RuntimeError, "RNG failed"):
                consumption.execute_registered_prepared_aim_ranged_attack(source, rng)
        register.assert_not_called()
        self.assertEqual(rng.randint.call_count, 2)
        self.assertEqual(source, before)
        for stage in ("register_aim_ranged_attack", "RegisteredPreparedAimRangedAttackExecutionResult"):
            rng = SequenceRandom([10] * 5 + [7])
            with self.subTest(stage=stage), patch.object(consumption, stage, side_effect=RuntimeError("stage failed")):
                with self.assertRaisesRegex(RuntimeError, "stage failed"):
                    consumption.execute_registered_prepared_aim_ranged_attack(source, rng)
            self.assertEqual(rng.randint(1, 10), 7)
            self.assertEqual(source, before)

    def test_result_rejects_rebound_prepared_execution_registration_history_and_trace(self):
        source = request()
        result = consumption.execute_registered_prepared_aim_ranged_attack(source, SequenceRandom([10] * 5))
        other = consumption.execute_registered_prepared_aim_ranged_attack(request(renamed=True), SequenceRandom([10] * 5))
        for changes in (
            {"request_id": "other"}, {"rule_id": "other"}, {"source_request": None},
            {"execution": None}, {"registration": None}, {"execution": other.execution},
            {"registration": other.registration}, {"applied_rule_ids": ()},
            {"applied_rule_ids": (*result.applied_rule_ids, "extra")},
            {"source_request": replace(source, state=replace(source.state, consumed_aim_source_ids=("different",)))},
        ):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(result, **changes)

    def test_returned_history_blocks_renamed_next_preparation(self):
        source = request()
        result = consumption.execute_registered_prepared_aim_ranged_attack(source, SequenceRandom([10] * 5))
        preparation = request(renamed=True).attack.preparation.source_request
        with self.assertRaisesRegex(ValueError, "source was already consumed"):
            prepare_ranged_weapon_attack_with_aim_history(result.state, preparation)
