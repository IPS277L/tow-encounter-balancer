from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from tests.unit.test_k1_attack_action_execution import (
    kernel_request,
    reserve_action,
    started_turn,
)
from tests.unit.test_k1_reload_resolution import reload_request
from tests.unit.test_k1_reloadable_ranged_attack_resolution import (
    attack_request,
)
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.reload_models import (
    FreeReloadWeaponState,
    ReloadableWeaponState,
    create_initial_ranged_weapon_reload_state,
)
from towr.domain.ranged_weapon_profiles import (
    RANGED_WEAPON_RELOAD_PROFILES,
    REPEATER_SHOOTING_BONUS_RULE_ID,
    RangedReloadTrigger,
    RangedWeaponId,
    ranged_weapon_reload_profile,
)
from towr.domain.test_models import DiceModifier
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind
from towr.rules.ranged_weapon_attack_resolution import (
    execute_reloadable_ranged_attack,
)


EXPECTED_PROFILES = {
    RangedWeaponId.SLING: (RangedReloadTrigger.FREE_WITH_ATTACK, None, 0),
    RangedWeaponId.SHORTBOW: (RangedReloadTrigger.FREE_WITH_ATTACK, None, 0),
    RangedWeaponId.WARBOW: (RangedReloadTrigger.FREE_WITH_ATTACK, None, 0),
    RangedWeaponId.LONGBOW: (RangedReloadTrigger.FREE_WITH_ATTACK, None, 0),
    RangedWeaponId.CROSSBOW: (RangedReloadTrigger.AFTER_EVERY_SHOT, 2, 0),
    RangedWeaponId.PISTOL: (RangedReloadTrigger.AFTER_EVERY_SHOT, 3, 0),
    RangedWeaponId.HANDGUN: (RangedReloadTrigger.AFTER_EVERY_SHOT, 3, 0),
    RangedWeaponId.BLUNDERBUSS: (RangedReloadTrigger.AFTER_EVERY_SHOT, 3, 0),
    RangedWeaponId.HOCHLAND_LONG_RIFLE: (
        RangedReloadTrigger.AFTER_EVERY_SHOT,
        4,
        0,
    ),
    RangedWeaponId.REPEATER_HANDBOW: (
        RangedReloadTrigger.AFTER_OPTIONAL_BONUS,
        3,
        1,
    ),
    RangedWeaponId.REPEATER_CROSSBOW: (
        RangedReloadTrigger.AFTER_OPTIONAL_BONUS,
        3,
        1,
    ),
    RangedWeaponId.REPEATER_PISTOL: (
        RangedReloadTrigger.AFTER_OPTIONAL_BONUS,
        3,
        2,
    ),
    RangedWeaponId.REPEATER_HANDGUN: (
        RangedReloadTrigger.AFTER_OPTIONAL_BONUS,
        5,
        3,
    ),
}


def attack_source_with_modifier(
    modifier: DiceModifier,
    *,
    request_id: str,
    kernel_id: str,
) -> AttackActionExecutionRequest:
    round_state = reserve_action(
        started_turn(),
        CombatActionDeclaration(CombatActionKind.ATTACK),
    )
    source_kernel = kernel_request(request_id=kernel_id)
    attacker_test = replace(
        source_kernel.attack.attacker_test,
        dice_modifiers=(modifier,),
    )
    prepared_kernel = replace(
        source_kernel,
        attack=replace(source_kernel.attack, attacker_test=attacker_test),
    )
    return AttackActionExecutionRequest(
        id=request_id,
        state=round_state,
        actor_id="hero",
        target_id="enemy",
        slot_index=1,
        kernel_request=prepared_kernel,
    )


