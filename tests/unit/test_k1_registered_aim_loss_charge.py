from copy import deepcopy
from dataclasses import replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_charge_loss_consumption import pending_inputs
from tests.unit.test_k1_aim_consumption_resolution import request as non_attack_request
from tests.unit.test_k1_aim_attack_consumption import request as applied_request
from tests.unit.test_k1_aim_attack_loss_consumption import request as attack_loss_request
from tests.unit.test_k1_aim_resolution import attack_execution_request
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from towr.domain.aim_consumption_models import AimConsumptionState, RegisteredAimLossChargeExecutionRequest
from towr.domain.attack_models import AttackOutcome
from towr.domain.movement_models import MovementSpeed
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind
from towr.rules import aim_consumption_resolution as consumption
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack_with_aim_history


def request(**kwargs):
    follow, charge = pending_inputs(**kwargs)
    return RegisteredAimLossChargeExecutionRequest(
        "registered:charge", AimConsumptionState("hero", ("source:older",), ("follow:older", "follow:prior")),
        follow, charge,
    )


class K1RegisteredAimLossChargeTests(unittest.TestCase):
    def test_one_charge_kernel_receipt_registration_for_hit_miss_aim_zero_positive_and_later_turn(self):
        for values, hit, later, target in product(((10, 10, 10), (1, 2, 10)), (False, True), (None, 2), ("enemy", "enemy:other")):
            with self.subTest(values=values, hit=hit, later=later, target=target):
                source = request(values=values, later_round=later, aim_target=target)
                before = deepcopy(source)
                rng, decisions = SequenceRandom([1 if hit else 10, 10, 7]), Mock()
                with (
                    patch.object(consumption, "execute_charge_action", wraps=consumption.execute_charge_action) as execute,
                    patch.object(consumption, "consume_charge_lost_aim", wraps=consumption.consume_charge_lost_aim) as register,
                    patch("towr.rules.charge_action_execution.resolve_kernel_attack", wraps=resolve_kernel_attack) as kernel,
                ):
                    result = consumption.execute_registered_aim_loss_charge(source, rng, decisions=decisions)
                execute.assert_called_once_with(source.charge, rng, decisions=decisions)
                kernel.assert_called_once()
                register.assert_called_once_with(result.registration.source_request)
                self.assertIs(result.execution, result.registration.source_request.execution)
                self.assertIs(result.state, result.registration.state)
                self.assertIs(result.registration.previous_state, source.state)
                self.assertIs(result.registration.source_request.follow_up, source.follow_up)
                self.assertEqual(result.state.consumed_aim_source_ids, ("source:older", "aim:execute"))
                self.assertEqual(result.state.consumed_aim_follow_up_ids, ("follow:older", "follow:prior", "follow:charge"))
                execution = result.execution
                self.assertEqual(execution.resolution.attack.attacker_test.trace.rolled_dice, 2)
                self.assertEqual(execution.resolution.attack.attacker_test.trace.regular_dice_delta, 1)
                self.assertIs(execution.resolution.attack.outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
                self.assertEqual(execution.previous_spatial_state, source.charge.spatial_state)
                self.assertEqual(execution.spatial_state.placement_for("hero").zone_id, "zone:b")
                self.assertEqual(execution.round_state.active_turn.action_slots[:-1], source.charge.round_state.active_turn.action_slots[:-1])
                self.assertEqual(execution.slot.execution.id, source.charge.id)
                self.assertTrue(execution.slot.executed)
                self.assertEqual(rng.randint(1, 10), 7)
                self.assertEqual(result.applied_rule_ids, tuple(dict.fromkeys((source.rule_id, *result.registration.applied_rule_ids))))
                self.assertEqual(source, before)

    def test_renamed_replay_and_shared_histories_fail_before_charge_rng_or_decisions(self):
        source = request()
        histories = (
            consumption.execute_registered_aim_loss_charge(source, SequenceRandom([10, 10])).state,
            consumption.consume_lost_aim(non_attack_request()).state,
            consumption.consume_attack_lost_aim(attack_loss_request()).state,
            consumption.register_aim_ranged_attack(applied_request()).state,
        )
        for history, candidate in product(histories, (source, request(renamed=True))):
            rng, decisions = Mock(), Mock()
            with self.subTest(id=candidate.charge.id, history=history), patch.object(consumption, "execute_charge_action") as execute:
                with self.assertRaisesRegex(ValueError, "source was already consumed"):
                    consumption.execute_registered_aim_loss_charge(
                        replace(candidate, id="wrapper:new", state=history), rng, decisions=decisions,
                    )
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])
            self.assertEqual(decisions.mock_calls, [])

    def test_actor_action_slot_and_history_guards_before_executor(self):
        source = request()
        turn = source.charge.round_state.active_turn
        wrong_slot = replace(turn.action_slots[-1], declaration=CombatActionDeclaration(CombatActionKind.RECOVER))
        wrong_charge = replace(source.charge, round_state=replace(source.charge.round_state,
            active_turn=replace(turn, action_slots=(*turn.action_slots[:-1], wrong_slot))))
        for changes in (
            {"state": replace(source.state, actor_id="other")},
            {"state": replace(source.state, consumed_aim_follow_up_ids=(source.follow_up.request_id,))},
            {"charge": replace(source.charge, id="different")}, {"charge": wrong_charge},
            {"charge": replace(source.charge, rule_id="foreign")},
            {"follow_up": non_attack_request().follow_up},
        ):
            rng = Mock()
            with self.subTest(changes=changes), patch.object(consumption, "execute_charge_action") as execute:
                with self.assertRaises(ValueError):
                    consumption.execute_registered_aim_loss_charge(replace(source, **changes), rng)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])

    def test_unsupported_skill_and_chronology_before_executor(self):
        for kwargs in ({"skill": Skill.BRAWN}, {"later_round": 1}, {"later_round": 2, "later_second": True}):
            rng = Mock()
            with self.subTest(kwargs=kwargs), patch.object(consumption, "execute_charge_action") as execute:
                with self.assertRaises(ValueError):
                    consumption.execute_registered_aim_loss_charge(request(**kwargs), rng)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])

    def test_runtime_rechecks_shared_preflight(self):
        source, rng = request(), Mock()
        with (
            patch.object(consumption, "_validate_charge_loss_preflight", side_effect=ValueError("preflight failed")) as check,
            patch.object(consumption, "execute_charge_action") as execute,
        ):
            with self.assertRaisesRegex(ValueError, "preflight failed"):
                consumption.execute_registered_aim_loss_charge(source, rng)
        check.assert_called_once_with(source.state, source.follow_up, source.charge)
        execute.assert_not_called()
        self.assertEqual(rng.mock_calls, [])

    def test_charge_guards_and_rng_failure_preserve_inputs_without_registration(self):
        source = request()
        for charge in (replace(source.charge, speed=MovementSpeed.SLOW), replace(source.charge, crosses_difficult_terrain=True)):
            rng = Mock()
            with patch.object(consumption, "consume_charge_lost_aim") as register:
                with self.assertRaises(ValueError):
                    consumption.execute_registered_aim_loss_charge(replace(source, charge=charge), rng)
            register.assert_not_called()
            self.assertEqual(rng.mock_calls, [])
        before = deepcopy(source)
        rng = Mock()
        rng.randint.side_effect = [1, RuntimeError("RNG failed")]
        with patch.object(consumption, "consume_charge_lost_aim") as register:
            with self.assertRaisesRegex(RuntimeError, "RNG failed"):
                consumption.execute_registered_aim_loss_charge(source, rng)
        register.assert_not_called()
        self.assertEqual(source, before)
        self.assertEqual(rng.randint.call_count, 2)

    def test_registration_or_result_failure_preserves_snapshots_without_undoing_rng(self):
        for stage in ("consume_charge_lost_aim", "RegisteredAimLossChargeExecutionResult"):
            source, rng = request(), SequenceRandom([10, 10, 7])
            before = deepcopy(source)
            with self.subTest(stage=stage), patch.object(consumption, stage, side_effect=RuntimeError("stage failed")):
                with self.assertRaisesRegex(RuntimeError, "stage failed"):
                    consumption.execute_registered_aim_loss_charge(source, rng)
            self.assertEqual(source, before)
            self.assertEqual(rng.randint(1, 10), 7)

    def test_result_binds_charge_source_states_kernel_history_and_exact_trace(self):
        source = request()
        result = consumption.execute_registered_aim_loss_charge(source, SequenceRandom([10, 10]))
        other = consumption.execute_registered_aim_loss_charge(request(renamed=True), SequenceRandom([10, 10]))
        changed_charges = (
            replace(source.charge, kernel_request=replace(source.charge.kernel_request, id="other")),
            replace(source.charge, spatial_state=replace(source.charge.spatial_state, free_move_used_entity_ids=())),
            replace(source.charge, round_state=replace(source.charge.round_state, completed_turn_entity_ids=("ally",))),
            replace(source.charge, speed=MovementSpeed.FAST),
        )
        for changes in (
            {"request_id": "other"}, {"rule_id": "other"}, {"source_request": None},
            {"registration": None}, {"registration": other.registration},
            {"source_request": replace(source, id="other")},
            {"source_request": replace(source, state=replace(source.state, consumed_aim_source_ids=("other",)))},
            *({"source_request": replace(source, charge=c)} for c in changed_charges),
            {"applied_rule_ids": ()}, {"applied_rule_ids": (*result.applied_rule_ids, "foreign")},
        ):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(result, **changes)

    def test_types_and_next_preparation_with_returned_history(self):
        source = request()
        for changes in ({"id": ""}, {"rule_id": "other"}, {"state": None}, {"follow_up": None}, {"charge": None}):
            with self.assertRaises((TypeError, ValueError)):
                replace(source, **changes)
        with self.assertRaises(TypeError):
            consumption.execute_registered_aim_loss_charge(None, Mock())
        result = consumption.execute_registered_aim_loss_charge(source, SequenceRandom([10, 10]))
        candidate = replace(preparation_request(RangedWeaponId.LONGBOW,
            aim=source.follow_up.source_request.aim, attack=replace(attack_execution_request(), id="attack:new")), id="prepare:new")
        with patch("towr.rules.ranged_weapon_attack_preparation.prepare_ranged_weapon_attack") as prepare:
            with self.assertRaisesRegex(ValueError, "source was already consumed"):
                prepare_ranged_weapon_attack_with_aim_history(result.state, candidate)
        prepare.assert_not_called()


if __name__ == "__main__":
    unittest.main()
