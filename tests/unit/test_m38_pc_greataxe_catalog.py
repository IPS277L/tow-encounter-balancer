"""GM147/PG107: Minotaur Greataxe has printed three dice but WS4 maximum eight."""
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


PROFILE=PcBookNpcProfile.MINOTAUR_GREATAXE
SOURCE='BOOK-GM-GUIDE:1.1:p147:minotaur_greataxe'


class PcGreataxeCatalogTests(unittest.TestCase):
    def test_printed_greataxe_keeps_base_three_dice_damage_eight_and_explicit_ws_four_cap(self):
        entry=get_pc_book_npc_entry(PROFILE)
        definition=entry.definition
        self.assertEqual((entry.profile_id,entry.book_id,entry.version,entry.chapter,entry.page),
            (PROFILE,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',147))
        self.assertEqual((definition.id,definition.source_rule_id,definition.injury_policy,
            definition.wound_limit,definition.resilience),
            ('pc-book-npc:minotaur_greataxe',SOURCE,TargetInjuryPolicy.BRUTE,3,ResilienceProfile(5,1)))
        attack,=definition.attacks
        self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,attack.damage,
            attack.range_min,attack.range_max,attack.hands,attack.ignores_armour,attack.secondary_effects),
            ('greataxe',SOURCE+':greataxe',Skill.MELEE,InlineProfile(3,5,8),DamageProfile(8),
             RangedWeaponRange.CLOSE,RangedWeaponRange.CLOSE,RangedWeaponHands.TWO_HANDED,False,()))
        self.assertEqual((attack.test_profile.base_dice,attack.test_profile.maximum_dice),(3,8))
        protection,=definition.protection
        self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
            (SOURCE+':athletics',Skill.ATHLETICS,InlineProfile(4,4)))
        self.assertIsNone(protection.test_profile.pool_cap)
        validate_pc_book_npc_definition(definition)

    def test_fresh_greataxe_loadout_is_armed_healthy_armoured_and_has_no_shield(self):
        snapshot=create_pc_book_npc(PROFILE,'minotaur')
        self.assertEqual((snapshot.state.actor_id,snapshot.state.definition_id,
            snapshot.state.wields_weapon,snapshot.state.holds_shield,snapshot.state.available_attack_ids,
            snapshot.state.current_resilience),
            ('minotaur','pc-book-npc:minotaur_greataxe',True,False,('greataxe',),ResilienceProfile(5,1)))
        self.assertEqual((snapshot.state.injury.wounds,snapshot.state.injury.wound_limit,
            snapshot.state.injury.defeated,snapshot.state.injury.defeat_cause),(0,3,False,None))
        self.assertFalse(snapshot.state.injury.conditions.conditions)

    def test_same_wound_rage_devour_bands_do_not_add_dual_damage_or_drained(self):
        entry=get_pc_book_npc_entry(PROFILE)
        self.assertEqual(entry.wound_bands,(PcBookNpcWoundBand(0,'No effect'),
            PcBookNpcWoundBand(1,'+1d Melee'),PcBookNpcWoundBand(2,'+2d Melee'),
            PcBookNpcWoundBand(3,'Defeated')))
        self.assertEqual(tuple(ability.name for ability in entry.active_abilities),
            ('Wounded Melee','Devour the Fallen'))
        rage,devour=entry.active_abilities
        self.assertEqual(rage.effect,'+1d Melee per Wound')
        self.assertIn('1 or 2 Wounds',rage.scope)
        self.assertIn('already Staggered, Prone, or Wounded before the attack',devour.scope)
        self.assertIn('once',devour.effect)

    def test_fearsome_and_separate_charging_bull_keep_their_entire_triggers(self):
        fear,bull=get_pc_book_npc_entry(PROFILE).inactive_abilities
        self.assertEqual(fear.name,'Fearsome')
        self.assertIn('Gives Ground',fear.scope)
        self.assertEqual(fear.effect,'That enemy suffers Broken')
        self.assertEqual(bull.name,'Charging Bull')
        self.assertIn('separately chosen action',bull.scope)
        self.assertIn('Zone within Medium Range',bull.scope)
        for detail in ('Brawn Test Opposed','Defence or Endurance',
                'every creature in the Zone except the Minotaur','failure Staggers the Minotaur itself'):
            self.assertIn(detail,bull.effect)

    def test_greataxe_selects_its_own_mode_while_previous_axe_loadouts_keep_their_sources_and_caps(self):
        entry=get_pc_book_npc_entry(PROFILE)
        self.assertIn('Greataxe',entry.name)
        self.assertEqual(entry.unselected_attack_names,('Axe',))
        self.assertEqual(entry.unselected_variant_names,('Single Axe','Dual Axes'))
        for profile in (PcBookNpcProfile.MINOTAUR_AXE,PcBookNpcProfile.MINOTAUR_DUAL_AXES):
            old=get_pc_book_npc_entry(profile)
            self.assertEqual(old.unselected_attack_names,('Greataxe',))
            self.assertEqual(old.definition.attacks[0].test_profile,InlineProfile(4,5))
            self.assertIsNone(old.definition.attacks[0].test_profile.pool_cap)
            self.assertEqual(old.definition.attacks[0].damage,DamageProfile(5))
            self.assertNotEqual(old.definition.id,entry.definition.id)
            validate_pc_book_npc_definition(old.definition)

    def test_canonical_cap_cannot_be_missing_or_shifted_and_protection_stays_null(self):
        definition=get_pc_book_npc_entry(PROFILE).definition
        attack,=definition.attacks
        protection,=definition.protection
        for cap in (None,6,7,9):
            with self.subTest(cap=cap),self.assertRaises((TypeError,ValueError)):
                validate_pc_book_npc_definition(replace(definition,
                    attacks=(replace(attack,test_profile=InlineProfile(3,5,cap)),)))
        for cap in (6,8):
            with self.subTest(protection_cap=cap),self.assertRaises((TypeError,ValueError)):
                validate_pc_book_npc_definition(replace(definition,
                    protection=(replace(protection,test_profile=InlineProfile(4,4,cap)),)))
        for profile in (InlineProfile(2,5,8),InlineProfile(4,5,8)):
            with self.subTest(double_weapon_penalty_or_ignored_printed_base=profile),self.assertRaises(ValueError):
                validate_pc_book_npc_definition(replace(definition,
                    attacks=(replace(attack,test_profile=profile),)))

    def test_partial_book_identity_changes_or_extra_weapon_damage_cannot_claim_greataxe(self):
        definition=get_pc_book_npc_entry(PROFILE).definition
        attack,=definition.attacks
        protection,=definition.protection
        candidates=(
            replace(definition,attacks=(replace(attack,damage=DamageProfile(9)),)),
            replace(definition,attacks=(replace(attack,hands=RangedWeaponHands.ONE_HANDED),)),
            replace(definition,resilience=ResilienceProfile(5,2)),
            replace(definition,id='authored:root',source_rule_id='authored:source'),
            replace(definition,id='authored:root',source_rule_id='authored:source',
                attacks=(replace(attack,source_rule_id='authored:attack'),)),
            replace(definition,id='authored:root',source_rule_id='authored:source',
                protection=(replace(protection,source_rule_id='authored:protection'),)),
        )
        for candidate in candidates:
            with self.subTest(candidate=candidate),self.assertRaises((TypeError,ValueError)):
                validate_pc_book_npc_definition(candidate)

    def test_equal_string_enums_float_cap_and_boolean_damage_aliases_are_rejected(self):
        definition=get_pc_book_npc_entry(PROFILE).definition
        for target,name,value in (('definition','injury_policy','brute'),('attack','skill','melee'),
                ('attack','hands','2h'),('attack','range_max','close'),('profile','pool_cap',8.0),
                ('damage','success_multiplier',True)):
            forged=deepcopy(definition)
            subject={'definition':forged,'attack':forged.attacks[0],
                'profile':forged.attacks[0].test_profile,'damage':forged.attacks[0].damage}[target]
            object.__setattr__(subject,name,value)
            self.assertEqual(forged,definition)
            with self.subTest(target=target,name=name),self.assertRaises(TypeError):
                validate_pc_book_npc_definition(forged)
        with self.assertRaises(TypeError):
            get_pc_book_npc_entry(PROFILE.value)

    def test_each_catalog_and_snapshot_call_has_fresh_attack_protection_and_injury_graphs(self):
        first=create_pc_book_npc(PROFILE,'first')
        second=create_pc_book_npc(PROFILE,'second')
        expected=deepcopy(second.definition)
        self.assertIsNot(first.definition,second.definition)
        self.assertIsNot(first.state.injury,second.state.injury)
        object.__setattr__(first.definition.attacks[0].test_profile,'pool_cap',6)
        object.__setattr__(first.definition.protection[0].test_profile,'dice',9)
        self.assertEqual(second.definition,expected)
        self.assertEqual(get_pc_book_npc_entry(PROFILE).definition,expected)
        with self.assertRaises(ValueError):
            validate_pc_book_npc_definition(first.definition)


if __name__=='__main__':
    unittest.main()
