"""C20 maximum-outcome receipts keep every actual raw die and resource price."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_honour_bound import context, state, unmitigated
from tests.unit.test_k1_attack_resolution import attack_request
from tests.unit.test_k1_aim_resolution import active_round as aim_round, reserve_action as aim_slot, aim_request
from tests.unit.test_k1_help_resolution import active_round as help_round, reserve_action as help_slot, help_request
from tests.unit.test_k1_hazard_resolution import exposure, avoidance_test
from tests.unit.test_k1_casting_test_resolution import casting_request
from towr.domain.attack_models import AttackOutcome, defender_won_attack_opposition
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.critical_injury_models import CriticalInjuryTestRequest, critical_injury_state_after_test
from towr.domain.exacting_test_models import ExactingTestProgress, ExactingTestContributionRequest
from towr.domain.fate_models import FateSessionState
from towr.domain.honour_bound_models import (
    HONOUR_BOUND_UNMITIGATED_RULE_ID, HonourBoundOutcomeGrant, HonourBoundUnmitigatedRequest,
    activate_honour_bound_unmitigated, grant_honour_bound_outcome,
)
from towr.domain.injury_models import CharacterInjuryState
from towr.domain.magic_models import WizardMagicState
from towr.domain.resolution_models import HazardResolutionRequest, TargetInjuryPolicy
from towr.domain.test_models import (
    BasicOutcome, DiceModifier, OpposedOutcome, OpposedSide, OpposedTestRequest, SuccessModifier,
    TestProfile, TestRequest, TestResult, TieBreak,
)
from towr.domain.turn_models import CombatActionKind
from towr.rules.aim_resolution import execute_aim_action
from towr.rules.attack_resolution import _resolve_attack_after_tests
from towr.rules.casting_test_resolution import _complete_casting_test
from towr.rules.exacting_test_resolution import complete_exacting_test_contribution
from towr.rules.hazard_resolution import resolve_hazard
from towr.rules.help_resolution import _complete_help_action
from towr.rules.miscast_pool_resolution import rule_of_nine_reroll_lock
from towr.rules.opposed_test import complete_opposed_test
from towr.rules.test_resolution import classify_basic_outcome, resolve_test


def granted(test, values=None, *, scope=True, actor='pc'):
    if values is None:
        values = [10] * test.profile.base_dice
    raw = resolve_test(test, SequenceRandom(values))
    request = HonourBoundUnmitigatedRequest('activate:' + test.id, state(actor),
        context(unmitigated_success_scope_confirmed=scope), FateSessionState('session',actor,2,2),
        test, 'gm:scope:' + test.id, final_result=raw)
    activation = activate_honour_bound_unmitigated(request)
    return grant_honour_bound_outcome(activation), raw, activation


class HonourBoundOutcomeTests(unittest.TestCase):
    def test_raw_trace_and_successes_are_unchanged_while_gm_maximum_is_explicit(self):
        test = TestRequest('actual',TestProfile(3,4),
            dice_modifiers=(DiceModifier('cap:bonus',100),DiceModifier('over:cap',2,True)),
            success_modifiers=(SuccessModifier('flat:penalty',-2),))
        result, raw, activation = granted(test,[10]*8)
        self.assertIs(result.trace,raw.trace)
        self.assertEqual(result.successes,0)
        self.assertEqual(raw.successes,0)
        self.assertEqual(result.effective_successes,6)  # Actual capped6 + bypass2 - flat2.
        self.assertTrue(result.succeeded)
        self.assertEqual(result.honour_bound.activation,activation)
        self.assertEqual(result.honour_bound.raw_test,raw)
        self.assertEqual(activation.fate_state.rating,2)
        self.assertEqual(activation.fate_state.remaining_spends,1)
        self.assertEqual(activation.fate_state.burns,())

    def test_one_die_or_zero_numeric_progress_still_has_categorical_total_success(self):
        for delta, maximum in ((None,1),(-3,0)):
            with self.subTest(delta=delta):
                modifiers=() if delta is None else (SuccessModifier('flat:penalty',delta),)
                result, raw, _ = granted(TestRequest('actual',TestProfile(1,1),success_modifiers=modifiers))
                self.assertEqual(result.successes,0)
                self.assertEqual(result.effective_successes,maximum)
                self.assertTrue(result.succeeded)
                self.assertIs(classify_basic_outcome(result),BasicOutcome.TOTAL_SUCCESS)
                self.assertIs(classify_basic_outcome(raw),BasicOutcome.FAILURE)

    def test_scope_and_complete_final_witness_are_mandatory(self):
        with self.assertRaises(ValueError):
            granted(TestRequest('actual',TestProfile(2,4)),scope=False)
        initial_only = activate_honour_bound_unmitigated(unmitigated())
        with self.assertRaises(ValueError):
            grant_honour_bound_outcome(initial_only)
        result, raw, activation = granted(TestRequest('actual',TestProfile(2,4)))
        with self.assertRaises(TypeError):
            HonourBoundOutcomeGrant(activation,result)
        with self.assertRaises(ValueError):
            HonourBoundOutcomeGrant(activation,resolve_test(TestRequest('other',TestProfile(2,4)),SequenceRandom([10,10])))

    def test_forged_cached_maximum_or_trace_cannot_change_outcome(self):
        result, raw, _ = granted(TestRequest('actual',TestProfile(2,4)))
        for maximum in (True,99):
            with self.subTest(maximum=maximum):
                forged=deepcopy(result.honour_bound)
                object.__setattr__(forged,'maximum_successes',maximum)
                with self.assertRaises(ValueError):
                    replace(result,honour_bound=forged)
        with self.assertRaises(ValueError):
            replace(result,trace=replace(raw.trace,successes=99))
        with self.assertRaises(ValueError):
            replace(result,trace=replace(raw.trace,successes=False))
        with self.assertRaises(TypeError):
            replace(result,honour_bound=True)

    def test_attack_force_hit_uses_maximum_margin_without_rewriting_either_test(self):
        request=attack_request()
        own, raw, _ = granted(request.attacker_test)
        defender=resolve_test(request.defender_test,SequenceRandom([1,1]))
        result=_resolve_attack_after_tests(request,own,defender)
        self.assertIs(result.outcome,AttackOutcome.HIT)
        self.assertEqual(result.success_margin,3)
        self.assertEqual(result.damage,7)
        self.assertFalse(result.tie_break_applied)
        self.assertIs(result.attacker_test,own)
        self.assertIs(result.defender_test,defender)
        self.assertEqual(result.attacker_test.successes,0)
        self.assertIn(HONOUR_BOUND_UNMITIGATED_RULE_ID,result.applied_rule_ids)
        plain=_resolve_attack_after_tests(request,raw,defender)
        self.assertIs(plain.outcome,AttackOutcome.MISS)

    def test_unopposed_attack_does_not_invent_a_defender(self):
        request=attack_request(defender=False)
        own, _, _ = granted(request.attacker_test)
        result=_resolve_attack_after_tests(request,own,None)
        self.assertIs(result.outcome,AttackOutcome.HIT)
        self.assertIsNone(result.defender_test)
        with self.assertRaises(ValueError):
            _resolve_attack_after_tests(request,own,own)

    def test_defender_grant_is_actual_successful_opposition_even_against_more_raw_successes(self):
        request=attack_request()
        attacker=resolve_test(request.attacker_test,SequenceRandom([1,1,1]))
        defender, raw, _ = granted(request.defender_test)
        result=_resolve_attack_after_tests(request,attacker,defender)
        self.assertIs(result.outcome,AttackOutcome.MISS)
        self.assertEqual(result.success_margin,0)
        self.assertTrue(defender_won_attack_opposition(request,result))
        self.assertEqual(defender.successes,raw.successes)
        self.assertEqual(defender.effective_successes,2)
        self.assertIn(HONOUR_BOUND_UNMITIGATED_RULE_ID,result.applied_rule_ids)

    def test_double_override_and_rebound_prepared_source_are_rejected(self):
        request=attack_request()
        attacker, _, _ = granted(request.attacker_test)
        defender, _, _ = granted(request.defender_test)
        with self.assertRaises(ValueError):
            _resolve_attack_after_tests(request,attacker,defender)
        altered=replace(request,attacker_test=replace(request.attacker_test,profile=TestProfile(3,6)))
        with self.assertRaises(ValueError):
            _resolve_attack_after_tests(altered,attacker,None)

    def test_opposed_override_has_total_success_and_maximum_margin_not_a_numeric_tie(self):
        request=OpposedTestRequest('opposed',TestRequest('first',TestProfile(1,3)),
            TestRequest('second',TestProfile(3,5)),TieBreak('ordinary:tie',OpposedSide.OPPONENT))
        first, _, _ = granted(request.initiator)
        second=resolve_test(request.opponent,SequenceRandom([1,1,1]))
        result=complete_opposed_test(request,first,second)
        self.assertIs(result.outcome,OpposedOutcome.INITIATOR_WINS)
        self.assertEqual(result.success_margin,1)
        self.assertIs(result.consequence,BasicOutcome.TOTAL_SUCCESS)
        self.assertFalse(result.tie_break_applied)
        second_override, _, _ = granted(request.opponent)
        with self.assertRaises(ValueError):
            complete_opposed_test(request,first,second_override)

    def test_exacting_adds_only_the_current_actual_test_maximum_not_total_task_completion(self):
        test=TestRequest('reload:actual',TestProfile(2,5))
        result, raw, _ = granted(test)
        request=ExactingTestContributionRequest('contribute',ExactingTestProgress('reload',8),'pc',test)
        contribution=complete_exacting_test_contribution(request,result)
        self.assertEqual(contribution.contribution.successes,2)
        self.assertEqual(contribution.progress.accumulated_successes,2)
        self.assertFalse(contribution.progress.completed)
        self.assertIs(contribution.test_result,result)
        self.assertEqual(contribution.test_result.trace,raw.trace)

    def test_help_uses_actual_pool_maximum_for_one_named_beneficiary_test(self):
        request=help_request(help_slot(help_round(),CombatActionKind.HELP))
        result, raw, _ = granted(request.help_test,actor=request.actor_id)
        completed=_complete_help_action(request,result)
        self.assertEqual(completed.bonus.bonus_dice,3)
        self.assertEqual(completed.bonus.beneficiary_test_id,request.beneficiary_test_id)
        self.assertEqual(completed.help_test_result.trace,raw.trace)
        self.assertTrue(completed.slot.executed)

    def test_aim_snapshot_uses_effective_pool_while_preserving_raw_awareness(self):
        request=aim_request(aim_slot(aim_round(),CombatActionKind.AIM))
        raw_execution=execute_aim_action(request,SequenceRandom([10,10,10]))
        result, raw, _ = granted(request.awareness_test,actor=request.actor_id)
        completed=replace(raw_execution,awareness_test_result=result,
            bonus=replace(raw_execution.bonus,bonus_dice=3))
        self.assertEqual(completed.bonus.bonus_dice,3)
        self.assertEqual(completed.awareness_test_result.trace,raw.trace)
        with self.assertRaises(ValueError):
            replace(completed,bonus=replace(completed.bonus,bonus_dice=0))

    def test_casting_progress_is_effective_but_actual_nines_still_generate_miscasts(self):
        request=casting_request(state=WizardMagicState())
        guarded=replace(request.test,reroll_locks=(*request.test.reroll_locks,rule_of_nine_reroll_lock()))
        result, raw, _ = granted(guarded,[9,10,9],actor=request.caster_id)
        completed=_complete_casting_test(request,result)
        self.assertEqual(completed.latest_roll_successes,3)
        self.assertEqual(completed.state.casting_successes,3)
        self.assertEqual(completed.miscast_dice_added,2)
        self.assertEqual(completed.follow_ups[0].amount,2)
        self.assertEqual(completed.test.trace.final_values,(9,10,9))
        self.assertEqual(completed.test.trace,raw.trace)

    def test_hazard_uses_the_best_reachable_reduction_without_inventing_more_successes(self):
        for rating, avoided, shortfall in ((1,True,0),(3,False,2)):
            with self.subTest(rating=rating):
                source=exposure(rating=rating)
                test=TestRequest(source.test_id,TestProfile(1,3))
                result, _, _ = granted(test)
                request=HazardResolutionRequest('hazard','pc',source,result,
                    TargetInjuryPolicy.PLAYER,CharacterInjuryState())
                completed=resolve_hazard(request,SequenceRandom([1]*shortfall))
                self.assertEqual(completed.successes,1)
                self.assertEqual(completed.avoided,avoided)
                self.assertEqual(completed.shortfall,shortfall)

    def test_critical_endurance_respects_categorical_success_without_rewriting_failure_dice(self):
        injury=CharacterInjuryState(conditions=ConditionState(frozenset({Condition.CRITICALLY_INJURED})))
        test=TestRequest('critical:actual',TestProfile(1,3))
        result, raw, _ = granted(test)
        request=CriticalInjuryTestRequest('critical','pc',injury,test.id)
        self.assertEqual(critical_injury_state_after_test(request,result),injury)
        self.assertFalse(raw.succeeded)
        self.assertTrue(critical_injury_state_after_test(request,raw).conditions.has(Condition.DEFENCELESS))


if __name__=='__main__':
    unittest.main()
