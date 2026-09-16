from __future__ import annotations

import unittest
from dataclasses import replace

from towr.domain.ranged_weapon_profiles import (
    RANGED_WEAPON_COMBAT_PROFILES,
    RangedReloadTrigger,
    RangedWeaponDamageKind,
    RangedWeaponHands,
    RangedWeaponId,
    RangedWeaponRange,
    ranged_weapon_combat_profile,
)


R = RangedWeaponRange
H = RangedWeaponHands
D = RangedWeaponDamageKind


EXPECTED_CORE = {
    RangedWeaponId.SLING: (R.MEDIUM, R.MEDIUM, D.STRENGTH, None, H.ONE_HANDED),
    RangedWeaponId.SHORTBOW: (R.SHORT, R.MEDIUM, D.FIXED, 3, H.TWO_HANDED),
    RangedWeaponId.WARBOW: (R.MEDIUM, R.LONG, D.FIXED, 3, H.TWO_HANDED),
    RangedWeaponId.LONGBOW: (R.MEDIUM, R.LONG, D.FIXED, 4, H.TWO_HANDED),
    RangedWeaponId.CROSSBOW: (R.SHORT, R.LONG, D.FIXED, 4, H.TWO_HANDED),
    RangedWeaponId.PISTOL: (R.CLOSE, R.SHORT, D.FIXED, 5, H.ONE_HANDED),
    RangedWeaponId.HANDGUN: (R.MEDIUM, R.LONG, D.FIXED, 5, H.TWO_HANDED),
    RangedWeaponId.BLUNDERBUSS: (R.SHORT, R.SHORT, D.FIXED, 4, H.TWO_HANDED),
    RangedWeaponId.HOCHLAND_LONG_RIFLE: (
        R.MEDIUM,
        R.EXTREME,
        D.FIXED,
        6,
        H.TWO_HANDED,
    ),
    RangedWeaponId.REPEATER_HANDBOW: (
        R.CLOSE,
        R.SHORT,
        D.FIXED,
        4,
        H.ONE_HANDED,
    ),
    RangedWeaponId.REPEATER_CROSSBOW: (
        R.SHORT,
        R.MEDIUM,
        D.FIXED,
        4,
        H.TWO_HANDED,
    ),
    RangedWeaponId.REPEATER_PISTOL: (
        R.CLOSE,
        R.SHORT,
        D.FIXED,
        5,
        H.ONE_HANDED,
    ),
    RangedWeaponId.REPEATER_HANDGUN: (
        R.SHORT,
        R.LONG,
        D.FIXED,
        5,
        H.TWO_HANDED,
    ),
}


