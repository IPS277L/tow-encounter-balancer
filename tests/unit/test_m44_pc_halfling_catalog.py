"""Printed GM103 Dagger/Stealth loadout and full canonical identity."""
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
from towr.domain.turn_models import CombatSide


PROFILE=PcBookNpcProfile.HALFLING_THIEF_DAGGER
SOURCE='BOOK-GM-GUIDE:1.1:p103:halfling_thief_dagger'


class PcHalflingCatalogTests(unittest.TestCase):
    def test_exact_printed_dagger_stealth_and_unarmoured_minion(self):
        entry=get_pc_book_npc_entry(PROFILE)
        definition=entry.definition
        self.assertEqual((entry.profile_id,entry.book_id,entry.version,entry.chapter,entry.page),
            (PROFILE,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',103))
        self.assertEqual((definition.id,definition.source_rule_id,definition.injury_policy,
            definition.wound_limit,definition.resilience),
            ('pc-book-npc:halfling_thief_dagger',SOURCE,TargetInjuryPolicy.MINION,1,ResilienceProfile(2,0)))
        attack,=definition.attacks
        self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,attack.damage,
            attack.range_min,attack.range_max,attack.hands,attack.ignores_armour,attack.secondary_effects),
            ('dagger',SOURCE+':dagger',Skill.MELEE,InlineProfile(2,3),DamageProfile(1),
             RangedWeaponRange.CLOSE,RangedWeaponRange.CLOSE,RangedWeaponHands.ONE_HANDED,False,()))
        protection,=definition.protection
        self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
            (SOURCE+':stealth',Skill.STEALTH,InlineProfile(3,5)))
        self.assertEqual((attack.test_profile.maximum_dice,protection.test_profile.maximum_dice),(4,6))
        self.assertIsNone(attack.test_profile.pool_cap)
        self.assertIsNone(protection.test_profile.pool_cap)
        validate_pc_book_npc_definition(definition)

    def test_factory_is_fresh_armed_no_shield_without_initial_conditions(self):
        snapshot=create_pc_book_npc(PROFILE,'thief')
        state=snapshot.state
        self.assertEqual((state.actor_id,state.definition_id,state.side,state.wields_weapon,
            state.holds_shield,state.current_resilience,state.available_attack_ids),
            ('thief','pc-book-npc:halfling_thief_dagger',CombatSide.OPPOSITION,True,False,
             ResilienceProfile(2,0),('dagger',)))
        self.assertEqual((state.injury.wounds,state.injury.wound_limit,state.injury.defeated,
            state.injury.defeat_cause),(0,1,False,None))
        self.assertFalse(state.injury.conditions.conditions)

    def test_now_you_see_me_is_active_for_aware_attacks_without_erasing_unopposed_rules(self):
        entry=get_pc_book_npc_entry(PROFILE)
        ability,=entry.active_abilities
        self.assertEqual(ability.name,'Now You See Me')
        self.assertIn('aware of',ability.scope)
        for detail in ('Stealth','Oppose','unaware','Defenceless'):
            self.assertIn(detail,ability.effect)
        self.assertEqual(entry.wound_bands,())
        self.assertEqual(entry.unselected_protection,())

    def test_theft_and_throwing_knives_are_preserved_without_silent_activation(self):
        entry=get_pc_book_npc_entry(PROFILE)
        theft,=entry.inactive_abilities
        self.assertEqual(theft.name,'Thieving Blighter')
        self.assertIn('Move Quietly',theft.scope)
        for detail in ('without cover or concealment','trapping','Asset','Coin','Close Range',
                'not in a character\'s hands','Dexterity','owner\'s Awareness'):
            self.assertIn(detail,theft.effect)
        self.assertEqual(entry.unselected_attack_names,('Throwing Knives',))
        self.assertEqual(entry.unselected_variant_names,())

    def test_changed_profiles_gear_and_partial_book_identities_cannot_claim_thief(self):
        definition=get_pc_book_npc_entry(PROFILE).definition
        attack,=definition.attacks
        protection,=definition.protection
        for forged in (
            replace(definition,resilience=ResilienceProfile(2,1)),
            replace(definition,attacks=(replace(attack,damage=DamageProfile(2)),)),
            replace(definition,attacks=(replace(attack,hands=RangedWeaponHands.TWO_HANDED),)),
            replace(definition,protection=(replace(protection,skill=Skill.ATHLETICS),)),
            replace(definition,protection=(replace(protection,test_profile=InlineProfile(3,4)),)),
            replace(definition,id='authored:root',source_rule_id='authored:source'),
            replace(definition,id='authored:root',source_rule_id='authored:source',
                attacks=(replace(attack,source_rule_id='authored:attack'),)),
            replace(definition,id='authored:root',source_rule_id='authored:source',
                protection=(replace(protection,source_rule_id='authored:protection'),)),
        ):
            with self.subTest(forged=forged),self.assertRaises((TypeError,ValueError)):
                validate_pc_book_npc_definition(forged)

    def test_equal_string_enum_float_dice_and_bool_aliases_are_rejected(self):
        definition=get_pc_book_npc_entry(PROFILE).definition
        for target,name,value in (('definition','injury_policy','minion'),('attack','skill','melee'),
                ('attack','hands','1h'),('protection','skill','stealth'),('profile','dice',3.0),
                ('damage','success_multiplier',True)):
            forged=deepcopy(definition)
            subject={'definition':forged,'attack':forged.attacks[0],
                'protection':forged.protection[0],'profile':forged.protection[0].test_profile,
                'damage':forged.attacks[0].damage}[target]
            object.__setattr__(subject,name,value)
            self.assertEqual(forged,definition)
            with self.subTest(target=target,name=name),self.assertRaises(TypeError):
                validate_pc_book_npc_definition(forged)
        with self.assertRaises(TypeError):
            get_pc_book_npc_entry(PROFILE.value)

    def test_factory_definition_and_state_graphs_are_independent(self):
        first=create_pc_book_npc(PROFILE,'one')
        second=create_pc_book_npc(PROFILE,'two')
        expected=deepcopy(second.definition)
        self.assertIsNot(first.definition,second.definition)
        self.assertIsNot(first.state.injury,second.state.injury)
        object.__setattr__(first.definition.protection[0].test_profile,'threshold',1)
        self.assertEqual(second.definition,expected)
        self.assertEqual(get_pc_book_npc_entry(PROFILE).definition,expected)
        with self.assertRaises(ValueError):
            validate_pc_book_npc_definition(first.definition)


if __name__=='__main__':
    unittest.main()
