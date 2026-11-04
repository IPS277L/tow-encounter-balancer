"""Printed GM1.1 combat profiles and strict independent catalog factories."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from enum import Enum
import unittest
from unittest.mock import patch

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.pc_npc_catalog import (PcBookNpcProfile,get_pc_book_npc_entry,
    create_pc_book_npc,validate_pc_book_npc_definition)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands,RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile,Skill
from towr.domain.turn_models import CombatSide


class ForeignSkill(str,Enum):
    ATHLETICS = 'athletics'


class CatalogTests(unittest.TestCase):
    def test_printed_sources_and_profiles_are_exact_including_townsfolk_two_dice(self):
        cases = ((PcBookNpcProfile.FOOTPAD,97,'Footpad',3,'Lurker'),
            (PcBookNpcProfile.EMPIRE_TOWNSFOLK,96,'Empire Townsfolk',2,'Streetwise'))
        for profile,page,name,dice,ability in cases:
            with self.subTest(profile=profile):
                entry = get_pc_book_npc_entry(profile)
                self.assertEqual((entry.profile_id,entry.book_id,entry.version,entry.chapter,entry.page,entry.name),
                    (profile,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',page,name))
                definition = entry.definition
                self.assertEqual((definition.id,definition.source_rule_id),
                    ('pc-book-npc:'+profile.value,f'BOOK-GM-GUIDE:1.1:p{page}:{profile.value}'))
                self.assertEqual((definition.injury_policy,definition.wound_limit,definition.resilience),
                    (TargetInjuryPolicy.MINION,1,ResilienceProfile(3)))
                attack, = definition.attacks
                self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,attack.damage,
                    attack.range_min,attack.range_max,attack.hands,attack.ignores_armour,attack.secondary_effects),
                    ('dagger',definition.source_rule_id+':dagger',Skill.MELEE,InlineProfile(dice,dice),DamageProfile(2),
                     RangedWeaponRange.CLOSE,RangedWeaponRange.CLOSE,RangedWeaponHands.ONE_HANDED,False,()))
                protection, = definition.protection
                self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
                    (definition.source_rule_id+':athletics',Skill.ATHLETICS,InlineProfile(dice,dice)))
                self.assertEqual(tuple(item.name for item in entry.inactive_abilities),(ability,))
                self.assertIn('Awareness',entry.inactive_abilities[0].scope)
                self.assertEqual(entry.inactive_abilities[0].effect,
                    'Grim Awareness Test' if profile is PcBookNpcProfile.FOOTPAD else '+1d Awareness')
                validate_pc_book_npc_definition(definition)

    def test_metadata_is_frozen_and_catalog_calls_return_fresh_complete_graphs(self):
        first = get_pc_book_npc_entry(PcBookNpcProfile.FOOTPAD)
        second = get_pc_book_npc_entry(PcBookNpcProfile.FOOTPAD)
        self.assertEqual(first,second)
        self.assertIsNot(first,second)
        for left,right in ((first.definition,second.definition),
                (first.definition.resilience,second.definition.resilience),
                (first.definition.attacks[0],second.definition.attacks[0]),
                (first.definition.attacks[0].test_profile,second.definition.attacks[0].test_profile),
                (first.definition.attacks[0].damage,second.definition.attacks[0].damage),
                (first.definition.protection[0],second.definition.protection[0]),
                (first.definition.protection[0].test_profile,second.definition.protection[0].test_profile),
                (first.inactive_abilities[0],second.inactive_abilities[0])):
            self.assertIsNot(left,right)
        with self.assertRaises(FrozenInstanceError):
            first.name = 'changed'

    def test_snapshots_are_independent_healthy_armed_opposition_minions(self):
        first = create_pc_book_npc(PcBookNpcProfile.FOOTPAD,'footpad1')
        second = create_pc_book_npc(PcBookNpcProfile.FOOTPAD,'footpad2')
        self.assertIsNot(first.definition,second.definition)
        self.assertIsNot(first.state,second.state)
        self.assertIsNot(first.state.injury,second.state.injury)
        self.assertIsNot(first.state.current_resilience,second.state.current_resilience)
        self.assertEqual((first.state.actor_id,first.state.definition_id,first.state.side),
            ('footpad1','pc-book-npc:footpad',CombatSide.OPPOSITION))
        self.assertEqual((first.state.injury.wounds,first.state.injury.wound_limit,first.state.injury.defeated),
            (0,1,False))
        self.assertEqual(first.state.injury.conditions.conditions,frozenset())
        self.assertEqual((first.state.available_attack_ids,first.state.current_resilience,
            first.state.wields_weapon,first.state.holds_shield),(('dagger',),ResilienceProfile(3),True,False))
        object.__setattr__(first.definition.attacks[0].damage,'base',9)
        self.assertEqual(second.definition.attacks[0].damage,DamageProfile(2))
        fresh = get_pc_book_npc_entry(PcBookNpcProfile.FOOTPAD).definition
        self.assertEqual(fresh.attacks[0].damage,DamageProfile(2))
        with self.assertRaises(ValueError):
            validate_pc_book_npc_definition(first.definition)

    def test_reserved_id_or_known_source_cannot_claim_an_altered_profile(self):
        definition = get_pc_book_npc_entry(PcBookNpcProfile.FOOTPAD).definition
        attack, = definition.attacks
        protection, = definition.protection
        forged = (replace(definition,id='pc-book-npc:unknown'),
            replace(definition,id='pc-book-npc:unknown',source_rule_id='authored:unknown'),
            replace(definition,id='authored:fake-book'),replace(definition,source_rule_id='authored:fake-source'),
            replace(definition,resilience=ResilienceProfile(4)),
            replace(definition,attacks=(replace(attack,damage=DamageProfile(3)),)),
            replace(definition,attacks=(replace(attack,test_profile=InlineProfile(3,3,4)),)),
            replace(definition,attacks=(replace(attack,source_rule_id='authored:attack'),)),
            replace(definition,protection=(replace(protection,skill=Skill.DEFENCE),)),
            replace(definition,protection=(replace(protection,test_profile=InlineProfile(3,2)),)))
        for candidate in forged:
            with self.subTest(candidate=candidate),self.assertRaises((ValueError,TypeError)):
                validate_pc_book_npc_definition(candidate)

    def test_equal_aliases_bools_and_noncanonical_containers_are_rejected(self):
        canonical = get_pc_book_npc_entry(PcBookNpcProfile.EMPIRE_TOWNSFOLK).definition
        cases = (('wound_limit',True),('injury_policy','minion'),('attacks',list(canonical.attacks)))
        for name,value in cases:
            forged = deepcopy(canonical)
            object.__setattr__(forged,name,value)
            with self.subTest(name=name),self.assertRaises(TypeError):
                validate_pc_book_npc_definition(forged)
        for value in ('athletics',ForeignSkill.ATHLETICS):
            forged = deepcopy(canonical)
            object.__setattr__(forged.protection[0],'skill',value)
            with self.subTest(value=value),self.assertRaises(TypeError):
                validate_pc_book_npc_definition(forged)
        forged = deepcopy(canonical)
        object.__setattr__(forged.resilience,'bonus',False)
        with self.assertRaises(TypeError):
            validate_pc_book_npc_definition(forged)
        forged = deepcopy(canonical)
        object.__setattr__(forged.attacks[0],'ignores_armour',0)
        with self.assertRaises(TypeError):
            validate_pc_book_npc_definition(forged)

    def test_unreserved_authored_numeric_definition_remains_accepted(self):
        authored = make_pc_melee_scenario().enemies[0].definition
        self.assertIsNone(validate_pc_book_npc_definition(authored))
        changed = replace(authored,resilience=ResilienceProfile(7))
        self.assertIsNone(validate_pc_book_npc_definition(changed))

    def test_nested_book_sources_remain_reserved_after_both_root_ids_are_renamed(self):
        for profile in PcBookNpcProfile:
            definition = get_pc_book_npc_entry(profile).definition
            attack, = definition.attacks
            protection, = definition.protection
            for claimed_part in ('attack','protection'):
                with self.subTest(profile=profile,claimed_part=claimed_part):
                    forged = replace(definition,id='authored:renamed',source_rule_id='authored:renamed-source',
                        attacks=(replace(attack,damage=DamageProfile(9),
                            source_rule_id=attack.source_rule_id if claimed_part=='attack' else 'authored:attack'),),
                        protection=(replace(protection,source_rule_id=protection.source_rule_id
                            if claimed_part=='protection' else 'authored:protection'),))
                    with self.assertRaises(ValueError):
                        validate_pc_book_npc_definition(forged)
            custom = replace(definition,id='authored:custom',source_rule_id='authored:custom-source',
                attacks=(replace(attack,damage=DamageProfile(9),source_rule_id='authored:attack'),),
                protection=(replace(protection,source_rule_id='authored:protection'),))
            self.assertIsNone(validate_pc_book_npc_definition(custom))

    def test_authored_profiles_return_before_building_any_canonical_graph(self):
        authored = make_pc_melee_scenario().enemies[0].definition
        with patch('towr.domain.pc_npc_catalog._definition',side_effect=AssertionError('unexpected catalog build')):
            self.assertIsNone(validate_pc_book_npc_definition(authored))

    def test_factory_inputs_require_exact_profile_enum_and_actor_id(self):
        for value in ('footpad',None,True):
            with self.subTest(value=value),self.assertRaises(TypeError):
                get_pc_book_npc_entry(value)
        for actor in ('', '   '):
            with self.subTest(actor=actor),self.assertRaises(ValueError):
                create_pc_book_npc(PcBookNpcProfile.FOOTPAD,actor)
        for actor in (False,1,None):
            with self.subTest(actor=actor),self.assertRaises(TypeError):
                create_pc_book_npc(PcBookNpcProfile.FOOTPAD,actor)


if __name__ == '__main__':
    unittest.main()