class K1RangedWeaponCombatProfileTests(unittest.TestCase):
    def test_catalog_covers_all_page_95_rows_with_exact_core_values(self) -> None:
        self.assertEqual(len(RANGED_WEAPON_COMBAT_PROFILES), 13)
        self.assertEqual(
            {profile.weapon_id for profile in RANGED_WEAPON_COMBAT_PROFILES},
            set(RangedWeaponId),
        )

        for weapon_id, expected in EXPECTED_CORE.items():
            with self.subTest(weapon_id=weapon_id):
                profile = ranged_weapon_combat_profile(weapon_id)
                self.assertEqual(
                    (
                        profile.optimum_range_min,
                        profile.optimum_range_max,
                        profile.damage_kind,
                        profile.damage_value,
                        profile.hands,
                    ),
                    expected,
                )

    def test_maximum_range_is_computed_from_hands_and_exception(self) -> None:
        one_handed = {
            RangedWeaponId.SLING,
            RangedWeaponId.PISTOL,
            RangedWeaponId.REPEATER_HANDBOW,
            RangedWeaponId.REPEATER_PISTOL,
        }
        for weapon_id in one_handed:
            with self.subTest(weapon_id=weapon_id):
                profile = ranged_weapon_combat_profile(weapon_id)
                self.assertIs(profile.maximum_range, R.LONG)
                self.assertFalse(profile.has_gm_defined_maximum_range)

        blunderbuss = ranged_weapon_combat_profile(RangedWeaponId.BLUNDERBUSS)
        self.assertIs(blunderbuss.maximum_range, R.MEDIUM)
        self.assertFalse(blunderbuss.has_gm_defined_maximum_range)

        gm_defined = set(RangedWeaponId) - one_handed - {
            RangedWeaponId.BLUNDERBUSS
        }
        for weapon_id in gm_defined:
            with self.subTest(weapon_id=weapon_id):
                profile = ranged_weapon_combat_profile(weapon_id)
                self.assertIsNone(profile.maximum_range)
                self.assertTrue(profile.has_gm_defined_maximum_range)

    def test_named_numeric_traits_match_page_95(self) -> None:
        expected = {
            RangedWeaponId.SHORTBOW: (1, 0, 0),
            RangedWeaponId.CROSSBOW: (0, 1, 0),
            RangedWeaponId.BLUNDERBUSS: (2, 0, 0),
            RangedWeaponId.HOCHLAND_LONG_RIFLE: (0, 0, 1),
        }
        for weapon_id in RangedWeaponId:
            with self.subTest(weapon_id=weapon_id):
                profile = ranged_weapon_combat_profile(weapon_id)
                self.assertEqual(
                    (
                        profile.short_range_shooting_bonus_dice,
                        profile.armoured_target_damage_bonus,
                        profile.wounds_table_bonus_dice,
                    ),
                    expected.get(weapon_id, (0, 0, 0)),
                )

    def test_named_boolean_traits_match_page_95(self) -> None:
        ignores_armour = {
            RangedWeaponId.PISTOL,
            RangedWeaponId.HANDGUN,
            RangedWeaponId.HOCHLAND_LONG_RIFLE,
            RangedWeaponId.REPEATER_PISTOL,
            RangedWeaponId.REPEATER_HANDGUN,
        }
        blackpowder = ignores_armour | {RangedWeaponId.BLUNDERBUSS}
        for weapon_id in RangedWeaponId:
            with self.subTest(weapon_id=weapon_id):
                profile = ranged_weapon_combat_profile(weapon_id)
                self.assertEqual(
                    profile.ignores_armour,
                    weapon_id in ignores_armour,
                )
                self.assertEqual(
                    profile.requires_blackpowder_lore,
                    weapon_id in blackpowder,
                )
                self.assertEqual(
                    profile.requires_aim_before_attack,
                    weapon_id is RangedWeaponId.HOCHLAND_LONG_RIFLE,
                )
                self.assertEqual(
                    profile.staggers_nearby_targets_on_hit,
                    weapon_id is RangedWeaponId.BLUNDERBUSS,
                )

    def test_combat_profile_links_the_existing_reload_catalog(self) -> None:
        for weapon_id in RangedWeaponId:
            with self.subTest(weapon_id=weapon_id):
                profile = ranged_weapon_combat_profile(weapon_id)
                self.assertIs(profile.reload.weapon_id, weapon_id)

        self.assertIs(
            ranged_weapon_combat_profile(RangedWeaponId.CROSSBOW).reload.trigger,
            RangedReloadTrigger.AFTER_EVERY_SHOT,
        )
        self.assertIs(
            ranged_weapon_combat_profile(
                RangedWeaponId.REPEATER_PISTOL
            ).reload.trigger,
            RangedReloadTrigger.AFTER_OPTIONAL_BONUS,
        )

    def test_profile_rejects_invalid_range_damage_hands_and_flags(self) -> None:
        sling = ranged_weapon_combat_profile(RangedWeaponId.SLING)
        with self.assertRaisesRegex(ValueError, "ordered"):
            replace(
                sling,
                optimum_range_min=R.LONG,
                optimum_range_max=R.SHORT,
            )
        with self.assertRaisesRegex(ValueError, "Strength damage"):
            replace(sling, damage_value=2)
        with self.assertRaisesRegex(ValueError, "requires a value"):
            replace(
                ranged_weapon_combat_profile(RangedWeaponId.SHORTBOW),
                damage_value=None,
            )
        with self.assertRaisesRegex(ValueError, "always Long"):
            replace(sling, maximum_range_override=R.EXTREME)
        with self.assertRaisesRegex(ValueError, "cannot precede"):
            replace(
                ranged_weapon_combat_profile(RangedWeaponId.LONGBOW),
                maximum_range_override=R.SHORT,
            )
        with self.assertRaisesRegex(TypeError, "boolean"):
            replace(sling, requires_aim_before_attack=1)
        with self.assertRaisesRegex(TypeError, "RangedWeaponId"):
            ranged_weapon_combat_profile("sling")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
