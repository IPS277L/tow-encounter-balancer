"""GM101/116/158–159: three shield-free Brutes, not implicit mounted profiles."""
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
    (PcBookNpcProfile.EMPIRE_KNIGHT_LANCE,101,'lance',4,4,RangedWeaponHands.ONE_HANDED,3,2,4,4,2),
    (PcBookNpcProfile.KNIGHT_WHITE_WOLF_HAMMER,116,'wolf_hammer',4,5,RangedWeaponHands.TWO_HANDED,3,2,4,3,2),
    (PcBookNpcProfile.BIG_UN_CHOPPAS,159,'choppas',3,5,RangedWeaponHands.TWO_HANDED,4,1,3,4,3),
)


class PcBruteCatalogTests(unittest.TestCase):
    def test_three_printed_attacks_protection_and_shield_free_resilience(self):
        for profile,page,attack_id,dice,damage,hands,toughness,armour,pdice,pthreshold,adice in CASES:
            with self.subTest(profile=profile):
                entry=get_pc_book_npc_entry(profile)
                definition=entry.definition
                source=f'BOOK-GM-GUIDE:1.1:p{page}:{profile.value}'
                self.assertEqual((entry.book_id,entry.version,entry.chapter,entry.page),
                    ('BOOK-GM-GUIDE','1.1','Allies and Antagonists',page))
                self.assertEqual((definition.id,definition.source_rule_id,definition.injury_policy,
                    definition.wound_limit,definition.resilience),
                    ('pc-book-npc:'+profile.value,source,TargetInjuryPolicy.BRUTE,2,
                     ResilienceProfile(toughness,armour)))
                attack,=definition.attacks
                self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,
                    attack.damage,attack.hands,attack.range_min,attack.range_max,
                    attack.ignores_armour,attack.secondary_effects),
                    (attack_id,source+':'+attack_id,Skill.MELEE,InlineProfile(dice,4),
                     DamageProfile(damage),hands,RangedWeaponRange.CLOSE,RangedWeaponRange.CLOSE,False,()))
                protection,=definition.protection
                self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
                    (source+':defence',Skill.DEFENCE,InlineProfile(pdice,pthreshold)))
                alternative,=entry.unselected_protection
                self.assertEqual((alternative.source_rule_id,alternative.skill,alternative.test_profile),
                    (source+':athletics',Skill.ATHLETICS,InlineProfile(adice,3)))
                validate_pc_book_npc_definition(definition)

    def test_live_state_is_healthy_armed_and_has_no_shield_or_mount_bonus(self):
        for profile,_,attack_id,_,_,_,toughness,armour,*_ in CASES:
            with self.subTest(profile=profile):
                snapshot=create_pc_book_npc(profile,'brute')
                self.assertEqual((snapshot.state.actor_id,snapshot.state.definition_id,
                    snapshot.state.wields_weapon,snapshot.state.holds_shield,
                    snapshot.state.current_resilience,snapshot.state.available_attack_ids),
                    ('brute','pc-book-npc:'+profile.value,True,False,
                     ResilienceProfile(toughness,armour),(attack_id,)))
                self.assertEqual((snapshot.state.injury.wounds,snapshot.state.injury.wound_limit,
                    snapshot.state.injury.defeated),(0,2,False))
                self.assertFalse(snapshot.state.injury.conditions.conditions)

    def test_cards_preserve_same_wound_bands_and_selected_loadout_names(self):
        bands=(PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'Drained'),
            PcBookNpcWoundBand(2,'Defeated'))
        for profile,*_ in CASES:
            with self.subTest(profile=profile):
                entry=get_pc_book_npc_entry(profile)
                self.assertEqual(entry.wound_bands,bands)
                self.assertEqual(tuple(a.name for a in entry.active_abilities),
                    ('Power of the Waaagh!',) if profile is PcBookNpcProfile.BIG_UN_CHOPPAS else ())
                self.assertIn('Defence',entry.name)
                if profile is not PcBookNpcProfile.KNIGHT_WHITE_WOLF_HAMMER:
                    self.assertIn('no shield',entry.name)
                if profile is not PcBookNpcProfile.BIG_UN_CHOPPAS:
                    self.assertIn('unmounted',entry.name)
                    self.assertIn('Mounted on Horse',entry.unselected_variant_names)

    def test_knight_cards_retain_conditional_mounted_and_charge_triggers(self):
        empire=get_pc_book_npc_entry(PcBookNpcProfile.EMPIRE_KNIGHT_LANCE)
        wolf=get_pc_book_npc_entry(PcBookNpcProfile.KNIGHT_WHITE_WOLF_HAMMER)
        for entry in (empire,wolf):
            self.assertEqual(entry.unselected_attack_names,())
            steed=entry.inactive_abilities[0]
            self.assertEqual(steed.name,'Noble Steed')
            self.assertIn('mounted on a Horse',steed.scope)
            for effect in ('+1 Resilience','Fast','non-Monstrosity','Prone before Give Ground'):
                self.assertIn(effect,steed.effect)
        self.assertEqual(tuple(a.name for a in empire.inactive_abilities),
            ('Noble Steed','Lance on Charge','For the Order'))
        lance,order=empire.inactive_abilities[1:]
        self.assertIn('whilst mounted',lance.scope)
        self.assertIn('+1d Melee and +1 Damage',lance.effect)
        self.assertIn('cannot dual wield',lance.effect)
        self.assertIn('whilst not Staggered',order.scope)
        self.assertIn('Glorious',order.effect)
        self.assertEqual(tuple(a.name for a in wolf.inactive_abilities),
            ('Noble Steed','Wolf Hammer on Charge','Furious Charge'))
        hammer,fury=wolf.inactive_abilities[1:]
        self.assertIn('Charge',hammer.scope)
        self.assertEqual(hammer.effect,'+1d Melee and +1 Damage')
        self.assertIn('successful attack as part of a Charge',fury.scope)
        self.assertIn('second action',fury.effect)
        self.assertIn('different enemy in Close Range',fury.effect)

    def test_big_un_inherits_orc_help_charge_and_unused_attacks(self):
        entry=get_pc_book_npc_entry(PcBookNpcProfile.BIG_UN_CHOPPAS)
        self.assertEqual(entry.unselected_attack_names,('Jagged Spear','Warbow'))
        self.assertEqual(tuple(a.name for a in entry.inactive_abilities),
            ('Choppas on Charge',))
        charge,=entry.inactive_abilities
        help_ability,=entry.active_abilities
        self.assertEqual((charge.scope,charge.effect),('An attack as part of a Charge','+1 Damage'))
        self.assertIn('Helps an ally make a Melee attack',help_ability.scope)
        self.assertIn('Do not Test',help_ability.effect)
        self.assertIn('1 free success',help_ability.effect)

    def test_reserved_source_rejects_changed_bonus_damage_protection_and_partial_renaming(self):
        for profile,_,_,_,_,_,toughness,armour,*_ in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            attack,=definition.attacks
            protection,=definition.protection
            alternatives=get_pc_book_npc_entry(profile).unselected_protection
            invalid=(replace(definition,resilience=ResilienceProfile(toughness,armour+1)),
                replace(definition,attacks=(replace(attack,damage=DamageProfile(9)),)),
                replace(definition,attacks=(replace(attack,hands=RangedWeaponHands.ONE_HANDED
                    if attack.hands is RangedWeaponHands.TWO_HANDED else RangedWeaponHands.TWO_HANDED),)),
                replace(definition,protection=alternatives),
                replace(definition,id='authored:root',source_rule_id='authored:source'),
                replace(definition,id='authored:root',source_rule_id='authored:source',
                    attacks=(replace(attack,source_rule_id='authored:attack'),)),
                replace(definition,id='authored:root',source_rule_id='authored:source',
                    attacks=(replace(attack,source_rule_id='authored:attack'),),
                    protection=(replace(protection,source_rule_id=alternatives[0].source_rule_id),)))
            for candidate in invalid:
                with self.subTest(profile=profile,candidate=candidate),self.assertRaises((TypeError,ValueError)):
                    validate_pc_book_npc_definition(candidate)
        with self.assertRaises(ValueError):
            validate_pc_book_npc_definition(replace(definition,id='pc-book-npc:unknown',
                source_rule_id='authored:source',attacks=(replace(attack,source_rule_id='authored:attack'),),
                protection=(replace(protection,source_rule_id='authored:protection'),)))

    def test_equal_string_enum_aliases_and_boolean_integer_aliases_cannot_bypass_canonical_types(self):
        for profile,*_ in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            for target,attribute,value in (('definition','injury_policy','brute'),
                    ('attack','hands',definition.attacks[0].hands.value),
                    ('attack','skill','melee'),('damage','success_multiplier',True)):
                forged=deepcopy(definition)
                subject={'definition':forged,'attack':forged.attacks[0],'damage':forged.attacks[0].damage}[target]
                object.__setattr__(subject,attribute,value)
                self.assertEqual(forged,definition)
                with self.subTest(profile=profile,target=target,attribute=attribute),self.assertRaises(TypeError):
                    validate_pc_book_npc_definition(forged)
            with self.assertRaises(TypeError):
                get_pc_book_npc_entry(profile.value)

    def test_snapshots_and_unused_protection_have_fresh_independent_graphs(self):
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
                self.assertNotEqual(get_pc_book_npc_entry(profile).unselected_protection,
                    entry.unselected_protection)


if __name__=='__main__':
    unittest.main()
