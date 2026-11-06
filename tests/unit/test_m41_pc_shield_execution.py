"""Shield variants retain their own rage, damage and first-Wound behavior."""
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import PcAttackProof,PcMeleeOutcome,PcMeleeStep,PcProfileWoundProof
from towr.domain.pc_npc_ability_models import GOR_PRIMAL_RAGE_RULE_ID,pc_npc_damage_modifiers
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy
from towr.domain.test_models import DiceModifier
from towr.engine.pc_melee_runner import apply_pc_melee_step,run_pc_melee_scenario


def scene(*,pcs=1,rounds=1,axe=False,**counts):
    source=book_pc_scenario(footpads=0,townsfolk=0,pc_count=pcs,max_rounds=rounds,**counts)
    return replace(source,facts=replace(source.facts,outnumbering_bonus_approved=False),
        party=tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.AXE)) if axe else member
            for member in source.party))


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def incoming(result,actor):
    return tuple(s for s in result.steps if type(s.proof) is PcAttackProof and s.proof.request.actor_id==actor)


class PcShieldExecutionTests(unittest.TestCase):
    def test_gor_self_staggered_rage_adds_one_die_but_single_axe_has_no_dual_damage(self):
        result=execute(scene(shield_gors=1),[1,10,10,1,10,10,10]+[1]*5+[10]*3+[1])
        attack,=incoming(result,'shield_gor1')
        self.assertTrue(attack.source.enemy('shield_gor1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(attack.proof.request.kernel_request.attack.attacker_test.dice_modifiers,
            (DiceModifier(GOR_PRIMAL_RAGE_RULE_ID,1),))
        raw=attack.proof.execution.resolution.attack
        self.assertEqual((raw.attacker_test.trace.base_dice,raw.attacker_test.trace.rolled_dice,
            raw.attacker_test.trace.pool_cap),(4,5,8))
        self.assertEqual(raw.impact_spec.damage.base,3)
        self.assertEqual(raw.impact_spec.damage_modifiers,())
        self.assertEqual(pc_npc_damage_modifiers(attack.source.enemy('shield_gor1').definition),())
        self.assertTrue(attack.source.enemy('shield_gor1').state.holds_shield)

    def test_gor_miss_adds_stagger_and_next_actual_attack_uses_rage_once(self):
        values=([10]*3+[1]*4+[10]*4+[1]*3
            +[10]*3+[1]*4+[10]*5+[1]*3)
        result=execute(scene(shield_gors=1,rounds=2),values)
        first,second=incoming(result,'shield_gor1')
        self.assertEqual(tuple(s.proof.execution.resolution.attack.attacker_test.trace.rolled_dice
            for s in (first,second)),(4,5))
        self.assertFalse(first.source.enemy('shield_gor1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(second.source.enemy('shield_gor1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(result.state.enemy('shield_gor1').state.injury.wounds,0)

    def test_printed_gor_shield_changes_damage_five_from_defeat_to_stagger(self):
        hit=[1]*3+[1,10,10,10]
        unshielded=execute(scene(gors=1),hit)
        self.assertIs(unshielded.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        shielded=execute(scene(shield_gors=1),hit+[10]*5+[1]*3)
        injury=shielded.state.enemy('shield_gor1').state.injury
        self.assertEqual((injury.wounds,injury.defeated),(0,False))
        self.assertTrue(injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(shielded.state.enemy('shield_gor1').state.current_resilience.total,5)

    def test_gor_rage_and_named_help_apply_as_distinct_ordinary_and_bypass_dice(self):
        source=scene(shield_gors=1,peasants=1)
        source=replace(source,enemy_activation_order=('peasant1','shield_gor1'),
            npc_help_policies=(PcNpcHelpPolicy('peasant1','shield_gor1'),))
        result=execute(source,[1,10,10,1,10,10,10]+[10]*6+[1]*3)
        attack,=incoming(result,'shield_gor1')
        trace=attack.proof.execution.resolution.attack.attacker_test.trace
        self.assertEqual((trace.base_dice,trace.regular_dice_delta,trace.cap_bypassing_dice,trace.rolled_dice),(4,1,1,6))
        self.assertEqual(len(attack.proof.npc_help_applications),1)
        self.assertEqual(result.executed_actions,3)

    def test_knight_shield_is_included_once_and_changes_damage_six_to_stagger(self):
        values=[1]*3+[10]*4+[10]*4+[1]*3
        unshielded=execute(scene(empire_knights=1),values)
        self.assertTrue(unshielded.state.enemy('empire_knight1').state.injury.conditions.has(Condition.DRAINED))
        shielded=execute(scene(shield_knights=1),values)
        enemy=shielded.state.enemy('shield_knight1')
        self.assertEqual((enemy.state.current_resilience.total,enemy.state.injury.wounds),(6,0))
        self.assertTrue(enemy.state.holds_shield)
        self.assertTrue(enemy.state.injury.conditions.has(Condition.STAGGERED))
        attack,=incoming(shielded,'shield_knight1')
        self.assertEqual(attack.proof.execution.resolution.attack.impact_spec.damage.base,4)
        self.assertEqual(attack.proof.execution.resolution.attack.impact_spec.damage_modifiers,())

    def test_knight_first_wound_drained_continues_with_four_dice_healthy_ally_gets_outnumbering(self):
        source=scene(shield_knights=2,axe=True)
        source=replace(source,facts=replace(source.facts,outnumbering_bonus_approved=True))
        result=execute(source,[1]*3+[10]*4+[1]*4+[10]*3+[1]+[1]*5+[10]*3+[1,1])
        ack,=tuple(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
        self.assertTrue(ack.state.enemy('shield_knight1').state.injury.conditions.has(Condition.DRAINED))
        first,=incoming(result,'shield_knight1')
        healthy,=incoming(result,'shield_knight2')
        self.assertEqual(first.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,4)
        self.assertEqual(healthy.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,5)
        self.assertEqual(first.proof.request.kernel_request.attack.attacker_test.dice_modifiers,())
        with self.assertRaises(ValueError):
            apply_pc_melee_step(ack.state,ack)

    def test_second_knight_wound_defeats_before_its_own_turn(self):
        result=execute(scene(shield_knights=1,pcs=2,axe=True),([1]*3+[10]*4)*2)
        acks=tuple(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
        self.assertEqual(tuple(s.proof.source.current_wounds for s in acks),(1,2))
        self.assertIsNone(acks[0].proof.decision)
        self.assertIsNotNone(acks[1].proof.decision)
        self.assertFalse(incoming(result,'shield_knight1'))
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)


if __name__=='__main__':
    unittest.main()
