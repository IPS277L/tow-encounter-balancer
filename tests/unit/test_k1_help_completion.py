"""Already completed Help Tests retain their real slot and ally provenance."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_help_resolution import active_round, help_request, reserve_action
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.help_models import _expected_help_execution
from towr.domain.turn_models import CombatActionKind
from towr.rules.help_resolution import _complete_help_action, execute_help_action
from towr.rules.test_resolution import resolve_test


def request():
    return help_request(reserve_action(active_round(),CombatActionKind.HELP))


class NoRolls:
    def randint(self, start, end):
        raise AssertionError('invalid Help consumed RNG before validation')


class K1HelpCompletionTests(unittest.TestCase):
    def test_completion_matches_execution_for_zero_partial_and_total_success(self):
        source = request()
        for values,expected_bonus in (((8,9,10),0),((1,5,10),2),((1,2,3),3)):
            with self.subTest(values=values):
                test = resolve_test(source.help_test,SequenceRandom(values))
                completed = _complete_help_action(source,test)
                direct = execute_help_action(source,SequenceRandom(values))
                self.assertEqual(completed,direct)
                self.assertEqual(completed,_expected_help_execution(source,test))
                self.assertEqual(completed.bonus.bonus_dice,expected_bonus)
                self.assertIs(completed.help_test_result,test)
                self.assertIs(completed.source_request,source)
                self.assertTrue(completed.slot.executed)

    def test_completion_uses_existing_test_without_rng_and_preserves_clock(self):
        source = request()
        test = resolve_test(source.help_test,SequenceRandom([1,5,10]))
        with patch('towr.rules.help_resolution.resolve_test',side_effect=AssertionError('rerolled Help')):
            completed = _complete_help_action(source,test)
        self.assertEqual(completed.previous_round_state,source.round_state)
        self.assertEqual(completed.round_state.round_number,source.round_state.round_number)
        self.assertEqual(completed.round_state.participants,source.round_state.participants)
        self.assertEqual(completed.round_state.completed_turn_entity_ids,
            source.round_state.completed_turn_entity_ids)
        self.assertEqual(completed.round_state.excluded_turn_entity_ids,
            source.round_state.excluded_turn_entity_ids)
        self.assertEqual(completed.bonus.beneficiary_id,'ally')
        self.assertEqual(completed.bonus.beneficiary_test_id,'beneficiary:test')
        self.assertEqual(completed.slot.execution.actor_id,'helper')
        self.assertEqual(completed.slot.execution.result_request_id,'help:test')

    def test_missing_foreign_or_malformed_completed_tests_are_refused(self):
        source = request()
        test = resolve_test(source.help_test,SequenceRandom([1,5,10]))
        for invalid in (None,object()):
            with self.assertRaises(TypeError):
                _complete_help_action(source,invalid)
        foreign = replace(test,trace=replace(test.trace,request_id='foreign-test'))
        with self.assertRaises(ValueError):
            _complete_help_action(source,foreign)
        for value,error_type in ((True,TypeError),(-1,ValueError)):
            corrupted = deepcopy(test)
            object.__setattr__(corrupted.trace,'successes',value)
            with self.subTest(value=value),self.assertRaises(error_type):
                _complete_help_action(source,corrupted)

    def test_illegal_slot_and_conditions_are_refused_before_rng_and_on_completion(self):
        source = request()
        test = resolve_test(source.help_test,SequenceRandom([1,5,10]))
        invalid = (help_request(active_round()),
            help_request(reserve_action(active_round(),CombatActionKind.ATTACK)),
            replace(source,rule_id='unknown-help-rule'),
            *(replace(source,actor_conditions=ConditionState().with_condition(condition))
                for condition in (Condition.DEAFENED,Condition.DEFENCELESS)))
        for bad in invalid:
            with self.subTest(source=bad):
                with self.assertRaises(ValueError):
                    execute_help_action(bad,NoRolls())
                with self.assertRaises(ValueError):
                    _complete_help_action(bad,test)

    def test_completed_slot_cannot_be_used_twice(self):
        source = request()
        test = resolve_test(source.help_test,SequenceRandom([1,5,10]))
        completed = _complete_help_action(source,test)
        replay = replace(source,round_state=completed.round_state)
        with self.assertRaises(ValueError):
            _complete_help_action(replay,test)
        with self.assertRaises(ValueError):
            execute_help_action(replay,NoRolls())


if __name__ == '__main__':
    unittest.main()
