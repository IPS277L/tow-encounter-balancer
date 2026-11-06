"""GM107/121/143: three exact Minion cards and their distinct Ability scopes."""
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


CASES=(
    (PcBookNpcProfile.SIGMARITE_CULTIST_WARHAMMER,121,'warhammer',3,3,
        RangedWeaponRange.CLOSE,RangedWeaponHands.ONE_HANDED,0,3,2,False),
    (PcBookNpcProfile.ELF_MILITIA_SPEAR,107,'spear',4,4,
        RangedWeaponRange.SHORT,RangedWeaponHands.TWO_HANDED,1,4,3,False),
    (PcBookNpcProfile.UNGOR_SPEAR,143,'crude_spear',3,3,
        RangedWeaponRange.SHORT,RangedWeaponHands.ONE_HANDED,1,4,2,True),
)


class PcMinionCatalogTests(unittest.TestCase):
    def test_printed_attacks_protection_and_resilience_have_full_book_identity(self):
        for profile,page,attack_id,dice,damage,maximum,hands,bonus,pdice,threshold,_ in CASES:
            with self.subTest(profile=profile):
                entry=get_pc_book_npc_entry(profile)
                definition=entry.definition
                source=f'BOOK-GM-GUIDE:1.1:p{page}:{profile.value}'
                self.assertEqual((entry.profile_id,entry.book_id,entry.version,entry.chapter,entry.page),
                    (profile,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',page))
                self.assertEqual((definition.id,definition.source_rule_id,definition.injury_policy,
                    definition.wound_limit,definition.resilience),
                    ('pc-book-npc:'+profile.value,source,TargetInjuryPolicy.MINION,1,
                     ResilienceProfile(3,bonus)))
                attack,=definition.attacks
                self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,
                    attack.damage,attack.range_min,attack.range_max,attack.hands,
                    attack.ignores_armour,attack.secondary_effects),
                    (attack_id,source+':'+attack_id,Skill.MELEE,InlineProfile(dice,3),
                     DamageProfile(damage),RangedWeaponRange.CLOSE,maximum,hands,False,()))
                protection,=definition.protection
                self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
                    (source+':athletics',Skill.ATHLETICS,InlineProfile(pdice,threshold)))
                self.assertEqual((entry.wound_bands,entry.unselected_protection,entry.unselected_variant_names),
                    ((),(),()))
                validate_pc_book_npc_definition(definition)

    def test_fresh_armed_loadouts_retain_only_the_printed_ungor_shield(self):
        for profile,_,attack_id,_,_,_,_,bonus,_,_,shield in CASES:
            with self.subTest(profile=profile):
                snapshot=create_pc_book_npc(profile,'npc')
                self.assertEqual((snapshot.state.actor_id,snapshot.state.definition_id,
                    snapshot.state.wields_weapon,snapshot.state.holds_shield,
                    snapshot.state.current_resilience,snapshot.state.available_attack_ids),
                    ('npc','pc-book-npc:'+profile.value,True,shield,ResilienceProfile(3,bonus),(attack_id,)))
                self.assertEqual((snapshot.state.injury.wounds,snapshot.state.injury.wound_limit,
                    snapshot.state.injury.defeated,snapshot.state.injury.defeat_cause),(0,1,False,None))
                self.assertFalse(snapshot.state.injury.conditions.conditions)

    def test_cultist_preserves_melee_only_no_test_cap_bypassing_help(self):
        entry=get_pc_book_npc_entry(PcBookNpcProfile.SIGMARITE_CULTIST_WARHAMMER)
        self.assertEqual(entry.inactive_abilities,())
        self.assertEqual(entry.unselected_attack_names,())
        ability,=entry.active_abilities
        self.assertEqual(ability.name,'Torches and Pitchforks')
        self.assertIn('Sigmarite Cultist Helps an ally make a Melee attack',ability.scope)
        for detail in ('Do not Test','+1d','Attack Test','exceed the usual bonus dice cap'):
            self.assertIn(detail,ability.effect)

    def test_elf_preserves_another_unengaged_militia_opposition_trigger(self):
        entry=get_pc_book_npc_entry(PcBookNpcProfile.ELF_MILITIA_SPEAR)
        self.assertEqual(entry.active_abilities,())
        self.assertEqual(entry.unselected_attack_names,('Longbow',))
        ability,=entry.inactive_abilities
        self.assertEqual(ability.name,'Martial Prowess')
        for detail in ('Opposing a Melee attack','another Elf Militia','same Zone',
                'not in Close Range of an enemy'):
            self.assertIn(detail,ability.scope)
        self.assertEqual(ability.effect,'+1d on that opposition Test')

    def test_ungor_preserves_target_staggered_spite_and_woodland_terrain_scope(self):
        entry=get_pc_book_npc_entry(PcBookNpcProfile.UNGOR_SPEAR)
        self.assertEqual(entry.unselected_attack_names,('Shortbow',))
        spite,=entry.active_abilities
        self.assertEqual((spite.name,spite.scope,spite.effect),
            ('Primal Spite','Attacks against an enemy who is Staggered','+1d on those Attack Tests'))
        forest,=entry.inactive_abilities
        self.assertEqual((forest.name,forest.scope,forest.effect),
            ('Child of the Forest','Difficult Terrain in woodland','Ignore the effects of that Difficult Terrain'))
        self.assertIn('shield',entry.name)

    def test_partial_source_renaming_and_changed_stats_cannot_claim_a_book_loadout(self):
        for profile,*_ in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            attack,=definition.attacks
            protection,=definition.protection
            invalid=(
                replace(definition,resilience=ResilienceProfile(3,2)),
                replace(definition,attacks=(replace(attack,damage=DamageProfile(9)),)),
                replace(definition,attacks=(replace(attack,range_max=RangedWeaponRange.MEDIUM),)),
                replace(definition,protection=(replace(protection,test_profile=InlineProfile(1,1)),)),
                replace(definition,id='authored:root',source_rule_id='authored:source'),
                replace(definition,id='authored:root',source_rule_id='authored:source',
                    attacks=(replace(attack,source_rule_id='authored:attack'),)),
                replace(definition,id='authored:root',source_rule_id='authored:source',
                    protection=(replace(protection,source_rule_id='authored:protection'),)),
            )
            for candidate in invalid:
                with self.subTest(profile=profile,candidate=candidate),self.assertRaises((TypeError,ValueError)):
                    validate_pc_book_npc_definition(candidate)

    def test_equal_string_enums_and_boolean_integers_are_not_canonical_book_types(self):
        for profile,*_ in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            aliases=(('definition','injury_policy','minion'),('definition','wound_limit',True),
                ('attack','hands',definition.attacks[0].hands.value),('attack','skill','melee'),
                ('attack','range_max',definition.attacks[0].range_max.value),
                ('damage','success_multiplier',True))
            for target,name,value in aliases:
                forged=deepcopy(definition)
                subject={'definition':forged,'attack':forged.attacks[0],'damage':forged.attacks[0].damage}[target]
                object.__setattr__(subject,name,value)
                self.assertEqual(forged,definition)
                with self.subTest(profile=profile,target=target,name=name),self.assertRaises(TypeError):
                    validate_pc_book_npc_definition(forged)
            with self.assertRaises(TypeError):
                get_pc_book_npc_entry(profile.value)

    def test_every_factory_call_has_independent_definition_and_injury_graphs(self):
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


if __name__=='__main__':
    unittest.main()
