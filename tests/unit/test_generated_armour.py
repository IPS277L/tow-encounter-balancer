"""Item-derived generated sources and admissible dynamic armour proposals."""
from tests.support.generated_weapon_sources import initial_generated_weapons
from dataclasses import replace
from random import Random
import unittest

from towr.application.dynamic_encounter import NpcSearchSpace,automatic_npc_search_space
from towr.domain.armour_models import ArmourLoadout,BodyArmour,HelmetKind,ShieldKind
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import (
    GeneratedNpc,GeneratedWeapon,generated_npc_profiles,validate_generated_definition,
)
from towr.domain.pc_mount_models import CombatMount,RiderKind
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.domain.pc_generated_equipment import npc_protection_test
from towr.domain.test_models import Skill
from tests.support.pc_melee_fixtures import make_pc_melee_scenario


def npc(**changes):
    facts=dict(weapon_skill=3,strength=3,toughness=3,agility=3,melee=4,athletics=4,
        defence=4,weapon=GeneratedWeapon.STAFF,armour=ArmourLoadout())
    facts.update(changes)
    facts['weapons'] = initial_generated_weapons(facts.pop('weapon'), facts.pop('weapon_grip', None))
    return GeneratedNpc(**facts)


def fixed_space(**changes):
    facts=dict(weapon_skill=(3,),strength=(3,),toughness=(3,),agility=(3,),melee=(4,),
        defence=(4,),athletics=(4,),weapon=(GeneratedWeapon.STAFF,),armour=(None,),
        shield=(None,),allowed_talents=(),brawn=(4,))
    facts.update(changes)
    return NpcSearchSpace(weapon_count=(1,), **facts)


