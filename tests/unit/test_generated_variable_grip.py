"""Literal variable-grip sources and conditional generated equipment choices."""
from copy import deepcopy
from dataclasses import replace
import pickle
from random import Random
import unittest

from towr.application.dynamic_encounter import NpcSearchSpace
from towr.domain.generated_npc_models import (
    GeneratedNpc, GeneratedWeapon, GENERATED_VARIABLE_GRIP_WEAPONS,
    generated_weapon_allows_shield, generated_weapon_grips,
    validate_generated_definition,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.test_models import Skill


ONE = RangedWeaponHands.ONE_HANDED
TWO = RangedWeaponHands.TWO_HANDED


def component(weapon=GeneratedWeapon.FOOT_SPEAR, *, grip=ONE, **changes):
    facts = dict(weapon_skill=3, strength=3, toughness=4, agility=2,
        melee=4, defence=4, athletics=3, weapon=weapon, light_armour=False,
        shield=False, weapon_grip=grip)
    facts.update(changes)
    return GeneratedNpc(**facts)


def space(**changes):
    facts = dict(weapon_skill=(3,), strength=(3,), toughness=(4,), agility=(2,),
        melee=(4,), defence=(4,), athletics=(3,),
        weapon=(GeneratedWeapon.FOOT_SPEAR,), light_armour=(False,),
        shield=(False,), abilities=((),), allowed_talents=(), weapon_grip=(ONE,TWO))
    facts.update(changes)
    return NpcSearchSpace(**facts)


class FirstChoice:
    def __init__(self):
        self.choices = []

    def choice(self, values):
        self.choices.append(tuple(values))
        return values[0]


class NoChoice:
    def choice(self, values):
        raise AssertionError('invalid source must be rejected before proposal RNG')


class GeneratedVariableGripSourceTests(unittest.TestCase):
    def test_literal_damage_hands_range_and_cap_follow_each_actual_grip(self):
        cases = (
            (GeneratedWeapon.FOOT_SPEAR, ONE, (1,4)),
            (GeneratedWeapon.FOOT_SPEAR, TWO, (2,5)),
            (GeneratedWeapon.POLEARM, ONE, (1,4)),
            (GeneratedWeapon.POLEARM, TWO, (3,6)),
        )
        for weapon,grip,damages in cases:
            for strength,damage in zip((1,4),damages):
                for ws in (1,3,6):
                    with self.subTest(weapon=weapon,grip=grip,strength=strength,ws=ws):
                        npc = component(weapon,grip=grip,strength=strength,weapon_skill=ws)
                        definition = npc.participant('not-a-catalogue-entry').definition
                        attack, = definition.attacks
                        self.assertIs(attack.skill,Skill.MELEE)
                        self.assertIs(attack.hands,grip)
                        self.assertEqual(attack.damage.base,damage)
                        self.assertEqual((attack.range_min,attack.range_max),
                            (RangedWeaponRange.CLOSE,RangedWeaponRange.SHORT))
                        self.assertEqual(attack.test_profile.maximum_dice,ws*2)
                        self.assertIsNone(attack.test_profile.pool_cap)
                        self.assertEqual(definition.generated_components,npc)
                        validate_generated_definition(definition)

    def test_variable_grip_is_required_exact_and_fixed_weapons_forbid_it(self):
        for weapon in GENERATED_VARIABLE_GRIP_WEAPONS:
            self.assertEqual(generated_weapon_grips(weapon),(ONE,TWO))
            for grip in (None,'1h','2h',True,1,(),object()):
                with self.subTest(weapon=weapon,grip=grip),self.assertRaises((TypeError,ValueError)):
                    component(weapon,grip=grip)
        for weapon in (GeneratedWeapon.SWORD,GeneratedWeapon.GREATSWORD):
            self.assertEqual(generated_weapon_grips(weapon),(None,))
            for grip in (ONE,TWO):
                with self.subTest(weapon=weapon,grip=grip),self.assertRaises(ValueError):
                    component(weapon,grip=grip)
            self.assertIsNone(component(weapon,grip=None).weapon_grip)

    def test_shield_compatibility_uses_actual_grip_without_repairing_source(self):
        for weapon in GENERATED_VARIABLE_GRIP_WEAPONS:
            with self.subTest(weapon=weapon):
                self.assertTrue(generated_weapon_allows_shield(weapon,ONE))
                self.assertFalse(generated_weapon_allows_shield(weapon,TWO))
                self.assertTrue(component(weapon,grip=ONE,shield=True).shield)
                with self.assertRaises(ValueError):
                    component(weapon,grip=TWO,shield=True)
                with self.assertRaises(ValueError):
                    generated_weapon_allows_shield(weapon)
        for grip in (ONE,TWO):
            with self.assertRaises(ValueError):
                generated_weapon_allows_shield(GeneratedWeapon.PISTOL,grip)

    def test_full_definition_readmission_binds_grip_to_derived_profile(self):
        for changed in ('grip','hands','damage','range','cap'):
            definition = deepcopy(component().participant('literal-source').definition)
            attack, = definition.attacks
            if changed == 'grip':
                object.__setattr__(definition.generated_components,'weapon_grip',TWO)
            elif changed == 'hands':
                object.__setattr__(attack,'hands',TWO)
            elif changed == 'damage':
                object.__setattr__(attack.damage,'base',4)
            elif changed == 'range':
                object.__setattr__(attack,'range_max',RangedWeaponRange.CLOSE)
            else:
                object.__setattr__(attack.test_profile,'pool_cap',8)
            with self.subTest(changed=changed),self.assertRaises(ValueError):
                validate_generated_definition(definition)

    def test_pickle_roundtrip_retains_explicit_grip_and_independent_values(self):
        source = component(GeneratedWeapon.POLEARM,grip=TWO)
        restored = pickle.loads(pickle.dumps(source))
        self.assertEqual(restored,source)
        self.assertIsNot(restored,source)
        self.assertIs(restored.weapon_grip,TWO)
        self.assertTrue(space(weapon=(GeneratedWeapon.POLEARM,)).contains(restored))


class GeneratedVariableGripSpaceTests(unittest.TestCase):
    def test_space_grip_choices_are_nonempty_unique_and_exact_enums(self):
        for grips in ([],(),(ONE,ONE),('1h',),(None,),(True,)):
            with self.subTest(grips=grips),self.assertRaises(ValueError):
                space(weapon_grip=grips)

    def test_unreachable_grip_and_shield_choices_are_rejected_before_rng(self):
        for grips,shields in (((ONE,TWO),(True,)),((TWO,),(True,)),((TWO,),(False,True))):
            with self.subTest(grips=grips,shields=shields),self.assertRaises(ValueError):
                space(weapon_grip=grips,shield=shields)
        one_handed = space(weapon_grip=(ONE,),shield=(True,))
        self.assertTrue(one_handed.contains(component(grip=ONE,shield=True)))
        self.assertFalse(one_handed.contains(component(grip=TWO)))

    def test_fixed_weapons_ignore_the_conditional_axis_without_spending_rng(self):
        first = space(weapon=(GeneratedWeapon.SWORD,),weapon_grip=(ONE,),shield=(True,))
        second = replace(first,weapon_grip=(TWO,))
        first_rng,second_rng = FirstChoice(),FirstChoice()
        a,b = first.sample(first_rng),second.sample(second_rng)
        self.assertEqual(a,b)
        self.assertEqual(first_rng.choices,second_rng.choices)
        self.assertIsNone(a.weapon_grip)
        self.assertTrue(a.shield)
        self.assertTrue(second.contains(a))
        fixed_two = space(weapon=(GeneratedWeapon.GREATAXE,),weapon_grip=(ONE,))
        self.assertTrue(fixed_two.contains(component(GeneratedWeapon.GREATAXE,grip=None)))

    def test_sampling_draws_a_compatible_branch_without_discarding_shield(self):
        two_handed = space(weapon_grip=(TWO,ONE),shield=(False,True))
        rng = FirstChoice()
        npc = two_handed.sample(rng)
        self.assertIs(npc.weapon_grip,TWO)
        self.assertFalse(npc.shield)
        self.assertNotIn((False,True),rng.choices)
        one_handed = space(weapon_grip=(ONE,),shield=(True,False))
        npc = one_handed.sample(FirstChoice())
        self.assertIs(npc.weapon_grip,ONE)
        self.assertTrue(npc.shield)

    def test_weapon_mutation_supplies_or_removes_only_the_conditional_grip(self):
        pool = space(weapon=(GeneratedWeapon.SWORD,GeneratedWeapon.FOOT_SPEAR),
            shield=(False,True))
        original = component(GeneratedWeapon.SWORD,grip=None,shield=True)
        changed = pool.mutate(original,FirstChoice())
        self.assertIs(changed.weapon,GeneratedWeapon.FOOT_SPEAR)
        self.assertIs(changed.weapon_grip,ONE)
        self.assertTrue(changed.shield)
        self.assertIsNone(original.weapon_grip)
        original = component(grip=TWO)
        changed = pool.mutate(original,FirstChoice())
        self.assertIs(changed.weapon,GeneratedWeapon.SWORD)
        self.assertIsNone(changed.weapon_grip)
        self.assertFalse(changed.shield)
        self.assertTrue(pool.contains(changed))

    def test_grip_mutation_is_separate_and_never_drops_an_occupied_shield(self):
        pool = space()
        original = component(grip=ONE)
        changed = pool.mutate(original,FirstChoice())
        self.assertEqual(changed,replace(original,weapon_grip=TWO))
        shielded_pool = space(shield=(False,True))
        original = component(grip=ONE,shield=True)
        changed = shielded_pool.mutate(original,FirstChoice())
        self.assertEqual(changed,replace(original,shield=False))
        self.assertIs(changed.weapon_grip,ONE)
        self.assertTrue(original.shield)

    def test_ranged_weapon_mutation_does_not_retain_a_melee_grip(self):
        pool = space(weapon=(GeneratedWeapon.PISTOL,GeneratedWeapon.FOOT_SPEAR),weapon_grip=(ONE,))
        shooter = pool.sample(FirstChoice())
        self.assertIsNone(shooter.weapon_grip)
        self.assertIsNotNone(shooter.ranged)
        spear = pool.mutate(shooter,FirstChoice())
        self.assertIs(spear.weapon,GeneratedWeapon.FOOT_SPEAR)
        self.assertIs(spear.weapon_grip,ONE)
        self.assertIsNone(spear.ranged)
        changed = pool.mutate(spear,FirstChoice())
        self.assertIs(changed.weapon,GeneratedWeapon.PISTOL)
        self.assertIsNone(changed.weapon_grip)
        self.assertIsNotNone(changed.ranged)

    def test_contains_and_mutation_readmit_grip_before_rng(self):
        pool = space(weapon_grip=(ONE,))
        self.assertFalse(pool.contains(component(grip=TWO)))
        forged = deepcopy(component(grip=ONE,shield=True))
        object.__setattr__(forged,'weapon_grip',TWO)
        self.assertFalse(pool.contains(forged))
        with self.assertRaises(ValueError):
            pool.mutate(forged,NoChoice())

    def test_numeric_resampling_preserves_actual_grip_and_inventory_facts(self):
        pool = space(strength=(1,3,4),weapon_skill=(1,3,5),light_armour=(False,True))
        for grip in (ONE,TWO):
            source = component(grip=grip,light_armour=True)
            saved = deepcopy(source)
            sampled, = pool.resample_numeric((source,),Random(18),bias=0.75).composition
            with self.subTest(grip=grip):
                self.assertEqual((sampled.weapon,sampled.weapon_grip,sampled.light_armour,sampled.shield),
                    (source.weapon,grip,True,False))
                self.assertEqual(source,saved)
                self.assertTrue(pool.contains(sampled))


if __name__ == '__main__':
    unittest.main()
