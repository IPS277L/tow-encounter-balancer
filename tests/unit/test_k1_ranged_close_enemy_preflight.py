from __future__ import annotations

import unittest
from dataclasses import fields, replace
from unittest.mock import Mock

from tests.helpers import SequenceRandom
from tests.unit.test_k1_ranged_weapon_attack_preparation import (
    aim_and_attack,
    preparation_request,
)
from towr.domain.attack_models import MissConsequence
from towr.domain.prepared_ranged_weapon_attack_models import (
    PreparedRangedWeaponAttackExecutionRequest,
)
from towr.domain.ranged_weapon_attack_preparation_models import (
    CLOSE_ENEMY_RANGED_RESTRICTION_RULE_ID,
    RangedWeaponAttackPreparationRequest,
)
from towr.domain.ranged_weapon_profiles import (
    RangedReloadTrigger,
    RangedWeaponId,
    RangedWeaponRange,
    ranged_weapon_reload_profile,
)
from towr.rules.prepared_ranged_weapon_attack_resolution import (
    execute_prepared_ranged_weapon_attack,
)
from towr.rules.ranged_weapon_attack_preparation import (
    prepare_ranged_weapon_attack,
)


CLOSE_CAPABLE_WEAPONS = {
    RangedWeaponId.PISTOL,
    RangedWeaponId.REPEATER_PISTOL,
    RangedWeaponId.REPEATER_HANDBOW,
}


def next_cycle(weapon: RangedWeaponId) -> str | None:
    if ranged_weapon_reload_profile(weapon).trigger is RangedReloadTrigger.AFTER_EVERY_SHOT:
        return f"weapon:{weapon.value}:hero:1:reload:1"
    return None