class GeneratedArmourTests(unittest.TestCase):
    def test_selected_body_helm_shield_and_barding_are_independent_sources(self):
        source=npc(armour=ArmourLoadout((BodyArmour.FULL_PLATE,),BodyArmour.FULL_PLATE,
            HelmetKind.HUNT,ShieldKind.BRIARROOT,True),mount=CombatMount.HORSE)
        resilience,_,_=generated_npc_profiles(source)
        self.assertEqual(resilience.total,10)  # T3 + body3 + helm1 + shield1 + horse1 + barding1.
        self.assertTrue(source.shield)

    def test_layered_body_does_not_sum_resilience_bonuses(self):
        for selected,bonus in ((BodyArmour.HEAVY,2),(BodyArmour.METEORIC_IRON,3)):
            with self.subTest(selected=selected):
                source=npc(armour=ArmourLoadout((BodyArmour.HEAVY,BodyArmour.METEORIC_IRON),selected))
                self.assertEqual(generated_npc_profiles(source)[0].bonus,bonus)

    def test_helmet_only_preserves_armoured_without_inventing_a_bonus(self):
        resilience,_,_=generated_npc_profiles(npc(armour=ArmourLoadout(helmet=HelmetKind.HELMET)))
        self.assertEqual(resilience.bonus,0)
        self.assertTrue(resilience.is_armoured)

    def test_agilulf_profiles_are_exact_five_and_leave_underlying_facts_intact(self):
        source=npc(weapon_skill=8,melee=6,defence=2,
            armour=ArmourLoadout((BodyArmour.AGILULF,),BodyArmour.AGILULF),
            agilulf_code_confirmed=True)
        _,attacks,protection=generated_npc_profiles(source)
        attack=attacks[0]
        self.assertEqual((attack.test_profile.base_dice,attack.test_profile.threshold),(5,5))
        self.assertEqual((protection[0].test_profile.base_dice,protection[0].test_profile.threshold),(5,5))
        self.assertEqual((source.weapon_skill,source.melee,source.defence),(8,6,2))

    def test_agilulf_requires_explicit_confirmation_for_any_worn_layer(self):
        armour=ArmourLoadout((BodyArmour.AGILULF,),BodyArmour.AGILULF)
        for confirmation in (None,False,1,'true'):
            with self.subTest(confirmation=confirmation),self.assertRaises((TypeError,ValueError)):
                npc(armour=armour,agilulf_code_confirmed=confirmation)
        with self.assertRaises(ValueError):
            npc(agilulf_code_confirmed=True)
        layered=ArmourLoadout((BodyArmour.HEAVY,BodyArmour.AGILULF),BodyArmour.HEAVY)
        with self.assertRaises(ValueError):
            npc(armour=layered)
        source=npc(armour=layered,agilulf_code_confirmed=True)
        self.assertEqual(generated_npc_profiles(source)[1][0].test_profile.base_dice,3)
        with self.assertRaises(ValueError):
            replace(source,weapons=initial_generated_weapons(GeneratedWeapon.WEIGHTED_NET),throwing=4,ballistic_skill=3)

    def test_close_shooting_and_throwing_protection_use_the_selected_armour_ratings(self):
        for raw_ws,raw_melee in ((8,6),(2,2)):
            for selected in (BodyArmour.AGILULF,BodyArmour.LIGHT):
                for skill in (Skill.SHOOTING,Skill.THROWING):
                    with self.subTest(raw=(raw_ws,raw_melee),selected=selected,skill=skill):
                        armour=ArmourLoadout((BodyArmour.LIGHT,BodyArmour.AGILULF),selected)
                        source=npc(weapon_skill=raw_ws,melee=raw_melee,agility=1,athletics=2,
                            armour=armour,agilulf_code_confirmed=True)
                        scenario=make_pc_melee_scenario()
                        state=initial_pc_melee_state(replace(scenario,
                            enemies=(source.participant('minion1'),)))
                        option,test=npc_protection_test(state,'minion1','pc','real-protection',
                            attack_skill=skill)
                        self.assertIs(option.skill,Skill.MELEE)
                        expected=(5,5) if selected is BodyArmour.AGILULF else (raw_ws,raw_melee)
                        self.assertEqual((test.profile.base_dice,test.profile.threshold),expected)
                        self.assertEqual((source.weapon_skill,source.melee),(raw_ws,raw_melee))

    def test_starting_burden_uses_strength_of_actual_worn_suit(self):
        for body,threshold in ((BodyArmour.HEAVY,3),(BodyArmour.FULL_PLATE,4)):
            for strength in (threshold-1,threshold):
                with self.subTest(body=body,strength=strength):
                    source=npc(strength=strength,armour=ArmourLoadout((body,),body))
                    conditions=source.participant('generated').state.injury.conditions
                    self.assertEqual(conditions.has(Condition.BURDENED),strength<threshold)
                    self.assertEqual(conditions.conditions,
                        frozenset((Condition.BURDENED,)) if strength<threshold else frozenset())

    def test_nonbenefit_heavy_layer_still_imposes_its_burden(self):
        source=npc(strength=2,armour=ArmourLoadout(
            (BodyArmour.HEAVY,BodyArmour.ITHILMAR),BodyArmour.ITHILMAR))
        self.assertTrue(source.participant('layered').state.injury.conditions.has(Condition.BURDENED))

    def test_barding_cannot_appear_without_a_mount(self):
        with self.assertRaises(ValueError):
            npc(armour=ArmourLoadout(barding=True))

    def test_beastly_mount_does_not_invent_human_rider(self):
        with self.assertRaises(ValueError):
            npc(mount=CombatMount.DEMIGRYPH)
        with self.assertRaises(ValueError):
            npc(mount=CombatMount.DEMIGRYPH,rider_kind=RiderKind.ELF)
        source=npc(mount=CombatMount.DEMIGRYPH,rider_kind=RiderKind.HUMAN,
            armour=ArmourLoadout(barding=True))
        self.assertEqual(generated_npc_profiles(source)[0].bonus,3)
        self.assertEqual(generated_npc_profiles(npc(mount=CombatMount.PEGASUS,
            rider_kind=RiderKind.ELF))[0].bonus,1)
        with self.assertRaises(ValueError):
            npc(mount=CombatMount.HORSE,rider_kind=RiderKind.HUMAN)

    def test_complete_definition_rederives_armour_protection(self):
        source=npc(armour=ArmourLoadout((BodyArmour.FULL_PLATE,),BodyArmour.FULL_PLATE))
        definition=source.participant('plate').definition
        validate_generated_definition(definition)
        with self.assertRaises(ValueError):
            replace(definition,resilience=replace(definition.resilience,bonus=2))

    def test_raw_bools_and_strings_are_not_armour_sources(self):
        for armour in (True,'heavy_armour',{'benefit':'heavy_armour'}):
            with self.subTest(armour=armour),self.assertRaises(TypeError):
                npc(armour=armour)
        with self.assertRaises(TypeError):
            npc(shield=True)


