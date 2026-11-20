"""Canonical mount metadata and fresh typed animal bodies, without native combat."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import pickle
import unittest

from tests.support.talent_sources import free_talent
from towr.domain.armour_models import ArmourLoadout, BodyArmour
from towr.domain.condition_models import Condition
from towr.domain.movement_models import MovementSpeed
from towr.domain.pc_mount_companion_sources import (
    MountCompanionCharacteristics, MountCompanionSkills, MountCompanionWoundBand,
    initial_mount_companion_snapshot, mount_companion_profile,
)
from towr.domain.pc_mount_models import CombatMount
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.talent_catalog import TalentId
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatSide


class MountCompanionSourceTests(unittest.TestCase):
    def test_all_six_species_have_full_exact_characteristics_and_skills(self):
        expected = {
            CombatMount.HORSE: ((3,0,3,3,3,4,2,1), 3,4,3,4,1),
            CombatMount.BRETONNIAN_WARHORSE: ((3,0,3,3,3,4,2,1), 3,4,3,4,1),
            CombatMount.ELVEN_STEED: ((3,0,3,3,3,4,2,1), 3,4,3,4,1),
            CombatMount.SKELETAL_STEED: ((3,0,3,3,3,4,2,1), 3,4,3,4,1),
            CombatMount.PEGASUS: ((3,0,4,3,4,4,2,1), 3,3,3,4,1),
            CombatMount.DEMIGRYPH: ((4,0,5,4,4,4,2,1), 4,4,3,3,2),
        }
        self.assertEqual(set(expected), set(CombatMount))
        for kind, (characteristics, melee, brawn, endurance, athletics, stealth) in expected.items():
            with self.subTest(kind=kind):
                profile = mount_companion_profile(kind)
                self.assertEqual(tuple(getattr(profile.characteristics, field.name)
                    for field in fields(MountCompanionCharacteristics)), characteristics)
                self.assertEqual(len(fields(MountCompanionSkills)), 17)
                self.assertEqual(profile.skills.default, 1)
                self.assertEqual((profile.skill_rating(Skill.MELEE), profile.skill_rating(Skill.BRAWN),
                    profile.skill_rating(Skill.ENDURANCE), profile.skill_rating(Skill.ATHLETICS),
                    profile.skill_rating(Skill.STEALTH)), (melee,brawn,endurance,athletics,stealth))
                self.assertEqual(profile.skill_rating(Skill.AWARENESS), 3)
                self.assertEqual(profile.skill_rating(Skill.WILLPOWER), 4 if kind is CombatMount.DEMIGRYPH else 3)
                for skill in (Skill.DEFENCE,Skill.SHOOTING,Skill.THROWING,Skill.TOIL,Skill.SURVIVAL,
                        Skill.DEXTERITY,Skill.RECALL,Skill.LEADERSHIP,Skill.CHARM):
                    self.assertEqual(profile.skill_rating(skill), 1)
                self.assertIs(profile.speed, MovementSpeed.FAST)

    def test_printed_attacks_protection_and_profile_hp_are_not_rider_sources(self):
        for kind in CombatMount:
            with self.subTest(kind=kind):
                profile = mount_companion_profile(kind)
                definition = profile.definition
                demigryph = kind is CombatMount.DEMIGRYPH
                self.assertEqual(definition.attacks[0].test_profile, InlineProfile(4,4) if demigryph else InlineProfile(3,3))
                self.assertIs(definition.attacks[0].skill, Skill.MELEE)
                self.assertIsNone(definition.attacks[0].hands)
                self.assertEqual(definition.attacks[0].damage.base, 5 if demigryph else 3)
                self.assertEqual(definition.protection[0].test_profile, InlineProfile(4,3 if demigryph else 4))
                self.assertIs(definition.protection[0].skill, Skill.ATHLETICS)
                brute = kind in (CombatMount.PEGASUS, CombatMount.DEMIGRYPH)
                self.assertIs(definition.injury_policy, TargetInjuryPolicy.BRUTE if brute else TargetInjuryPolicy.MINION)
                self.assertEqual(definition.wound_limit, 3 if demigryph else 2 if kind is CombatMount.PEGASUS else 1)
                self.assertEqual(definition.talents, ())
                self.assertIsNone(definition.generated_components)
                self.assertEqual(profile.armour, ArmourLoadout())
                self.assertEqual(definition.resilience.total, profile.characteristics.toughness)

    def test_barding_only_adds_own_resilience_and_retains_unmodified_printed_tests(self):
        for kind in CombatMount:
            with self.subTest(kind=kind):
                plain = mount_companion_profile(kind)
                barded = mount_companion_profile(kind, barding=True)
                self.assertEqual(barded.definition.id, 'mount-companion:'+kind.value+':true')
                self.assertEqual(plain.definition.id, 'mount-companion:'+kind.value+':false')
                self.assertFalse(barded.definition.id.startswith('pc-book-npc:'))
                self.assertEqual(barded.definition.resilience.bonus, 1)
                self.assertTrue(barded.definition.resilience.is_armoured)
                self.assertEqual(barded.definition.resilience.toughness, plain.definition.resilience.toughness)
                self.assertEqual(barded.definition.attacks, plain.definition.attacks)
                self.assertEqual(barded.definition.protection, plain.definition.protection)
                self.assertEqual(barded.skills, plain.skills)
                self.assertEqual(barded.armour, ArmourLoadout(barding=True))

    def test_taxonomy_and_wound_band_are_intrinsic_and_skeletal_behavior_is_not_granted(self):
        for kind in CombatMount:
            with self.subTest(kind=kind):
                profile = mount_companion_profile(kind)
                self.assertIs(profile.can_fly, kind is CombatMount.PEGASUS)
                self.assertIs(profile.fearsome, kind is CombatMount.DEMIGRYPH)
                self.assertIs(profile.undead, kind is CombatMount.SKELETAL_STEED)
                band = (MountCompanionWoundBand.DRAINED_1_2 if kind is CombatMount.DEMIGRYPH
                    else MountCompanionWoundBand.GROUNDED_FROM_1 if kind is CombatMount.PEGASUS
                    else MountCompanionWoundBand.NONE)
                self.assertIs(profile.wound_band, band)
                self.assertEqual(profile.definition.attacks[0].secondary_effects, ())
                self.assertEqual(profile.definition.talents, ())

    def test_skill_characteristics_preserve_bs_zero_without_inventing_an_attack_test(self):
        profile = mount_companion_profile(CombatMount.PEGASUS)
        expected = dict(melee=3,defence=3,shooting=0,throwing=0,brawn=4,toil=4,survival=3,endurance=3,
            awareness=4,dexterity=4,athletics=4,stealth=4,willpower=2,recall=2,leadership=1,charm=1)
        self.assertEqual({skill.value:profile.characteristic_for_skill(skill) for skill in Skill}, expected)
        self.assertEqual(len(profile.definition.attacks), 1)
        for skill in (Skill.ATHLETICS,Skill.BRAWN,Skill.ENDURANCE,Skill.WILLPOWER):
            self.assertGreater(profile.characteristic_for_skill(skill), 0)
        for query in (profile.skill_rating, profile.characteristic_for_skill):
            with self.assertRaises(TypeError):
                query('athletics')

    def test_initial_snapshots_keep_the_actual_side_and_fresh_separate_injury_without_fate(self):
        for side in CombatSide:
            for kind in CombatMount:
                with self.subTest(side=side,kind=kind):
                    one = initial_mount_companion_snapshot('animal:1', side, kind, barding=True)
                    two = initial_mount_companion_snapshot('animal:2', side, kind, barding=True)
                    self.assertIs(one.state.side, side)
                    self.assertIs(one.turn_participant.side, side)
                    self.assertEqual(one.state.injury.wounds, 0)
                    self.assertFalse(one.state.injury.defeated)
                    self.assertIsNot(one.state.injury, two.state.injury)
                    self.assertFalse(one.state.wields_weapon)
                    self.assertFalse(one.state.holds_shield)
                    self.assertFalse(hasattr(one.state, 'fate'))
                    self.assertEqual(one.state.available_attack_ids, tuple(attack.id for attack in one.definition.attacks))
                    injured = replace(one, state=replace(one.state, injury=replace(one.state.injury,
                        conditions=one.state.injury.conditions.with_condition(Condition.STAGGERED))))
                    self.assertFalse(two.state.injury.conditions.has(Condition.STAGGERED))
                    self.assertTrue(injured.state.injury.conditions.has(Condition.STAGGERED))
                    self.assertEqual(pickle.loads(pickle.dumps(one)), one)

    def test_profile_is_immutable_pickle_safe_and_rejects_foreign_or_aliased_facts(self):
        profile = mount_companion_profile(CombatMount.HORSE)
        self.assertEqual(pickle.loads(pickle.dumps(profile)), profile)
        with self.assertRaises(FrozenInstanceError):
            profile.speed = MovementSpeed.SLOW
        invalid = (dict(kind='horse'), dict(can_fly=1), dict(speed='fast'), dict(wound_band='none'),
            dict(skills=replace(profile.skills, athletics=5)),
            dict(characteristics=replace(profile.characteristics, ballistic_skill=1)),
            dict(armour=ArmourLoadout((BodyArmour.LIGHT,), BodyArmour.LIGHT)),
            dict(definition=replace(profile.definition, talents=(free_talent(TalentId.HARDY),))))
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(profile, **changes)
        forged = deepcopy(profile.definition)
        object.__setattr__(forged, 'wound_limit', True)
        with self.assertRaises((TypeError, ValueError)):
            replace(profile, definition=forged)
        for kind in ('horse', None, True):
            with self.assertRaises(TypeError):
                mount_companion_profile(kind)
        for barding in (1,0,'true',None):
            with self.assertRaises(TypeError):
                mount_companion_profile(CombatMount.HORSE, barding=barding)
        with self.assertRaises(TypeError):
            initial_mount_companion_snapshot('animal', 'opposition', CombatMount.HORSE)
        with self.assertRaises(TypeError):
            initial_mount_companion_snapshot('', CombatSide.OPPOSITION, CombatMount.HORSE)


if __name__ == '__main__':
    unittest.main()
