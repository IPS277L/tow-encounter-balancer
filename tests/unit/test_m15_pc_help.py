"""Actual Help turns retain their intended-Test bonus and resource provenance."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario, with_pc_melee_brute
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.pc_help_models import build_pc_help_action, pc_help_beneficiary, pc_attack_help_applications
from towr.domain.pc_melee_models import PcMeleePolicy, PcHelpPolicy, PcHelpTarget, PcFatePolicy, PcGloriousPolicy
from towr.domain.pc_melee_result_models import (
    PcAttackProof,PcHelpProof,PcRecoverProof,PcMeleeOutcome,PcMeleeStep,PcTurnEndProof,
    initial_pc_melee_state,pc_melee_selected_action,pc_melee_action_id,build_pc_melee_attack,
)
from towr.domain.test_models import Skill, TestQuality
from towr.domain.turn_models import CombatActionKind, CombatTurnStartRequest
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step
from towr.rules.turn_resolution import start_combat_turn


def help_source(*, pc_count=2,enemy_count=1,max_rounds=1,helpers=('pc1',)):
    source = make_pc_melee_party_scenario(pc_count=pc_count,enemy_count=enemy_count,max_rounds=max_rounds)
    beneficiary = source.party[-1].actor_id
    return replace(source,party=tuple(replace(member,
        policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
        help_policy=PcHelpPolicy(beneficiary,PcHelpTarget.MELEE_ATTACK,None)) if member.actor_id in helpers else member
        for member in source.party))


def execute(source,values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def basic_values(*, help_success=True):
    return ([1,1,1] if help_success else [10,10,10]) + (
        [1]*6 if help_success else [1]*4) + [10,10]


def helping_steps(result):
    return tuple(step for step in result.steps if isinstance(step.proof,PcHelpProof))


def beneficiary_attack(result):
    return next(step for step in result.steps if isinstance(step.proof,PcAttackProof)
        and step.proof.request.actor_id == result.source.party[-1].actor_id)


class PcHelpTests(unittest.TestCase):
    def test_help_uses_real_slot_then_exact_upcoming_attack_with_normal_pool_cap(self):
        result = execute(help_source(),basic_values())
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        help_step, = helping_steps(result)
        proof = help_step.proof
        attack = beneficiary_attack(result)
        self.assertIs(proof.execution.slot.declaration.kind,CombatActionKind.HELP)
        self.assertEqual(proof.execution.bonus.bonus_dice,3)
        self.assertEqual(proof.execution.bonus.beneficiary_test_id,
            attack.proof.request.kernel_request.attack.attacker_test.id)
        self.assertEqual(attack.proof.help_applications[0].source_request.help,proof.execution)
        trace = attack.proof.execution.resolution.attack.attacker_test.trace
        self.assertEqual((trace.base_dice,trace.pool_cap,trace.regular_dice_delta,trace.rolled_dice),(3,6,4,6))
        self.assertEqual(result.executed_actions,2)
        self.assertEqual(proof.request.help_test.dice_modifiers,())
        self.assertEqual(proof.fate_decline.source_id,proof.request.help_test.id)
        self.assertFalse(result.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))

    def test_zero_success_help_spends_action_without_miss_stagger_or_bonus_dice(self):
        result = execute(help_source(),basic_values(help_success=False))
        step, = helping_steps(result)
        self.assertEqual(step.proof.execution.bonus.bonus_dice,0)
        attack = beneficiary_attack(result)
        self.assertEqual(len(attack.proof.help_applications),1)
        self.assertIsNone(attack.proof.help_applications[0].modifier)
        self.assertEqual(attack.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,4)
        self.assertFalse(step.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(result.executed_actions,2)

    def test_two_actual_helpers_stack_in_history_order_without_bypassing_cap(self):
        source = help_source(pc_count=3,enemy_count=2,helpers=('pc1','pc2'))
        result = execute(source,[1]*3+[1]*3+[1]*6+[10,10]+[10,10]+[1]*3)
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
        attack = beneficiary_attack(result)
        self.assertEqual(tuple(application.source_request.help.source_request.actor_id
            for application in attack.proof.help_applications),('pc1','pc2'))
        self.assertEqual(tuple(application.modifier.amount for application in attack.proof.help_applications),(3,3))
        self.assertEqual(attack.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,6)

    def test_helpers_and_beneficiary_can_spend_glorious_on_their_own_tests(self):
        source = help_source()
        source = replace(source,party=tuple(replace(member,fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.MELEE,),0,0)) for member in source.party))
        result = execute(source,[10]*3+[1]*3+[10]*6+[1]*6+[10,10])
        helper, = helping_steps(result)
        attack = beneficiary_attack(result)
        self.assertIsNotNone(helper.proof.glorious)
        self.assertIsNotNone(attack.proof.glorious)
        self.assertEqual(helper.proof.glorious.source_request.initial_roll.initial_values,(10,10,10))
        self.assertEqual(helper.proof.execution.help_test_result.trace.final_values,(1,1,1))
        self.assertEqual(tuple(len(member.fate.spends) for member in result.state.party),(1,1))
        self.assertEqual(tuple(member.fate.rating for member in result.state.party),(3,3))

    def test_pure_attack_preparation_blocks_positive_help_if_recipient_is_drained(self):
        result = execute(help_source(),basic_values())
        attack = beneficiary_attack(result)
        # Current numeric PC-first rounds cannot acquire this condition between
        # Help and Attack. Exercise preparation's state boundary explicitly.
        state = replace(attack.source,party=tuple(replace(member,injury=replace(member.injury,
            conditions=ConditionState(frozenset({Condition.DRAINED})))) if member.actor_id == 'pc2' else member
            for member in attack.source.party))
        prepared,_ = build_pc_melee_attack(state)
        applications = pc_attack_help_applications(state,prepared.kernel_request.attack)
        self.assertEqual(applications[0].modifier.amount,3)
        self.assertFalse(any(mod.amount > 0 for mod in prepared.kernel_request.attack.attacker_test.dice_modifiers))

    def test_pure_application_never_retargets_old_help_to_another_round(self):
        result = execute(help_source(max_rounds=2),basic_values())
        attack = beneficiary_attack(result)
        state = replace(attack.source,round_state=replace(attack.source.round_state,round_number=2))
        prepared,_ = build_pc_melee_attack(state)
        self.assertEqual(pc_attack_help_applications(state,prepared.kernel_request.attack),())
        self.assertFalse(any(mod.rule_id.startswith('RULE-TEST-005')
            for mod in prepared.kernel_request.attack.attacker_test.dice_modifiers))

    def test_another_pc_victory_leaves_bound_help_unused_without_blocking_outcome(self):
        source = help_source(pc_count=3)
        result = execute(source,[1]*3+[1]*4+[10,10])
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(len(helping_steps(result)),1)
        self.assertFalse(any(isinstance(step.proof,PcAttackProof) and step.proof.request.actor_id == 'pc3'
            for step in result.steps))

    def test_glorious_help_consumes_actual_next_test_grim_but_keeps_drained(self):
        source = with_pc_melee_brute(help_source(max_rounds=2),'minion1',wound_limit=2)
        source = replace(source,party=tuple(replace(member,fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.MELEE,),3,0)) for member in source.party))
        values = [1]*3+[1]*6+[10,10]+[1,1]+[10]*3+[10]+[1]*3+[1]*6+[10,10]
        result = execute(source,values)
        helps = helping_steps(result)
        second = helps[1]
        self.assertTrue(second.source.participant('pc1').injury.conditions.has(Condition.DRAINED))
        self.assertTrue(second.proof.request.help_test.quality_modifiers)
        self.assertIsNotNone(second.proof.glorious)
        trace = second.proof.execution.help_test_result.trace
        self.assertIs(trace.quality,TestQuality.NORMAL)
        self.assertEqual(trace.rerolls,())
        self.assertEqual(trace.initial_values,trace.final_values)
        self.assertTrue(second.state.participant('pc1').injury.conditions.has(Condition.DRAINED))

    def test_unavailable_help_falls_back_without_inventing_a_test_or_bonus(self):
        source = help_source()
        state = initial_pc_melee_state(source)
        state = replace(state,round_state=start_combat_turn(CombatTurnStartRequest(
            pc_melee_action_id(state,'pc1')+':start',state.round_state,'pc1')).state)
        for actor,condition in (('pc1',Condition.DEAFENED),('pc2',Condition.DRAINED),('pc2',Condition.DEFENCELESS)):
            member = state.participant(actor)
            changed = replace(member,injury=replace(member.injury,
                conditions=ConditionState(frozenset({condition}))))
            current = replace(state,party=tuple(changed if original.actor_id == actor else original for original in state.party))
            with self.subTest(actor=actor,condition=condition):
                self.assertIsNone(pc_help_beneficiary(current))
                self.assertIs(pc_melee_selected_action(current),CombatActionKind.ATTACK)
        for actor in ('pc1','pc2'):
            current = replace(state,party=tuple(replace(member,weapon_hand=None) if member.actor_id == actor else member
                for member in state.party))
            self.assertIsNone(pc_help_beneficiary(current))
            self.assertIs(pc_melee_selected_action(current),CombatActionKind.RECOVER if actor == 'pc1' else CombatActionKind.ATTACK)

    def test_help_is_an_actual_non_recover_action_for_heavy_wound_critical_end_phase(self):
        source = help_source(enemy_count=2,max_rounds=2)
        values = ([1]*3+[10]*6+[1,1]
            +[1,1]+[10]*3+[1]+[1,1]+[10]*3+[7,7]
            +[1]*3+[1]*3+[1]*6+[10,10]+[10,10]+[1]*3)
        result = execute(source,values)
        second = helping_steps(result)[1]
        self.assertFalse(second.source.participant('pc1').injury.conditions.has(Condition.CRITICALLY_INJURED))
        self.assertTrue(second.state.participant('pc1').injury.conditions.has(Condition.CRITICALLY_INJURED))
        end = next(step for step in result.steps if isinstance(step.proof,PcTurnEndProof)
            and step.source.round_state.round_number == 2
            and step.source.round_state.active_turn.actor_id == 'pc1')
        self.assertIsNotNone(end.proof.critical)
        self.assertTrue(end.proof.critical.result.test.succeeded)
        self.assertFalse(result.state.participant('pc1').injury.dead)

    def test_actual_deafened_wound_makes_helper_attack_on_next_round(self):
        source = help_source(enemy_count=2,max_rounds=2)
        values = ([1]*3+[10]*6+[1,1]
            +[1,1]+[10]*3+[1]+[1,1]+[10]*3+[5,6]+[1]*3
            +[1]*3+[10,10]+[1]*4+[10,10])
        result = execute(source,values)
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(len(helping_steps(result)),1)
        attack = next(step for step in result.steps if isinstance(step.proof,PcAttackProof)
            and step.proof.request.actor_id == 'pc1')
        self.assertEqual(attack.source.round_state.round_number,2)
        self.assertTrue(attack.source.participant('pc1').injury.conditions.has(Condition.DEAFENED))
        self.assertEqual(attack.proof.help_applications,())

    def test_help_glorious_cannot_be_removed_or_rebound_to_foreign_resource(self):
        source = help_source()
        source = replace(source,party=tuple(replace(member,fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.MELEE,),0,0)) for member in source.party))
        result = execute(source,[10]*3+[1]*3+[10]*6+[1]*6+[10,10])
        helper, = helping_steps(result)
        with self.assertRaises(TypeError):
            PcMeleeStep(helper.source,replace(helper.proof,glorious=None))
        proof = deepcopy(helper.proof)
        object.__setattr__(proof.glorious.previous_state,'actor_id','foreign')
        with self.assertRaises(ValueError):
            PcMeleeStep(helper.source,proof)

    def test_forged_help_bonus_clock_and_fate_provenance_are_rejected(self):
        result = execute(help_source(),basic_values())
        helper, = helping_steps(result)
        for branch,field,value in (('bonus','bonus_dice',2),('bonus','beneficiary_id','pc1'),
                ('slot','index',2)):
            proof = deepcopy(helper.proof)
            target = getattr(proof.execution,branch)
            object.__setattr__(target,field,value)
            with self.subTest(field=field),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(helper.source,proof)
        proof = deepcopy(helper.proof)
        object.__setattr__(proof.execution.bonus,'helper_id',Enum('Foreign',{'VALUE':'pc1'},type=str).VALUE)
        self.assertEqual(proof,helper.proof)
        with self.assertRaises(TypeError):
            PcMeleeStep(helper.source,proof)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(helper.state,helper)

    def test_attack_cannot_drop_duplicate_or_forge_a_help_application(self):
        result = execute(help_source(),basic_values())
        attack = beneficiary_attack(result)
        for applications in ((),attack.proof.help_applications*2,list(attack.proof.help_applications)):
            with self.subTest(applications=len(applications)),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(attack.source,replace(attack.proof,help_applications=applications))
        proof = deepcopy(attack.proof)
        object.__setattr__(proof.help_applications[0].source_request.help.bonus,'bonus_dice',True)
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(attack.source,proof)


if __name__ == '__main__':
    unittest.main()
