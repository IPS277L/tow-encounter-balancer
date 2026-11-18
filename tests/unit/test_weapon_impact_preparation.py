from dataclasses import replace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.weapon_fixtures import weapon_use
from towr.domain.attack_models import (
    AttackRequest, ConditionImpactSpec, DamageImpactSpec, HazardImpactSpec, ResilienceProfile,
)
from towr.domain.condition_models import Condition, ConditionState, StaggerChoice
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.resolution_models import HazardExposureRequest, KernelAttackRequest, TargetInjuryPolicy
from towr.domain.test_models import Skill, TestProfile, TestRequest
from towr.domain.weapon_catalog import WeaponKind as W
from towr.domain.weapon_impact_preparation import prepare_weapon_impact
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.test_resolution import RerollAllFailures


class SufferWound(RerollAllFailures):
    def choose_repeated_stagger(self, **kwargs):
        return StaggerChoice.SUFFER_WOUND


def attack(prepared, conditions=ConditionState()):
    request = AttackRequest('attack', TestRequest('attack:test', TestProfile(2, 5)),
        None, prepared.impact_spec, True, False, secondary_effects=prepared.secondary_effects)
    return KernelAttackRequest('kernel', 'target', request, TargetInjuryPolicy.MINION,
        ProfileInjuryState(0, 1, conditions), False, False,
        wound_dice_modifiers=prepared.wound_dice_modifiers, physical_attack=True)


