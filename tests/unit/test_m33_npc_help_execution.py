"""Actual no-Test NPC Help, fixed policy fallback and exact source-bound receipts."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
import unittest
from unittest.mock import Mock,patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.application.pc_melee_balance_models import (
    PcMeleeBalanceRequest,PcMeleeCompositionGroup,project_pc_melee_candidate,
)
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.automatic_help_models import expected_automatic_help_action,AutomaticHelpEffectKind
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import (
    PcAttackProof,PcNpcHelpProof,PcTurnEndProof,PcMeleeStep,PcMeleeOutcome,
)
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy,PEASANT_HELP_RULE_ID,MILITIA_HELP_RULE_ID
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


def help_scene(*,rounds=1,watch=False):
    source=book_pc_scenario(peasants=2,militia=1,watch=int(watch),
        footpads=0,townsfolk=0,pc_count=1,max_rounds=rounds)
    return replace(source,enemy_activation_order=(('watch1',) if watch else ())+
        ('peasant1','militia1','peasant2'),npc_help_policies=(
            PcNpcHelpPolicy('peasant1','peasant2'),PcNpcHelpPolicy('militia1','peasant2')))


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def simple_help(*,rounds=1):
    return execute(help_scene(rounds=rounds),([10]*3+[1]*3+[10]*5+[1]*3)*rounds)


class NpcHelpPolicyTests(unittest.TestCase):
    def test_count_projection_drops_missing_recipient_or_helper_without_reassigning_survivors(self):
        source=help_scene()
        groups=(PcMeleeCompositionGroup('helper',('peasant1',),1,1),
            PcMeleeCompositionGroup('militia',('militia1',),0,1),
            PcMeleeCompositionGroup('recipient',('peasant2',),0,1))
        request=PcMeleeBalanceRequest(source,groups,source.facts,42,1,4,4,
            ObjectiveRateWindow(Fraction(0),Fraction(1,2),Fraction(1)),1)
        without_recipient=project_pc_melee_candidate(request,(1,1,0)).scenario
        self.assertEqual(without_recipient.npc_help_policies,())
        self.assertEqual(without_recipient.enemy_activation_order,('peasant1','militia1'))
        without_militia=project_pc_melee_candidate(request,(1,0,1)).scenario
        self.assertEqual(without_militia.npc_help_policies,(PcNpcHelpPolicy('peasant1','peasant2'),))
        complete=project_pc_melee_candidate(request,(1,1,1)).scenario
        self.assertEqual(complete.npc_help_policies,source.npc_help_policies)

    def test_source_allows_several_pairs_and_more_than_one_helper_for_same_attack(self):
        source=help_scene()
        self.assertEqual(len(source.npc_help_policies),2)
        many=book_pc_scenario(peasants=3,militia=2,watch=1,footpads=0,townsfolk=0,pc_count=1)
        order=('peasant1','peasant2','peasant3','militia1','militia2','watch1')
        many=replace(many,enemy_activation_order=order,
            npc_help_policies=tuple(PcNpcHelpPolicy(actor,'watch1') for actor in order[:-1]))
        self.assertEqual(len(many.npc_help_policies),5)

    def test_source_rejects_wrong_side_unknown_ids_duplicate_roles_chains_and_early_recipient(self):
        source=help_scene()
        for policies in ((PcNpcHelpPolicy('pc1','peasant2'),),
                (PcNpcHelpPolicy('peasant1','pc1'),),(PcNpcHelpPolicy('absent','peasant2'),),
                (PcNpcHelpPolicy('peasant1','absent'),),
                (PcNpcHelpPolicy('peasant1','peasant2'),)*2,
                (PcNpcHelpPolicy('peasant2','peasant1'),),
                (PcNpcHelpPolicy('peasant1','militia1'),PcNpcHelpPolicy('militia1','peasant2'))):
            with self.subTest(policies=policies),self.assertRaises(ValueError):
                replace(source,npc_help_policies=policies)
        with self.assertRaises(TypeError):
            replace(source,npc_help_policies=list(source.npc_help_policies))
        with self.assertRaises(ValueError):
            PcNpcHelpPolicy('peasant1','peasant1')
        source=book_pc_scenario(watch=1,militia=1,footpads=0,townsfolk=0)
        with self.assertRaises(ValueError):
            replace(source,npc_help_policies=(PcNpcHelpPolicy('watch1','militia1'),))

    def test_cached_equal_policy_id_alias_is_rejected_before_native_runner_or_rng(self):
        class IdAlias(str):pass
        request=PcMeleeSimulationRequest(help_scene(),42,1)
        forged=deepcopy(request)
        object.__setattr__(forged.scenario.npc_help_policies[0],'helper_id',IdAlias('peasant1'))
        self.assertEqual(forged,request)
        rng=Mock(side_effect=AssertionError('wrong cached policy cannot consume RNG'))
        runner=Mock(side_effect=AssertionError('wrong cached policy cannot become an observation'))
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',runner):
            with self.assertRaises(TypeError):
                run_pc_melee_trial(forged,0,rng_factory=rng)
        rng.assert_not_called()
        runner.assert_not_called()


class NpcHelpExecutionTests(unittest.TestCase):
    def test_two_helpers_spend_real_actions_without_tests_or_rng_and_keep_their_turn_ends(self):
        result=simple_help()
        helps=tuple(s for s in result.steps if type(s.proof) is PcNpcHelpProof)
        self.assertEqual(tuple(s.proof.request.actor_id for s in helps),('peasant1','militia1'))
        self.assertEqual(tuple(s.proof.execution.bonus.rule_id for s in helps),
            (PEASANT_HELP_RULE_ID,MILITIA_HELP_RULE_ID))
        for step in helps:
            self.assertFalse(hasattr(step.proof.request,'help_test'))
            self.assertFalse(hasattr(step.proof.execution,'help_test_result'))
            self.assertTrue(step.proof.execution.slot.executed)
            actor=step.proof.request.actor_id
            self.assertFalse(step.state.enemy(actor).state.injury.conditions.has(Condition.STAGGERED))
            self.assertTrue(any(type(s.proof) is PcTurnEndProof and
                s.source.round_state.active_turn.actor_id==actor for s in result.steps))
        incoming=next(s.proof for s in result.steps if type(s.proof) is PcAttackProof
            and s.proof.request.actor_id=='peasant2')
        trace=incoming.execution.resolution.attack.attacker_test.trace
        self.assertEqual((trace.base_dice,trace.pool_cap,trace.cap_bypassing_dice,trace.rolled_dice),(2,4,2,5))
        self.assertEqual(len(incoming.npc_help_applications),2)
        self.assertEqual(result.executed_actions,4)
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
        self.assertIsNone(result.unsupported)

    def test_normal_outnumbering_and_higher_ground_are_capped_before_each_special_bonus(self):
        # Actual Watch Wound9 makes PC Prone before the two Help actions.
        result=execute(help_scene(watch=True),[10]*3+[1]*3+[1]*4+[10]*3+[9]+[10]*6+[1]*3)
        step=next(s for s in result.steps if type(s.proof) is PcAttackProof and s.proof.request.actor_id=='peasant2')
        self.assertTrue(step.source.party[0].injury.conditions.has(Condition.PRONE))
        trace=step.proof.execution.resolution.attack.attacker_test.trace
        self.assertEqual((trace.regular_dice_delta,trace.pool_cap,trace.cap_bypassing_dice,trace.rolled_dice),(2,4,2,6))
        self.assertEqual(result.executed_actions,5)

    def test_actual_staggered_helper_can_help_and_does_not_remove_its_condition(self):
        source=help_scene()
        member=source.party[0]
        source=replace(source,party=(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.DAGGER)),))
        result=execute(source,[1,10,10]+[10]*3+[10]*5+[1]*3)
        help_step=next(s for s in result.steps if type(s.proof) is PcNpcHelpProof
            and s.proof.request.actor_id=='peasant1')
        self.assertTrue(help_step.source.enemy('peasant1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(help_step.proof.request.actor_conditions.has(Condition.STAGGERED))
        self.assertTrue(help_step.state.enemy('peasant1').state.injury.conditions.has(Condition.STAGGERED))

    def test_early_recipient_defeat_drained_or_broken_selects_attack_fallback(self):
        for keyword,recipient,values,outcome in (
                ('watch','watch1',[1]*3+[10]*3+[10]*2+[1]*3,PcMeleeOutcome.ROUND_LIMIT),
                ('empire_knights','empire_knight1',[1]*3+[10]*4+[10]*3+[1]*3+[10]*4+[1]*3,
                 PcMeleeOutcome.ROUND_LIMIT),
                ('officials','official1',[1]*3+[10]*3+[10]*3+[1]*3,PcMeleeOutcome.UNSUPPORTED_PATH)):
            with self.subTest(recipient=recipient):
                source=book_pc_scenario(peasants=1,**{keyword:1},footpads=0,townsfolk=0,pc_count=1,max_rounds=1)
                member=source.party[0]
                priority=(recipient,'peasant1')
                source=replace(source,party=(replace(member,target_priority=priority,
                    defeat_decisions=tuple(member.defeat_decision(a) for a in priority)),),
                    npc_help_policies=(PcNpcHelpPolicy('peasant1',recipient),))
                result=execute(source,values)
                self.assertFalse(any(type(s.proof) is PcNpcHelpProof for s in result.steps))
                self.assertTrue(any(type(s.proof) is PcAttackProof and s.proof.request.actor_id=='peasant1'
                    for s in result.steps))
                self.assertIs(result.outcome,outcome)

    def test_receipts_bind_each_round_test_without_carrying_previous_round_bonus(self):
        result=simple_help(rounds=2)
        incoming=tuple(s.proof for s in result.steps if type(s.proof) is PcAttackProof
            and s.proof.request.actor_id=='peasant2')
        self.assertEqual(tuple(len(p.npc_help_applications) for p in incoming),(2,2))
        self.assertEqual(tuple(p.execution.resolution.attack.attacker_test.trace.rolled_dice for p in incoming),(5,5))
        self.assertNotEqual(incoming[0].npc_help_applications[0].source_request.help.bonus.id,
            incoming[1].npc_help_applications[0].source_request.help.bonus.id)
        self.assertEqual(result.executed_actions,8)

    def test_actor_rule_test_receipt_and_application_source_cannot_be_replayed_or_swapped(self):
        result=simple_help()
        helps=tuple(s for s in result.steps if type(s.proof) is PcNpcHelpProof)
        help_step=helps[0]
        with self.assertRaises(ValueError):
            apply_pc_melee_step(help_step.state,help_step)
        bad_request=replace(help_step.proof.request,source_rule_id='RULE-OTHER:automatic-help')
        with self.assertRaises(ValueError):
            PcMeleeStep(help_step.source,PcNpcHelpProof(bad_request,expected_automatic_help_action(bad_request)))
        with self.assertRaises(ValueError):
            PcMeleeStep(helps[1].source,helps[0].proof)
        attack=next(s for s in result.steps if type(s.proof) is PcAttackProof and s.proof.request.actor_id=='peasant2')
        apps=attack.proof.npc_help_applications
        for wrong in ((),(*apps,apps[0]),tuple(reversed(apps))):
            with self.subTest(applications=wrong),self.assertRaises(ValueError):
                PcMeleeStep(attack.source,replace(attack.proof,npc_help_applications=wrong))
        forged=deepcopy(result)
        proof=next(s.proof for s in forged.steps if type(s.proof) is PcNpcHelpProof)
        object.__setattr__(proof.execution.bonus,'effect_kind',AutomaticHelpEffectKind.FREE_SUCCESS)
        with self.assertRaises(ValueError):
            replace(forged)


if __name__=='__main__':
    unittest.main()
