from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import Mock

from towr.domain.armour_models import (
    BARDING_AGILITY_RULE_ID,
    FULL_PLATE_ARMOUR_AGILITY_RULE_ID, FULL_PLATE_ARMOUR_BURDEN_RULE_ID,
    HEAVY_ARMOUR_AGILITY_RULE_ID, HEAVY_ARMOUR_BURDEN_RULE_ID,
    HELM_OF_HUNT_GLORIOUS_RULE_ID, ITHILMAR_ENVIRONMENT_RULE_ID,
    ArmourLoadout, BodyArmour, HelmetKind, ShieldKind,
    active_agilulf, armour_allows_near_miss, armour_burden_sources,
    armour_casting_grim, armour_is_worn, armour_quality_modifiers,
    armour_test_modifiers, body_resilience_bonus, helmet_resilience_bonus,
    protects_against_mundane_armour_effects,
)
from towr.domain.test_models import DiceModifier, QualityModifier, Skill, TestProfile, TestQuality, TestRequest
from towr.rules.test_resolution import roll_test_initial


def loadout(body, **kwargs):
    return ArmourLoadout((body,), body, **kwargs)


class ArmourSourcesTest(unittest.TestCase):
    def test_each_book_body_has_its_actual_bonus(self):
        expected = {BodyArmour.LIGHT: 1, BodyArmour.HEAVY: 2, BodyArmour.FULL_PLATE: 3,
            BodyArmour.AGILULF: 2, BodyArmour.METEORIC_IRON: 3, BodyArmour.ITHILMAR: 3}
        for item, bonus in expected.items():
            with self.subTest(item=item):
                self.assertEqual(body_resilience_bonus(loadout(item)), bonus)
        self.assertEqual(body_resilience_bonus(ArmourLoadout()), 0)

    def test_layering_uses_chosen_benefits_instead_of_adding_suits(self):
        source = ArmourLoadout((BodyArmour.HEAVY, BodyArmour.METEORIC_IRON), BodyArmour.METEORIC_IRON)
        self.assertEqual(body_resilience_bonus(source), 3)
        self.assertEqual(body_resilience_bonus(replace(source, benefit=BodyArmour.HEAVY)), 2)
        self.assertTrue(protects_against_mundane_armour_effects(source))
        self.assertFalse(protects_against_mundane_armour_effects(replace(source, benefit=BodyArmour.HEAVY)))

    def test_helmet_hunt_stacks_but_ordinary_helmet_has_no_invented_bonus(self):
        body = loadout(BodyArmour.FULL_PLATE)
        self.assertEqual(helmet_resilience_bonus(replace(body, helmet=HelmetKind.HELMET)), 0)
        self.assertEqual(helmet_resilience_bonus(replace(body, helmet=HelmetKind.HUNT)), 1)
        self.assertEqual(body_resilience_bonus(replace(body, helmet=HelmetKind.HUNT)), 3)

    def test_worn_armour_is_distinct_from_shield_and_barding(self):
        for source in (ArmourLoadout(), ArmourLoadout(shield=ShieldKind.SHIELD), ArmourLoadout(barding=True)):
            self.assertFalse(armour_is_worn(source))
        self.assertTrue(armour_is_worn(ArmourLoadout(helmet=HelmetKind.HELMET)))
        self.assertTrue(armour_is_worn(loadout(BodyArmour.LIGHT)))

    def test_exact_types_unique_pieces_and_real_benefit_are_required(self):
        invalid = (
            dict(body=[BodyArmour.LIGHT], benefit=BodyArmour.LIGHT),
            dict(body=('light_armour',), benefit=BodyArmour.LIGHT),
            dict(body=(BodyArmour.LIGHT,), benefit='light_armour'),
            dict(helmet='helmet'), dict(shield='shield'), dict(barding=1),
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(TypeError):
                ArmourLoadout(**values)
        for values in (dict(body=(BodyArmour.LIGHT,)), dict(benefit=BodyArmour.LIGHT),
                dict(body=(BodyArmour.LIGHT,), benefit=BodyArmour.HEAVY),
                dict(body=(BodyArmour.LIGHT, BodyArmour.LIGHT), benefit=BodyArmour.LIGHT),
                dict(body=(BodyArmour.LIGHT, BodyArmour.HEAVY), benefit=BodyArmour.LIGHT),
                dict(body=(BodyArmour.AGILULF, BodyArmour.ITHILMAR), benefit=BodyArmour.ITHILMAR)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                ArmourLoadout(**values)

    def test_source_is_immutable_and_cached_malformed_sources_are_readmitted(self):
        source = loadout(BodyArmour.LIGHT)
        with self.assertRaises(FrozenInstanceError):
            source.benefit = None
        object.__setattr__(source, 'benefit', BodyArmour.HEAVY)
        with self.assertRaises(ValueError):
            body_resilience_bonus(source)


class ArmourPenaltiesTest(unittest.TestCase):
    def test_book_strength_boundaries_and_inactive_layer_burden(self):
        for item, required, rule in ((BodyArmour.HEAVY, 3, HEAVY_ARMOUR_BURDEN_RULE_ID),
                (BodyArmour.FULL_PLATE, 4, FULL_PLATE_ARMOUR_BURDEN_RULE_ID)):
            source = ArmourLoadout((item, BodyArmour.ITHILMAR), BodyArmour.ITHILMAR)
            with self.subTest(item=item):
                self.assertEqual(armour_burden_sources(source, required-1), (rule,))
                self.assertEqual(armour_burden_sources(source, required), ())
                self.assertEqual(armour_burden_sources(source, required+1), ())
        self.assertEqual(armour_burden_sources(loadout(BodyArmour.METEORIC_IRON), 1), ())

    def test_only_agility_skills_receive_penalties(self):
        source = loadout(BodyArmour.HEAVY, barding=True)
        for skill in Skill:
            with self.subTest(skill=skill):
                expected = (DiceModifier(HEAVY_ARMOUR_AGILITY_RULE_ID, -1),
                    DiceModifier(BARDING_AGILITY_RULE_ID, -1)) if skill in (Skill.ATHLETICS, Skill.STEALTH) else ()
                self.assertEqual(armour_test_modifiers(source, skill, mounted=True), expected)

    def test_independent_mount_exceptions_do_not_excuse_other_penalties(self):
        heavy = loadout(BodyArmour.HEAVY, barding=True)
        full = loadout(BodyArmour.FULL_PLATE, barding=True)
        self.assertEqual(armour_test_modifiers(heavy, Skill.ATHLETICS, mounted=True, ignore_heavy=True),
            (DiceModifier(BARDING_AGILITY_RULE_ID, -1),))
        self.assertEqual(armour_test_modifiers(full, Skill.ATHLETICS, mounted=True, ignore_heavy=True, ignore_barding=True),
            (DiceModifier(FULL_PLATE_ARMOUR_AGILITY_RULE_ID, -1),))
        self.assertEqual(armour_test_modifiers(full, Skill.ATHLETICS, mounted=True, ignore_full_plate=True),
            (DiceModifier(BARDING_AGILITY_RULE_ID, -1),))
        self.assertEqual(armour_test_modifiers(full, Skill.ATHLETICS, mounted=True, ignore_full_plate=True, ignore_barding=True), ())

    def test_dismounted_rider_has_no_barding_penalty_but_keeps_body_penalty(self):
        self.assertEqual(armour_test_modifiers(loadout(BodyArmour.FULL_PLATE, barding=True), Skill.ATHLETICS),
            (DiceModifier(FULL_PLATE_ARMOUR_AGILITY_RULE_ID, -1),))

    def test_penalty_retains_characteristic_cap_and_one_die_fallback(self):
        modifiers = armour_test_modifiers(loadout(BodyArmour.HEAVY, barding=True), Skill.ATHLETICS, mounted=True)
        request = TestRequest('armour-test', TestProfile(1, 6), modifiers)
        rng = Mock()
        rng.randint.return_value = 2
        prepared = roll_test_initial(request, rng)
        rng.randint.assert_called_once_with(1, 10)
        self.assertEqual(request.profile.characteristic, 1)
        self.assertEqual(request.profile.maximum_dice, 2)
        self.assertEqual(prepared.pool_cap, 2)
        self.assertEqual(prepared.rolled_dice, 1)
        self.assertEqual(prepared.threshold, 1)
        self.assertTrue(prepared.minimum_die_rule_applied)

    def test_environmental_bonus_belongs_only_to_active_mantle_and_real_context(self):
        source = loadout(BodyArmour.ITHILMAR)
        self.assertEqual(armour_test_modifiers(source, Skill.ENDURANCE), ())
        self.assertEqual(armour_test_modifiers(source, Skill.ENDURANCE, environmental=True),
            (DiceModifier(ITHILMAR_ENVIRONMENT_RULE_ID, 1),))
        source = ArmourLoadout((BodyArmour.HEAVY, BodyArmour.ITHILMAR), BodyArmour.HEAVY)
        self.assertEqual(armour_test_modifiers(source, Skill.ENDURANCE, environmental=True), ())
        source = replace(source, benefit=BodyArmour.ITHILMAR)
        self.assertEqual(armour_test_modifiers(source, Skill.ATHLETICS, environmental=True),
            (DiceModifier(HEAVY_ARMOUR_AGILITY_RULE_ID, -1), DiceModifier(ITHILMAR_ENVIRONMENT_RULE_ID, 1)))

    def test_contexts_and_strength_do_not_accept_truthy_or_coerced_values(self):
        source = ArmourLoadout()
        for name in ('ignore_heavy', 'ignore_full_plate', 'ignore_barding', 'mounted', 'environmental'):
            with self.subTest(name=name), self.assertRaises(TypeError):
                armour_test_modifiers(source, Skill.ATHLETICS, **{name: 1})
        with self.assertRaises(TypeError):
            armour_test_modifiers(source, 'athletics')
        for strength in (True, 0, -1, 3.0, '3'):
            with self.subTest(strength=strength), self.assertRaises(ValueError):
                armour_burden_sources(source, strength)


class MagicArmourBenefitsTest(unittest.TestCase):
    def test_ithilmar_excuses_itself_but_not_other_armour_or_actual_shield(self):
        mantle = loadout(BodyArmour.ITHILMAR, shield=ShieldKind.SHIELD)
        self.assertFalse(armour_casting_grim(mantle, working_shield=False))
        self.assertTrue(armour_casting_grim(mantle, working_shield=True))
        self.assertTrue(armour_casting_grim(replace(mantle, helmet=HelmetKind.HELMET), working_shield=False))
        layered = ArmourLoadout((BodyArmour.HEAVY, BodyArmour.ITHILMAR), BodyArmour.ITHILMAR)
        self.assertTrue(armour_casting_grim(layered, working_shield=False))
        self.assertFalse(armour_casting_grim(ArmourLoadout(barding=True), working_shield=False))
        with self.assertRaises(TypeError):
            armour_casting_grim(mantle, working_shield=1)

    def test_agilulf_fixed_ratings_belong_only_to_active_benefit(self):
        self.assertTrue(active_agilulf(loadout(BodyArmour.AGILULF)))
        self.assertFalse(active_agilulf(ArmourLoadout((BodyArmour.LIGHT, BodyArmour.AGILULF), BodyArmour.LIGHT)))

    def test_hunt_helm_grants_one_glorious_source_only_in_its_contexts(self):
        source = loadout(BodyArmour.FULL_PLATE, helmet=HelmetKind.HUNT)
        expected = (QualityModifier(HELM_OF_HUNT_GLORIOUS_RULE_ID, TestQuality.GLORIOUS),)
        self.assertEqual(armour_quality_modifiers(source), ())
        self.assertEqual(armour_quality_modifiers(source, charge_attack=True), expected)
        self.assertEqual(armour_quality_modifiers(source, tracking_or_pursuit=True), expected)
        self.assertEqual(armour_quality_modifiers(source, charge_attack=True, tracking_or_pursuit=True), expected)
        self.assertEqual(armour_quality_modifiers(replace(source, helmet=HelmetKind.HELMET), charge_attack=True), ())
        with self.assertRaises(TypeError):
            armour_quality_modifiers(source, charge_attack=1)

    def test_near_miss_restriction_does_not_depend_on_body_selection(self):
        self.assertFalse(armour_allows_near_miss(loadout(BodyArmour.LIGHT, helmet=HelmetKind.HUNT)))
        self.assertTrue(armour_allows_near_miss(loadout(BodyArmour.LIGHT, helmet=HelmetKind.HELMET)))
        self.assertTrue(armour_allows_near_miss(ArmourLoadout()))


if __name__ == '__main__':
    unittest.main()
