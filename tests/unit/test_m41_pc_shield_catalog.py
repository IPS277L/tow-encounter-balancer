"""GM101/143: retained shields change exact combat loadouts, not printed base Damage."""
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
    (PcBookNpcProfile.GOR_AXE_SHIELD,143,'crude_axes',3,3,4,1,TargetInjuryPolicy.MINION,1,Skill.ATHLETICS,3),
    (PcBookNpcProfile.EMPIRE_KNIGHT_LANCE_SHIELD,101,'lance',4,4,3,3,TargetInjuryPolicy.BRUTE,2,Skill.DEFENCE,4),
)


class PcShieldCatalogTests(unittest.TestCase):
    def test_printed_one_handed_attacks_protection_resilience_and_full_book_sources(self):
        for profile,page,attack_id,threshold,damage,toughness,bonus,policy,limit,skill,pthreshold in CASES:
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
                self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,attack.damage,
                    attack.range_min,attack.range_max,attack.hands,attack.ignores_armour,attack.secondary_effects),
                    (attack_id,source+':'+attack_id,Skill.MELEE,InlineProfile(4,threshold),DamageProfile(damage),
                     RangedWeaponRange.CLOSE,RangedWeaponRange.CLOSE,RangedWeaponHands.ONE_HANDED,False,()))
                protection,=definition.protection
                self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
                    (source+':'+skill.value,skill,InlineProfile(4,pthreshold)))
                validate_pc_book_npc_definition(definition)

    def test_fresh_shields_are_included_once_without_inventing_a_mount_bonus(self):
        for profile,_,attack_id,_,_,toughness,bonus,_,limit,*_ in CASES:
            with self.subTest(profile=profile):
                snapshot=create_pc_book_npc(profile,'shielded')
                self.assertEqual((snapshot.state.actor_id,snapshot.state.definition_id,
                    snapshot.state.wields_weapon,snapshot.state.holds_shield,snapshot.state.current_resilience,
                    snapshot.state.available_attack_ids),
                    ('shielded','pc-book-npc:'+profile.value,True,True,ResilienceProfile(toughness,bonus),(attack_id,)))
                self.assertIs(snapshot.state.holds_shield,True)
                self.assertEqual((snapshot.state.injury.wounds,snapshot.state.injury.wound_limit,
                    snapshot.state.injury.defeated,snapshot.state.injury.defeat_cause),(0,limit,False,None))
                self.assertFalse(snapshot.state.injury.conditions.conditions)
                self.assertEqual(snapshot.state.current_resilience.total,5 if toughness==4 else 6)

    def test_gor_keeps_self_staggered_rage_and_selects_single_axe_not_dual_damage(self):
        entry=get_pc_book_npc_entry(PcBookNpcProfile.GOR_AXE_SHIELD)
        self.assertIn('single Crude Axe',entry.name)
        self.assertIn('shield',entry.name)
        rage,=entry.active_abilities
        self.assertEqual((rage.name,rage.scope,rage.effect),
            ('Primal Rage','Melee attacks whilst the Gor itself is Staggered','+1d Melee'))
        forest,=entry.inactive_abilities
        self.assertEqual((forest.name,forest.scope,forest.effect),
            ('Child of the Forest','Movement through woodland Difficult Terrain',
             'Ignore the effects of woodland Difficult Terrain'))
        self.assertEqual(entry.unselected_variant_names,('Dual Crude Axes (no shield)',))
        self.assertEqual((entry.unselected_attack_names,entry.wound_bands,entry.unselected_protection),((),(),()))

    def test_knight_preserves_full_conditional_mounted_charge_rules_and_drained_band(self):
        entry=get_pc_book_npc_entry(PcBookNpcProfile.EMPIRE_KNIGHT_LANCE_SHIELD)
        self.assertIn('unmounted',entry.name)
        self.assertEqual(entry.active_abilities,())
        steed,charge,order=entry.inactive_abilities
        self.assertEqual(steed.name,'Noble Steed')
        self.assertIn('mounted on a Horse',steed.scope)
        for detail in ('+1 Resilience','Fast Speed','successful Charge','non-Monstrosity','Prone before Give Ground'):
            self.assertIn(detail,steed.effect)
        self.assertEqual((charge.name,charge.scope,charge.effect),
            ('Lance on Charge','A Charge attack whilst mounted',
             '+1d Melee and +1 Damage; Lance cannot dual wield'))
        self.assertEqual((order.name,order.scope,order.effect),
            ('For the Order','Attack Tests as part of a Charge whilst not Staggered',
             'Those Attack Tests are Glorious'))
        self.assertEqual(entry.wound_bands,(PcBookNpcWoundBand(0,'No effect'),
            PcBookNpcWoundBand(1,'Drained'),PcBookNpcWoundBand(2,'Defeated')))
        self.assertEqual(entry.unselected_variant_names,('Mounted on Horse',))
        self.assertEqual(entry.unselected_attack_names,())
        alternative,=entry.unselected_protection
        self.assertEqual((alternative.source_rule_id,alternative.skill,alternative.test_profile),
            (entry.definition.source_rule_id+':athletics',Skill.ATHLETICS,InlineProfile(2,3)))

    def test_previous_unshielded_dual_gor_and_lance_knight_keep_distinct_loadouts(self):
        for selected,previous,old_res,new_res in (
                (PcBookNpcProfile.GOR_AXE_SHIELD,PcBookNpcProfile.GOR_DUAL_AXES,4,5),
                (PcBookNpcProfile.EMPIRE_KNIGHT_LANCE_SHIELD,PcBookNpcProfile.EMPIRE_KNIGHT_LANCE,5,6)):
            old=create_pc_book_npc(previous,'old')
            new=create_pc_book_npc(selected,'new')
            self.assertFalse(old.state.holds_shield)
            self.assertTrue(new.state.holds_shield)
            self.assertEqual((old.definition.resilience.total,new.definition.resilience.total),(old_res,new_res))
            self.assertNotEqual(old.definition.id,new.definition.id)
            validate_pc_book_npc_definition(old.definition)
        old_gor=get_pc_book_npc_entry(PcBookNpcProfile.GOR_DUAL_AXES)
        self.assertEqual(tuple(ability.name for ability in old_gor.active_abilities),
            ('Primal Rage','Dual-wielded Crude Axes'))
        self.assertEqual(old_gor.definition.attacks[0].damage.base,3)

    def test_whole_and_nested_book_identities_reject_changed_stats_or_partial_renaming(self):
        for profile,*_ in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            attack,=definition.attacks
            protection,=definition.protection
            invalid=(
                replace(definition,resilience=ResilienceProfile(definition.resilience.toughness,
                    definition.resilience.bonus+1)),
                replace(definition,attacks=(replace(attack,damage=DamageProfile(9)),)),
                replace(definition,attacks=(replace(attack,hands=RangedWeaponHands.TWO_HANDED),)),
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
        definition=get_pc_book_npc_entry(PcBookNpcProfile.EMPIRE_KNIGHT_LANCE_SHIELD).definition
        alternative,=get_pc_book_npc_entry(PcBookNpcProfile.EMPIRE_KNIGHT_LANCE_SHIELD).unselected_protection
        with self.assertRaises(ValueError):
            validate_pc_book_npc_definition(replace(definition,protection=(alternative,)))

    def test_equal_string_enums_and_boolean_damage_aliases_are_not_canonical(self):
        for profile,*_ in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            for target,name,value in (('definition','injury_policy',definition.injury_policy.value),
                    ('attack','skill','melee'),('attack','hands','1h'),('attack','range_max','close'),
                    ('damage','success_multiplier',True)):
                forged=deepcopy(definition)
                subject={'definition':forged,'attack':forged.attacks[0],'damage':forged.attacks[0].damage}[target]
                object.__setattr__(subject,name,value)
                self.assertEqual(forged,definition)
                with self.subTest(profile=profile,target=target,name=name),self.assertRaises(TypeError):
                    validate_pc_book_npc_definition(forged)
            with self.assertRaises(TypeError):
                get_pc_book_npc_entry(profile.value)

    def test_factories_preserve_independent_definition_injury_and_unused_protection_graphs(self):
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
        entry=get_pc_book_npc_entry(PcBookNpcProfile.EMPIRE_KNIGHT_LANCE_SHIELD)
        object.__setattr__(entry.unselected_protection[0].test_profile,'dice',9)
        self.assertNotEqual(get_pc_book_npc_entry(PcBookNpcProfile.EMPIRE_KNIGHT_LANCE_SHIELD).unselected_protection,
            entry.unselected_protection)


if __name__=='__main__':
    unittest.main()