class K1RangedWeaponReloadProfileTests(unittest.TestCase):
    def test_catalog_covers_every_page_95_weapon_exactly(self) -> None:
        self.assertEqual(len(RANGED_WEAPON_RELOAD_PROFILES), 13)
        self.assertEqual(
            {profile.weapon_id for profile in RANGED_WEAPON_RELOAD_PROFILES},
            set(RangedWeaponId),
        )
        for weapon_id, expected in EXPECTED_PROFILES.items():
            with self.subTest(weapon_id=weapon_id):
                profile = ranged_weapon_reload_profile(weapon_id)
                self.assertEqual(
                    (
                        profile.trigger,
                        profile.required_successes,
                        profile.optional_shooting_bonus_dice,
                    ),
                    expected,
                )

    def test_factory_separates_free_and_exacting_reload_states(self) -> None:
        for weapon_id, (trigger, target, _) in EXPECTED_PROFILES.items():
            with self.subTest(weapon_id=weapon_id):
                state = create_initial_ranged_weapon_reload_state(
                    f"weapon:{weapon_id.value}:1",
                    weapon_id,
                )
                if trigger is RangedReloadTrigger.FREE_WITH_ATTACK:
                    self.assertIsInstance(state, FreeReloadWeaponState)
                else:
                    self.assertIsInstance(state, ReloadableWeaponState)
                    self.assertEqual(state.required_successes, target)
                    self.assertTrue(state.loaded)
                    self.assertIsNone(state.exacting)

    def test_reload_state_rejects_target_or_profile_forgery(self) -> None:
        state = create_initial_ranged_weapon_reload_state(
            "weapon:crossbow:1",
            RangedWeaponId.CROSSBOW,
        )
        assert isinstance(state, ReloadableWeaponState)

        with self.assertRaisesRegex(ValueError, "weapon profile"):
            replace(state, required_successes=3)
        with self.assertRaisesRegex(ValueError, "reloads freely"):
            replace(state, weapon_id=RangedWeaponId.LONGBOW)

    def test_repeater_without_bonus_fires_without_opening_reload(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "weapon:repeater-pistol:1",
            RangedWeaponId.REPEATER_PISTOL,
        )
        assert isinstance(weapon, ReloadableWeaponState)
        request = attack_request(
            weapon,
            request_id="repeater-shot:ordinary",
            attack_id="execute:repeater-shot:ordinary",
            kernel_id="kernel:repeater-shot:ordinary",
            next_cycle_id=None,
        )

        result = execute_reloadable_ranged_attack(
            request,
            SequenceRandom([10, 10, 10]),
        )

        self.assertIs(result.weapon_state, weapon)
        self.assertTrue(result.weapon_state.loaded)
        self.assertEqual(result.weapon_state.reload_cycle_ids, ())

    def test_repeater_bonus_is_exact_and_opens_book_reload_target(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "weapon:repeater-pistol:1",
            RangedWeaponId.REPEATER_PISTOL,
        )
        assert isinstance(weapon, ReloadableWeaponState)
        profile = ranged_weapon_reload_profile(weapon.weapon_id)
        source = attack_source_with_modifier(
            profile.optional_bonus_modifier(),
            request_id="execute:repeater-shot:bonus",
            kernel_id="kernel:repeater-shot:bonus",
        )
        request = attack_request(
            weapon,
            request_id="repeater-shot:bonus",
            source=source,
            next_cycle_id="weapon:repeater-pistol:1:reload:1",
            uses_optional_reload_bonus=True,
        )

        result = execute_reloadable_ranged_attack(
            request,
            SequenceRandom([10, 10, 10, 10, 10]),
        )

        self.assertFalse(result.weapon_state.loaded)
        self.assertEqual(result.weapon_state.required_successes, 3)
        self.assertEqual(
            result.weapon_state.exacting.required_successes,
            3,
        )

    def test_repeater_bonus_flag_modifier_and_cycle_must_agree(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "weapon:repeater-handgun:1",
            RangedWeaponId.REPEATER_HANDGUN,
        )
        assert isinstance(weapon, ReloadableWeaponState)
        with self.assertRaisesRegex(ValueError, "must match"):
            attack_request(
                weapon,
                request_id="repeater-shot:missing-modifier",
                attack_id="execute:repeater-shot:missing-modifier",
                kernel_id="kernel:repeater-shot:missing-modifier",
                next_cycle_id="weapon:repeater-handgun:1:reload:1",
                uses_optional_reload_bonus=True,
            )

        source = attack_source_with_modifier(
            DiceModifier(REPEATER_SHOOTING_BONUS_RULE_ID, 3),
            request_id="execute:repeater-shot:unannounced",
            kernel_id="kernel:repeater-shot:unannounced",
        )
        with self.assertRaisesRegex(ValueError, "explicit bonus use"):
            attack_request(
                weapon,
                request_id="repeater-shot:unannounced",
                source=source,
                next_cycle_id=None,
            )

    def test_ordinary_reload_weapon_rejects_repeater_bonus(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "weapon:pistol:1",
            RangedWeaponId.PISTOL,
        )
        assert isinstance(weapon, ReloadableWeaponState)
        with self.assertRaisesRegex(ValueError, "no Repeater bonus"):
            attack_request(
                weapon,
                request_id="pistol-shot:invalid-bonus",
                attack_id="execute:pistol-shot:invalid-bonus",
                kernel_id="kernel:pistol-shot:invalid-bonus",
                next_cycle_id="weapon:pistol:1:reload:1",
                uses_optional_reload_bonus=True,
            )

    def test_free_reload_state_cannot_enter_exacting_consumers(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "weapon:longbow:1",
            RangedWeaponId.LONGBOW,
        )
        assert isinstance(weapon, FreeReloadWeaponState)

        with self.assertRaisesRegex(TypeError, "ReloadableWeaponState"):
            reload_request(weapon)
        with self.assertRaisesRegex(TypeError, "ReloadableWeaponState"):
            attack_request(weapon)


if __name__ == "__main__":
    unittest.main()
