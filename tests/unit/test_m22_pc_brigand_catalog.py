"""GM1.1 p97 Brigand's explicit Axe loadout and reserved combat provenance."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import patch

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.pc_npc_catalog import (PcBookNpcProfile, PcBookNpcAbility,
    get_pc_book_npc_entry, create_pc_book_npc, validate_pc_book_npc_definition)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatSide


class BrigandCatalogTests(unittest.TestCase):
    def test_printed_axe_attack_and_athletics_protection_keep_distinct_thresholds(self):
        entry = get_pc_book_npc_entry(PcBookNpcProfile.BRIGAND_AXE)
        self.assertEqual((entry.book_id,entry.version,entry.chapter,entry.page,entry.name),
            ('BOOK-GM-GUIDE','1.1','Allies and Antagonists',97,'Brigand (Axe)'))
        definition = entry.definition
        self.assertEqual((definition.id,definition.source_rule_id),
            ('pc-book-npc:brigand_axe','BOOK-GM-GUIDE:1.1:p97:brigand_axe'))
        self.assertEqual((definition.injury_policy,definition.wound_limit,definition.resilience),
            (TargetInjuryPolicy.MINION,1,ResilienceProfile(3,1)))
        attack, = definition.attacks
        self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,attack.damage,
            attack.range_min,attack.range_max,attack.hands,attack.ignores_armour,attack.secondary_effects),
            ('axe','BOOK-GM-GUIDE:1.1:p97:brigand_axe:axe',Skill.MELEE,InlineProfile(3,3),DamageProfile(3),
             RangedWeaponRange.CLOSE,RangedWeaponRange.CLOSE,RangedWeaponHands.ONE_HANDED,False,()))
        protection, = definition.protection
        self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
            ('BOOK-GM-GUIDE:1.1:p97:brigand_axe:athletics',Skill.ATHLETICS,InlineProfile(3,2)))
        validate_pc_book_npc_definition(definition)

    def test_active_ability_and_unselected_warbow_are_explicit_metadata(self):
        entry = get_pc_book_npc_entry(PcBookNpcProfile.BRIGAND_AXE)
        self.assertEqual(entry.inactive_abilities,())
        self.assertEqual(entry.active_abilities,(PcBookNpcAbility('Craven Opportunist',
            'Melee attacks against an enemy the Brigand actually outnumbers','+2d instead of +1d'),))
        self.assertEqual(entry.unselected_attack_names,('Warbow',))
        with self.assertRaises(FrozenInstanceError):
            entry.active_abilities[0].effect = '+3d'
        for profile in (PcBookNpcProfile.FOOTPAD,PcBookNpcProfile.EMPIRE_TOWNSFOLK):
            original = get_pc_book_npc_entry(profile)
            self.assertEqual(original.active_abilities,())
            self.assertEqual(original.unselected_attack_names,())
            self.assertEqual(len(original.inactive_abilities),1)

    def test_snapshot_has_only_selected_axe_and_independent_armoured_state(self):
        first = create_pc_book_npc(PcBookNpcProfile.BRIGAND_AXE,'brigand1')
        second = create_pc_book_npc(PcBookNpcProfile.BRIGAND_AXE,'brigand2')
        self.assertEqual((first.state.actor_id,first.state.side,first.state.available_attack_ids,
            first.state.current_resilience,first.state.wields_weapon,first.state.holds_shield),
            ('brigand1',CombatSide.OPPOSITION,('axe',),ResilienceProfile(3,1),True,False))
        self.assertEqual((first.state.injury.wounds,first.state.injury.wound_limit,first.state.injury.defeated),(0,1,False))
        self.assertIsNot(first.definition,second.definition)
        self.assertIsNot(first.definition.attacks[0],second.definition.attacks[0])
        self.assertIsNot(first.definition.resilience,second.definition.resilience)
        self.assertIsNot(first.state.injury,second.state.injury)
        self.assertIsNot(first.state.current_resilience,second.state.current_resilience)
        object.__setattr__(first.definition.attacks[0].damage,'base',9)
        self.assertEqual(second.definition.attacks[0].damage,DamageProfile(3))
        self.assertEqual(get_pc_book_npc_entry(PcBookNpcProfile.BRIGAND_AXE).definition.attacks[0].damage,DamageProfile(3))
        with self.assertRaises(ValueError):
            validate_pc_book_npc_definition(first.definition)

    def test_known_brigand_root_and_nested_sources_reserve_the_whole_canonical_loadout(self):
        definition = get_pc_book_npc_entry(PcBookNpcProfile.BRIGAND_AXE).definition
        attack, = definition.attacks
        protection, = definition.protection
        candidates = (replace(definition,resilience=ResilienceProfile(4)),
            replace(definition,attacks=(replace(attack,damage=DamageProfile(4)),)),
            replace(definition,protection=(replace(protection,test_profile=InlineProfile(3,3)),)),
            replace(definition,id='authored:renamed',source_rule_id='authored:renamed-source',
                attacks=(replace(attack,damage=DamageProfile(9)),),
                protection=(replace(protection,source_rule_id='authored:protection'),)),
            replace(definition,id='authored:renamed',source_rule_id='authored:renamed-source',
                attacks=(replace(attack,source_rule_id='authored:attack'),)))
        for candidate in candidates:
            with self.subTest(candidate=candidate),self.assertRaises(ValueError):
                validate_pc_book_npc_definition(candidate)
        alias = deepcopy(definition)
        object.__setattr__(alias.resilience,'bonus',True)
        with self.assertRaises(TypeError):
            validate_pc_book_npc_definition(alias)

    def test_authored_numeric_profile_keeps_cheap_nonbook_path(self):
        numeric = make_pc_melee_scenario().enemies[0].definition
        with patch('towr.domain.pc_npc_catalog._definition',side_effect=AssertionError('unexpected canonical graph')):
            self.assertIsNone(validate_pc_book_npc_definition(numeric))


if __name__ == '__main__':
    unittest.main()
