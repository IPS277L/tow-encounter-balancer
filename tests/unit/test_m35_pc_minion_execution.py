"""Target-bound Primal Spite and actual Sigmarite Cultist no-Test Help."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_m28_pc_beast_orc_modifiers import pure_active
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.pc_melee_result_models import PcAttackProof,PcNpcHelpProof,PcMeleeStep,build_pc_melee_attack
from towr.domain.pc_npc_ability_models import UNGOR_PRIMAL_SPITE_RULE_ID,pc_npc_attack_modifiers
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy,CULTIST_HELP_RULE_ID
from towr.domain.pc_npc_catalog import PcBookNpcProfile,get_pc_book_npc_entry
from towr.domain.test_models import DiceModifier
from towr.engine.pc_melee_runner import run_pc_melee_scenario


def scene(**kwargs):
    return book_pc_scenario(footpads=0,townsfolk=0,pc_count=1,max_rounds=kwargs.pop('rounds',1),**kwargs)


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def attacks(result,actor):
    return tuple(s for s in result.steps if type(s.proof) is PcAttackProof and s.proof.request.actor_id==actor)


class PcMinionExecutionTests(unittest.TestCase):
    def test_actual_pc_miss_gives_ungor_one_ordinary_die_against_staggered_target(self):
        result=execute(scene(ungors=1),[10]*3+[1]*4+[10]*4+[1]*3)
        step,=attacks(result,'ungor1')
        self.assertTrue(step.source.party[0].injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(step.source.enemy('ungor1').state.injury.conditions.has(Condition.STAGGERED))
        request=step.proof.request.kernel_request.attack
        self.assertEqual(request.attacker_test.dice_modifiers,(DiceModifier(UNGOR_PRIMAL_SPITE_RULE_ID,1),))
        trace=step.proof.execution.resolution.attack.attacker_test.trace
        self.assertEqual((trace.base_dice,trace.regular_dice_delta,trace.cap_bypassing_dice,trace.rolled_dice),
            (3,1,0,4))
        self.assertEqual((request.impact_spec.damage.base,request.impact_spec.damage_modifiers),(3,()))

    def test_actual_wound_clears_target_stagger_so_ungors_own_stagger_cannot_keep_bonus(self):
        values=[10]*3+[1]*4+[1]*4+[10]*3+[1]
        values += [1,10,10]+[10]*4+[10]*3+[1]*3
        result=execute(scene(ungors=1,rounds=2),values)
        first,second=attacks(result,'ungor1')
        self.assertTrue(first.source.party[0].injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(second.source.party[0].injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(second.source.enemy('ungor1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(second.proof.request.kernel_request.attack.attacker_test.dice_modifiers,())
        self.assertEqual(second.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,3)
        self.assertEqual(len(second.source.party[0].injury.wounds),1)

    def test_preparation_uses_actual_named_target_not_another_pc_or_own_conditions(self):
        source=book_pc_scenario(ungors=1,footpads=0,townsfolk=0,pc_count=2,max_rounds=1)
        source=replace(source,enemy_target_priority=('pc2','pc1'))
        state=pure_active(source,'ungor1')
        pc1,pc2=state.party
        pc1=replace(pc1,injury=replace(pc1.injury,conditions=ConditionState(frozenset({Condition.STAGGERED}))))
        state=replace(state,party=(pc1,pc2))
        request,_=build_pc_melee_attack(state)
        self.assertEqual(request.target_id,'pc2')
        self.assertEqual(request.kernel_request.attack.attacker_test.dice_modifiers,())
        pc2=replace(pc2,injury=replace(pc2.injury,conditions=ConditionState(frozenset({Condition.STAGGERED}))))
        state=replace(state,party=(pc1,pc2))
        request,_=build_pc_melee_attack(state)
        self.assertEqual(request.kernel_request.attack.attacker_test.dice_modifiers,
            (DiceModifier(UNGOR_PRIMAL_SPITE_RULE_ID,1),))

    def test_drained_removes_positive_spite_at_preparation_without_removing_target_stagger(self):
        state=pure_active(scene(ungors=1,cultists=1),'ungor1')
        enemy=state.enemy('ungor1')
        enemy=replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
            conditions=ConditionState(frozenset({Condition.DRAINED})))) )
        pc=state.party[0]
        pc=replace(pc,injury=replace(pc.injury,conditions=ConditionState(frozenset({Condition.STAGGERED}))))
        state=replace(state,enemies=tuple(enemy if e.state.actor_id=='ungor1' else e for e in state.enemies),party=(pc,))
        request,_=build_pc_melee_attack(state)
        self.assertEqual(request.kernel_request.attack.attacker_test.dice_modifiers,())
        self.assertTrue(state.party[0].injury.conditions.has(Condition.STAGGERED))

    def test_cultist_no_test_help_stacks_separately_from_ungor_spite_and_outnumbering(self):
        source=scene(cultists=1,ungors=1)
        member=source.party[0]
        priority=('ungor1','cultist1')
        source=replace(source,party=(replace(member,target_priority=priority,
            defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority)),),
            npc_help_policies=(PcNpcHelpPolicy('cultist1','ungor1'),))
        result=execute(source,[10]*3+[1]*4+[10]*6+[1]*3)
        help_step,=tuple(s for s in result.steps if type(s.proof) is PcNpcHelpProof)
        self.assertEqual(help_step.proof.execution.bonus.rule_id,CULTIST_HELP_RULE_ID)
        self.assertFalse(hasattr(help_step.proof.execution,'help_test_result'))
        attack,=attacks(result,'ungor1')
        self.assertEqual(attack.proof.request.kernel_request.attack.attacker_test.dice_modifiers,
            (DiceModifier('RULE-COMBAT-007:outnumbering',1),DiceModifier(UNGOR_PRIMAL_SPITE_RULE_ID,1),
             DiceModifier(CULTIST_HELP_RULE_ID,1,True)))
        trace=attack.proof.execution.resolution.attack.attacker_test.trace
        self.assertEqual((trace.regular_dice_delta,trace.cap_bypassing_dice,trace.rolled_dice),(2,1,6))
        self.assertEqual(result.executed_actions,3)
        forged_request=replace(help_step.proof.request,source_rule_id='RULE-PROFILE-TALABEC-001:torches-and-pitchforks')
        from towr.domain.automatic_help_models import expected_automatic_help_action
        with self.assertRaises(ValueError):
            PcMeleeStep(help_step.source,PcNpcHelpProof(forged_request,expected_automatic_help_action(forged_request)))

    def test_duplicate_alias_or_removed_primal_spite_cannot_change_native_proof(self):
        result=execute(scene(ungors=1),[10]*3+[1]*4+[10]*4+[1]*3)
        step,=attacks(result,'ungor1')
        for amount in (True,2):
            forged=deepcopy(step.proof)
            object.__setattr__(forged.request.kernel_request.attack.attacker_test.dice_modifiers[0],'amount',amount)
            with self.subTest(amount=amount),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(step.source,forged)
        for duplicate in (False,True):
            forged=deepcopy(step.proof)
            test=forged.request.kernel_request.attack.attacker_test
            object.__setattr__(test,'dice_modifiers',test.dice_modifiers*2 if duplicate else ())
            with self.subTest(duplicate=duplicate),self.assertRaises(ValueError):
                PcMeleeStep(step.source,forged)
        ungor=get_pc_book_npc_entry(PcBookNpcProfile.UNGOR_SPEAR).definition
        numeric=replace(ungor,id='authored:ungor',source_rule_id='authored:source',
            attacks=(replace(ungor.attacks[0],source_rule_id='authored:attack'),),
            protection=(replace(ungor.protection[0],source_rule_id='authored:protection'),))
        self.assertEqual(pc_npc_attack_modifiers(numeric,ConditionState(),
            target_conditions=ConditionState(frozenset({Condition.STAGGERED})),attacker_wounds=0),())


if __name__=='__main__':
    unittest.main()
