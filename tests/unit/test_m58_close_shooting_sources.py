"""Book-backed M58 profiles retain full sources and true Characteristic caps."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_pistol_scenarios import make_pc_pistol_scenario, pistol_profile
from towr.domain.pc_melee_models import (
    PcMeleeWeapon, validate_pc_melee_scenario_admission,
)
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile, create_pc_book_npc, get_pc_book_npc_entry,
)
from towr.domain.pc_npc_close_shooting_models import (
    PcNpcCloseShootingProtectionPolicy as Policy, pc_close_shooting_protection_profile,
)
from towr.domain.test_models import DiceModifier, InlineProfile, Skill, TestRequest
from towr.rules.test_resolution import resolve_test
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


PROFILES = (
    (PcBookNpcProfile.NASTY_SKULKER, InlineProfile(4,4), InlineProfile(3,3), 157),
    (PcBookNpcProfile.DWARF_BREWGUARD_WARHAMMER, InlineProfile(4,3), InlineProfile(2,3), 104),
    (PcBookNpcProfile.DWARF_MINER_PICKAXE, InlineProfile(4,3), InlineProfile(1,3,4), 105),
    (PcBookNpcProfile.BESTIGOR_MASSIVE_AXE, InlineProfile(4,4), InlineProfile(3,3,8), 144),
)


def book_source():
    return book_pc_scenario(footpads=0,townsfolk=0,skulkers=1,brewguards=1,
        miners=1,bestigors=1,pc_count=1)


def configured_source(skill=Skill.MELEE):
    base = book_source()
    member = base.party[0]
    member = replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.PISTOL,
        ranged=pistol_profile()))
    return replace(base,party=(member,),npc_close_shooting_protection_policies=tuple(
        Policy(actor,skill) for actor in base.enemy_activation_order))


class M58CloseShootingSourceTests(unittest.TestCase):
    def test_four_profiles_have_verified_skills_caps_pages_and_original_defence(self):
        for profile,melee,athletics,page in PROFILES:
            with self.subTest(profile=profile):
                entry = get_pc_book_npc_entry(profile)
                definition = entry.definition
                original = deepcopy(definition)
                self.assertEqual((entry.version,entry.page),('1.1',page))
                for skill,expected in ((Skill.MELEE,melee),(Skill.ATHLETICS,athletics)):
                    selected = pc_close_shooting_protection_profile(definition,skill)
                    self.assertIs(selected.skill,skill)
                    self.assertEqual(selected.test_profile,expected)
                    self.assertTrue(selected.source_rule_id.startswith(definition.source_rule_id+':'))
                self.assertEqual(definition,original)
                self.assertIs(definition.protection[0].skill,Skill.DEFENCE)
                self.assertIsNone(definition.protection[0].test_profile.pool_cap)

    def test_modified_athletics_pools_cap_at_original_agility_without_second_penalty(self):
        for profile,printed,cap in (
                (PcBookNpcProfile.DWARF_MINER_PICKAXE,1,4),
                (PcBookNpcProfile.BESTIGOR_MASSIVE_AXE,3,8)):
            with self.subTest(profile=profile):
                entry = get_pc_book_npc_entry(profile)
                selected = pc_close_shooting_protection_profile(entry.definition,Skill.ATHLETICS)
                self.assertEqual(selected,entry.unselected_protection[0])
                self.assertEqual((selected.test_profile.base_dice,selected.test_profile.threshold,
                    selected.test_profile.maximum_dice),(printed,3,cap))
                ordinary = resolve_test(TestRequest('printed',selected.test_profile),
                    SequenceRandom([1]*printed))
                bounded = resolve_test(TestRequest('bounded',selected.test_profile,
                    dice_modifiers=(DiceModifier('fixture:ordinary-bonus',10),)),
                    SequenceRandom([1]*cap))
                self.assertEqual(ordinary.trace.rolled_dice,printed)
                self.assertEqual((bounded.trace.rolled_dice,bounded.trace.pool_cap),(cap,cap))

    def test_bestigor_defensive_melee_is_not_reduced_massive_axe_attack_pool(self):
        definition = get_pc_book_npc_entry(PcBookNpcProfile.BESTIGOR_MASSIVE_AXE).definition
        attack = definition.attacks[0]
        selected = pc_close_shooting_protection_profile(definition,Skill.MELEE)
        self.assertEqual(attack.test_profile,InlineProfile(3,4,8))
        self.assertEqual(selected.test_profile,InlineProfile(4,4))
        self.assertEqual(selected.test_profile.maximum_dice,8)
        self.assertEqual(attack.damage.base,7)
        rage = next(ability for ability in get_pc_book_npc_entry(
            PcBookNpcProfile.BESTIGOR_MASSIVE_AXE).active_abilities if ability.name=='Blood Rage')
        self.assertIn('Melee attacks',rage.effect)

    def test_whole_chunk_admits_both_skills_without_changing_selected_definitions(self):
        original = book_source()
        for skill in (Skill.MELEE,Skill.ATHLETICS):
            source = configured_source(skill)
            validate_pc_melee_scenario_admission(source)
            self.assertEqual(source.enemies,original.enemies)
            self.assertEqual(len(source.npc_close_shooting_protection_policies),4)
            self.assertTrue(all(policy.skill is skill for policy in
                source.npc_close_shooting_protection_policies))

    def test_new_sources_reject_full_definition_forgery_and_equal_skill_aliases(self):
        class Alias(str,Enum):
            MELEE = 'melee'
        for profile,_,_,_ in PROFILES:
            original = create_pc_book_npc(profile,'npc').definition
            for change in ('attack','defence','rename','cap'):
                forged = deepcopy(original)
                if change=='attack':
                    object.__setattr__(forged.attacks[0].damage,'base',99)
                elif change=='defence':
                    object.__setattr__(forged.protection[0].test_profile,'threshold',1)
                elif change=='rename':
                    object.__setattr__(forged,'id','authored:renamed')
                else:
                    object.__setattr__(forged.attacks[0].test_profile,'pool_cap',True)
                with self.subTest(profile=profile,change=change),self.assertRaises((TypeError,ValueError)):
                    pc_close_shooting_protection_profile(forged,Skill.MELEE)
            for skill in (Alias.MELEE,'melee',True):
                with self.subTest(profile=profile,skill=skill),self.assertRaises(TypeError):
                    pc_close_shooting_protection_profile(original,skill)

    def test_forged_native_policy_and_selected_cap_are_rejected_before_rng(self):
        request = PcMeleeSimulationRequest(configured_source(),42,1)
        for change in ('policy','book_profile'):
            forged = deepcopy(request)
            if change=='policy':
                object.__setattr__(forged.scenario.npc_close_shooting_protection_policies[0],
                    'skill','melee')
            else:
                object.__setattr__(forged.scenario.enemies[0].definition.protection[0].test_profile,
                    'pool_cap',8)
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                with self.subTest(change=change),self.assertRaises((TypeError,ValueError)):
                    run_pc_melee_trial(forged,0,rng_factory=rng)
                rng.assert_not_called()

    def test_existing_and_unsupported_sources_keep_exact_scope(self):
        for profile in (PcBookNpcProfile.EMPIRE_STATE_TROOPER_HALBERD,
                PcBookNpcProfile.ORC_BOY_CHOPPAS):
            definition = create_pc_book_npc(profile,'old').definition
            self.assertIs(pc_close_shooting_protection_profile(definition,Skill.MELEE).skill,Skill.MELEE)
        for definition in (make_pc_pistol_scenario().enemies[0].definition,
                create_pc_book_npc(PcBookNpcProfile.HALFLING_THIEF_DAGGER,'other').definition):
            with self.assertRaises(ValueError):
                pc_close_shooting_protection_profile(definition,Skill.MELEE)


if __name__ == '__main__':
    unittest.main()
