"""GM156–157: exact melee Goblin loadouts, shields and printed variant replacement."""
from copy import deepcopy
from dataclasses import replace
import unittest

from towr.domain.attack_models import DamageProfile,ResilienceProfile
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile,create_pc_book_npc,get_pc_book_npc_entry,validate_pc_book_npc_definition,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands,RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile,Skill


WARRIOR=PcBookNpcProfile.GOBLIN_WARRIOR_SPEAR
SKULKER=PcBookNpcProfile.NASTY_SKULKER
NIGHT=PcBookNpcProfile.NIGHT_GOBLIN_SPEAR
CASES=(
    (WARRIOR,156,'jagged_spear',2,3,2,Skill.ATHLETICS,3,2,RangedWeaponRange.SHORT,True),
    (SKULKER,157,'long_knives',4,4,1,Skill.DEFENCE,4,4,RangedWeaponRange.CLOSE,False),
    (NIGHT,157,'jagged_spear',2,3,1,Skill.ATHLETICS,3,2,RangedWeaponRange.SHORT,True),
)


class PcGoblinCatalogTests(unittest.TestCase):
    def test_printed_profiles_keep_weapon_maximum_range_and_protection(self):
        for profile,page,attack_id,dice,threshold,bonus,skill,pdice,pthreshold,maximum,shield in CASES:
            with self.subTest(profile=profile):
                entry=get_pc_book_npc_entry(profile)
                definition=entry.definition
                source=f'BOOK-GM-GUIDE:1.1:p{page}:{profile.value}'
                self.assertEqual((entry.book_id,entry.version,entry.chapter,entry.page),
                    ('BOOK-GM-GUIDE','1.1','Allies and Antagonists',page))
                self.assertEqual((definition.id,definition.source_rule_id,definition.injury_policy,
                    definition.wound_limit,definition.resilience),
                    ('pc-book-npc:'+profile.value,source,TargetInjuryPolicy.MINION,1,ResilienceProfile(3,bonus)))
                attack,=definition.attacks
                self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,
                    attack.damage,attack.hands,attack.range_min,attack.range_max,
                    attack.ignores_armour,attack.secondary_effects),
                    (attack_id,source+':'+attack_id,Skill.MELEE,InlineProfile(dice,threshold),
                     DamageProfile(3),RangedWeaponHands.ONE_HANDED,RangedWeaponRange.CLOSE,maximum,False,()))
                protection,=definition.protection
                self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
                    (source+':'+skill.value,skill,InlineProfile(pdice,pthreshold)))
                validate_pc_book_npc_definition(definition)

    def test_shield_is_carried_without_adding_to_printed_resilience_twice(self):
        for profile,_,attack_id,_,_,bonus,*rest in CASES:
            with self.subTest(profile=profile):
                shield=rest[-1]
                actor=create_pc_book_npc(profile,'goblin')
                self.assertEqual((actor.state.wields_weapon,actor.state.holds_shield,
                    actor.state.current_resilience,actor.state.available_attack_ids),
                    (True,shield,ResilienceProfile(3,bonus),(attack_id,)))
                self.assertEqual(actor.state.current_resilience,actor.definition.resilience)
                self.assertTrue(actor.definition.resilience.is_armoured)
                self.assertEqual((actor.state.injury.wounds,actor.state.injury.wound_limit,
                    actor.state.injury.defeated),(0,1,False))
                self.assertFalse(actor.state.injury.conditions.conditions)
        # Night Goblin's explicit total4 replaces Warrior's5 while keeping its shield.
        warrior=create_pc_book_npc(WARRIOR,'warrior')
        night=create_pc_book_npc(NIGHT,'night')
        self.assertEqual((warrior.state.current_resilience.bonus,night.state.current_resilience.bonus),(2,1))
        self.assertTrue(warrior.state.holds_shield and night.state.holds_shield)

    def test_warrior_and_night_preserve_horde_dirty_coward_and_unused_attacks(self):
        for profile,unused in ((WARRIOR,('Shortbow',)),(NIGHT,('Weighted Net','Shortbow'))):
            with self.subTest(profile=profile):
                entry=get_pc_book_npc_entry(profile)
                self.assertEqual(entry.unselected_attack_names,unused)
                self.assertEqual(entry.unselected_protection,())
                self.assertEqual(entry.wound_bands,())
                self.assertIn('shield',entry.name)
                self.assertEqual(entry.inactive_abilities,())
                coward,horde=entry.active_abilities
                self.assertEqual(horde.name,'Horde')
                self.assertIn('Helps an ally make an attack',horde.scope)
                self.assertIn('Do not Test',horde.effect)
                self.assertIn('+1d',horde.effect)
                self.assertIn('exceed the usual bonus dice cap',horde.effect)
                self.assertEqual(coward.name,'Dirty Coward')
                self.assertIn('already Staggered',coward.scope)
                self.assertIn('receives Staggered again',coward.scope)
                self.assertIn('defeated without a Wound',coward.effect)
                self.assertIn('drops its weapon',coward.effect)
                self.assertIn('flees combat',coward.effect)

    def test_skulker_keeps_actual_unopposed_trigger_and_five_other_goblins(self):
        entry=get_pc_book_npc_entry(SKULKER)
        self.assertEqual((entry.unselected_attack_names,entry.wound_bands), ((),()))
        alternative,=entry.unselected_protection
        self.assertEqual((alternative.source_rule_id,alternative.skill,alternative.test_profile),
            ('BOOK-GM-GUIDE:1.1:p157:nasty_skulker:athletics',Skill.ATHLETICS,InlineProfile(3,3)))
        backstab,=entry.active_abilities
        self.assertEqual((backstab.name,backstab.scope),('Backstabba','A genuinely unopposed Melee attack'))
        self.assertIn('+1 additional Damage per success',backstab.effect)
        self.assertIn('+2 Damage per success in total',backstab.effect)
        menace,=entry.inactive_abilities
        self.assertEqual(menace.name,'Skulking Menace')
        self.assertIn('at least 5 other Goblins',menace.scope)
        self.assertIn('Stealth',menace.scope)
        self.assertIn('without cover or concealment',menace.effect)

    def test_canonical_identities_reject_wrong_resilience_range_damage_and_protection(self):
        for profile,_,_,_,_,bonus,*_ in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            attack,=definition.attacks
            protection,=definition.protection
            invalid=(replace(definition,resilience=ResilienceProfile(3,bonus+1)),
                replace(definition,attacks=(replace(attack,damage=DamageProfile(4)),)),
                replace(definition,attacks=(replace(attack,range_max=RangedWeaponRange.LONG),)),
                replace(definition,attacks=(replace(attack,skill=Skill.SHOOTING),)),
                replace(definition,protection=(replace(protection,test_profile=InlineProfile(2,2)),)),
                replace(definition,id='authored:goblin',source_rule_id='authored:source'),
                replace(definition,id='authored:goblin',source_rule_id='authored:source',
                    attacks=(replace(attack,source_rule_id='authored:attack'),)))
            for candidate in invalid:
                with self.subTest(profile=profile,candidate=candidate),self.assertRaises((TypeError,ValueError)):
                    validate_pc_book_npc_definition(candidate)
        skulker=get_pc_book_npc_entry(SKULKER)
        with self.assertRaises(ValueError):
            validate_pc_book_npc_definition(replace(skulker.definition,protection=skulker.unselected_protection))
        renamed=replace(skulker.definition,id='authored:root',source_rule_id='authored:source',
            attacks=(replace(skulker.definition.attacks[0],source_rule_id='authored:attack'),),
            protection=skulker.unselected_protection)
        with self.assertRaises(ValueError):
            validate_pc_book_npc_definition(renamed)

    def test_equal_alias_types_and_unknown_reserved_ids_are_rejected(self):
        for profile,*_ in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            for target,attribute,value in (('definition','injury_policy','minion'),
                    ('definition','wound_limit',True),('attack','hands','1h'),('attack','skill','melee')):
                forged=deepcopy(definition)
                subject=forged if target=='definition' else forged.attacks[0]
                object.__setattr__(subject,attribute,value)
                self.assertEqual(forged,definition)
                with self.subTest(profile=profile,attribute=attribute),self.assertRaises(TypeError):
                    validate_pc_book_npc_definition(forged)
            with self.assertRaises(TypeError):
                create_pc_book_npc(profile.value,'bad')
        attack,=definition.attacks
        protection,=definition.protection
        unknown=replace(definition,id='pc-book-npc:unknown-goblin',source_rule_id='authored:source',
            attacks=(replace(attack,source_rule_id='authored:attack'),),
            protection=(replace(protection,source_rule_id='authored:protection'),))
        with self.assertRaises(ValueError):
            validate_pc_book_npc_definition(unknown)

    def test_catalog_returns_fresh_nested_graphs_and_independent_injuries(self):
        for profile,*_ in CASES:
            with self.subTest(profile=profile):
                first=create_pc_book_npc(profile,'first')
                second=create_pc_book_npc(profile,'second')
                expected=deepcopy(second.definition)
                self.assertIsNot(first.definition,second.definition)
                self.assertIsNot(first.state.injury,second.state.injury)
                object.__setattr__(first.definition.attacks[0].damage,'base',99)
                self.assertEqual(second.definition,expected)
                self.assertEqual(get_pc_book_npc_entry(profile).definition,expected)
                with self.assertRaises(ValueError):
                    validate_pc_book_npc_definition(first.definition)
        first=get_pc_book_npc_entry(SKULKER)
        object.__setattr__(first.unselected_protection[0].test_profile,'dice',9)
        self.assertEqual(get_pc_book_npc_entry(SKULKER).unselected_protection[0].test_profile,InlineProfile(3,3))


if __name__=='__main__':
    unittest.main()
