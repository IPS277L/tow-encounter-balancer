"""GM138: Bear Sweeping Claws and its persistent first-Wound Drained band."""
from copy import deepcopy
from dataclasses import replace
import unittest

from towr.domain.attack_models import DamageProfile,ResilienceProfile
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.injury_models import ProfileInjuryState,ProfileNpcType,ProfileStateChangeRequest
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile,PcBookNpcWoundBand,create_pc_book_npc,get_pc_book_npc_entry,
    validate_pc_book_npc_definition,
)
from towr.domain.pc_npc_wound_models import pc_npc_drained_profile_wound_state
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile,Skill


PROFILE=PcBookNpcProfile.BEAR_SWEEPING_CLAWS
SOURCE='BOOK-GM-GUIDE:1.1:p138:bear_sweeping_claws'


class PcBearCatalogTests(unittest.TestCase):
    def test_exact_bear_source_keeps_printed_natural_attack_and_athletics(self):
        entry=get_pc_book_npc_entry(PROFILE)
        definition=entry.definition
        self.assertEqual((entry.profile_id,entry.book_id,entry.version,entry.chapter,entry.page),
            (PROFILE,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',138))
        self.assertEqual((definition.id,definition.source_rule_id,definition.injury_policy,
            definition.wound_limit,definition.resilience),
            ('pc-book-npc:bear_sweeping_claws',SOURCE,TargetInjuryPolicy.BRUTE,3,ResilienceProfile(5,1)))
        attack,=definition.attacks
        self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,attack.damage,
            attack.range_min,attack.range_max,attack.hands,attack.ignores_armour,attack.secondary_effects),
            ('sweeping_claws',SOURCE+':sweeping_claws',Skill.MELEE,InlineProfile(4,3),DamageProfile(5),
             RangedWeaponRange.CLOSE,RangedWeaponRange.CLOSE,None,False,()))
        protection,=definition.protection
        self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
            (SOURCE+':athletics',Skill.ATHLETICS,InlineProfile(3,3)))
        self.assertEqual((attack.test_profile.maximum_dice,protection.test_profile.maximum_dice),(8,6))
        self.assertIsNone(attack.test_profile.pool_cap)
        self.assertIsNone(protection.test_profile.pool_cap)
        validate_pc_book_npc_definition(definition)

    def test_fresh_bear_has_no_weapon_or_shield_and_starts_with_no_conditions(self):
        snapshot=create_pc_book_npc(PROFILE,'bear')
        self.assertEqual((snapshot.state.actor_id,snapshot.state.definition_id,
            snapshot.state.wields_weapon,snapshot.state.holds_shield,snapshot.state.available_attack_ids,
            snapshot.state.current_resilience),
            ('bear','pc-book-npc:bear_sweeping_claws',False,False,('sweeping_claws',),ResilienceProfile(5,1)))
        self.assertEqual((snapshot.state.injury.wounds,snapshot.state.injury.wound_limit,
            snapshot.state.injury.defeated,snapshot.state.injury.defeat_cause),(0,3,False,None))
        self.assertFalse(snapshot.state.injury.conditions.conditions)

    def test_enduring_strength_requires_success_and_a_different_close_enemy(self):
        entry=get_pc_book_npc_entry(PROFILE)
        ability,=entry.active_abilities
        self.assertEqual(ability.name,'Enduring Strength')
        self.assertIn('successful Attack action',ability.scope)
        self.assertIn('second action remains available this turn',ability.scope)
        self.assertEqual(ability.effect,
            'May take a second action to Attack a different enemy in Close Range')
        fear,=entry.inactive_abilities
        self.assertEqual((fear.name,fear.scope,fear.effect),
            ('Fearsome','An enemy Gives Ground from a Bear attack','That enemy suffers Broken'))
        self.assertEqual((entry.unselected_attack_names,entry.unselected_protection,
            entry.unselected_variant_names),(('Crushing Weight',),(),()))

    def test_printed_wound_bands_cover_drained_one_two_and_defeat_three(self):
        self.assertEqual(get_pc_book_npc_entry(PROFILE).wound_bands,
            (PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'Drained'),
             PcBookNpcWoundBand(2,'Drained'),PcBookNpcWoundBand(3,'Defeated')))

    def test_actual_first_wound_ack_adds_drained_without_discarding_other_conditions(self):
        definition=get_pc_book_npc_entry(PROFILE).definition
        injury=ProfileInjuryState(1,3,ConditionState(frozenset({Condition.PRONE})))
        change=ProfileStateChangeRequest(ProfileNpcType.BRUTE,0,1,False)
        actual=pc_npc_drained_profile_wound_state(definition,injury,change)
        self.assertEqual((actual.wounds,actual.wound_limit,actual.defeated),(1,3,False))
        self.assertEqual(actual.conditions.conditions,frozenset({Condition.PRONE,Condition.DRAINED}))

    def test_second_wound_retains_existing_drained_and_third_is_ordinary_defeat(self):
        definition=get_pc_book_npc_entry(PROFILE).definition
        first=pc_npc_drained_profile_wound_state(definition,ProfileInjuryState(1,3),
            ProfileStateChangeRequest(ProfileNpcType.BRUTE,0,1,False))
        second=replace(first,wounds=2)
        self.assertIs(pc_npc_drained_profile_wound_state(definition,second,
            ProfileStateChangeRequest(ProfileNpcType.BRUTE,1,2,False)),second)
        self.assertTrue(second.conditions.has(Condition.DRAINED))
        third=replace(second,wounds=3,defeated=True)
        self.assertIs(pc_npc_drained_profile_wound_state(definition,third,
            ProfileStateChangeRequest(ProfileNpcType.BRUTE,2,3,True)),third)
        # Existing White Wolf still uses its original two-Wound first-band rule.
        wolf=get_pc_book_npc_entry(PcBookNpcProfile.WHITE_WOLF_CLAMPING_JAWS).definition
        actual=pc_npc_drained_profile_wound_state(wolf,ProfileInjuryState(1,2),
            ProfileStateChangeRequest(ProfileNpcType.BRUTE,0,1,False))
        self.assertTrue(actual.conditions.has(Condition.DRAINED))

    def test_first_wound_effect_requires_exact_band_and_canonical_updated_injury(self):
        definition=get_pc_book_npc_entry(PROFILE).definition
        injury=ProfileInjuryState(1,3)
        change=ProfileStateChangeRequest(ProfileNpcType.BRUTE,0,1,False)
        for malformed in (replace(change,previous_wounds=False),replace(change,current_wounds=True),
                replace(change,previous_wounds=1),replace(change,npc_type='brute')):
            with self.subTest(change=malformed):
                self.assertIs(pc_npc_drained_profile_wound_state(definition,injury,malformed),injury)
        with self.assertRaises(ValueError):
            pc_npc_drained_profile_wound_state(definition,ProfileInjuryState(0,3),change)
        with self.assertRaises(ValueError):
            pc_npc_drained_profile_wound_state(replace(definition,resilience=ResilienceProfile(5,2)),injury,change)
        other=get_pc_book_npc_entry(PcBookNpcProfile.MINOTAUR_AXE).definition
        self.assertIs(pc_npc_drained_profile_wound_state(other,injury,change),injury)

    def test_full_book_source_rejects_changed_attack_protection_or_partial_identity(self):
        definition=get_pc_book_npc_entry(PROFILE).definition
        attack,=definition.attacks
        protection,=definition.protection
        candidates=(
            replace(definition,attacks=(replace(attack,damage=DamageProfile(7)),)),
            replace(definition,attacks=(replace(attack,test_profile=InlineProfile(3,3,8)),)),
            replace(definition,protection=(replace(protection,test_profile=InlineProfile(4,3)),)),
            replace(definition,wound_limit=2),
            replace(definition,id='authored:root',source_rule_id='authored:source'),
            replace(definition,id='authored:root',source_rule_id='authored:source',
                attacks=(replace(attack,source_rule_id='authored:attack'),)),
            replace(definition,id='authored:root',source_rule_id='authored:source',
                protection=(replace(protection,source_rule_id='authored:protection'),)),
        )
        for candidate in candidates:
            with self.subTest(candidate=candidate),self.assertRaises((TypeError,ValueError)):
                validate_pc_book_npc_definition(candidate)

    def test_equal_string_enum_or_boolean_damage_aliases_do_not_bypass_book_types(self):
        definition=get_pc_book_npc_entry(PROFILE).definition
        for target,name,value in (('definition','injury_policy','brute'),('attack','skill','melee'),
                ('attack','range_max','close'),('damage','success_multiplier',True)):
            forged=deepcopy(definition)
            subject={'definition':forged,'attack':forged.attacks[0],'damage':forged.attacks[0].damage}[target]
            object.__setattr__(subject,name,value)
            self.assertEqual(forged,definition)
            with self.subTest(target=target,name=name),self.assertRaises(TypeError):
                validate_pc_book_npc_definition(forged)
        with self.assertRaises(TypeError):
            get_pc_book_npc_entry(PROFILE.value)

    def test_catalog_and_snapshot_factories_return_independent_graphs(self):
        first=create_pc_book_npc(PROFILE,'first')
        second=create_pc_book_npc(PROFILE,'second')
        expected=deepcopy(second.definition)
        self.assertIsNot(first.definition,second.definition)
        self.assertIsNot(first.state.injury,second.state.injury)
        object.__setattr__(first.definition.attacks[0].damage,'base',7)
        self.assertEqual(second.definition,expected)
        self.assertEqual(get_pc_book_npc_entry(PROFILE).definition,expected)
        with self.assertRaises(ValueError):
            validate_pc_book_npc_definition(first.definition)


if __name__=='__main__':
    unittest.main()
