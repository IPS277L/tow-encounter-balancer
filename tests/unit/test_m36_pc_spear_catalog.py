"""GM100/158/159: exact one-handed spear loadouts and retained shield totals."""
from copy import deepcopy
from dataclasses import replace
import unittest

from towr.domain.attack_models import DamageProfile,ResilienceProfile
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile,PcBookNpcWoundBand,create_pc_book_npc,get_pc_book_npc_entry,
    validate_pc_book_npc_definition,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands,RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile,Skill


CASES=(
    (PcBookNpcProfile.EMPIRE_STATE_TROOPER_SPEAR,100,'spear',3,3,3,1,
        TargetInjuryPolicy.MINION,1,False),
    (PcBookNpcProfile.ORC_BOY_SPEAR_SHIELD,158,'jagged_spear',4,3,4,2,
        TargetInjuryPolicy.MINION,1,True),
    (PcBookNpcProfile.BIG_UN_SPEAR_SHIELD,159,'jagged_spear',4,4,4,2,
        TargetInjuryPolicy.BRUTE,2,True),
)


class PcSpearCatalogTests(unittest.TestCase):
    def test_three_exact_short_spears_defence_and_alternative_athletics(self):
        for profile,page,attack_id,threshold,damage,toughness,bonus,policy,limit,_ in CASES:
            with self.subTest(profile=profile):
                entry=get_pc_book_npc_entry(profile)
                definition=entry.definition
                source=f'BOOK-GM-GUIDE:1.1:p{page}:{profile.value}'
                self.assertEqual((entry.profile_id,entry.book_id,entry.version,entry.chapter,entry.page),
                    (profile,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',page))
                self.assertEqual((definition.id,definition.source_rule_id,definition.injury_policy,
                    definition.wound_limit,definition.resilience),
                    ('pc-book-npc:'+profile.value,source,policy,limit,ResilienceProfile(toughness,bonus)))
                attack,=definition.attacks
                self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,
                    attack.damage,attack.range_min,attack.range_max,attack.hands,
                    attack.ignores_armour,attack.secondary_effects),
                    (attack_id,source+':'+attack_id,Skill.MELEE,InlineProfile(3,threshold),
                     DamageProfile(damage),RangedWeaponRange.CLOSE,RangedWeaponRange.SHORT,
                     RangedWeaponHands.ONE_HANDED,False,()))
                protection,=definition.protection
                self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
                    (source+':defence',Skill.DEFENCE,InlineProfile(3,4)))
                alternative,=entry.unselected_protection
                self.assertEqual((alternative.source_rule_id,alternative.skill,alternative.test_profile),
                    (source+':athletics',Skill.ATHLETICS,InlineProfile(3,3)))
                validate_pc_book_npc_definition(definition)

    def test_fresh_spear_orcs_retain_shield_without_adding_it_to_printed_resilience_again(self):
        for profile,_,attack_id,_,_,toughness,bonus,_,limit,shield in CASES:
            with self.subTest(profile=profile):
                snapshot=create_pc_book_npc(profile,'npc')
                self.assertEqual((snapshot.state.actor_id,snapshot.state.definition_id,
                    snapshot.state.wields_weapon,snapshot.state.holds_shield,
                    snapshot.state.current_resilience,snapshot.state.available_attack_ids),
                    ('npc','pc-book-npc:'+profile.value,True,shield,ResilienceProfile(toughness,bonus),(attack_id,)))
                self.assertIs(snapshot.state.holds_shield,shield)
                self.assertEqual((snapshot.state.injury.wounds,snapshot.state.injury.wound_limit,
                    snapshot.state.injury.defeated,snapshot.state.injury.defeat_cause),(0,limit,False,None))
                self.assertFalse(snapshot.state.injury.conditions.conditions)
                self.assertTrue(snapshot.definition.resilience.is_armoured)
                self.assertEqual(snapshot.state.current_resilience.total,4 if not shield else 6)

    def test_trooper_supporting_action_keeps_entire_entry_and_adjacent_unengaged_trigger(self):
        entry=get_pc_book_npc_entry(PcBookNpcProfile.EMPIRE_STATE_TROOPER_SPEAR)
        self.assertEqual(entry.active_abilities,())
        support,=entry.inactive_abilities
        self.assertEqual(support.name,'Supporting Action')
        for detail in ('enemy moves into Close Range of a State Trooper','allied State Trooper',
                'Free Company Militia','adjacent Zone','not in Close Range of an enemy'):
            self.assertIn(detail,support.scope)
        self.assertIn('One eligible ally',support.effect)
        self.assertIn('immediately Charge or make a ranged attack',support.effect)
        self.assertEqual(entry.unselected_attack_names,('Halberd','Crossbow','Handgun'))
        self.assertEqual((entry.wound_bands,entry.unselected_variant_names),((),()))

    def test_orc_cards_keep_spear_charge_free_success_help_and_only_big_un_wound_bands(self):
        for profile in (PcBookNpcProfile.ORC_BOY_SPEAR_SHIELD,PcBookNpcProfile.BIG_UN_SPEAR_SHIELD):
            with self.subTest(profile=profile):
                entry=get_pc_book_npc_entry(profile)
                charge,=entry.inactive_abilities
                self.assertEqual((charge.name,charge.scope,charge.effect),
                    ('Jagged Spear on Charge','An attack as part of a Charge','+1 Damage'))
                help_ability,=entry.active_abilities
                self.assertEqual(help_ability.name,'Power of the Waaagh!')
                self.assertIn('Helps an ally make a Melee attack',help_ability.scope)
                self.assertEqual(help_ability.effect,'Do not Test; the ally gains 1 free success on that Attack Test')
                self.assertEqual(entry.unselected_attack_names,('Couple of Choppas','Warbow'))
                self.assertEqual(entry.unselected_variant_names,('Mounted on Giant Boar',))
                self.assertIn('shield',entry.name)
                expected=((PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'Drained'),
                    PcBookNpcWoundBand(2,'Defeated')) if profile is PcBookNpcProfile.BIG_UN_SPEAR_SHIELD else ())
                self.assertEqual(entry.wound_bands,expected)

    def test_new_spears_are_distinct_from_existing_two_handed_loadouts(self):
        alternatives=((PcBookNpcProfile.EMPIRE_STATE_TROOPER_SPEAR,PcBookNpcProfile.EMPIRE_STATE_TROOPER_HALBERD,3,5),
            (PcBookNpcProfile.ORC_BOY_SPEAR_SHIELD,PcBookNpcProfile.ORC_BOY_CHOPPAS,3,4),
            (PcBookNpcProfile.BIG_UN_SPEAR_SHIELD,PcBookNpcProfile.BIG_UN_CHOPPAS,4,5))
        for selected,other,damage,other_damage in alternatives:
            with self.subTest(profile=selected):
                spear=get_pc_book_npc_entry(selected).definition
                old=get_pc_book_npc_entry(other).definition
                self.assertNotEqual(spear.id,old.id)
                self.assertEqual((spear.attacks[0].damage.base,old.attacks[0].damage.base),(damage,other_damage))
                self.assertIs(old.attacks[0].hands,RangedWeaponHands.TWO_HANDED)
                self.assertIs(old.attacks[0].range_max,RangedWeaponRange.CLOSE)
                self.assertFalse(create_pc_book_npc(other,'old').state.holds_shield)
                validate_pc_book_npc_definition(old)

    def test_whole_and_unused_book_sources_reject_changed_stats_or_partial_renaming(self):
        for profile,*_ in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            attack,=definition.attacks
            protection,=definition.protection
            alternative,=get_pc_book_npc_entry(profile).unselected_protection
            invalid=(
                replace(definition,resilience=ResilienceProfile(definition.resilience.toughness,
                    definition.resilience.bonus+1)),
                replace(definition,attacks=(replace(attack,damage=DamageProfile(9)),)),
                replace(definition,attacks=(replace(attack,hands=RangedWeaponHands.TWO_HANDED),)),
                replace(definition,attacks=(replace(attack,range_max=RangedWeaponRange.CLOSE),)),
                replace(definition,protection=(alternative,)),
                replace(definition,id='authored:root',source_rule_id='authored:source'),
                replace(definition,id='authored:root',source_rule_id='authored:source',
                    attacks=(replace(attack,source_rule_id='authored:attack'),)),
                replace(definition,id='authored:root',source_rule_id='authored:source',
                    attacks=(replace(attack,source_rule_id='authored:attack'),),
                    protection=(replace(protection,source_rule_id=alternative.source_rule_id),)),
            )
            for candidate in invalid:
                with self.subTest(profile=profile,candidate=candidate),self.assertRaises((TypeError,ValueError)):
                    validate_pc_book_npc_definition(candidate)

    def test_equal_string_enums_and_boolean_damage_aliases_are_not_canonical(self):
        for profile,*_ in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            for target,name,value in (('definition','injury_policy',definition.injury_policy.value),
                    ('attack','skill','melee'),('attack','hands','1h'),('attack','range_max','short'),
                    ('damage','success_multiplier',True)):
                forged=deepcopy(definition)
                subject={'definition':forged,'attack':forged.attacks[0],'damage':forged.attacks[0].damage}[target]
                object.__setattr__(subject,name,value)
                self.assertEqual(forged,definition)
                with self.subTest(profile=profile,target=target,name=name),self.assertRaises(TypeError):
                    validate_pc_book_npc_definition(forged)
            with self.assertRaises(TypeError):
                get_pc_book_npc_entry(profile.value)

    def test_each_definition_injury_and_unused_protection_graph_is_fresh(self):
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
                entry=get_pc_book_npc_entry(profile)
                object.__setattr__(entry.unselected_protection[0].test_profile,'dice',9)
                self.assertNotEqual(get_pc_book_npc_entry(profile).unselected_protection,entry.unselected_protection)


if __name__=='__main__':
    unittest.main()
