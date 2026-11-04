"""Literal Protection Help targets remain fixed through the intervening PC turn."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario,with_pc_melee_brute
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.pc_help_models import (
    build_pc_help_action,pc_attack_help_applications,pc_help_beneficiary,
)
from towr.domain.pc_melee_models import (
    PcFatePolicy,PcGloriousPolicy,PcHelpPolicy,PcHelpTarget,PcMeleePolicy,PcMeleeWeapon,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof,PcHelpProof,PcMeleeOutcome,PcMeleeStep,PcRecoverProof,PcTurnEndProof,
    build_pc_melee_attack,initial_pc_melee_state,pc_melee_action_id,
)
from towr.domain.test_models import Skill,TestQuality
from towr.domain.turn_models import CombatTurnStartRequest
from towr.engine.pc_melee_runner import apply_pc_melee_step,run_pc_melee_scenario
from towr.rules.turn_resolution import start_combat_turn


def protection_source(*,pc_count=2,enemy_count=1,max_rounds=1,helpers=('pc1',),skill=Skill.DEFENCE):
    source = make_pc_melee_party_scenario(pc_count=pc_count,enemy_count=enemy_count,max_rounds=max_rounds)
    beneficiary = source.party[-1].actor_id
    source = replace(source,party=tuple(replace(member,
        policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
        help_policy=PcHelpPolicy(beneficiary,PcHelpTarget.FIRST_INCOMING_PROTECTION,skill))
        if member.actor_id in helpers else member for member in source.party),
        enemy_target_priority=(beneficiary,*(member.actor_id for member in source.party if member.actor_id!=beneficiary)))
    for enemy in source.enemies:
        source = with_pc_melee_brute(source,enemy.state.actor_id,wound_limit=5)
    return source


def execute(source,values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def helper_steps(result):
    return tuple(step for step in result.steps if isinstance(step.proof,PcHelpProof))


def npc_attacks(result):
    return tuple(step for step in result.steps if isinstance(step.proof,PcAttackProof)
        and step.proof.request.actor_id in result.source.enemy_activation_order)


def basic_values(success=True):
    return ([1]*3 if success else [10]*3)+[1]*4+[10]*2+[1]*2+([1]*6 if success else [1]*3)


class PcProtectionHelpTests(unittest.TestCase):
    def test_real_help_survives_ally_attack_and_boosts_only_named_incoming_protection(self):
        result = execute(protection_source(),basic_values())
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
        helper, = helper_steps(result)
        incoming, = npc_attacks(result)
        own = next(step for step in result.steps if isinstance(step.proof,PcAttackProof)
            and step.proof.request.actor_id=='pc2')
        self.assertEqual(own.proof.help_applications,())
        self.assertIs(helper.proof.request.help_skill,Skill.DEFENCE)
        self.assertEqual(helper.proof.execution.bonus.beneficiary_test_id,
            incoming.proof.execution.resolution.attack.defender_test.trace.request_id)
        application, = incoming.proof.help_applications
        self.assertEqual(application.source_request.help,helper.proof.execution)
        self.assertEqual(application.source_request.beneficiary_id,'pc2')
        trace = incoming.proof.execution.resolution.attack.defender_test.trace
        self.assertEqual((trace.base_dice,trace.regular_dice_delta,trace.pool_cap,trace.rolled_dice),(3,3,6,6))
        self.assertEqual(result.executed_actions,3)
        self.assertEqual(incoming.proof.protection.source_request.options[0].test,
            incoming.proof.request.kernel_request.attack.defender_test)

    def test_zero_help_still_consumes_action_and_preserves_zero_application(self):
        result = execute(protection_source(),basic_values(False))
        helper, = helper_steps(result)
        incoming, = npc_attacks(result)
        self.assertEqual(helper.proof.execution.bonus.bonus_dice,0)
        self.assertIsNone(incoming.proof.help_applications[0].modifier)
        self.assertEqual(incoming.proof.execution.resolution.attack.defender_test.trace.rolled_dice,3)
        self.assertFalse(helper.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))

    def test_already_acted_beneficiary_can_receive_protection_help(self):
        source = replace(protection_source(),pc_activation_order=('pc2','pc1'))
        result = execute(source,[1]*4+[10]*2+[1]*3+[1]*2+[1]*6)
        helper, = helper_steps(result)
        self.assertIn('pc2',helper.source.round_state.completed_turn_entity_ids)
        self.assertEqual(len(npc_attacks(result)[0].proof.help_applications),1)

    def test_two_helpers_stack_on_first_incoming_test_under_normal_pool_cap(self):
        source = protection_source(pc_count=3,helpers=('pc1','pc2'))
        result = execute(source,[1]*3+[1]*3+[1]*4+[10]*2+[1]*2+[1]*6)
        incoming, = npc_attacks(result)
        self.assertEqual(tuple(app.source_request.help.source_request.actor_id
            for app in incoming.proof.help_applications),('pc1','pc2'))
        trace = incoming.proof.execution.resolution.attack.defender_test.trace
        self.assertEqual((trace.regular_dice_delta,trace.rolled_dice),(6,6))

    def test_sword_and_glorious_apply_to_helper_and_recipient_own_defence_tests(self):
        source = protection_source()
        source = replace(source,party=tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.SWORD),
            fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.DEFENCE,),0,0)) for member in source.party))
        result = execute(source,[10]*4+[1]*4+[1]*4+[10]*2+[1]*2+[10]*6+[1]*6)
        helper, = helper_steps(result)
        incoming, = npc_attacks(result)
        self.assertIsNotNone(helper.proof.glorious)
        self.assertEqual(helper.proof.request.help_test.dice_modifiers[0].amount,1)
        self.assertIsNotNone(incoming.proof.glorious)
        self.assertIs(incoming.proof.execution.resolution.attack.defender_test.trace.quality,TestQuality.GLORIOUS)
        self.assertEqual(tuple(len(member.fate.spends) for member in result.state.party),(1,1))

    def test_killed_named_npc_does_not_retarget_help_to_another_incoming_test(self):
        source = make_pc_melee_party_scenario(pc_count=3,enemy_count=2,max_rounds=1)
        source = replace(source,party=(replace(source.party[0],
            policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
            help_policy=PcHelpPolicy('pc3',PcHelpTarget.FIRST_INCOMING_PROTECTION,Skill.DEFENCE)),*source.party[1:]),
            enemy_target_priority=('pc3','pc1','pc2'))
        source = with_pc_melee_brute(source,'minion2',wound_limit=5)
        result = execute(source,[1]*3+[1]*4+[10]*2+[1]*4+[10]*2+[1]*2+[1]*3)
        helper, = helper_steps(result)
        incoming, = npc_attacks(result)
        self.assertEqual(incoming.proof.request.actor_id,'minion2')
        self.assertIn(':minion1:protection',helper.proof.request.beneficiary_test_id)
        self.assertEqual(incoming.proof.help_applications,())

    def test_actual_recover_changes_skill_and_leaves_athletics_help_unused(self):
        source = protection_source(max_rounds=2,skill=Skill.ATHLETICS)
        values = [1]*4+[10]*2+[1]*4+[10]*2+[1]*2+[10]*3+[4]+[10]*3+[1]+[1]*3+[1]*2+[1]*3
        result = execute(source,values)
        helper, = helper_steps(result)
        self.assertEqual(helper.source.round_state.round_number,2)
        self.assertIs(helper.proof.request.help_skill,Skill.ATHLETICS)
        self.assertTrue(any(isinstance(step.proof,PcRecoverProof) and step.proof.result.source_request.actor_id=='pc2'
            for step in result.steps))
        incoming = npc_attacks(result)[-1]
        self.assertIs(incoming.proof.protection.source_request.selected_skill,Skill.DEFENCE)
        self.assertEqual(incoming.proof.help_applications,())
        # Keep the genuine earlier Athletics receipt, then exercise preparation
        # for an ally who remained unarmed. This is a pure boundary test.
        state = replace(incoming.source,party=tuple(replace(member,weapon_hand=None)
            if member.actor_id=='pc2' else member for member in incoming.source.party))
        prepared,protection = build_pc_melee_attack(state)
        self.assertIs(protection.selected_skill,Skill.ATHLETICS)
        applications = pc_attack_help_applications(state,prepared.kernel_request.attack)
        self.assertEqual(len(applications),1)
        self.assertEqual(prepared.kernel_request.attack.defender_test.profile,source.party[1].pc.athletics_profile)
        self.assertEqual(sum(mod.amount for mod in prepared.kernel_request.attack.defender_test.dice_modifiers),3)

    def test_pure_drained_and_defenceless_preparation_keep_correct_bonus_and_test_boundaries(self):
        result = execute(protection_source(),basic_values())
        incoming, = npc_attacks(result)
        for condition in (Condition.DRAINED,Condition.DEFENCELESS):
            state = replace(incoming.source,party=tuple(replace(member,injury=replace(member.injury,
                conditions=ConditionState(frozenset({condition})))) if member.actor_id=='pc2' else member
                for member in incoming.source.party))
            prepared,protection = build_pc_melee_attack(state)
            applications = pc_attack_help_applications(state,prepared.kernel_request.attack)
            if condition is Condition.DRAINED:
                self.assertEqual(len(applications),1)
                self.assertFalse(any(mod.amount>0 for mod in prepared.kernel_request.attack.defender_test.dice_modifiers))
            else:
                self.assertIsNone(protection.selected_skill)
                self.assertIsNone(prepared.kernel_request.attack.defender_test)
                self.assertEqual(applications,())

    def test_wrong_predicted_target_and_skill_do_not_invent_help(self):
        source = protection_source()
        state = initial_pc_melee_state(replace(source,enemy_target_priority=('pc1','pc2')))
        state = replace(state,round_state=start_combat_turn(CombatTurnStartRequest(
            pc_melee_action_id(state,'pc1')+':start',state.round_state,'pc1')).state)
        self.assertIsNone(pc_help_beneficiary(state))
        with self.assertRaises(ValueError):
            build_pc_help_action(state)
        state = initial_pc_melee_state(protection_source(skill=Skill.ATHLETICS))
        state = replace(state,round_state=start_combat_turn(CombatTurnStartRequest(
            pc_melee_action_id(state,'pc1')+':start',state.round_state,'pc1')).state)
        self.assertIsNone(pc_help_beneficiary(state))

    def test_defenceless_after_real_critical_end_has_no_protection_test_or_application(self):
        source = protection_source(enemy_count=3,max_rounds=2)
        values = ([1]*3+[1]*3+[10]*2
            +[1]*3+[10]*6+[1]+[1]*3+[10]*3+[7,8]+[10]*3+[1]*3
            +[1]*3+[1]*3+[10]*2+[10]*3
            +[1]*3+[1,1,1]+[10]*3+[10]*3)
        result = execute(source,values)
        helper = helper_steps(result)[-1]
        incoming = next(step for step in npc_attacks(result)
            if step.source.round_state.round_number==2 and step.proof.request.actor_id=='minion1')
        self.assertEqual(helper.proof.request.beneficiary_test_id,
            incoming.proof.request.kernel_request.attack.id.replace(':attack-request',':protection'))
        self.assertTrue(incoming.source.participant('pc2').injury.conditions.has(Condition.DEFENCELESS))
        self.assertIsNone(incoming.proof.execution.resolution.attack.defender_test)
        self.assertIsNone(incoming.proof.fate_decline)
        self.assertIsNone(incoming.proof.glorious)
        self.assertEqual(incoming.proof.help_applications,())
        self.assertTrue(any(isinstance(step.proof,PcTurnEndProof) and step.proof.critical is not None
            for step in result.steps))

    def test_protection_applications_cannot_be_dropped_duplicated_or_forged(self):
        result = execute(protection_source(),basic_values())
        incoming, = npc_attacks(result)
        for applications in ((),incoming.proof.help_applications*2,list(incoming.proof.help_applications)):
            with self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(incoming.source,replace(incoming.proof,help_applications=applications))
        proof = deepcopy(incoming.proof)
        object.__setattr__(proof.help_applications[0].source_request,'beneficiary_skill',
            Enum('Foreign',{'VALUE':'defence'},type=str).VALUE)
        self.assertEqual(proof,incoming.proof)
        with self.assertRaises(TypeError):
            PcMeleeStep(incoming.source,proof)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(incoming.state,incoming)


if __name__=='__main__':
    unittest.main()
