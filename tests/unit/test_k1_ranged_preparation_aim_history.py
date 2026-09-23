from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_consumption_resolution import request as loss_request
from tests.unit.test_k1_ranged_weapon_attack_preparation import aim_and_attack, preparation_request
from towr.domain.aim_consumption_models import AimConsumptionState
from towr.domain.aim_models import AIM_FOLLOW_UP_RULE_ID
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.rules.aim_consumption_resolution import consume_lost_aim
from towr.rules.aim_resolution import execute_aim_action
from towr.rules import ranged_weapon_attack_preparation as preparation


def candidate(weapon_id=RangedWeaponId.CROSSBOW, *, aimed=True, zero_aim=False):
    aim, attack = aim_and_attack()
    if zero_aim:
        aim = execute_aim_action(aim.source_request, SequenceRandom([10, 10, 10]))
    return preparation_request(weapon_id, attack=attack, aim=aim if aimed else None,
                               next_cycle="reload:next" if weapon_id is RangedWeaponId.CROSSBOW else None)


class K1RangedPreparationAimHistoryTests(unittest.TestCase):
    def test_fresh_aim_and_no_aim_delegate_once_and_preserve_exact_result(self):
        for weapon_id in (RangedWeaponId.SLING, RangedWeaponId.CROSSBOW):
            for aimed, zero_aim in ((False, False), (True, False), (True, True)):
                with self.subTest(weapon=weapon_id, aimed=aimed, zero=zero_aim):
                    request = candidate(weapon_id, aimed=aimed, zero_aim=zero_aim)
                    state = AimConsumptionState("hero", ("older:aim",), ("older:follow",))
                    before = deepcopy((state, request))
                    expected = preparation.prepare_ranged_weapon_attack(request)
                    with patch.object(preparation, "prepare_ranged_weapon_attack", return_value=expected) as prepare:
                        result = preparation.prepare_ranged_weapon_attack_with_aim_history(state, request)
                    prepare.assert_called_once_with(request)
                    self.assertIs(result, expected)
                    self.assertIs(result.source_request, request)
                    modifiers = result.execution.attack.kernel_request.attack.attacker_test.dice_modifiers
                    self.assertEqual(sum(m.amount for m in modifiers if m.rule_id == AIM_FOLLOW_UP_RULE_ID),
                                     1 if aimed and not zero_aim else 0)
                    self.assertEqual((state, request), before)

    def test_consumed_source_blocks_original_and_new_preparation_ids_before_delegate(self):
        for zero_aim in (False, True):
            request = candidate(zero_aim=zero_aim)
            state = consume_lost_aim(loss_request()).state
            self.assertIn(request.aim.request_id, state.consumed_aim_source_ids)
            before = deepcopy((state, request))
            for changed in (request, replace(request, id="prepare:new", attack=replace(request.attack, id="attack:new"))):
                with self.subTest(zero=zero_aim, id=changed.id), \
                     patch.object(preparation, "prepare_ranged_weapon_attack") as prepare:
                    with self.assertRaisesRegex(ValueError, "source was already consumed"):
                        preparation.prepare_ranged_weapon_attack_with_aim_history(state, changed)
                prepare.assert_not_called()
            self.assertEqual((state, request), before)

    def test_no_aim_is_allowed_after_loss_and_history_is_not_reset(self):
        state = consume_lost_aim(loss_request()).state
        request = candidate(aimed=False)
        before = deepcopy(state)
        result = preparation.prepare_ranged_weapon_attack_with_aim_history(state, request)
        self.assertIsNone(result.aim_follow_up)
        self.assertEqual(state, before)
        self.assertIs(result.execution.weapon_state, request.weapon_state)

    def test_another_actors_history_is_rejected_even_without_aim(self):
        for aimed in (False, True):
            request = candidate(aimed=aimed)
            with self.subTest(aimed=aimed), patch.object(preparation, "prepare_ranged_weapon_attack") as prepare:
                with self.assertRaisesRegex(ValueError, "another actor"):
                    preparation.prepare_ranged_weapon_attack_with_aim_history(AimConsumptionState("other"), request)
            prepare.assert_not_called()

    def test_bad_types_are_rejected_before_delegate(self):
        for state, request in ((None, candidate()), (AimConsumptionState("hero"), None)):
            with self.subTest(state=state), patch.object(preparation, "prepare_ranged_weapon_attack") as prepare:
                with self.assertRaises(TypeError):
                    preparation.prepare_ranged_weapon_attack_with_aim_history(state, request)
            prepare.assert_not_called()

    def test_preparation_failure_keeps_history_and_inputs_unchanged(self):
        state, request = AimConsumptionState("hero"), candidate()
        before = deepcopy((state, request))
        with patch.object(preparation, "prepare_ranged_weapon_attack", side_effect=ValueError("preparation failed")) as prepare:
            with self.assertRaisesRegex(ValueError, "preparation failed"):
                preparation.prepare_ranged_weapon_attack_with_aim_history(state, request)
        prepare.assert_called_once_with(request)
        self.assertEqual((state, request), before)