class ArmourSearchSpaceTests(unittest.TestCase):
    def test_defaults_propose_all_mundane_suits_and_no_magic(self):
        space=NpcSearchSpace(weapon_count=(1,), )
        self.assertEqual(set(space.armour),{None,BodyArmour.LIGHT,BodyArmour.HEAVY,BodyArmour.FULL_PLATE})
        self.assertEqual(space.secondary_armour,(None,))
        self.assertEqual(space.helmet,(None,))
        self.assertEqual(space.shield,(None,ShieldKind.SHIELD))
        self.assertIsNone(space.agilulf_code_confirmed)

    def test_automatic_space_includes_ordinary_helmet_and_compatible_barded_horses(self):
        party=make_pc_melee_scenario().party
        spec=PcBattlefieldSpec(RangedWeaponRange.SHORT,RangedWeaponRange.LONG)
        space=automatic_npc_search_space(party,battlefield=spec)
        self.assertEqual(space.helmet,(None,HelmetKind.HELMET))
        self.assertEqual(space.barding,(False,True))
        self.assertEqual(space.mount,
            (None,CombatMount.HORSE,CombatMount.BRETONNIAN_WARHORSE,CombatMount.ELVEN_STEED))
        self.assertNotIn(BodyArmour.AGILULF,space.armour)
        stationary=automatic_npc_search_space(party)
        self.assertEqual(stationary.mount,(None,))
        self.assertEqual(stationary.barding,(False,))

    def test_all_explicit_gear_choices_are_sampled_as_valid_components(self):
        space=fixed_space(armour=(None,BodyArmour.LIGHT,BodyArmour.HEAVY,BodyArmour.FULL_PLATE),
            helmet=(None,HelmetKind.HELMET,HelmetKind.HUNT),
            shield=(None,ShieldKind.SHIELD,ShieldKind.BRIARROOT))
        samples=tuple(space.sample(Random(seed)) for seed in range(120))
        self.assertTrue(all(space.contains(member) for member in samples))
        self.assertEqual({member.armour.benefit for member in samples},set(space.armour))
        self.assertEqual({member.armour.helmet for member in samples},set(space.helmet))
        self.assertEqual({member.armour.shield for member in samples},set(space.shield))

    def test_sampling_keeps_legal_mount_barding_and_rider_pairs(self):
        space=fixed_space(mount=(None,CombatMount.HORSE,CombatMount.DEMIGRYPH,CombatMount.PEGASUS),
            barding=(False,True))
        samples=tuple(space.sample(Random(seed)) for seed in range(100))
        self.assertEqual({member.mount for member in samples},set(space.mount))
        self.assertTrue(any(member.armour.barding for member in samples))
        self.assertTrue(all(space.contains(member) for member in samples))
        self.assertTrue(all(not member.armour.barding for member in samples if member.mount is None))
        self.assertTrue(all(member.rider_kind is RiderKind.HUMAN for member in samples
            if member.mount is CombatMount.DEMIGRYPH))

    def test_invalid_joint_axes_fail_before_sampling(self):
        malformed=(dict(barding=(True,)),dict(mount=(None,CombatMount.HORSE),barding=(True,)),
            dict(mount=(CombatMount.DEMIGRYPH,),rider_kind=(RiderKind.OTHER,)),
            dict(armour=(BodyArmour.HEAVY,),secondary_armour=(BodyArmour.LIGHT,)),
            dict(armour=(None,),secondary_armour=(BodyArmour.METEORIC_IRON,)),
            dict(weapon=(GeneratedWeapon.GREATSWORD,),shield=(ShieldKind.SHIELD,)),
            dict(shield=(True,)),dict(armour=('heavy_armour',)))
        for changes in malformed:
            with self.subTest(changes=changes),self.assertRaises((TypeError,ValueError)):
                fixed_space(**changes)

    def test_magic_is_available_only_from_its_explicit_axes(self):
        space=fixed_space(armour=(BodyArmour.METEORIC_IRON,BodyArmour.ITHILMAR),
            secondary_armour=(None,BodyArmour.HEAVY))
        samples=tuple(space.sample(Random(seed)) for seed in range(40))
        self.assertTrue(all(space.contains(member) for member in samples))
        self.assertEqual({member.armour.benefit for member in samples},set(space.armour))
        self.assertTrue(any(len(member.armour.body)==2 for member in samples))
        with self.assertRaises(ValueError):
            fixed_space(armour=(BodyArmour.AGILULF,))
        source=fixed_space(armour=(BodyArmour.AGILULF,),agilulf_code_confirmed=True).sample(Random(1))
        self.assertIs(source.agilulf_code_confirmed,True)

    def test_shooting_and_throwing_branches_never_drop_a_drawn_agilulf_layer(self):
        space=fixed_space(weapon=(GeneratedWeapon.STAFF,GeneratedWeapon.PISTOL,GeneratedWeapon.WEIGHTED_NET),
            armour=(None,BodyArmour.LIGHT,BodyArmour.AGILULF),
            secondary_armour=(None,BodyArmour.AGILULF),agilulf_code_confirmed=True)
        samples=tuple(space.sample(Random(seed)) for seed in range(90))
        self.assertEqual({member.weapon for member in samples},set(space.weapon))
        self.assertTrue(any(BodyArmour.AGILULF in member.armour.body for member in samples))
        self.assertTrue(all(space.contains(member) for member in samples))
        self.assertTrue(all(member.weapon is GeneratedWeapon.STAFF for member in samples
            if BodyArmour.AGILULF in member.armour.body))
        with self.assertRaises(ValueError):
            fixed_space(weapon=(GeneratedWeapon.PISTOL,),armour=(BodyArmour.AGILULF,),
                agilulf_code_confirmed=True)
        with self.assertRaises(ValueError):
            fixed_space(weapon=(GeneratedWeapon.PISTOL,),armour=(BodyArmour.HEAVY,),
                secondary_armour=(None,BodyArmour.AGILULF),agilulf_code_confirmed=True)

    def test_mutations_and_numeric_sampling_keep_complete_gear_admitted(self):
        space=NpcSearchSpace(weapon_count=(1,), armour=(None,BodyArmour.HEAVY,BodyArmour.METEORIC_IRON),
            secondary_armour=(None,),helmet=(None,HelmetKind.HUNT),
            shield=(None,ShieldKind.SHIELD,ShieldKind.BRIARROOT),
            mount=(None,CombatMount.HORSE,CombatMount.PEGASUS),barding=(False,True))
        rng=Random(77)
        current=space.sample(rng)
        for _ in range(70):
            current=space.mutate(current,rng)
            self.assertTrue(space.contains(current))
        result=space.resample_numeric((current,),rng,bias=-1)
        sampled,=result.composition
        self.assertTrue(space.contains(sampled))
        self.assertEqual(sampled.armour,current.armour)
        self.assertEqual((sampled.mount,sampled.rider_kind),(current.mount,current.rider_kind))

    def test_fixed_axes_do_not_invent_an_alternative_loadout(self):
        space=fixed_space(armour=(BodyArmour.FULL_PLATE,),helmet=(HelmetKind.HUNT,),
            shield=(ShieldKind.BRIARROOT,),mount=(CombatMount.HORSE,),barding=(True,))
        source=space.sample(Random(1))
        self.assertEqual(space.mutate(source,Random(2)),source)
        self.assertFalse(replace(space,armour=(BodyArmour.HEAVY,)).contains(source))


if __name__=='__main__':
    unittest.main()
