"""GM1.1 VI85: armour-specific mundane effects are cancelled at damage time."""
from tests.support.generated_weapon_sources import initial_generated_weapons
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_k1_ranged_weapon_attack_preparation import base_attack,preparation_request
from towr.domain.armour_models import ArmourLoadout,BodyArmour,METEORIC_PROTECTION_RULE_ID
from towr.domain.attack_models import (
    AttackRequest,AttackOutcome,DamageImpactSpec,DamageModifier,DamageProfile,
    ImpactOutcome,ResilienceModifier,ResilienceProfile,
    effective_damage_modifiers,effective_ignores_armour,armour_ward_cancels_effects,
)
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon,generated_npc_profiles
from towr.domain.npc_champion_attack_models import _actual_attack
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_armour_models import advised_damage_modifiers
from towr.domain.pc_weapon_models import pc_weapon_damage_modifiers
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.test_models import TestProfile,TestRequest
from towr.rules.attack_resolution import resolve_attack
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack


def impact(**changes):
    values=dict(damage=DamageProfile(6),resilience=ResilienceProfile(3,3,mundane_armour_ward=True))
    values.update(changes)
    return DamageImpactSpec(**values)


def request(spec):
    return AttackRequest('attack',TestRequest('attacker',TestProfile(1,6)),
        TestRequest('defender',TestProfile(1,6)),spec,True,False)


def hit(spec):
    return resolve_attack(request(spec),SequenceRandom((1,1)))