class WeaponImpactPreparationTests(unittest.TestCase):
    def test_special_impacts_do_not_manufacture_damage_even_against_defenceless(self):
        for kind, condition in ((W.UNARMED, Condition.STAGGERED), (W.ROCK, Condition.STAGGERED),
                (W.WEIGHTED_NET, Condition.BURDENED), (W.OIL_FLASK, Condition.ABLAZE)):
            with self.subTest(kind=kind):
                prepared = prepare_weapon_impact(weapon_use(kind), 4, ResilienceProfile(3))
                self.assertIs(type(prepared.impact_spec), ConditionImpactSpec)
                self.assertIsNone(prepared.damage.damage)
                rng = ScriptedD10([1, 10])
                result = resolve_kernel_attack(attack(prepared,
                    ConditionState(frozenset((Condition.DEFENCELESS,)))), rng, decisions=SufferWound())
                rng.assert_exhausted()
                self.assertEqual(result.target_state.wounds, 0)
                self.assertTrue(result.target_state.conditions.has(condition))
                self.assertIsNone(result.character_wound)
                self.assertIsNone(result.profile_wound)

    def test_unarmed_and_rock_repeated_stagger_still_cause_actual_wound(self):
        for kind in (W.UNARMED, W.ROCK):
            with self.subTest(kind=kind):
                prepared = prepare_weapon_impact(weapon_use(kind), 4, ResilienceProfile(3))
                rng = ScriptedD10([1, 10])
                result = resolve_kernel_attack(attack(prepared,
                    ConditionState(frozenset((Condition.STAGGERED,)))), rng, decisions=SufferWound())
                rng.assert_exhausted()
                self.assertEqual(result.target_state.wounds, 1)
                self.assertIsNotNone(result.profile_wound)
                self.assertTrue(result.target_state.defeated)

    def test_knuckledusters_keep_normal_damage_and_defenceless_wound(self):
        prepared = prepare_weapon_impact(weapon_use(W.KNUCKLEDUSTERS), 1, ResilienceProfile(100))
        self.assertIs(type(prepared.impact_spec), DamageImpactSpec)
        self.assertEqual(prepared.impact_spec.damage.base, 0)
        rng = ScriptedD10([1, 10])
        result = resolve_kernel_attack(attack(prepared,
            ConditionState(frozenset((Condition.DEFENCELESS,)))), rng, decisions=SufferWound())
        rng.assert_exhausted()
        self.assertEqual(result.target_state.wounds, 1)

    def test_blast_keeps_endurance_hazard_and_explicit_full_zone_obligation(self):
        prepared = prepare_weapon_impact(weapon_use(W.BLASTING_CHARGE), 3, ResilienceProfile(3))
        self.assertIs(type(prepared.impact_spec), HazardImpactSpec)
        self.assertEqual((prepared.impact_spec.rating, prepared.impact_spec.avoidance_skill), (3, Skill.ENDURANCE))
        self.assertTrue(prepared.requires_blast_zone_targets_even_on_miss)
        self.assertFalse(prepared.requires_oil_nearby_targets)
        rng = ScriptedD10([1, 10])
        result = resolve_kernel_attack(attack(prepared), rng, decisions=SufferWound())
        rng.assert_exhausted()
        self.assertEqual(result.target_state.wounds, 0)
        self.assertTrue(any(type(request) is HazardExposureRequest for request in result.follow_ups))

    def test_oil_explicitly_requires_nearby_ablaze_without_damage(self):
        prepared = prepare_weapon_impact(weapon_use(W.OIL_FLASK), 3, ResilienceProfile(3))
        self.assertTrue(prepared.requires_oil_nearby_targets)
        self.assertFalse(prepared.requires_blast_zone_targets_even_on_miss)
        self.assertEqual(prepared.secondary_effects, ())

    def test_scarab_secondary_condition_executes_after_primary_without_summing_damage(self):
        use = weapon_use(W.KNUCKLEDUSTERS, offhand=W.SCARAB_KNIFE)
        prepared = prepare_weapon_impact(use, 3, ResilienceProfile(100))
        self.assertEqual(prepared.impact_spec.damage.base, 2)
        self.assertFalse(prepared.impact_spec.magical_source)
        self.assertEqual(prepared.hit_condition_sources[0].item_id, use.contributor_item_ids[0])
        rng = ScriptedD10([1, 10])
        result = resolve_kernel_attack(attack(prepared), rng, decisions=SufferWound())
        rng.assert_exhausted()
        self.assertEqual(result.target_state.wounds, 0)
        self.assertTrue(result.target_state.conditions.has(Condition.STAGGERED))
        self.assertTrue(result.target_state.conditions.has(Condition.DRAINED))

    def test_two_scarabs_keep_two_sources_and_one_nonstacking_drained(self):
        use = weapon_use(W.SCARAB_KNIFE, offhand=W.SCARAB_KNIFE)
        prepared = prepare_weapon_impact(use, 3, ResilienceProfile(100))
        self.assertEqual(len(prepared.hit_condition_sources), 2)
        self.assertEqual(len(prepared.secondary_effects), 1)

    def test_dragon_activation_must_be_unused_and_is_not_spent_by_preparation(self):
        use = weapon_use(W.DRAGON_BOW)
        prepared = prepare_weapon_impact(use, 3, ResilienceProfile(3), dragon_fire=True)
        self.assertEqual(prepared.secondary_effects[0].condition, Condition.ABLAZE)
        self.assertFalse(use.primary.dragon_arrow_used)
        spent = use.inventory.with_item(replace(use.primary, dragon_arrow_used=True))
        with self.assertRaises(ValueError):
            prepare_weapon_impact(replace(use, inventory=spent), 3, ResilienceProfile(3), dragon_fire=True)
        with self.assertRaises(ValueError):
            prepare_weapon_impact(weapon_use(W.WARBOW), 3, ResilienceProfile(3), dragon_fire=True)

    def test_wounds_table_sources_stack_without_becoming_damage_or_attack_dice(self):
        use = weapon_use(W.SWORD_OF_JUSTICE, offhand=W.SWORD_OF_JUSTICE)
        prepared = prepare_weapon_impact(use, 3, ResilienceProfile(3))
        self.assertEqual(prepared.impact_spec.damage.base, 4)
        self.assertEqual(tuple(source.item_id for source in prepared.wound_dice_sources), use.item_ids)
        self.assertEqual(tuple(modifier.amount for modifier in prepared.wound_dice_modifiers), (2,))
        hochland = prepare_weapon_impact(weapon_use(W.HOCHLAND_LONG_RIFLE), 3, ResilienceProfile(3))
        self.assertEqual(hochland.wound_dice_modifiers[0].amount, 1)

    def test_only_selected_actual_unwavering_forbids_give_ground(self):
        spear = prepare_weapon_impact(weapon_use(W.UNWAVERING_SPEAR), 3, ResilienceProfile(3))
        ordinary = prepare_weapon_impact(weapon_use(W.CAVALRY_SPEAR), 3, ResilienceProfile(3))
        self.assertTrue(spear.forbids_give_ground)
        self.assertFalse(ordinary.forbids_give_ground)

    def test_impact_rejects_removed_effect_or_changed_item_sources(self):
        prepared = prepare_weapon_impact(weapon_use(W.SCARAB_KNIFE), 3, ResilienceProfile(3))
        with self.assertRaises(ValueError):
            replace(prepared, hit_condition_sources=())
        with self.assertRaises(ValueError):
            replace(prepared, hit_condition_sources=(replace(prepared.hit_condition_sources[0], item_id='foreign'),))


if __name__ == '__main__':
    unittest.main()
