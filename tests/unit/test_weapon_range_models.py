"""Book range limits, Strength bands and canonical shared range results."""
from dataclasses import FrozenInstanceError, replace
import unittest

from towr.domain.ranged_weapon_profiles import RangedWeaponRange as R
from towr.domain.test_models import DiceModifier
from towr.domain.weapon_catalog import WeaponGroup, WeaponKind as W, WEAPON_PROFILES
from towr.domain.weapon_range_models import (
    OUTSIDE_OPTIMUM_RANGE_RULE_ID, WeaponRangeAssessment, WeaponRangeContext,
    WeaponRangeReason as Reason, assess_weapon_attack_range,
    weapon_optimum_range, weapon_target_within_optimum,
)


def assess(kind, target=R.CLOSE, *, strength=3, **kwargs):
    return assess_weapon_attack_range(kind, WeaponRangeContext(target, strength, **kwargs))


class WeaponRangeModelsTests(unittest.TestCase):
    def assert_range(self, result, allowed, reason, modifiers=()):
        self.assertIs(result.allowed, allowed)
        self.assertIs(result.reason, reason)
        self.assertEqual(result.dice_modifiers, modifiers)

    def test_all_melee_profiles_use_printed_maximum_without_an_optimum_band(self):
        reach = {W.FOOT_SPEAR, W.CAVALRY_SPEAR, W.POLEARM, W.UNWAVERING_SPEAR}
        for profile in WEAPON_PROFILES:
            if profile.group is not WeaponGroup.MELEE:
                continue
            kind = profile.kind
            with self.subTest(kind=kind):
                self.assertIsNone(weapon_optimum_range(kind, strength=4))
                self.assertFalse(weapon_target_within_optimum(kind, R.CLOSE, strength=4))
                self.assert_range(assess(kind), True, Reason.IN_RANGE)
                self.assert_range(assess(kind, R.SHORT), kind in reach,
                    Reason.IN_RANGE if kind in reach else Reason.TARGET_BEYOND_MAXIMUM)
                self.assert_range(assess(kind, R.MEDIUM, gm_shooting_maximum=R.EXTREME),
                    False, Reason.TARGET_BEYOND_MAXIMUM)
        self.assertIs(assess(W.UNARMED).maximum_range, R.CLOSE)
        self.assert_range(assess(W.SWORD, charging=True), True, Reason.IN_RANGE)

    def test_shooting_bands_do_not_depend_on_strength(self):
        bands = {
            W.SLING: (R.MEDIUM, R.MEDIUM), W.SHORTBOW: (R.SHORT, R.MEDIUM),
            W.WARBOW: (R.MEDIUM, R.LONG), W.LONGBOW: (R.MEDIUM, R.LONG),
            W.CROSSBOW: (R.SHORT, R.LONG), W.PISTOL: (R.CLOSE, R.SHORT),
            W.HANDGUN: (R.MEDIUM, R.LONG), W.BLUNDERBUSS: (R.SHORT, R.SHORT),
            W.HOCHLAND_LONG_RIFLE: (R.MEDIUM, R.EXTREME),
            W.REPEATER_HANDBOW: (R.CLOSE, R.SHORT),
            W.REPEATER_CROSSBOW: (R.SHORT, R.MEDIUM),
            W.REPEATER_PISTOL: (R.CLOSE, R.SHORT),
            W.REPEATER_HANDGUN: (R.SHORT, R.LONG),
            W.DRAGON_BOW: (R.MEDIUM, R.EXTREME),
            W.OGRE_PISTOL: (R.CLOSE, R.MEDIUM),
        }
        for kind, band in bands.items():
            for strength in (1, 3, 4, 100):
                with self.subTest(kind=kind, strength=strength):
                    self.assertEqual(weapon_optimum_range(kind, strength=strength), band)
                    self.assertTrue(weapon_target_within_optimum(kind, band[0], strength=strength))
                    self.assertTrue(weapon_target_within_optimum(kind, band[1], strength=strength))

    def test_all_throwing_bands_extend_only_upper_end_by_one_step_at_strength_four(self):
        bands = {
            W.ROCK: (R.SHORT, R.MEDIUM, R.LONG),
            W.THROWING_SPEAR: (R.CLOSE, R.MEDIUM, R.LONG),
            W.THROWING_AXE: (R.SHORT, R.SHORT, R.MEDIUM),
            W.WEIGHTED_NET: (R.CLOSE, R.SHORT, R.MEDIUM),
            W.THROWING_KNIVES: (R.SHORT, R.SHORT, R.MEDIUM),
            W.OIL_FLASK: (R.SHORT, R.MEDIUM, R.LONG),
            W.BLASTING_CHARGE: (R.SHORT, R.MEDIUM, R.LONG),
        }
        for kind, (low, ordinary_high, strong_high) in bands.items():
            for strength, high in ((1, ordinary_high), (3, ordinary_high),
                    (4, strong_high), (100, strong_high)):
                with self.subTest(kind=kind, strength=strength):
                    self.assertEqual(weapon_optimum_range(kind, strength=strength), (low, high))
                    for target in R:
                        expected = list(R).index(low) <= list(R).index(target) <= list(R).index(high)
                        self.assertIs(weapon_target_within_optimum(kind, target,
                            strength=strength), expected)
                        self.assert_range(assess(kind, target, strength=strength), expected,
                            Reason.IN_RANGE if expected else Reason.TARGET_OUTSIDE_THROWING_OPTIMUM)
        self.assertIs(assess(W.WEIGHTED_NET, R.MEDIUM, strength=4).maximum_range, R.MEDIUM)

    def test_throwing_does_not_get_shooting_penalty_or_close_enemy_prohibition(self):
        self.assert_range(assess(W.THROWING_AXE, R.MEDIUM), False,
            Reason.TARGET_OUTSIDE_THROWING_OPTIMUM)
        self.assert_range(assess(W.OIL_FLASK), False, Reason.TARGET_OUTSIDE_THROWING_OPTIMUM)
        self.assert_range(assess(W.THROWING_AXE, R.SHORT, has_enemy_in_close_range=True),
            True, Reason.IN_RANGE)
        self.assert_range(assess(W.WEIGHTED_NET, has_enemy_in_close_range=True),
            True, Reason.IN_RANGE)

    def test_proven_throwing_charge_treats_the_attack_as_optimum(self):
        for profile in WEAPON_PROFILES:
            if profile.group is WeaponGroup.THROWING:
                with self.subTest(kind=profile.kind):
                    self.assert_range(assess(profile.kind, charging=True,
                        has_enemy_in_close_range=True), True, Reason.CHARGE_THROWING)
        self.assert_range(assess(W.THROWING_AXE), False, Reason.TARGET_OUTSIDE_THROWING_OPTIMUM)

    def test_one_handed_shooting_has_fixed_long_maximum_even_with_extra_gm_context(self):
        for kind in (W.SLING, W.PISTOL, W.REPEATER_HANDBOW, W.REPEATER_PISTOL, W.OGRE_PISTOL):
            with self.subTest(kind=kind):
                long = assess(kind, R.LONG, gm_shooting_maximum=R.EXTREME)
                self.assertIs(long.maximum_range, R.LONG)
                self.assert_range(long, True, Reason.OUTSIDE_OPTIMUM,
                    (DiceModifier(OUTSIDE_OPTIMUM_RANGE_RULE_ID, -1),))
                self.assert_range(assess(kind, R.EXTREME, gm_shooting_maximum=R.EXTREME),
                    False, Reason.TARGET_BEYOND_MAXIMUM)

    def test_two_handed_shooting_requires_an_actual_gm_maximum_even_within_optimum(self):
        kinds = (W.SHORTBOW, W.WARBOW, W.LONGBOW, W.CROSSBOW, W.HANDGUN,
            W.HOCHLAND_LONG_RIFLE, W.REPEATER_CROSSBOW, W.REPEATER_HANDGUN, W.DRAGON_BOW)
        for kind in kinds:
            with self.subTest(kind=kind):
                self.assert_range(assess(kind, R.MEDIUM), False,
                    Reason.GM_SHOOTING_MAXIMUM_REQUIRED)
                self.assertIsNone(assess(kind, R.MEDIUM).maximum_range)
                self.assert_range(assess(kind, R.MEDIUM, gm_shooting_maximum=R.LONG),
                    True, Reason.IN_RANGE)
                self.assert_range(assess(kind, R.LONG, gm_shooting_maximum=R.MEDIUM),
                    False, Reason.TARGET_BEYOND_MAXIMUM)
        self.assert_range(assess(W.HOCHLAND_LONG_RIFLE, R.EXTREME,
            gm_shooting_maximum=R.EXTREME), True, Reason.IN_RANGE)

    def test_blunderbuss_fixed_medium_override_and_short_bonus_have_separate_owners(self):
        self.assert_range(assess(W.BLUNDERBUSS, R.SHORT), True, Reason.IN_RANGE)
        medium = assess(W.BLUNDERBUSS, R.MEDIUM, gm_shooting_maximum=R.EXTREME)
        self.assertIs(medium.maximum_range, R.MEDIUM)
        self.assert_range(medium, True, Reason.OUTSIDE_OPTIMUM,
            (DiceModifier(OUTSIDE_OPTIMUM_RANGE_RULE_ID, -1),))
        self.assert_range(assess(W.BLUNDERBUSS, R.LONG, gm_shooting_maximum=R.EXTREME),
            False, Reason.TARGET_BEYOND_MAXIMUM)
        self.assert_range(assess(W.PISTOL, R.SHORT), True, Reason.IN_RANGE)

    def test_close_enemy_blocks_shooting_when_close_is_not_optimum(self):
        for kind in (W.SLING, W.SHORTBOW, W.HANDGUN, W.BLUNDERBUSS, W.DRAGON_BOW):
            with self.subTest(kind=kind):
                self.assert_range(assess(kind, R.MEDIUM, has_enemy_in_close_range=True,
                    gm_shooting_maximum=R.LONG), False, Reason.CLOSE_ENEMY_BLOCKS_SHOOTING)
                # The chosen target itself is a Close enemy, independent of the
                # summary fact about other nearby enemies.
                self.assert_range(assess(kind, gm_shooting_maximum=R.LONG),
                    False, Reason.CLOSE_ENEMY_BLOCKS_SHOOTING)
        for kind in (W.PISTOL, W.REPEATER_PISTOL, W.REPEATER_HANDBOW, W.OGRE_PISTOL):
            with self.subTest(kind=kind):
                self.assert_range(assess(kind, has_enemy_in_close_range=True), True, Reason.IN_RANGE)

    def test_no_shooting_profile_gains_permission_to_charge(self):
        for profile in WEAPON_PROFILES:
            if profile.group is WeaponGroup.SHOOTING:
                with self.subTest(kind=profile.kind):
                    self.assert_range(assess(profile.kind, R.SHORT, charging=True,
                        gm_shooting_maximum=R.EXTREME), False, Reason.SHOOTING_CHARGE_FORBIDDEN)

    def test_only_dragon_bow_explicitly_forbids_unseen_targets_in_this_owner(self):
        self.assert_range(assess(W.DRAGON_BOW, R.MEDIUM, target_visible=False,
            gm_shooting_maximum=R.LONG), False, Reason.TARGET_NOT_VISIBLE)
        for kind in (W.WARBOW, W.PISTOL, W.SWORD, W.THROWING_AXE):
            with self.subTest(kind=kind):
                self.assertTrue(assess(kind, R.SHORT if kind is not W.SWORD else R.CLOSE,
                    target_visible=False, gm_shooting_maximum=R.LONG).allowed)

    def test_dragon_bow_keeps_raw_range_penalty_without_bypassing_actual_limits(self):
        result = assess(W.DRAGON_BOW, R.SHORT, gm_shooting_maximum=R.LONG)
        self.assert_range(result, True, Reason.OUTSIDE_OPTIMUM,
            (DiceModifier(OUTSIDE_OPTIMUM_RANGE_RULE_ID, -1),))
        self.assert_range(assess(W.DRAGON_BOW, R.EXTREME, gm_shooting_maximum=R.LONG),
            False, Reason.TARGET_BEYOND_MAXIMUM)
        self.assertEqual(result.optimum_range, (R.MEDIUM, R.EXTREME))

    def test_context_and_helpers_reject_coerced_or_malformed_source_values(self):
        for strength, error in ((True, TypeError), (3.0, TypeError), (0, ValueError), (-1, ValueError)):
            with self.subTest(strength=strength):
                with self.assertRaises(error): WeaponRangeContext(R.SHORT, strength)
                with self.assertRaises(error): weapon_optimum_range(W.SWORD, strength=strength)
                with self.assertRaises(error): weapon_target_within_optimum(W.PISTOL, R.SHORT, strength=strength)
        for kwargs in ({'has_enemy_in_close_range': 1}, {'charging': 0},
                {'target_visible': None}, {'gm_shooting_maximum': 'long'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(TypeError):
                WeaponRangeContext(R.SHORT, 3, **kwargs)
        with self.assertRaises(TypeError): WeaponRangeContext('short', 3)
        with self.assertRaises(TypeError): weapon_optimum_range('pistol', strength=3)
        with self.assertRaises(TypeError): weapon_target_within_optimum(W.PISTOL, 'short', strength=3)
        with self.assertRaises(TypeError): assess_weapon_attack_range(W.PISTOL, {'target_range': R.SHORT})
        context = WeaponRangeContext(R.SHORT, 3)
        object.__setattr__(context, 'charging', 1)
        with self.assertRaises(TypeError): assess_weapon_attack_range(W.PISTOL, context)

    def test_assessment_is_frozen_and_rederives_permission_reason_and_modifiers(self):
        result = assess(W.PISTOL, R.LONG)
        self.assertIs(type(result), WeaponRangeAssessment)
        self.assertIs(result.kind, W.PISTOL)
        with self.assertRaises(FrozenInstanceError): result.allowed = False
        for kwargs in ({'allowed': False}, {'reason': Reason.IN_RANGE}, {'dice_modifiers': ()},
                {'dice_modifiers': result.dice_modifiers * 2}, {'kind': W.SWORD},
                {'context': WeaponRangeContext(R.SHORT, 3)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError): replace(result, **kwargs)
        for kwargs in ({'allowed': 1}, {'reason': 'outside_optimum'},
                {'kind': 'pistol'}, {'dice_modifiers': list(result.dice_modifiers)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(TypeError): replace(result, **kwargs)
        self.assertIs(result.context.target_range, R.LONG)
        self.assertEqual(result.dice_modifiers, (DiceModifier(OUTSIDE_OPTIMUM_RANGE_RULE_ID, -1),))


if __name__ == '__main__':
    unittest.main()
