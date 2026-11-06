"""GM138/147: Razorgor and two Minotaur Axe loadouts, with full printed triggers."""
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
    (PcBookNpcProfile.RAZORGOR,138,'razor_tusks',3,4,None,3,3),
    (PcBookNpcProfile.MINOTAUR_AXE,147,'axe',4,5,RangedWeaponHands.ONE_HANDED,4,4),
    (PcBookNpcProfile.MINOTAUR_DUAL_AXES,147,'axe',4,5,RangedWeaponHands.ONE_HANDED,4,4),
)


class PcDevourCatalogTests(unittest.TestCase):
    def test_exact_brute_cards_keep_printed_base_damage_and_full_source_identity(self):
        for profile,page,attack_id,dice,threshold,hands,pdice,pthreshold in CASES:
            with self.subTest(profile=profile):
                entry=get_pc_book_npc_entry(profile)
                definition=entry.definition
                source=f'BOOK-GM-GUIDE:1.1:p{page}:{profile.value}'
                self.assertEqual((entry.profile_id,entry.book_id,entry.version,entry.chapter,entry.page),
                    (profile,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',page))
                self.assertEqual((definition.id,definition.source_rule_id,definition.injury_policy,
                    definition.wound_limit,definition.resilience),
                    ('pc-book-npc:'+profile.value,source,TargetInjuryPolicy.BRUTE,3,ResilienceProfile(5,1)))
                attack,=definition.attacks
                self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,
                    attack.damage,attack.range_min,attack.range_max,attack.hands,
                    attack.ignores_armour,attack.secondary_effects),
                    (attack_id,source+':'+attack_id,Skill.MELEE,InlineProfile(dice,threshold),DamageProfile(5),
                     RangedWeaponRange.CLOSE,RangedWeaponRange.CLOSE,hands,False,()))
                protection,=definition.protection
                self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
                    (source+':athletics',Skill.ATHLETICS,InlineProfile(pdice,pthreshold)))
                self.assertEqual(entry.unselected_protection,())
                validate_pc_book_npc_definition(definition)

    def test_fresh_razorgor_is_natural_and_minotaurs_are_armed_without_shields(self):
        for profile,_,attack_id,_,_,hands,*_ in CASES:
            with self.subTest(profile=profile):
                snapshot=create_pc_book_npc(profile,'npc')
                self.assertEqual((snapshot.state.actor_id,snapshot.state.definition_id,
                    snapshot.state.wields_weapon,snapshot.state.holds_shield,
                    snapshot.state.current_resilience,snapshot.state.available_attack_ids),
                    ('npc','pc-book-npc:'+profile.value,hands is not None,False,ResilienceProfile(5,1),(attack_id,)))
                self.assertEqual((snapshot.state.injury.wounds,snapshot.state.injury.wound_limit,
                    snapshot.state.injury.defeated,snapshot.state.injury.defeat_cause),(0,3,False,None))
                self.assertFalse(snapshot.state.injury.conditions.conditions)

    def test_wound_bands_and_devour_retain_pre_attack_union_without_imposing_drained(self):
        expected=(PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'+1d Melee'),
            PcBookNpcWoundBand(2,'+2d Melee'),PcBookNpcWoundBand(3,'Defeated'))
        for profile,*_ in CASES:
            with self.subTest(profile=profile):
                entry=get_pc_book_npc_entry(profile)
                self.assertEqual(entry.wound_bands,expected)
                rage,devour,*_=entry.active_abilities
                self.assertEqual((rage.name,rage.scope,rage.effect),
                    ('Wounded Melee','Melee attacks whilst at 1 or 2 Wounds','+1d Melee per Wound'))
                self.assertEqual(devour.name,'Devour the Fallen')
                self.assertIn('already Staggered, Prone, or Wounded before the attack',devour.scope)
                self.assertEqual(devour.effect,
                    '+1d on the Wounds Table once, even if several of those conditions apply')
                self.assertFalse(any('Drained' in band.effect for band in entry.wound_bands))

    def test_razorgor_preserves_both_charge_modifiers_and_fearsome_give_ground_trigger(self):
        entry=get_pc_book_npc_entry(PcBookNpcProfile.RAZORGOR)
        charge,fear=entry.inactive_abilities
        self.assertEqual((charge.name,charge.scope,charge.effect),
            ('Razor Tusks on Charge','An attack as part of a Charge','+1d Melee and +1 Damage'))
        self.assertEqual((fear.name,fear.scope,fear.effect),
            ('Fearsome',"An enemy Gives Ground from this creature's attacks",'That enemy suffers Broken'))
        self.assertEqual((entry.unselected_attack_names,entry.unselected_variant_names),((),()))

    def test_minotaur_preserves_charging_bull_and_only_dual_mode_has_extra_damage(self):
        for profile in (PcBookNpcProfile.MINOTAUR_AXE,PcBookNpcProfile.MINOTAUR_DUAL_AXES):
            with self.subTest(profile=profile):
                entry=get_pc_book_npc_entry(profile)
                fear,bull=entry.inactive_abilities
                self.assertEqual(fear.name,'Fearsome')
                self.assertIn('Gives Ground',fear.scope)
                self.assertEqual(fear.effect,'That enemy suffers Broken')
                self.assertEqual(bull.name,'Charging Bull')
                self.assertIn('separately chosen action',bull.scope)
                self.assertIn('Zone within Medium Range',bull.scope)
                for detail in ('Brawn Test Opposed','enemy in that Zone best able',
                        'Defence or Endurance','every creature in the Zone except the Minotaur',
                        'failure Staggers the Minotaur itself'):
                    self.assertIn(detail,bull.effect)
                if profile is PcBookNpcProfile.MINOTAUR_DUAL_AXES:
                    axes=entry.active_abilities[2]
                    self.assertEqual(axes.name,'Dual-wielded Axes')
                    self.assertIn('occupies both hands',axes.scope)
                    self.assertIn('shield is not carried',axes.scope)
                    self.assertEqual(axes.effect,'+1 Damage')
                    self.assertEqual(entry.unselected_variant_names,('Single Axe',))
                else:
                    self.assertEqual(len(entry.active_abilities),2)
                    self.assertIn('single Axe',entry.name)
                    self.assertEqual(entry.unselected_variant_names,('Dual Axes',))

    def test_chosen_axes_preserve_ws_four_cap_eight_without_admitting_greataxe(self):
        for profile in (PcBookNpcProfile.MINOTAUR_AXE,PcBookNpcProfile.MINOTAUR_DUAL_AXES):
            with self.subTest(profile=profile):
                entry=get_pc_book_npc_entry(profile)
                self.assertEqual(entry.unselected_attack_names,('Greataxe',))
                self.assertEqual((entry.definition.attacks[0].test_profile.base_dice,
                    entry.definition.attacks[0].test_profile.maximum_dice),(4,8))
                self.assertIsNone(entry.definition.attacks[0].test_profile.pool_cap)
                self.assertEqual(entry.definition.attacks[0].damage.base,5)

    def test_partial_book_sources_and_changed_stats_cannot_claim_a_canonical_loadout(self):
        for profile,*_ in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            attack,=definition.attacks
            protection,=definition.protection
            invalid=(
                replace(definition,wound_limit=2),
                replace(definition,resilience=ResilienceProfile(5,2)),
                replace(definition,attacks=(replace(attack,damage=DamageProfile(6)),)),
                replace(definition,attacks=(replace(attack,test_profile=InlineProfile(3,5)),)),
                replace(definition,protection=(replace(protection,skill=Skill.DEFENCE),)),
                replace(definition,id='authored:root',source_rule_id='authored:source'),
                replace(definition,id='authored:root',source_rule_id='authored:source',
                    attacks=(replace(attack,source_rule_id='authored:attack'),)),
                replace(definition,id='authored:root',source_rule_id='authored:source',
                    protection=(replace(protection,source_rule_id='authored:protection'),)),
            )
            for candidate in invalid:
                with self.subTest(profile=profile,candidate=candidate),self.assertRaises((TypeError,ValueError)):
                    validate_pc_book_npc_definition(candidate)

    def test_equal_string_enums_and_boolean_damage_aliases_do_not_bypass_canonical_types(self):
        for profile,*_ in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            aliases=[('definition','injury_policy','brute'),('attack','skill','melee'),
                ('attack','range_max','close'),('damage','success_multiplier',True)]
            if definition.attacks[0].hands is not None:
                aliases.append(('attack','hands','1h'))
            for target,name,value in aliases:
                forged=deepcopy(definition)
                subject={'definition':forged,'attack':forged.attacks[0],'damage':forged.attacks[0].damage}[target]
                object.__setattr__(subject,name,value)
                self.assertEqual(forged,definition)
                with self.subTest(profile=profile,target=target,name=name),self.assertRaises(TypeError):
                    validate_pc_book_npc_definition(forged)
            with self.assertRaises(TypeError):
                get_pc_book_npc_entry(profile.value)

    def test_each_catalog_and_snapshot_call_returns_independent_fresh_graphs(self):
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
