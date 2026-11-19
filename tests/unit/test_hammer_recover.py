"""A real paid GM83 Hammer extraction is an alternate Recover, not Burdened."""
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_k1_recover_resolution import (
    active_round, reserve_action, recover_request, self_target, ally_target,
)
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.magic_models import WizardMagicState
from towr.domain.recover_models import (
    RecoverMode, RecoverHammerRetrievalChoice, RecoverHammerRetrievalResult,
    RecoverStandardChoice, _expected_recover_execution,
)
from towr.domain.test_models import (
    DiceModifier, QualityModifier, Skill, TestProfile, TestQuality, TestRequest,
)
from towr.domain.turn_models import CombatActionKind
from towr.domain.weapon_magic_lifecycle import (
    GROTARGG_RETRIEVE_RULE_ID, prepare_hammer_retrieval_test,
)
from towr.rules.recover_resolution import (
    execute_recover_action, _complete_hammer_retrieval_after_test,
)
from towr.rules.test_resolution import resolve_test, RerollAllFailures


class NoRandom:
    def randint(self, *_):
        raise AssertionError('a completed or unavailable extraction cannot roll again')


def source(*, conditions=None, glorious=False, kind=CombatActionKind.RECOVER,
        reserved=True, enemy=False):
    conditions = conditions if conditions is not None else ConditionState({Condition.STAGGERED, Condition.PRONE})
    test = TestRequest('hammer:brawn', TestProfile(4, 5),
        quality_modifiers=(QualityModifier('actual-glory', TestQuality.GLORIOUS),) if glorious else ())
    test = prepare_hammer_retrieval_test(test)
    choice = RecoverHammerRetrievalChoice(self_target(conditions), 'actual-hammer-unit', test)
    clock = reserve_action(active_round(), kind) if reserved else active_round()
    return recover_request(clock, actor_conditions=conditions,
        mode=RecoverMode.RETRIEVE_HAMMER, choice=choice, actor_has_enemy_in_zone=enemy)


class HammerRecoverTests(unittest.TestCase):
    def test_actual_success_or_failure_spends_one_recover_and_grants_no_standard_benefits(self):
        for dice, success in (([1, 10], True), ([10, 10], False)):
            with self.subTest(dice=dice):
                request = source()
                result = execute_recover_action(request, SequenceRandom(dice))
                self.assertIs(type(result.resolution), RecoverHammerRetrievalResult)
                self.assertEqual(result.resolution.succeeded, success)
                self.assertEqual(result.resolution.test_result.trace.initial_values, tuple(dice))
                self.assertEqual(result.resolution.source.target.conditions, request.actor_conditions)
                self.assertEqual(result.resolution.source.test_skill, Skill.BRAWN)
                self.assertFalse(hasattr(result.resolution, 'condition_changes'))
                self.assertFalse(hasattr(result.resolution, 'magic_state'))
                self.assertFalse(hasattr(result.resolution, 'object_interaction_follow_up'))
                self.assertTrue(result.slot.executed)
                self.assertEqual(result.slot.execution.result_request_id, 'hammer:brawn')
                self.assertEqual(result.round_state.active_turn.action_slots, (result.slot,))
                self.assertIn(GROTARGG_RETRIEVE_RULE_ID, result.applied_rule_ids)

    def test_already_owned_glorious_test_can_complete_without_a_second_roll(self):
        request = source(glorious=True)
        test = resolve_test(request.choice.test, SequenceRandom([10, 10, 1, 10]),
            decisions=RerollAllFailures())
        resolution = _complete_hammer_retrieval_after_test(request.choice, test)
        result = _expected_recover_execution(request, resolution)
        self.assertIs(result.resolution.test_result, test)
        self.assertTrue(result.resolution.succeeded)
        self.assertEqual(len(test.trace.rerolls), 2)
        self.assertIn('actual-glory', result.applied_rule_ids)
        self.assertEqual(result.slot.execution.result_request_id, test.trace.request_id)

    def test_choice_requires_exact_item_actual_self_and_very_difficult_source(self):
        request = source()
        for changes in ({'item_id': ''}, {'rule_id': 'not-hammer'},
                {'test': replace(request.choice.test, dice_modifiers=())},
                {'test': replace(request.choice.test,
                    dice_modifiers=(DiceModifier(GROTARGG_RETRIEVE_RULE_ID, -1),))}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(request.choice, **changes)
        with self.assertRaises(ValueError):
            replace(request, choice=replace(request.choice,
                target=ally_target(request.actor_conditions)))
        with self.assertRaises(ValueError):
            replace(request, choice=replace(request.choice,
                target=self_target(ConditionState())))

    def test_standard_and_hammer_modes_cannot_impersonate_each_other(self):
        request = source()
        with self.assertRaises(TypeError):
            replace(request, mode=RecoverMode.STANDARD)
        with self.assertRaises(TypeError):
            replace(request, choice=RecoverStandardChoice(WizardMagicState()))

    def test_cannot_execute_missing_consumed_or_wrong_action_slot(self):
        for request in (source(reserved=False), source(kind=CombatActionKind.ATTACK)):
            with self.subTest(request=request), self.assertRaises(ValueError):
                execute_recover_action(request, NoRandom())
        request = source()
        result = execute_recover_action(request, SequenceRandom([1, 1]))
        with self.assertRaises(ValueError):
            execute_recover_action(replace(request, round_state=result.round_state), NoRandom())
        with self.assertRaises(ValueError):
            _expected_recover_execution(replace(request, round_state=result.round_state), result.resolution)

    def test_broken_unsafe_or_defenceless_actor_is_rejected_before_rng(self):
        for conditions, enemy in ((ConditionState({Condition.BROKEN}), True),
                (ConditionState({Condition.DEFENCELESS}), False)):
            with self.subTest(conditions=conditions), self.assertRaises(ValueError):
                execute_recover_action(source(conditions=conditions, enemy=enemy), NoRandom())

    def test_result_cannot_forge_foreign_test_or_success_counter(self):
        request = source()
        test = resolve_test(request.choice.test, SequenceRandom([10, 10]))
        for trace in (replace(test.trace, request_id='other'), replace(test.trace, successes=2),
                replace(test.trace, successes=True), replace(test.trace, threshold=10)):
            with self.subTest(trace=trace), self.assertRaises((TypeError, ValueError)):
                _complete_hammer_retrieval_after_test(request.choice, replace(test, trace=trace))


if __name__ == '__main__':
    unittest.main()