class K1RangedCloseEnemyPreflightTests(unittest.TestCase):
    def test_close_enemy_fact_is_required_and_strictly_boolean(self) -> None:
        request = preparation_request(RangedWeaponId.LONGBOW)
        kwargs = {
            field.name: getattr(request, field.name)
            for field in fields(request)
            if field.name != "has_enemy_in_close_range"
        }
        with self.assertRaisesRegex(TypeError, "has_enemy_in_close_range"):
            RangedWeaponAttackPreparationRequest(**kwargs)
        for invalid in (None, 0, 1, "false", (), []):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(TypeError, "must be a boolean"):
                    replace(request, has_enemy_in_close_range=invalid)

    def test_all_profiles_check_nearby_enemy_independently_of_distant_target(self) -> None:
        aim, attack = aim_and_attack()
        for weapon in RangedWeaponId:
            with self.subTest(weapon=weapon):
                request = preparation_request(
                    weapon, attack=attack, aim=aim, lore=True,
                    target_range=RangedWeaponRange.MEDIUM,
                    next_cycle=next_cycle(weapon),
                    has_close_enemy=False,
                )
                clear = prepare_ranged_weapon_attack(request)
                self.assertIn(CLOSE_ENEMY_RANGED_RESTRICTION_RULE_ID, clear.applied_rule_ids)
                if weapon in CLOSE_CAPABLE_WEAPONS:
                    nearby = prepare_ranged_weapon_attack(
                        replace(request, has_enemy_in_close_range=True)
                    )
                    self.assertEqual(nearby.execution, clear.execution)
                    self.assertTrue(nearby.source_request.has_enemy_in_close_range)
                else:
                    with self.assertRaisesRegex(ValueError, "enemy in Close Range"):
                        replace(request, has_enemy_in_close_range=True)

    def test_aim_and_gm_range_approval_do_not_bypass_close_enemy(self) -> None:
        aim, attack = aim_and_attack()
        request = preparation_request(
            RangedWeaponId.LONGBOW, attack=attack, aim=aim,
            target_range=RangedWeaponRange.EXTREME, range_approved=True,
        )
        prepare_ranged_weapon_attack(request)
        rng = Mock()
        with self.assertRaisesRegex(ValueError, "enemy in Close Range"):
            execute_prepared_ranged_weapon_attack(
                PreparedRangedWeaponAttackExecutionRequest(
                    id="execute:blocked",
                    preparation=prepare_ranged_weapon_attack(
                        replace(request, has_enemy_in_close_range=True)
                    ),
                ),
                rng,
            )
        rng.randint.assert_not_called()
        self.assertFalse(attack.state.active_turn.action_slots[-1].executed)

    def test_close_capable_weapons_keep_actual_target_range_on_execution(self) -> None:
        for weapon in sorted(CLOSE_CAPABLE_WEAPONS, key=lambda value: value.value):
            for target_range in (RangedWeaponRange.CLOSE, RangedWeaponRange.MEDIUM):
                with self.subTest(weapon=weapon, target_range=target_range):
                    preparation = prepare_ranged_weapon_attack(preparation_request(
                        weapon, target_range=target_range, lore=True,
                        has_close_enemy=True, next_cycle=next_cycle(weapon),
                    ))
                    is_close = target_range is RangedWeaponRange.CLOSE
                    self.assertEqual(
                        preparation.execution.attack.kernel_request.attack.is_close_range,
                        is_close,
                    )
                    dice = 3 if is_close else 2  # Outside Optimum penalty is independent.
                    rng = SequenceRandom([10] * dice + [7])
                    result = execute_prepared_ranged_weapon_attack(
                        PreparedRangedWeaponAttackExecutionRequest(
                            id="execute:close-capable", preparation=preparation,
                        ), rng,
                    )
                    self.assertEqual(rng.randint(1, 10), 7)
                    self.assertEqual(
                        result.ranged_attack.attack.resolution.attack.miss_consequence,
                        MissConsequence.STAGGER_ATTACKER if is_close else MissConsequence.NONE,
                    )
                    self.assertTrue(result.ranged_attack.attack.slot.executed)
                    self.assertEqual(
                        result.ranged_attack.weapon_state.loaded,
                        weapon is not RangedWeaponId.PISTOL,
                    )
                    self.assertIn(CLOSE_ENEMY_RANGED_RESTRICTION_RULE_ID, result.applied_rule_ids)

    def test_negative_fact_does_not_override_selected_target_close_restriction(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot attack at Close"):
            preparation_request(
                RangedWeaponId.LONGBOW,
                target_range=RangedWeaponRange.CLOSE,
                has_close_enemy=False,
            )

    def test_allowed_aimed_shot_preserves_close_enemy_fact_and_consumes_aim(self) -> None:
        aim, attack = aim_and_attack()
        preparation = prepare_ranged_weapon_attack(preparation_request(
            RangedWeaponId.REPEATER_HANDBOW,
            attack=attack, aim=aim, has_close_enemy=True,
            target_range=RangedWeaponRange.MEDIUM,
        ))
        rng = SequenceRandom([10, 10, 10, 7])
        result = execute_prepared_ranged_weapon_attack(
            PreparedRangedWeaponAttackExecutionRequest(
                id="execute:aim-near-enemy", preparation=preparation,
                consumed_aim_follow_up_ids=("aim:older",),
            ), rng,
        )
        self.assertEqual(rng.randint(1, 10), 7)
        self.assertTrue(
            result.source_request.preparation.source_request.has_enemy_in_close_range
        )
        self.assertEqual(
            result.consumed_aim_follow_up_ids,
            ("aim:older", preparation.aim_follow_up.request_id),
        )
        self.assertIn(CLOSE_ENEMY_RANGED_RESTRICTION_RULE_ID, result.applied_rule_ids)

    def test_preparation_trace_cannot_omit_close_enemy_check(self) -> None:
        for has_enemy in (False, True):
            with self.subTest(has_enemy=has_enemy):
                result = prepare_ranged_weapon_attack(preparation_request(
                    RangedWeaponId.REPEATER_HANDBOW,
                    target_range=RangedWeaponRange.SHORT,
                    has_close_enemy=has_enemy,
                ))
                with self.assertRaisesRegex(ValueError, "trace is inconsistent"):
                    replace(result, applied_rule_ids=tuple(
                        rule for rule in result.applied_rule_ids
                        if rule != CLOSE_ENEMY_RANGED_RESTRICTION_RULE_ID
                    ))


if __name__ == "__main__":
    unittest.main()
