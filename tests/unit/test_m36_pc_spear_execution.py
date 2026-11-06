"""Printed shield/Spear loadouts retain actual Help and first-Wound consequences."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import (
    PcAttackProof,PcNpcHelpProof,PcProfileWoundProof,PcMeleeStep,PcMeleeOutcome,
)
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy,WAAAGH_HELP_RULE_ID
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step


def scene(*,pcs=1,axe=False,**counts):
    source=book_pc_scenario(footpads=0,townsfolk=0,pc_count=pcs,max_rounds=1,**counts)
    if axe:
        source=replace(source,party=tuple(replace(m,pc=replace(m.pc,weapon=PcMeleeWeapon.AXE)) for m in source.party))
    return source


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def incoming(result,actor):
    return next(s for s in result.steps if type(s.proof) is PcAttackProof and s.proof.request.actor_id==actor)


class PcSpearExecutionTests(unittest.TestCase):
    def test_orc_shield_is_included_once_and_changes_staff_wound_into_stagger(self):
        unshielded=execute(scene(orcs=1),[1]*3+[10]*3)
        self.assertTrue(unshielded.state.enemy('orc1').state.injury.defeated)
        shielded=execute(scene(spear_orcs=1),[1]*3+[10]*3+[10]*3+[1]*3)
        pc_attack=next(s for s in shielded.steps if type(s.proof) is PcAttackProof)
        raw=pc_attack.proof.execution.resolution.attack
        self.assertTrue(pc_attack.proof.protection.source_request.defender_holds_shield)
        self.assertEqual((raw.damage,raw.effective_resilience),(6,6))
        self.assertEqual(shielded.state.enemy('spear_orc1').state.injury.wounds,0)
        self.assertFalse(shielded.state.enemy('spear_orc1').state.injury.defeated)
        self.assertTrue(shielded.state.enemy('spear_orc1').state.injury.conditions.has(Condition.STAGGERED))

    def test_three_actual_spear_attacks_keep_printed_damage_without_charge_or_pc_traits(self):
        for keyword,actor,threshold,damage in (
                ('spear_troopers','spear_trooper1',3,3),('spear_orcs','spear_orc1',4,3),
                ('spear_big_uns','spear_big_un1',4,4)):
            with self.subTest(profile=keyword):
                result=execute(scene(**{keyword:1}),[10]*3+[1]*3+[1]*3+[10]*3+[1])
                step=incoming(result,actor)
                raw=step.proof.execution.resolution.attack
                self.assertEqual((raw.attacker_test.trace.base_dice,raw.attacker_test.trace.rolled_dice,
                    raw.attacker_test.trace.threshold),(3,3,threshold))
                self.assertEqual((raw.impact_spec.damage.base,raw.damage),(damage,damage+3))
                self.assertEqual(raw.impact_spec.damage_modifiers,())
                self.assertEqual(len(result.state.party[0].injury.wounds),1)

    def test_big_un_first_wound_adds_drained_and_only_its_own_outnumber_bonus_is_lost(self):
        result=execute(scene(spear_big_uns=2,axe=True),[1]*3+[10]*3+[10]*3+[1]*3+[10]*4+[1]*3)
        ack,=tuple(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
        self.assertFalse(ack.source.enemy('spear_big_un1').state.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(ack.state.enemy('spear_big_un1').state.injury.conditions.conditions,
            frozenset({Condition.DRAINED}))
        first=incoming(result,'spear_big_un1').proof
        second=incoming(result,'spear_big_un2').proof
        self.assertEqual((first.execution.resolution.attack.attacker_test.trace.rolled_dice,
            second.execution.resolution.attack.attacker_test.trace.rolled_dice),(3,4))
        self.assertEqual(first.request.kernel_request.attack.attacker_test.dice_modifiers,())
        self.assertEqual(first.execution.resolution.attack.impact_spec.damage.base,4)
        self.assertFalse(ack.state.enemy('spear_big_un2').state.injury.conditions.has(Condition.DRAINED))
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)

    def test_second_big_un_wound_defeats_before_own_turn_and_preserves_disposition(self):
        result=execute(scene(spear_big_uns=1,pcs=2,axe=True),([1]*4+[10]*3)*2)
        acks=tuple(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
        self.assertEqual(tuple((s.proof.source.previous_wounds,s.proof.source.current_wounds,
            s.proof.source.defeated) for s in acks),((0,1,False),(1,2,True)))
        self.assertIsNone(acks[0].proof.decision)
        self.assertIsNotNone(acks[1].proof.decision)
        self.assertTrue(acks[0].state.enemy('spear_big_un1').state.injury.conditions.has(Condition.DRAINED))
        self.assertFalse(any(type(s.proof) is PcAttackProof and s.proof.request.actor_id=='spear_big_un1'
            for s in result.steps))
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_orc_spear_helps_drained_big_un_with_free_success_and_no_bonus_die(self):
        source=scene(spear_orcs=1,spear_big_uns=1,axe=True)
        member=source.party[0]
        priority=('spear_big_un1','spear_orc1')
        source=replace(source,party=(replace(member,target_priority=priority,
            defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority)),),
            npc_help_policies=(PcNpcHelpPolicy('spear_orc1','spear_big_un1'),))
        result=execute(source,[1]*3+[10]*3+[10]*3+[1]*3)
        help_step,=tuple(s for s in result.steps if type(s.proof) is PcNpcHelpProof)
        self.assertEqual(help_step.proof.request.actor_id,'spear_orc1')
        self.assertEqual(help_step.proof.execution.bonus.rule_id,WAAAGH_HELP_RULE_ID)
        self.assertTrue(help_step.source.enemy('spear_big_un1').state.injury.conditions.has(Condition.DRAINED))
        attack=incoming(result,'spear_big_un1').proof
        trace=attack.execution.resolution.attack.attacker_test.trace
        self.assertEqual((trace.rolled_dice,trace.cap_bypassing_dice,trace.success_delta,trace.successes),(3,0,1,1))
        self.assertEqual(attack.request.kernel_request.attack.attacker_test.dice_modifiers,())
        self.assertEqual(len(attack.npc_help_applications),1)

    def test_wounded_shielded_big_un_can_help_without_a_test(self):
        source=scene(spear_troopers=1,spear_big_uns=1,axe=True)
        member=source.party[0]
        priority=('spear_big_un1','spear_trooper1')
        source=replace(source,enemy_activation_order=priority,
            party=(replace(member,target_priority=priority,
                defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority)),),
            npc_help_policies=(PcNpcHelpPolicy('spear_big_un1','spear_trooper1'),))
        result=execute(source,[1]*3+[10]*3+[10]*4+[1]*3)
        help_step,=tuple(s for s in result.steps if type(s.proof) is PcNpcHelpProof)
        self.assertTrue(help_step.proof.request.actor_conditions.has(Condition.DRAINED))
        self.assertTrue(help_step.state.enemy('spear_big_un1').state.holds_shield)
        self.assertFalse(hasattr(help_step.proof.execution,'help_test_result'))
        self.assertEqual(incoming(result,'spear_trooper1').proof.execution.resolution.attack.attacker_test.successes,1)

    def test_big_un_repeated_stagger_also_applies_first_wound_band(self):
        # Two PCs each deal Staff Damage6 vs printed shielded Resilience6.
        result=execute(scene(spear_big_uns=1,pcs=2),([1,1,1,10]+[10]*3)*2+[10]*3+[1]*3)
        ack,=tuple(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
        injury=ack.state.enemy('spear_big_un1').state.injury
        self.assertEqual((injury.wounds,injury.defeated,injury.conditions.conditions),
            (1,False,frozenset({Condition.DRAINED})))

    def test_first_wound_receipt_cannot_repeat_or_lose_drained_in_cached_state(self):
        result=execute(scene(spear_big_uns=1,axe=True),[1]*3+[10]*3+[10]*3+[1]*3)
        ack,=tuple(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(ack.state,ack)
        with self.assertRaises(ValueError):
            PcMeleeStep(ack.source,replace(ack.proof,source=replace(ack.proof.source,previous_wounds=1)))
        forged=deepcopy(result)
        cached=next(s for s in forged.steps if type(s.proof) is PcProfileWoundProof)
        enemy=cached.state.enemy('spear_big_un1')
        object.__setattr__(cached.state,'enemies',(replace(enemy,state=replace(enemy.state,
            injury=replace(enemy.state.injury,conditions=ConditionState()))),))
        with self.assertRaises(ValueError):
            replace(forged)


if __name__=='__main__':
    unittest.main()
