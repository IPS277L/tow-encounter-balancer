"""GM104 plus accepted ADR-0088 scope, without inventing printed focus or weapon Traits."""
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


PROFILE=PcBookNpcProfile.DWARF_BREWGUARD_WARHAMMER
SOURCE='BOOK-GM-GUIDE:1.1:p104:dwarf_brewguard_warhammer'


class PcBrewguardCatalogTests(unittest.TestCase):
    def test_exact_printed_warhammer_defence_resilience_and_whole_book_identity(self):
        entry=get_pc_book_npc_entry(PROFILE)
        definition=entry.definition
        self.assertEqual((entry.profile_id,entry.book_id,entry.version,entry.chapter,entry.page),
            (PROFILE,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',104))
        self.assertEqual((definition.id,definition.source_rule_id,definition.injury_policy,
            definition.wound_limit,definition.resilience),
            ('pc-book-npc:dwarf_brewguard_warhammer',SOURCE,TargetInjuryPolicy.BRUTE,2,ResilienceProfile(4,1)))
        attack,=definition.attacks
        self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,attack.damage,
            attack.range_min,attack.range_max,attack.hands,attack.ignores_armour,attack.secondary_effects),
            ('warhammer',SOURCE+':warhammer',Skill.MELEE,InlineProfile(4,3),DamageProfile(3),
             RangedWeaponRange.CLOSE,RangedWeaponRange.CLOSE,RangedWeaponHands.ONE_HANDED,False,()))
        protection,=definition.protection
        self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
            (SOURCE+':defence',Skill.DEFENCE,InlineProfile(4,3)))
        self.assertEqual((attack.test_profile.maximum_dice,protection.test_profile.maximum_dice),(8,8))
        self.assertIsNone(attack.test_profile.pool_cap)
        self.assertIsNone(protection.test_profile.pool_cap)
        validate_pc_book_npc_definition(definition)

    def test_fresh_armed_brewguard_has_light_armour_without_shield_or_initial_distraction(self):
        snapshot=create_pc_book_npc(PROFILE,'brewguard')
        self.assertEqual((snapshot.state.actor_id,snapshot.state.definition_id,
            snapshot.state.wields_weapon,snapshot.state.holds_shield,snapshot.state.current_resilience,
            snapshot.state.available_attack_ids),
            ('brewguard','pc-book-npc:dwarf_brewguard_warhammer',True,False,ResilienceProfile(4,1),('warhammer',)))
        self.assertEqual((snapshot.state.injury.wounds,snapshot.state.injury.wound_limit,
            snapshot.state.injury.defeated,snapshot.state.injury.defeat_cause),(0,2,False,None))
        self.assertFalse(snapshot.state.injury.conditions.conditions)

    def test_printed_first_wound_row_is_distinct_from_explicitly_accepted_focus_interpretation(self):
        entry=get_pc_book_npc_entry(PROFILE)
        self.assertEqual(entry.wound_bands,(PcBookNpcWoundBand(0,'No effect'),
            PcBookNpcWoundBand(1,'Attacker inflicts Distracted condition'),PcBookNpcWoundBand(2,'Defeated')))
        ability,=entry.active_abilities
        self.assertEqual(ability.name,'First-Wound Distracted')
        self.assertEqual(ability.scope,'A living Brewguard suffers its first Wound')
        for detail in ('Accepted ADR-0088 interpretation','actual first-Wound attacker is the focus',
                'ordinary one-shot Distracted','not an ongoing Wound cause',
                'focus death clears it','Defenceless alone does not'):
            self.assertIn(detail,ability.effect)

    def test_cooler_heads_is_a_separate_leadership_action_with_one_character_per_success(self):
        ability,=get_pc_book_npc_entry(PROFILE).inactive_abilities
        self.assertEqual((ability.name,ability.scope),
            ('Cooler Heads Prevail','A separately chosen action: Leadership Test'))
        self.assertEqual(ability.effect,
            'For every success, choose one character within Medium Range and remove its Distracted condition')

    def test_bare_hands_and_printed_athletics_are_unselected_not_merged_into_warhammer(self):
        entry=get_pc_book_npc_entry(PROFILE)
        self.assertEqual(entry.unselected_attack_names,('Bare Hands',))
        self.assertEqual(entry.unselected_variant_names,())
        alternative,=entry.unselected_protection
        self.assertEqual((alternative.source_rule_id,alternative.skill,alternative.test_profile),
            (SOURCE+':athletics',Skill.ATHLETICS,InlineProfile(2,3)))
        self.assertIsNone(alternative.test_profile.pool_cap)
        self.assertEqual(entry.definition.attacks[0].damage,DamageProfile(3))
        self.assertEqual(entry.definition.attacks[0].secondary_effects,())
        with self.assertRaises(ValueError):
            validate_pc_book_npc_definition(replace(entry.definition,protection=(alternative,)))

    def test_altered_stats_and_partial_book_source_cannot_claim_canonical_brewguard(self):
        definition=get_pc_book_npc_entry(PROFILE).definition
        attack,=definition.attacks
        protection,=definition.protection
        alternative,=get_pc_book_npc_entry(PROFILE).unselected_protection
        candidates=(
            replace(definition,attacks=(replace(attack,damage=DamageProfile(4)),)),
            replace(definition,attacks=(replace(attack,test_profile=InlineProfile(3,4)),)),
            replace(definition,attacks=(replace(attack,hands=None),)),
            replace(definition,resilience=ResilienceProfile(4,2)),
            replace(definition,id='authored:root',source_rule_id='authored:source'),
            replace(definition,id='authored:root',source_rule_id='authored:source',
                attacks=(replace(attack,source_rule_id='authored:attack'),)),
            replace(definition,id='authored:root',source_rule_id='authored:source',
                attacks=(replace(attack,source_rule_id='authored:attack'),),
                protection=(replace(protection,source_rule_id=alternative.source_rule_id),)),
        )
        for candidate in candidates:
            with self.subTest(candidate=candidate),self.assertRaises((TypeError,ValueError)):
                validate_pc_book_npc_definition(candidate)

    def test_equal_string_enums_float_dice_and_boolean_damage_aliases_are_rejected(self):
        definition=get_pc_book_npc_entry(PROFILE).definition
        for target,name,value in (('definition','injury_policy','brute'),('attack','skill','melee'),
                ('attack','hands','1h'),('attack','range_max','close'),('profile','dice',4.0),
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

    def test_each_definition_injury_and_unused_protection_graph_is_fresh(self):
        first=create_pc_book_npc(PROFILE,'first')
        second=create_pc_book_npc(PROFILE,'second')
        expected=deepcopy(second.definition)
        self.assertIsNot(first.definition,second.definition)
        self.assertIsNot(first.state.injury,second.state.injury)
        object.__setattr__(first.definition.attacks[0].damage,'base',99)
        self.assertEqual(second.definition,expected)
        self.assertEqual(get_pc_book_npc_entry(PROFILE).definition,expected)
        with self.assertRaises(ValueError):
            validate_pc_book_npc_definition(first.definition)
        entry=get_pc_book_npc_entry(PROFILE)
        object.__setattr__(entry.unselected_protection[0].test_profile,'dice',9)
        self.assertNotEqual(get_pc_book_npc_entry(PROFILE).unselected_protection,entry.unselected_protection)


if __name__=='__main__':
    unittest.main()
