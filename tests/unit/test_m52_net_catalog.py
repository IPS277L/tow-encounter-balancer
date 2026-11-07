"""Printed finite Net loadout, exact primary impact and source admission."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from towr.domain.attack_models import ConditionImpactSpec, DamageProfile, ResilienceProfile
from towr.domain.condition_models import Condition, EffectClassification
from towr.domain.pc_melee_models import validate_pc_melee_scenario_admission
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile,create_pc_book_npc,get_pc_book_npc_entry,validate_pc_book_npc_definition,
)
from towr.domain.pc_npc_net_policy_models import PcNpcNetMode,PcNpcNetPolicy
from towr.domain.ranged_weapon_profiles import RangedWeaponHands,RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile,Skill


PROFILE = PcBookNpcProfile.NIGHT_GOBLIN_NET_SPEAR
SOURCE = 'BOOK-GM-GUIDE:1.1:p157:night_goblin_net_spear'


def scene(**kwargs):
    return book_pc_scenario(footpads=0,townsfolk=0,net_goblins=1,**kwargs)


class NetCatalogTests(unittest.TestCase):
    def test_complete_printed_source_caps_hands_and_armoured_zero_bonus(self):
        entry = get_pc_book_npc_entry(PROFILE)
        definition = entry.definition
        self.assertEqual((entry.book_id,entry.version,entry.chapter,entry.page),
            ('BOOK-GM-GUIDE','1.1','Allies and Antagonists',157))
        self.assertEqual((definition.id,definition.source_rule_id,definition.injury_policy,definition.wound_limit),
            ('pc-book-npc:night_goblin_net_spear',SOURCE,TargetInjuryPolicy.MINION,1))
        self.assertEqual(definition.resilience,ResilienceProfile(3,armoured=True))
        self.assertTrue(definition.resilience.is_armoured)
        self.assertEqual(definition.resilience.bonus,0)
        spear,net = definition.attacks
        self.assertEqual((spear.id,spear.source_rule_id,spear.skill,spear.test_profile,spear.damage,
            spear.range_min,spear.range_max,spear.hands),
            ('jagged_spear',SOURCE+':jagged_spear',Skill.MELEE,InlineProfile(2,3),DamageProfile(3),
             RangedWeaponRange.CLOSE,RangedWeaponRange.SHORT,RangedWeaponHands.ONE_HANDED))
        self.assertEqual((net.id,net.source_rule_id,net.skill,net.test_profile,net.damage,
            net.range_min,net.range_max,net.hands),
            ('weighted_net',SOURCE+':weighted_net',Skill.THROWING,InlineProfile(2,3,6),None,
             RangedWeaponRange.CLOSE,RangedWeaponRange.SHORT,RangedWeaponHands.TWO_HANDED))
        self.assertEqual(net.condition_impact,ConditionImpactSpec(Condition.BURDENED,
            'RULE-EQUIPMENT-005:weighted-net-burdened',EffectClassification.UNCLASSIFIED))
        self.assertEqual((spear.test_profile.maximum_dice,net.test_profile.maximum_dice),(4,6))
        self.assertEqual((definition.protection[0].skill,definition.protection[0].test_profile),
            (Skill.ATHLETICS,InlineProfile(3,2)))
        self.assertEqual({ability.name for ability in entry.active_abilities},{'Dirty Coward','Horde'})
        self.assertEqual(entry.unselected_attack_names,('Shortbow',))
        validate_pc_book_npc_definition(definition)

    def test_fresh_independent_state_retains_stock_weapon_profiles_and_no_shield(self):
        first,second = (create_pc_book_npc(PROFILE,actor) for actor in ('one','two'))
        self.assertEqual(first.state.available_attack_ids,('jagged_spear','weighted_net'))
        self.assertTrue(first.state.wields_weapon)
        self.assertFalse(first.state.holds_shield)
        self.assertEqual(first.state.current_resilience,first.definition.resilience)
        self.assertIsNot(first.definition.attacks[1].condition_impact,second.definition.attacks[1].condition_impact)
        self.assertEqual(scene().npc_net_policies,(PcNpcNetPolicy('net_goblin1',1,PcNpcNetMode.THROW_ONCE_THEN_SPEAR),))

    def test_policy_is_exact_required_unique_and_in_canonical_enemy_order(self):
        source = book_pc_scenario(footpads=1,townsfolk=0,net_goblins=2)
        policies = source.npc_net_policies
        for invalid in ((),policies[:1],policies[::-1],(*policies,policies[0]),list(policies),
                (replace(policies[0],actor_id='footpad1'),policies[1])):
            with self.subTest(invalid=invalid),self.assertRaises((TypeError,ValueError)):
                replace(source,npc_net_policies=invalid)
        for changes in ({'initial_count':True},{'initial_count':0},{'initial_count':2},{'mode':'spear_only'}):
            with self.subTest(changes=changes),self.assertRaises((TypeError,ValueError)):
                replace(policies[0],**changes)
        replace(source,npc_net_policies=tuple(replace(p,mode=PcNpcNetMode.SPEAR_ONLY) for p in policies))

    def test_source_guard_reserves_secondary_sources_and_all_nested_types(self):
        definition = get_pc_book_npc_entry(PROFILE).definition
        for field,value in (('skill',Skill.MELEE),('test_profile',InlineProfile(3,3,6)),
                ('test_profile',InlineProfile(2,3)),('range_max',RangedWeaponRange.CLOSE),
                ('hands',RangedWeaponHands.ONE_HANDED)):
            net = replace(definition.attacks[1],**{field:value})
            with self.subTest(field=field,value=value),self.assertRaises((TypeError,ValueError)):
                validate_pc_book_npc_definition(replace(definition,attacks=(definition.attacks[0],net)))
        clone = replace(definition,id='authored:clone',source_rule_id='authored:source')
        with self.assertRaises(ValueError):
            validate_pc_book_npc_definition(clone)
        forged = deepcopy(scene())
        object.__setattr__(forged.enemies[0].definition.attacks[1].condition_impact,'condition','burdened')
        with self.assertRaises((TypeError,ValueError)):
            validate_pc_melee_scenario_admission(forged)

    def test_explicit_armour_metadata_and_extra_profile_are_closed_to_canonical_net(self):
        source = book_pc_scenario(footpads=1,townsfolk=0)
        enemy = source.enemies[0]
        for armoured in (True,False):
            resilience = replace(enemy.definition.resilience,armoured=armoured)
            with self.assertRaises(ValueError):
                replace(source,enemies=(replace(enemy,definition=replace(enemy.definition,resilience=resilience),
                    state=replace(enemy.state,current_resilience=resilience)),))
        net = get_pc_book_npc_entry(PROFILE).definition.attacks[1]
        with self.assertRaises((TypeError,ValueError)):
            replace(source,enemies=(replace(enemy,definition=replace(enemy.definition,
                attacks=(*enemy.definition.attacks,net)),state=replace(enemy.state,
                    available_attack_ids=(*enemy.state.available_attack_ids,net.id))),))
