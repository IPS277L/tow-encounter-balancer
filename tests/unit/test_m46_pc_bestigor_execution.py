"""Literal Bestigor choices, actual W1 entitlement and exactly one Glorious Attack."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import (
    PcAttackProof,PcProfileWoundProof,PcMeleeStep,PcMeleeOutcome,build_pc_melee_attack,
)
from towr.domain.pc_bestigor_models import (
    PcNpcBloodRageProof,expected_pc_npc_blood_rage,pc_bestigor_glorious_source,
)
from towr.domain.pc_npc_blood_rage_policy_models import BLOOD_RAGE_RULE_ID,BESTIGOR_WOUND_GLORIOUS_RULE_ID
from towr.domain.pc_npc_ability_models import pc_npc_attack_modifiers
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy
from towr.domain.test_models import (
    DiceModifier,InlineProfile,QualityModifier,RerollLock,Skill,TestQuality,TestRequest,
)
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step
from towr.rules.test_resolution import resolve_test,RerollAllFailures


def scene(*,selected=True,axe=True,pcs=1,bestigors=1,rounds=2,**counts):
    source=book_pc_scenario(bestigors=bestigors,footpads=0,townsfolk=0,
        pc_count=pcs,max_rounds=rounds,**counts)
    return replace(source,npc_blood_rage_actor_ids=tuple(f'bestigor{i+1}' for i in range(bestigors)) if selected else (),
        party=tuple(replace(m,pc=replace(m.pc,weapon=PcMeleeWeapon.AXE if axe else PcMeleeWeapon.STAFF))
            for m in source.party))


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def attacks(result,actor='bestigor1'):
    return tuple(s for s in result.steps if type(s.proof) is PcAttackProof and s.proof.request.actor_id==actor)


def wounded_two_rounds():
    return execute(scene(),[1]*3+[10]*4
        +[10,1,10,1]+[1,10]+[1]*3+[1]
        +[10]*3+[1]*4+[10]*4+[1]*3)


class PcBestigorExecutionTests(unittest.TestCase):
    def test_rage_follows_reservation_before_roll_without_action_rng_or_wound(self):
        result=wounded_two_rounds()
        rage,=tuple(s for s in result.steps if type(s.proof) is PcNpcBloodRageProof)
        self.assertEqual(rage.proof.actor_id,'bestigor1')
        turn=rage.source.round_state.active_turn
        self.assertEqual((turn.actor_id,len(turn.action_slots),turn.action_slots[0].executed),('bestigor1',1,False))
        self.assertEqual(rage.source.round_state,rage.state.round_state)
        self.assertEqual(rage.source.enemy('bestigor1').state.injury.wounds,1)
        self.assertEqual(rage.state.enemy('bestigor1').state.injury.wounds,1)
        self.assertFalse(rage.source.enemy('bestigor1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(rage.state.enemy('bestigor1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(result.executed_actions,4)

    def test_selected_rage_cannot_be_skipped_duplicated_retargeted_or_applied_early(self):
        result=wounded_two_rounds()
        rage=next(s for s in result.steps if type(s.proof) is PcNpcBloodRageProof)
        with self.assertRaises(ValueError):build_pc_melee_attack(rage.source)
        with self.assertRaises(ValueError):apply_pc_melee_step(rage.state,rage)
        with self.assertRaises(ValueError):PcMeleeStep(rage.state,rage.proof)
        for proof in (replace(rage.proof,actor_id='pc1'),replace(rage.proof,action_id='foreign')):
            with self.assertRaises(ValueError):PcMeleeStep(rage.source,proof)
        with self.assertRaises(ValueError):PcMeleeStep(result.steps[0].source,rage.proof)
        attack=attacks(result)[0]
        with self.assertRaises(ValueError):PcMeleeStep(rage.source,attack.proof)

    def test_actual_w1_ack_grants_only_next_attack_and_rerolls_all_failed_dice_once(self):
        result=wounded_two_rounds()
        ack,=tuple(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
        self.assertIsNone(pc_bestigor_glorious_source(ack.source,'bestigor1'))
        source=pc_bestigor_glorious_source(ack.state,'bestigor1')
        self.assertEqual(source.profile_change,ack.proof.source)
        first,second=attacks(result)
        self.assertEqual(first.proof.npc_glorious_source,source)
        self.assertIsNone(second.proof.npc_glorious_source)
        trace=first.proof.execution.resolution.attack.attacker_test.trace
        self.assertIs(trace.quality,TestQuality.GLORIOUS)
        self.assertEqual((trace.initial_values,trace.final_values),((10,1,10,1),(1,1,10,1)))
        self.assertEqual(tuple((r.index,r.original,r.replacement) for r in trace.rerolls),((0,10,1),(2,10,10)))
        self.assertIn(BESTIGOR_WOUND_GLORIOUS_RULE_ID,trace.applied_rule_ids)
        self.assertEqual(trace.rolled_dice,4)
        self.assertIs(second.proof.execution.resolution.attack.attacker_test.trace.quality,TestQuality.NORMAL)
        self.assertFalse(second.proof.execution.resolution.attack.attacker_test.trace.rerolls)
        self.assertEqual(result.state.enemy('bestigor1').state.injury.wounds,1)
        self.assertIsNone(pc_bestigor_glorious_source(result.state,'bestigor1'))
        self.assertTrue(all(m.fate==source_member.fate for m,source_member in zip(result.state.party,result.source.party)))

    def test_empty_list_declines_acquisition_but_natural_stagger_still_grants_rage_bonus(self):
        result=execute(scene(selected=False),[1]*3+[10]*4
            +[10,1,10]+[1,10]+[1]*3
            +[10]*3+[1]*4+[10]*4+[1]*3)
        self.assertFalse(any(type(s.proof) is PcNpcBloodRageProof for s in result.steps))
        first,second=attacks(result)
        self.assertEqual(tuple(s.proof.execution.resolution.attack.attacker_test.trace.rolled_dice for s in (first,second)),(3,4))
        self.assertIsNotNone(first.proof.npc_glorious_source)
        self.assertIsNone(second.proof.npc_glorious_source)
        self.assertTrue(second.source.enemy('bestigor1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(second.proof.request.kernel_request.attack.attacker_test.dice_modifiers,
            (DiceModifier(BLOOD_RAGE_RULE_ID,1),))

    def test_repeated_stagger_wound_grants_glorious_and_removal_allows_one_new_rage(self):
        result=execute(scene(axe=False),[1]*3+[10]*4+[10]*4+[1]*3
            +[1]*3+[10]*4+[10]*4+[10]*4+[1]*3)
        first,second=attacks(result)
        self.assertIsNone(first.proof.npc_glorious_source)
        self.assertIsNotNone(second.proof.npc_glorious_source)
        self.assertTrue(first.source.enemy('bestigor1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(second.source.enemy('bestigor1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(len(tuple(s for s in result.steps if type(s.proof) is PcNpcBloodRageProof)),1)
        ack,=tuple(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
        self.assertEqual((ack.proof.source.previous_wounds,ack.proof.source.current_wounds),(0,1))
        self.assertFalse(ack.state.enemy('bestigor1').state.injury.conditions.has(Condition.STAGGERED))

    def test_w1_glorious_with_all_initial_successes_needs_no_rerolls(self):
        result=execute(scene(selected=False,rounds=1),[1]*3+[10]*4+[1]*3+[1]*3+[1])
        trace=attacks(result)[0].proof.execution.resolution.attack.attacker_test.trace
        self.assertIs(trace.quality,TestQuality.GLORIOUS)
        self.assertEqual(trace.rerolls,())
        self.assertIsNone(pc_bestigor_glorious_source(result.state,'bestigor1'))

    def test_w2_before_own_turn_defeats_without_voluntary_rage_or_fake_glorious_attack(self):
        result=execute(scene(pcs=2),([1]*4+[10]*4)*2)
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertFalse(attacks(result))
        self.assertFalse(any(type(s.proof) is PcNpcBloodRageProof for s in result.steps))
        self.assertIsNone(pc_bestigor_glorious_source(result.state,'bestigor1'))

    def test_multiple_bestigors_keep_independent_wound_and_attack_sources(self):
        source=scene(pcs=2,bestigors=2,rounds=1)
        second=source.party[1];priority=('bestigor2','bestigor1')
        source=replace(source,party=(source.party[0],replace(second,target_priority=priority,
            defeat_decisions=tuple(second.defeat_decision(a) for a in priority))))
        result=execute(source,([1]*3+[10]*4)*2+([10]*4+[10]*4+[1]*3)*2)
        one,two=attacks(result,'bestigor1')[0],attacks(result,'bestigor2')[0]
        self.assertEqual((one.proof.npc_glorious_source.actor_id,two.proof.npc_glorious_source.actor_id),('bestigor1','bestigor2'))
        self.assertNotEqual(one.proof.npc_glorious_source.wound_attack_id,two.proof.npc_glorious_source.wound_attack_id)
        self.assertEqual(result.executed_actions,4)

    def test_glorious_source_and_quality_cannot_be_dropped_or_retargeted_in_replay(self):
        first=attacks(wounded_two_rounds())[0]
        with self.assertRaises(ValueError):PcMeleeStep(first.source,replace(first.proof,npc_glorious_source=None))
        wrong=replace(first.proof.npc_glorious_source,actor_id='other')
        with self.assertRaises(ValueError):PcMeleeStep(first.source,replace(first.proof,npc_glorious_source=wrong))
        forged=deepcopy(first.proof)
        object.__setattr__(forged.request.kernel_request.attack.attacker_test,'quality_modifiers',())
        with self.assertRaises(ValueError):PcMeleeStep(first.source,forged)

    def test_rage_bonus_uses_cap8_named_bypass_and_is_not_a_defence_bonus(self):
        first=attacks(wounded_two_rounds())[0]
        request,protection=build_pc_melee_attack(first.source)
        self.assertEqual(request.kernel_request.attack.defender_test.profile.base_dice,3)
        self.assertEqual(request.kernel_request.attack.attacker_test.profile.maximum_dice,8)
        profile=request.kernel_request.attack.attacker_test.profile
        modified=TestRequest('cap',profile,(DiceModifier(BLOOD_RAGE_RULE_ID,1),
            DiceModifier('ordinary:bonus',10),DiceModifier('named:bypass',1,True)))
        rng=ScriptedD10([1]*9)
        self.assertEqual(resolve_test(modified,rng).trace.rolled_dice,9)
        rng.assert_exhausted()
        defending=next(s.proof for s in wounded_two_rounds().steps if type(s.proof) is PcAttackProof
            and s.proof.request.actor_id=='pc1').protection
        self.assertEqual(defending.attack.defender_test.dice_modifiers,())

    def test_drained_filters_ordinary_rage_bonus_without_removing_glorious(self):
        # Pure preparation boundary; the fixed current scene has no external Drained source for Bestigor.
        state=attacks(wounded_two_rounds())[0].source
        enemy=state.enemy('bestigor1')
        drained=replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
            conditions=enemy.state.injury.conditions.with_condition(Condition.DRAINED))))
        state=replace(state,enemies=(drained,))
        request,_=build_pc_melee_attack(state)
        self.assertEqual(request.kernel_request.attack.attacker_test.dice_modifiers,())
        self.assertEqual(request.kernel_request.attack.attacker_test.quality_modifiers,
            (QualityModifier(BESTIGOR_WOUND_GLORIOUS_RULE_ID,TestQuality.GLORIOUS),))

    def test_glorious_uses_existing_grim_cancellation_and_locked_failure_rules(self):
        glorious=QualityModifier(BESTIGOR_WOUND_GLORIOUS_RULE_ID,TestQuality.GLORIOUS)
        for modifiers,locks,values,quality in (
                ((glorious,QualityModifier('external:grim',TestQuality.GRIM)),(),[10,10,10],TestQuality.NORMAL),
                ((glorious,),(RerollLock('external:locked',10),),[10,6,1,2],TestQuality.GLORIOUS)):
            rng=ScriptedD10(values)
            test=TestRequest('quality',InlineProfile(3,4,8),quality_modifiers=modifiers,reroll_locks=locks)
            result=resolve_test(test,rng,decisions=RerollAllFailures())
            rng.assert_exhausted()
            self.assertIs(result.trace.quality,quality)

    def test_named_orc_help_remains_free_success_on_glorious_bestigor_attack(self):
        source=scene(orcs=1,rounds=1)
        source=replace(source,enemy_activation_order=('orc1','bestigor1'),
            npc_help_policies=(PcNpcHelpPolicy('orc1','bestigor1'),))
        result=execute(source,[1]*3+[10]*4+[10]*5+[10]*5+[1]*3)
        attack=attacks(result)[0].proof
        trace=attack.execution.resolution.attack.attacker_test.trace
        self.assertEqual((trace.rolled_dice,trace.cap_bypassing_dice,trace.success_delta),(5,0,1))
        self.assertEqual(len(attack.npc_help_applications),1)
        self.assertIsNotNone(attack.npc_glorious_source)

    def test_selected_w0_rage_is_available_without_a_wound_and_glorious_is_not(self):
        result=execute(scene(rounds=1),[10]*3+[1]*4+[10]*4+[1]*3)
        attack=attacks(result)[0]
        self.assertEqual(attack.source.enemy('bestigor1').state.injury.wounds,0)
        self.assertIsNone(attack.proof.npc_glorious_source)
        self.assertIs(attack.proof.execution.resolution.attack.attacker_test.trace.quality,TestQuality.NORMAL)
        self.assertEqual(len(tuple(s for s in result.steps if type(s.proof) is PcNpcBloodRageProof)),1)