class MeteoricArmourTests(unittest.TestCase):
    def test_mundane_ignore_is_cancelled_without_rewriting_the_weapon_trait(self):
        spec=impact(damage=DamageProfile(5),ignores_armour=True)
        protected=hit(spec)
        ordinary=hit(replace(spec,resilience=replace(spec.resilience,mundane_armour_ward=False)))
        self.assertIs(protected.impact,ImpactOutcome.STAGGERED)
        self.assertIs(ordinary.impact,ImpactOutcome.WOUND)
        self.assertEqual((protected.damage,ordinary.damage),(5,5))
        self.assertEqual((protected.effective_resilience,ordinary.effective_resilience),(6,3))
        self.assertIs(protected.impact_spec,spec)
        self.assertIs(spec.ignores_armour,True)
        self.assertFalse(effective_ignores_armour(spec))
        self.assertIn(METEORIC_PROTECTION_RULE_ID,protected.applied_rule_ids)

    def test_armour_bonus_is_cancelled_but_unrelated_damage_and_penalties_remain(self):
        bonus=DamageModifier('axe:armoured',1,armour_specific=True)
        ordinary=DamageModifier('other:damage',2)
        penalty=DamageModifier('other:penalty',-1)
        spec=impact(damage_modifiers=(bonus,ordinary,penalty))
        result=hit(spec)
        self.assertEqual(result.damage,7)
        self.assertEqual(effective_damage_modifiers(spec),(ordinary,penalty))
        self.assertEqual(result.applied_rule_ids,
            ('other:damage','other:penalty',METEORIC_PROTECTION_RULE_ID,'RULE-COMBAT-006:attack-tie'))
        self.assertEqual(result.impact_spec.damage_modifiers,(bonus,ordinary,penalty))

    def test_an_armour_specific_damage_penalty_is_not_an_extra_bonus(self):
        penalty=DamageModifier('armour:penalty',-1,armour_specific=True)
        spec=impact(damage_modifiers=(penalty,))
        self.assertEqual(hit(spec).damage,5)
        self.assertEqual(effective_damage_modifiers(spec),(penalty,))
        self.assertFalse(armour_ward_cancels_effects(spec))

    def test_magical_source_retains_ignore_and_armour_specific_bonus(self):
        bonus=DamageModifier('magic:armoured',1,armour_specific=True,magical_source=True)
        spec=impact(ignores_armour=True,damage_modifiers=(bonus,),magical_source=True)
        result=hit(spec)
        self.assertEqual((result.damage,result.effective_resilience),(7,3))
        self.assertIs(result.impact,ImpactOutcome.WOUND)
        self.assertTrue(effective_ignores_armour(spec))
        self.assertEqual(effective_damage_modifiers(spec),(bonus,))
        self.assertNotIn(METEORIC_PROTECTION_RULE_ID,result.applied_rule_ids)

    def test_magical_primary_does_not_enchant_a_mundane_axe_contribution(self):
        axe=DamageModifier('axe:armoured',1,armour_specific=True)
        spec=impact(magical_source=True,damage_modifiers=(axe,))
        result=hit(spec)
        self.assertEqual(result.damage,6)
        self.assertIs(result.impact,ImpactOutcome.STAGGERED)
        self.assertEqual(effective_damage_modifiers(spec),())
        self.assertEqual(advised_damage_modifiers(spec.damage_modifiers,spec.resilience),())
        self.assertEqual(result.applied_rule_ids.count(METEORIC_PROTECTION_RULE_ID),1)
        self.assertIs(result.impact_spec,spec)
        self.assertIs(spec.damage_modifiers[0],axe)
        self.assertTrue(spec.magical_source)
        self.assertFalse(axe.magical_source)
        _actual_attack(request(spec),result)

    def test_mundane_primary_preserves_an_explicit_magical_armour_bonus(self):
        bonus=DamageModifier('magic:armoured',1,armour_specific=True,magical_source=True)
        for ignores in (False,True):
            with self.subTest(ignores=ignores):
                spec=impact(ignores_armour=ignores,damage_modifiers=(bonus,))
                result=hit(spec)
                self.assertEqual((result.damage,result.effective_resilience),(7,6))
                self.assertEqual(effective_damage_modifiers(spec),(bonus,))
                self.assertEqual(advised_damage_modifiers(spec.damage_modifiers,spec.resilience),(bonus,))
                self.assertEqual(result.applied_rule_ids.count(METEORIC_PROTECTION_RULE_ID),int(ignores))
                self.assertFalse(spec.magical_source)
                self.assertIs(result.impact_spec,spec)

    def test_mixed_modifier_origins_preserve_ordinary_damage_and_all_penalties(self):
        mundane=DamageModifier('axe:armoured',1,armour_specific=True)
        magical=DamageModifier('magic:armoured',2,armour_specific=True,magical_source=True)
        ordinary=DamageModifier('other:damage',3)
        penalty=DamageModifier('other:penalty',-1)
        armour_penalty=DamageModifier('armour:penalty',-2,armour_specific=True)
        modifiers=(mundane,magical,ordinary,penalty,armour_penalty)
        active=(magical,ordinary,penalty,armour_penalty)
        for primary_magic in (False,True):
            with self.subTest(primary_magic=primary_magic):
                spec=impact(magical_source=primary_magic,ignores_armour=True,
                    damage_modifiers=modifiers)
                result=hit(spec)
                self.assertEqual(effective_damage_modifiers(spec),active)
                self.assertEqual(advised_damage_modifiers(modifiers,spec.resilience),active)
                self.assertEqual(result.damage,8)
                self.assertEqual(result.effective_resilience,3 if primary_magic else 6)
                self.assertEqual(result.applied_rule_ids,tuple(modifier.rule_id for modifier in active)
                    +(METEORIC_PROTECTION_RULE_ID,'RULE-COMBAT-006:attack-tie'))
                self.assertEqual(result.applied_rule_ids.count(METEORIC_PROTECTION_RULE_ID),1)
                self.assertEqual(spec.damage_modifiers,modifiers)
                self.assertIs(result.impact_spec,spec)
                unwarded=replace(spec,resilience=replace(spec.resilience,mundane_armour_ward=False))
                self.assertEqual(effective_damage_modifiers(unwarded),modifiers)
                self.assertFalse(armour_ward_cancels_effects(unwarded))
                _actual_attack(request(spec),result)

    def test_resilience_modifiers_and_success_margin_are_preserved(self):
        spec=impact(damage=DamageProfile(4,2),ignores_armour=True,
            damage_modifiers=(DamageModifier('armour:bonus',3,armour_specific=True),),
            resilience_modifiers=(ResilienceModifier('other:resilience',1),))
        attack=request(spec)
        result=resolve_attack(attack,SequenceRandom((1,10)))
        self.assertEqual(result.success_margin,1)
        self.assertEqual(result.damage,6)
        self.assertEqual(result.effective_resilience,7)
        self.assertIs(result.impact,ImpactOutcome.STAGGERED)

    def test_ward_rule_is_recorded_once_when_it_cancels_two_traits(self):
        spec=impact(ignores_armour=True,
            damage_modifiers=(DamageModifier('armour:bonus',1,armour_specific=True),))
        self.assertEqual(hit(spec).applied_rule_ids.count(METEORIC_PROTECTION_RULE_ID),1)

    def test_ward_has_no_damage_phase_effect_on_a_miss(self):
        spec=impact(ignores_armour=True)
        result=resolve_attack(request(spec),SequenceRandom((10,1)))
        self.assertIs(result.outcome,AttackOutcome.MISS)
        self.assertIsNone(result.damage)
        self.assertIsNone(result.effective_resilience)
        self.assertNotIn(METEORIC_PROTECTION_RULE_ID,result.applied_rule_ids)
        self.assertIs(result.impact_spec,spec)

    def test_no_cancelled_trait_does_not_report_an_invoked_ward(self):
        spec=impact(damage_modifiers=(DamageModifier('ordinary:bonus',1),))
        self.assertEqual(hit(spec).damage,7)
        self.assertFalse(armour_ward_cancels_effects(spec))
        self.assertNotIn(METEORIC_PROTECTION_RULE_ID,hit(spec).applied_rule_ids)

    def test_all_ordinary_armour_weapon_bonus_sources_keep_their_metadata(self):
        target=ResilienceProfile(3,3,mundane_armour_ward=True)
        for weapon in (PcMeleeWeapon.AXE,PcMeleeWeapon.HALBERD,PcMeleeWeapon.GREATAXE,PcMeleeWeapon.CROSSBOW):
            with self.subTest(weapon=weapon):
                modifiers=pc_weapon_damage_modifiers(weapon,target)
                self.assertEqual(len(modifiers),1)
                self.assertIs(modifiers[0].armour_specific,True)
                self.assertEqual(effective_damage_modifiers(impact(damage_modifiers=modifiers)),())
        self.assertEqual(pc_weapon_damage_modifiers(PcMeleeWeapon.SWORD,target),())

    def test_generated_resilience_ward_comes_from_selected_meteoric_armour(self):
        fields=dict(weapon_skill=3,strength=3,toughness=3,agility=3,melee=4,athletics=4,
            defence=4,weapon=GeneratedWeapon.STAFF)
        fields['weapons'] = initial_generated_weapons(fields.pop('weapon'), fields.pop('weapon_grip', None))
        protected=GeneratedNpc(**fields,
            armour=ArmourLoadout((BodyArmour.METEORIC_IRON,),BodyArmour.METEORIC_IRON))
        inactive=replace(protected,armour=ArmourLoadout(
            (BodyArmour.METEORIC_IRON,BodyArmour.HEAVY),BodyArmour.HEAVY))
        self.assertTrue(generated_npc_profiles(protected)[0].mundane_armour_ward)
        self.assertFalse(generated_npc_profiles(inactive)[0].mundane_armour_ward)

    def test_profile_preparation_keeps_crossbow_and_gun_traits_in_full_source(self):
        for weapon in (RangedWeaponId.CROSSBOW,RangedWeaponId.HANDGUN):
            with self.subTest(weapon=weapon):
                base=base_attack()
                kernel=base.kernel_request
                attack=kernel.attack
                source=replace(base,kernel_request=replace(kernel,attack=replace(attack,
                    impact_spec=replace(attack.impact_spec,
                        resilience=ResilienceProfile(3,3,mundane_armour_ward=True)))))
                result=prepare_ranged_weapon_attack(preparation_request(weapon,attack=source,
                    lore=weapon is RangedWeaponId.HANDGUN,next_cycle='reload:after-shot'))
                spec=result.profile_attack.kernel_request.attack.impact_spec
                self.assertTrue(spec.resilience.mundane_armour_ward)
                if weapon is RangedWeaponId.HANDGUN:
                    self.assertTrue(spec.ignores_armour)
                    self.assertFalse(effective_ignores_armour(spec))
                else:
                    self.assertEqual(len(spec.damage_modifiers),1)
                    self.assertTrue(spec.damage_modifiers[0].armour_specific)
                    self.assertEqual(effective_damage_modifiers(spec),())
                    forged=replace(result.profile_attack,kernel_request=replace(
                        result.profile_attack.kernel_request,attack=replace(
                            result.profile_attack.kernel_request.attack,impact_spec=replace(spec,
                                damage_modifiers=tuple(replace(modifier,armour_specific=False)
                                    for modifier in spec.damage_modifiers)))))
                    with self.assertRaises(ValueError):
                        replace(result,profile_attack=forged)

    def test_champion_retained_result_guard_uses_the_same_damage_projection(self):
        spec=impact(ignores_armour=True,
            damage_modifiers=(DamageModifier('armour:bonus',1,armour_specific=True),))
        source=request(spec)
        actual=hit(spec)
        _actual_attack(source,actual)
        with self.assertRaises(ValueError):
            _actual_attack(source,replace(actual,effective_resilience=3,impact=ImpactOutcome.WOUND))

    def test_metadata_flags_require_exact_booleans(self):
        for value in (None,0,1,'true'):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    ResilienceProfile(3,3,mundane_armour_ward=value)
                with self.assertRaises(TypeError):
                    DamageModifier('armour:bonus',1,armour_specific=value)
                with self.assertRaises(TypeError):
                    DamageModifier('armour:bonus',1,magical_source=value)
                with self.assertRaises(TypeError):
                    impact(magical_source=value)


if __name__=='__main__':
    unittest.main()
