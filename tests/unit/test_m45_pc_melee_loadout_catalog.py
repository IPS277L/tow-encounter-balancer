"""GM93/114/143/158–159: one Axe Brute and three explicit unshielded loadouts."""
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
    (PcBookNpcProfile.HOCHLAND_SHARPSHOOTER_AXE,114,'axe',3,3,3,RangedWeaponRange.CLOSE,
        4,1,TargetInjuryPolicy.BRUTE,2,Skill.ATHLETICS,4,4),
    (PcBookNpcProfile.GOR_AXE,143,'crude_axes',4,3,3,RangedWeaponRange.CLOSE,
        4,0,TargetInjuryPolicy.MINION,1,Skill.ATHLETICS,4,3),
    (PcBookNpcProfile.ORC_BOY_SPEAR,158,'jagged_spear',3,4,3,RangedWeaponRange.SHORT,
        4,1,TargetInjuryPolicy.MINION,1,Skill.DEFENCE,3,4),
    (PcBookNpcProfile.BIG_UN_SPEAR,159,'jagged_spear',3,4,4,RangedWeaponRange.SHORT,
        4,1,TargetInjuryPolicy.BRUTE,2,Skill.DEFENCE,3,4),
)


class PcMeleeLoadoutCatalogTests(unittest.TestCase):
    def test_four_complete_printed_profiles_and_sources(self):
        for profile,page,attack_id,dice,threshold,damage,maximum,toughness,bonus,policy,limit,skill,pdice,pthreshold in CASES:
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
                    (attack_id,source+':'+attack_id,Skill.MELEE,InlineProfile(dice,threshold),
                     DamageProfile(damage),RangedWeaponRange.CLOSE,maximum,RangedWeaponHands.ONE_HANDED,False,()))
                protection,=definition.protection
                self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
                    (source+':'+skill.value,skill,InlineProfile(pdice,pthreshold)))
                self.assertEqual((attack.test_profile.maximum_dice,protection.test_profile.maximum_dice),
                    (dice*2,pdice*2))
                self.assertIsNone(attack.test_profile.pool_cap)
                self.assertIsNone(protection.test_profile.pool_cap)
                validate_pc_book_npc_definition(definition)

    def test_fresh_sources_have_one_armed_attack_and_no_shield_or_initial_conditions(self):
        for profile,_,attack_id,_,_,_,_,toughness,bonus,_,limit,*_ in CASES:
            with self.subTest(profile=profile):
                snapshot=create_pc_book_npc(profile,'fighter')
                self.assertEqual((snapshot.state.actor_id,snapshot.state.definition_id,
                    snapshot.state.wields_weapon,snapshot.state.holds_shield,
                    snapshot.state.available_attack_ids,snapshot.state.current_resilience),
                    ('fighter','pc-book-npc:'+profile.value,True,False,(attack_id,),ResilienceProfile(toughness,bonus)))
                self.assertEqual((snapshot.state.injury.wounds,snapshot.state.injury.wound_limit,
                    snapshot.state.injury.defeated,snapshot.state.injury.defeat_cause),(0,limit,False,None))
                self.assertFalse(snapshot.state.injury.conditions.conditions)

    def test_omitting_a_shield_subtracts_one_resilience_without_changing_the_printed_attack(self):
        for selected,shielded,expected_total in (
                (PcBookNpcProfile.GOR_AXE,PcBookNpcProfile.GOR_AXE_SHIELD,4),
                (PcBookNpcProfile.ORC_BOY_SPEAR,PcBookNpcProfile.ORC_BOY_SPEAR_SHIELD,5),
                (PcBookNpcProfile.BIG_UN_SPEAR,PcBookNpcProfile.BIG_UN_SPEAR_SHIELD,5)):
            with self.subTest(profile=selected):
                current=create_pc_book_npc(selected,'new')
                old=create_pc_book_npc(shielded,'old')
                self.assertFalse(current.state.holds_shield)
                self.assertTrue(old.state.holds_shield)
                self.assertEqual(current.definition.resilience.total,expected_total)
                self.assertEqual(old.definition.resilience.total,expected_total+1)
                new_attack,old_attack=current.definition.attacks[0],old.definition.attacks[0]
                self.assertEqual((new_attack.test_profile,new_attack.damage,new_attack.hands,new_attack.range_max),
                    (old_attack.test_profile,old_attack.damage,old_attack.hands,old_attack.range_max))
                self.assertNotEqual(current.definition.source_rule_id,old.definition.source_rule_id)

    def test_single_axe_gor_preserves_self_rage_without_the_dual_damage_ability(self):
        entry=get_pc_book_npc_entry(PcBookNpcProfile.GOR_AXE)
        forest,=entry.inactive_abilities
        rage,=entry.active_abilities
        self.assertEqual((forest.name,forest.scope,forest.effect),('Child of the Forest',
            'Movement through woodland Difficult Terrain','Ignore the effects of woodland Difficult Terrain'))
        self.assertEqual((rage.name,rage.scope,rage.effect),
            ('Primal Rage','Melee attacks whilst the Gor itself is Staggered','+1d Melee'))
        self.assertIn('single Crude Axe',entry.name)
        self.assertIn('no shield',entry.name)
        self.assertEqual(entry.definition.attacks[0].damage.base,3)
        self.assertIn('Single Crude Axe with shield',entry.unselected_variant_names)
        self.assertIn('Dual Crude Axes (no shield)',entry.unselected_variant_names)

    def test_orc_spears_preserve_full_charge_help_and_big_un_wound_rules(self):
        for profile,big_un in ((PcBookNpcProfile.ORC_BOY_SPEAR,False),(PcBookNpcProfile.BIG_UN_SPEAR,True)):
            entry=get_pc_book_npc_entry(profile)
            charge,=entry.inactive_abilities
            help_ability,=entry.active_abilities
            self.assertEqual((charge.name,charge.scope,charge.effect),
                ('Jagged Spear on Charge','An attack as part of a Charge','+1 Damage'))
            self.assertEqual(help_ability.name,'Power of the Waaagh!')
            self.assertIn('Helps an ally make a Melee attack',help_ability.scope)
            self.assertEqual(help_ability.effect,'Do not Test; the ally gains 1 free success on that Attack Test')
            self.assertEqual(entry.unselected_attack_names,('Couple of Choppas','Warbow'))
            alternative,=entry.unselected_protection
            self.assertEqual((alternative.source_rule_id,alternative.skill,alternative.test_profile),
                (entry.definition.source_rule_id+':athletics',Skill.ATHLETICS,InlineProfile(3,3)))
            self.assertEqual(entry.wound_bands,(PcBookNpcWoundBand(0,'No effect'),
                PcBookNpcWoundBand(1,'Drained'),PcBookNpcWoundBand(2,'Defeated')) if big_un else ())

    def test_sharpshooter_keeps_cancel_aim_and_full_unselected_rifle_reload_and_terrain_metadata(self):
        entry=get_pc_book_npc_entry(PcBookNpcProfile.HOCHLAND_SHARPSHOOTER_AXE)
        self.assertEqual(entry.active_abilities,())
        reload,terrain=entry.inactive_abilities
        self.assertEqual(reload.name,'Rapid Reload')
        for detail in ('successful Dexterity','reload a weapon','not Staggered','without moving'):
            self.assertIn(detail,reload.scope)
        self.assertEqual(reload.effect,'May immediately Aim or Attack with that weapon as a second action')
        self.assertEqual((terrain.name,terrain.scope,terrain.effect),
            ("Sniper's Nest",'Movement through woodland Difficult Terrain','Ignore Difficult Terrain in woodland areas'))
        self.assertEqual(entry.unselected_attack_names,('Hochland Long Rifle',))
        self.assertEqual(entry.wound_bands,(PcBookNpcWoundBand(0,'No effect'),
            PcBookNpcWoundBand(1,'Cancel Aim'),PcBookNpcWoundBand(2,'Defeated')))
        self.assertEqual(entry.unselected_protection,())

    def test_full_canonical_graph_rejects_changed_numbers_hands_and_partial_source_renames(self):
        for profile,*_ in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            attack,=definition.attacks
            protection,=definition.protection
            for candidate in (replace(definition,resilience=ResilienceProfile(4,4)),
                    replace(definition,attacks=(replace(attack,damage=DamageProfile(99)),)),
                    replace(definition,attacks=(replace(attack,hands=RangedWeaponHands.TWO_HANDED),)),
                    replace(definition,protection=(replace(protection,test_profile=InlineProfile(1,1)),)),
                    replace(definition,id='authored:root',source_rule_id='authored:root'),
                    replace(definition,id='authored:root',source_rule_id='authored:root',
                        attacks=(replace(attack,source_rule_id='authored:attack'),))):
                with self.subTest(profile=profile,candidate=candidate),self.assertRaises((TypeError,ValueError)):
                    validate_pc_book_npc_definition(candidate)

    def test_equal_enum_string_float_and_boolean_aliases_are_rejected(self):
        for profile,*_ in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            for subject_name,field,value in (('definition','injury_policy',definition.injury_policy.value),
                    ('attack','skill','melee'),('attack','hands','1h'),('profile','dice',float(definition.attacks[0].test_profile.dice)),
                    ('damage','success_multiplier',True)):
                forged=deepcopy(definition)
                subject={'definition':forged,'attack':forged.attacks[0],
                    'profile':forged.attacks[0].test_profile,'damage':forged.attacks[0].damage}[subject_name]
                object.__setattr__(subject,field,value)
                self.assertEqual(forged,definition)
                with self.subTest(profile=profile,field=field),self.assertRaises(TypeError):
                    validate_pc_book_npc_definition(forged)

    def test_factory_graphs_are_independent(self):
        for profile,*_ in CASES:
            first=create_pc_book_npc(profile,'one')
            second=create_pc_book_npc(profile,'two')
            expected=deepcopy(second.definition)
            self.assertIsNot(first.definition,second.definition)
            self.assertIsNot(first.state.injury,second.state.injury)
            object.__setattr__(first.definition.attacks[0].damage,'base',99)
            self.assertEqual(second.definition,expected)
            self.assertEqual(get_pc_book_npc_entry(profile).definition,expected)
