"""GM1.1 pp93/100: fixed Halberd/Defence loadout, without PC weapon traits."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from enum import Enum
import unittest
from unittest.mock import patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import PcAttackProof
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile, create_pc_book_npc, get_pc_book_npc_entry,
    validate_pc_book_npc_definition,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario


TROOPER=PcBookNpcProfile.EMPIRE_STATE_TROOPER_HALBERD
SOURCE='BOOK-GM-GUIDE:1.1:p100:empire_state_trooper_halberd'


def single_source():
    return book_pc_scenario(troopers=1,footpads=0,townsfolk=0,pc_count=1,max_rounds=1)


class PcStateTrooperTests(unittest.TestCase):
    def test_printed_halberd_defence_and_armour_are_selected_explicitly(self):
        entry=get_pc_book_npc_entry(TROOPER)
        self.assertEqual((entry.book_id,entry.version,entry.chapter,entry.page,entry.name),
            ('BOOK-GM-GUIDE','1.1','Allies and Antagonists',100,
             'Empire State Trooper (Halberd, Defence)'))
        definition=entry.definition
        self.assertEqual((definition.id,definition.source_rule_id,definition.injury_policy,
            definition.wound_limit,definition.resilience),
            ('pc-book-npc:empire_state_trooper_halberd',SOURCE,
             TargetInjuryPolicy.MINION,1,ResilienceProfile(3,1)))
        attack,=definition.attacks
        self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,
            attack.damage,attack.hands,attack.range_min,attack.range_max,
            attack.ignores_armour,attack.secondary_effects),
            ('halberd',SOURCE+':halberd',Skill.MELEE,InlineProfile(3,3),DamageProfile(5),
             RangedWeaponHands.TWO_HANDED,RangedWeaponRange.CLOSE,
             RangedWeaponRange.CLOSE,False,()))
        protection,=definition.protection
        self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
            (SOURCE+':defence',Skill.DEFENCE,InlineProfile(3,4)))
        self.assertIsNone(validate_pc_book_npc_definition(definition))

    def test_full_trigger_and_numeric_unselected_athletics_remain_metadata(self):
        entry=get_pc_book_npc_entry(TROOPER)
        self.assertEqual((entry.active_abilities,entry.wound_bands),((),()))
        self.assertEqual(entry.unselected_attack_names,('Spear','Crossbow','Handgun'))
        ability,=entry.inactive_abilities
        self.assertEqual(ability.name,'Supporting Action')
        self.assertIn('An enemy moves into Close Range',ability.scope)
        self.assertIn('adjacent Zone',ability.scope)
        self.assertIn('not in Close Range of an enemy',ability.scope)
        self.assertIn('Charge or make a ranged attack',ability.effect)
        alternative,=entry.unselected_protection
        self.assertEqual((alternative.source_rule_id,alternative.skill,alternative.test_profile),
            (SOURCE+':athletics',Skill.ATHLETICS,InlineProfile(3,3)))
        self.assertEqual(tuple(p.skill for p in entry.definition.protection),(Skill.DEFENCE,))
        with self.assertRaises(FrozenInstanceError):
            entry.unselected_protection=()
        for old in PcBookNpcProfile:
            if old is not TROOPER:
                self.assertEqual(get_pc_book_npc_entry(old).unselected_protection,())

    def test_fresh_snapshots_and_metadata_do_not_share_mutable_bypass_graphs(self):
        first=create_pc_book_npc(TROOPER,'trooper1')
        second=create_pc_book_npc(TROOPER,'trooper2')
        self.assertEqual((first.state.injury.wounds,first.state.injury.wound_limit,
            first.state.injury.defeated,first.state.available_attack_ids,
            first.state.wields_weapon,first.state.holds_shield,
            first.state.current_resilience),(0,1,False,('halberd',),True,False,ResilienceProfile(3,1)))
        self.assertIsNot(first.definition,second.definition)
        self.assertIsNot(first.state.injury,second.state.injury)
        self.assertIsNot(first.definition.resilience,first.state.current_resilience)
        object.__setattr__(first.definition.attacks[0].damage,'base',9)
        self.assertEqual(second.definition.attacks[0].damage,DamageProfile(5))
        with self.assertRaises(ValueError):
            validate_pc_book_npc_definition(first.definition)
        entry=get_pc_book_npc_entry(TROOPER)
        object.__setattr__(entry.unselected_protection[0].test_profile,'dice',9)
        self.assertEqual(get_pc_book_npc_entry(TROOPER).unselected_protection[0].test_profile,InlineProfile(3,3))

    def test_fixed_identity_rejects_alternative_or_modified_combat_profiles(self):
        entry=get_pc_book_npc_entry(TROOPER)
        definition=entry.definition
        attack,=definition.attacks
        protection,=definition.protection
        invalid=(replace(definition,resilience=ResilienceProfile(4)),
            replace(definition,attacks=(replace(attack,damage=DamageProfile(6)),)),
            replace(definition,attacks=(replace(attack,hands=RangedWeaponHands.ONE_HANDED),)),
            replace(definition,protection=entry.unselected_protection),
            replace(definition,protection=(replace(protection,test_profile=InlineProfile(3,3)),)),
            replace(definition,id='authored:renamed',source_rule_id='authored:source',
                attacks=(replace(attack,source_rule_id='authored:attack'),)),
            replace(definition,id='authored:renamed',source_rule_id='authored:source',
                attacks=(replace(attack,source_rule_id='authored:attack'),),
                protection=entry.unselected_protection))
        for candidate in invalid:
            with self.subTest(candidate=candidate),self.assertRaises(ValueError):
                validate_pc_book_npc_definition(candidate)
        for path,name,value in (('resilience','bonus',True),
                ('protection','skill',Enum('OtherSkill',{'DEFENCE':'defence'},type=str).DEFENCE)):
            forged=deepcopy(definition)
            target=forged.resilience if path=='resilience' else forged.protection[0]
            object.__setattr__(target,name,value)
            with self.assertRaises(TypeError):
                validate_pc_book_npc_definition(forged)

    def test_native_two_handed_protection_uses_defence_four_not_athletics_three(self):
        rng=ScriptedD10([1,10,10]+[4,10,10]+[10]*3+[1,10,10])
        result=run_pc_melee_scenario(single_source(),rng)
        rng.assert_exhausted()
        proof=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof)
        self.assertIs(proof.protection.source_request.selected_skill,Skill.DEFENCE)
        defender=proof.execution.resolution.attack.defender_test
        self.assertEqual((defender.trace.rolled_dice,defender.trace.threshold,defender.successes),(3,4,1))

    def test_npc_printed_halberd_does_not_inherit_pc_bonus_against_armour(self):
        source=single_source()
        member=source.party[0]
        source=replace(source,party=(replace(member,pc=replace(member.pc,armour_bonus=1)),))
        rng=ScriptedD10([10]*3+[1]*3+[1]*3+[10]*3+[1])
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        proof=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='trooper1')
        attack=proof.execution.resolution.attack
        self.assertEqual((attack.impact_spec.damage.base,attack.impact_spec.damage_modifiers,
            attack.damage,attack.effective_resilience),(5,(),8,4))

    def test_pc_axe_still_gets_its_own_bonus_against_trooper_armour(self):
        source=single_source()
        member=source.party[0]
        source=replace(source,party=(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.AXE)),))
        rng=ScriptedD10([1,10,10]+[10]*3)
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        proof=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof)
        attack=proof.execution.resolution.attack
        self.assertEqual((attack.damage,attack.effective_resilience),(5,4))
        self.assertEqual(len(attack.impact_spec.damage_modifiers),1)
        self.assertTrue(result.state.enemy('trooper1').state.injury.defeated)

    def test_forged_source_is_rejected_before_any_random_roll(self):
        source=deepcopy(single_source())
        object.__setattr__(source.enemies[0].definition.protection[0],'skill',Skill.ATHLETICS)
        with patch('towr.engine.pc_melee_runner.resolve_test') as resolve:
            with self.assertRaises((TypeError,ValueError)):
                run_pc_melee_scenario(source,ScriptedD10(()))
            resolve.assert_not_called()


if __name__=='__main__':
    unittest.main()
