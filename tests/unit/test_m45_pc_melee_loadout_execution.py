"""One shield-free chunk keeps Rage, real Help, Wound ACKs and action costs."""
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import (
    PcAttackProof,PcNpcHelpProof,PcProfileWoundProof,PcMeleeStep,PcMeleeOutcome,
)
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy,WAAAGH_HELP_RULE_ID
from towr.domain.pc_npc_ability_models import GOR_PRIMAL_RAGE_RULE_ID
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step


def scene(*,pcs=1,axe=False,rounds=1,**counts):
    source=book_pc_scenario(footpads=0,townsfolk=0,pc_count=pcs,max_rounds=rounds,**counts)
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


class PcMeleeLoadoutExecutionTests(unittest.TestCase):
    def test_removing_orc_shield_turns_equal_damage_stagger_into_real_wound(self):
        unshielded=execute(scene(unshielded_orcs=1),[1]*3+[10]*3)
        shielded=execute(scene(spear_orcs=1),[1]*3+[10]*3+[10]*3+[1]*3)
        self.assertTrue(unshielded.state.enemy('unshielded_orc1').state.injury.defeated)
        self.assertFalse(shielded.state.enemy('spear_orc1').state.injury.defeated)
        self.assertTrue(shielded.state.enemy('spear_orc1').state.injury.conditions.has(Condition.STAGGERED))
        first=next(s.proof for s in unshielded.steps if type(s.proof) is PcAttackProof)
        self.assertFalse(first.protection.source_request.defender_holds_shield)
        self.assertEqual(first.execution.resolution.attack.effective_resilience,5)

    def test_single_gor_keeps_primal_rage_after_actual_miss_without_dual_damage(self):
        result=execute(scene(single_gors=1,rounds=2),[10]*3+[1]*4+[10]*4+[1]*3
            +[10]*3+[1]*4+[10]*5+[1]*3)
        attacks=tuple(s.proof for s in result.steps if type(s.proof) is PcAttackProof
            and s.proof.request.actor_id=='single_gor1')
        self.assertEqual(tuple(p.execution.resolution.attack.attacker_test.trace.rolled_dice for p in attacks),(4,5))
        self.assertEqual(attacks[1].request.kernel_request.attack.attacker_test.dice_modifiers[0].rule_id,
            GOR_PRIMAL_RAGE_RULE_ID)
        self.assertTrue(all(p.execution.resolution.attack.impact_spec.damage.base==3 for p in attacks))
        self.assertTrue(all(p.execution.resolution.attack.impact_spec.damage_modifiers==() for p in attacks))

    def test_unshielded_orc_helps_drained_big_un_with_free_success_not_bonus_dice(self):
        source=scene(unshielded_orcs=1,unshielded_big_uns=1,axe=True)
        member=source.party[0];priority=('unshielded_big_un1','unshielded_orc1')
        source=replace(source,party=(replace(member,target_priority=priority,
            defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority)),),
            npc_help_policies=(PcNpcHelpPolicy('unshielded_orc1','unshielded_big_un1'),))
        result=execute(source,[1]*3+[10]*3+[10]*3+[1]*3)
        help_step,=tuple(s for s in result.steps if type(s.proof) is PcNpcHelpProof)
        self.assertTrue(help_step.source.enemy('unshielded_big_un1').state.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(help_step.proof.execution.bonus.rule_id,WAAAGH_HELP_RULE_ID)
        attack=incoming(result,'unshielded_big_un1').proof
        trace=attack.execution.resolution.attack.attacker_test.trace
        self.assertEqual((trace.rolled_dice,trace.cap_bypassing_dice,trace.success_delta,trace.successes),(3,0,1,1))
        self.assertEqual(attack.request.kernel_request.attack.attacker_test.dice_modifiers,())
        self.assertEqual(result.executed_actions,3)

    def test_wounded_unshielded_big_un_can_itself_help_later_sharpshooter(self):
        source=scene(unshielded_big_uns=1,sharpshooters=1,axe=True)
        source=replace(source,npc_help_policies=(PcNpcHelpPolicy('unshielded_big_un1','sharpshooter1'),))
        result=execute(source,[1]*3+[10]*3+[10]*4+[1]*3)
        help_step,=tuple(s for s in result.steps if type(s.proof) is PcNpcHelpProof)
        self.assertTrue(help_step.proof.request.actor_conditions.has(Condition.DRAINED))
        self.assertFalse(help_step.state.enemy('unshielded_big_un1').state.holds_shield)
        self.assertEqual(incoming(result,'sharpshooter1').proof.execution.resolution.attack.attacker_test.successes,1)

    def test_sharpshooter_first_wound_with_no_aim_keeps_printed_axe_and_normal_turn(self):
        result=execute(scene(sharpshooters=1,axe=True),[1]*3+[10]*4+[10]*3+[1]*3)
        ack,=tuple(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
        self.assertEqual(ack.state.enemy('sharpshooter1').state.injury.wounds,1)
        self.assertFalse(ack.state.enemy('sharpshooter1').state.injury.conditions.conditions)
        attack=incoming(result,'sharpshooter1').proof
        self.assertEqual((attack.execution.resolution.attack.attacker_test.trace.rolled_dice,
            attack.execution.resolution.attack.impact_spec.damage.base),(3,3))
        self.assertEqual(result.executed_actions,2)
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)

    def test_second_sharpshooter_wound_defeats_before_turn_and_ack_cannot_repeat(self):
        result=execute(scene(sharpshooters=1,pcs=2,axe=True),([1]*4+[10]*4)*2)
        acks=tuple(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
        self.assertEqual(tuple(s.proof.source.current_wounds for s in acks),(1,2))
        self.assertIsNone(acks[0].proof.decision)
        self.assertIsNotNone(acks[1].proof.decision)
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        with self.assertRaises(ValueError):apply_pc_melee_step(acks[0].state,acks[0])
        with self.assertRaises(ValueError):
            PcMeleeStep(acks[0].source,replace(acks[0].proof,source=replace(acks[0].proof.source,previous_wounds=1)))

    def test_four_printed_attacks_keep_damage_and_independent_protection_numbers(self):
        for keyword,actor,attack_dice,protection_dice,damage in (
                ('single_gors','single_gor1',4,4,3),('sharpshooters','sharpshooter1',3,4,3),
                ('unshielded_orcs','unshielded_orc1',3,3,3),
                ('unshielded_big_uns','unshielded_big_un1',3,3,4)):
            # PC misses, NPC succeeds with3 net successes: printed Damage then wounds once.
            result=execute(scene(**{keyword:1}),[10]*3+[1]*protection_dice
                +[1]*3+[10]*(attack_dice-3)+[10]*3+[1])
            raw=incoming(result,actor).proof.execution.resolution.attack
            self.assertEqual(raw.impact_spec.damage.base,damage)
            self.assertEqual(raw.damage,damage+3)
            self.assertEqual(raw.impact_spec.damage_modifiers,())
