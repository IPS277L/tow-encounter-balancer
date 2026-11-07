"""Complete M56 source admission and book-backed opposition profiles."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from enum import Enum
import pickle
import unittest
from unittest.mock import patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_pistol_scenarios import make_pc_pistol_scenario, pistol_profile
from towr.domain.pc_melee_models import (
    PcMeleeScenario, PcMeleeWeapon, validate_pc_melee_scenario_admission,
)
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile, create_pc_book_npc, get_pc_book_npc_entry,
)
from towr.domain.pc_npc_close_shooting_models import (
    PcNpcCloseShootingProtectionPolicy as Policy, pc_close_shooting_protection_profile,
)
from towr.domain.test_models import InlineProfile, Skill
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


PROFILES = (
    (PcBookNpcProfile.EMPIRE_STATE_TROOPER_HALBERD, InlineProfile(3,3), InlineProfile(3,3)),
    (PcBookNpcProfile.EMPIRE_STATE_TROOPER_SPEAR, InlineProfile(3,3), InlineProfile(3,3)),
    (PcBookNpcProfile.EMPIRE_KNIGHT_LANCE, InlineProfile(4,4), InlineProfile(2,3,6)),
    (PcBookNpcProfile.KNIGHT_WHITE_WOLF_HAMMER, InlineProfile(4,4), InlineProfile(2,3,6)),
)


def book_source():
    return book_pc_scenario(footpads=0,townsfolk=0,troopers=1,spear_troopers=1,
        empire_knights=1,wolf_knights=1,pc_count=1)


def configured_source(skill=Skill.MELEE):
    source = book_source()
    party = tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.PISTOL,
        pistol=pistol_profile())) for member in source.party)
    policies = tuple(Policy(actor,skill) for actor in source.enemy_activation_order)
    return replace(source,party=party,npc_close_shooting_protection_policies=policies)


class M56CloseShootingSourceTests(unittest.TestCase):
    def test_policy_is_closed_frozen_and_pickle_preserves_exact_skill(self):
        policy = Policy('trooper',Skill.MELEE)
        with self.assertRaises(FrozenInstanceError):
            policy.skill = Skill.ATHLETICS
        restored = pickle.loads(pickle.dumps(policy))
        self.assertEqual(restored,policy)
        self.assertIs(restored.skill,Skill.MELEE)
        class Alias(str,Enum):
            MELEE='melee'
        for actor in ('',True,1,None):
            with self.subTest(actor=actor),self.assertRaises(TypeError):
                Policy(actor,Skill.MELEE)
        for skill in ('melee',Alias.MELEE,True,None):
            with self.subTest(skill=skill),self.assertRaises(TypeError):
                Policy('trooper',skill)
        for skill in (Skill.DEFENCE,Skill.STEALTH,Skill.SHOOTING):
            with self.assertRaises(ValueError):
                Policy('trooper',skill)

    def test_optional_field_is_absent_by_default_and_requires_explicit_nonempty_tuple(self):
        source = make_pc_pistol_scenario()
        field = next(field for field in fields(PcMeleeScenario)
            if field.name=='npc_close_shooting_protection_policies')
        self.assertIsNone(field.default)
        self.assertTrue(field.kw_only)
        self.assertIsNone(source.npc_close_shooting_protection_policies)
        for value in ([],[Policy('minion1',Skill.MELEE)],{},True):
            with self.subTest(value=value),self.assertRaises(TypeError):
                replace(source,npc_close_shooting_protection_policies=value)
        with self.assertRaises(ValueError):
            replace(source,npc_close_shooting_protection_policies=())

    def test_each_profile_has_explicit_book_melee_and_printed_athletics_without_changing_defence(self):
        for profile,melee,athletics in PROFILES:
            with self.subTest(profile=profile):
                definition = create_pc_book_npc(profile,'enemy').definition
                original = deepcopy(definition)
                for skill,expected in ((Skill.MELEE,melee),(Skill.ATHLETICS,athletics)):
                    chosen = pc_close_shooting_protection_profile(definition,skill)
                    self.assertIs(chosen.skill,skill)
                    self.assertEqual(chosen.test_profile,expected)
                    self.assertTrue(chosen.source_rule_id.startswith(definition.source_rule_id+':'))
                self.assertEqual(definition,original)
                self.assertIs(definition.protection[0].skill,Skill.DEFENCE)

    def test_knight_athletics_uses_agility_cap_six_without_second_armour_penalty(self):
        for profile in (PcBookNpcProfile.EMPIRE_KNIGHT_LANCE,
                PcBookNpcProfile.KNIGHT_WHITE_WOLF_HAMMER):
            entry = get_pc_book_npc_entry(profile)
            chosen = pc_close_shooting_protection_profile(entry.definition,Skill.ATHLETICS)
            self.assertEqual(chosen,entry.unselected_protection[0])
            self.assertEqual((chosen.test_profile.base_dice,chosen.test_profile.threshold,
                chosen.test_profile.maximum_dice),(2,3,6))
            self.assertIsNone(entry.definition.protection[0].test_profile.pool_cap)
        shielded = get_pc_book_npc_entry(PcBookNpcProfile.EMPIRE_KNIGHT_LANCE_SHIELD)
        self.assertIsNone(shielded.unselected_protection[0].test_profile.pool_cap)

    def test_helper_rejects_other_canonical_authored_and_equal_skill_aliases(self):
        for definition in (make_pc_pistol_scenario().enemies[0].definition,
                create_pc_book_npc(PcBookNpcProfile.FOOTPAD,'footpad').definition,
                create_pc_book_npc(PcBookNpcProfile.EMPIRE_KNIGHT_LANCE_SHIELD,'knight').definition):
            with self.subTest(definition=definition.id),self.assertRaises(ValueError):
                pc_close_shooting_protection_profile(definition,Skill.MELEE)
        definition = create_pc_book_npc(PROFILES[0][0],'trooper').definition
        for skill in ('melee',True,None):
            with self.assertRaises(TypeError):
                pc_close_shooting_protection_profile(definition,skill)
        with self.assertRaises(ValueError):
            pc_close_shooting_protection_profile(definition,Skill.DEFENCE)

    def test_helper_readmits_full_definition_not_just_the_reserved_id(self):
        original = create_pc_book_npc(PROFILES[0][0],'trooper').definition
        for change in ('damage','protection','partial_rename','cap_alias'):
            forged = deepcopy(original)
            if change=='damage':
                object.__setattr__(forged.attacks[0].damage,'base',99)
            elif change=='protection':
                object.__setattr__(forged.protection[0].test_profile,'threshold',1)
            elif change=='partial_rename':
                object.__setattr__(forged,'id','authored:trooper')
            else:
                object.__setattr__(forged.attacks[0].test_profile,'pool_cap',True)
            with self.subTest(change=change),self.assertRaises((TypeError,ValueError)):
                pc_close_shooting_protection_profile(forged,Skill.MELEE)

    def test_full_four_actor_source_allows_each_skill_but_never_changes_selected_definition(self):
        source = book_source()
        for skill in (Skill.MELEE,Skill.ATHLETICS):
            configured = configured_source(skill)
            validate_pc_melee_scenario_admission(configured)
            self.assertEqual(configured.enemies,source.enemies)
            self.assertEqual(len(configured.npc_close_shooting_protection_policies),4)
        with self.assertRaisesRegex(ValueError,'Pistol opponents'):
            replace(configured_source(),npc_close_shooting_protection_policies=None)

    def test_policies_require_existing_opposition_actors_a_pistol_and_unique_actors(self):
        source = configured_source()
        policy = source.npc_close_shooting_protection_policies[0]
        for policies in ((policy,policy),(replace(policy,actor_id='pc1'),),
                (replace(policy,actor_id='missing'),),({'actor_id':policy.actor_id,'skill':'melee'},)):
            with self.subTest(policies=policies),self.assertRaises((TypeError,ValueError)):
                replace(source,npc_close_shooting_protection_policies=policies)
        with self.assertRaisesRegex(ValueError,'require a Pistol'):
            replace(book_source(),npc_close_shooting_protection_policies=(policy,))

    def test_policy_for_unsupported_or_forged_full_source_is_rejected_before_rng(self):
        request = PcMeleeSimulationRequest(configured_source(),42,1)
        for change in ('actor','skill','profile','tuple'):
            forged = deepcopy(request)
            source = forged.scenario
            if change=='actor':
                object.__setattr__(source.npc_close_shooting_protection_policies[0],'actor_id','pc1')
            elif change=='skill':
                object.__setattr__(source.npc_close_shooting_protection_policies[0],'skill','melee')
            elif change=='profile':
                object.__setattr__(source.enemies[0].definition.attacks[0].test_profile,'dice',99)
            else:
                object.__setattr__(source,'npc_close_shooting_protection_policies',list(
                    source.npc_close_shooting_protection_policies))
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                with self.subTest(change=change),self.assertRaises((TypeError,ValueError)):
                    run_pc_melee_trial(forged,0,rng_factory=rng)
                rng.assert_not_called()


if __name__=='__main__':
    unittest.main()
