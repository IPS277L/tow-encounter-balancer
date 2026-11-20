"""Preparation and real opposed resolution, without claiming actor admission."""
from copy import deepcopy
import unittest

from tests.helpers import SequenceRandom
from towr.domain.talent_tie_models import compose_talent_tie_break
from towr.domain.test_models import (
    BasicOutcome, OpposedOutcome, OpposedSide, OpposedTestRequest,
    TestProfile, TestRequest, TieBreak,
)
from towr.rules.opposed_test import resolve_opposed_test


class CountingRandom(SequenceRandom):
    def __init__(self, values):
        super().__init__(values)
        self.calls = []

    def randint(self, start, end):
        self.calls.append((start, end))
        return super().randint(start, end)


def ordinary(winner=OpposedSide.INITIATOR):
    return TieBreak('RULE-TEST-006:ordinary', winner)


def preference(rule='RULE-TALENT-002:short-size', winner=OpposedSide.OPPONENT):
    return TieBreak(rule, winner)


def resolve(tie_break, rolls):
    rng = CountingRandom(rolls)
    source = OpposedTestRequest('talent-contest',
        TestRequest('initiator', TestProfile(2, 5)),
        TestRequest('opponent', TestProfile(2, 5)), tie_break)
    return source, resolve_opposed_test(source, rng), rng


class TalentTiePreparationTests(unittest.TestCase):
    def test_without_preferences_the_exact_ordinary_source_is_retained(self):
        for side in OpposedSide:
            source = ordinary(side)
            self.assertIs(compose_talent_tie_break(source, ()), source)

    def test_same_side_preferences_retain_all_sources_and_ignore_tuple_order(self):
        source = ordinary()
        first = preference()
        second = preference('RULE-TALENT-002:battlefield-musician')
        before = deepcopy((source, first, second))
        result = compose_talent_tie_break(source, (first, second))
        self.assertIs(result.winner, OpposedSide.OPPONENT)
        self.assertEqual(result, compose_talent_tie_break(source, (second, first)))
        for value in (source, first, second):
            self.assertIn(value.rule_id, result.rule_id)
        self.assertEqual((source, first, second), before)
        self.assertNotEqual(result, compose_talent_tie_break(
            ordinary(OpposedSide.OPPONENT), (first, second)))
        self.assertNotEqual(result, compose_talent_tie_break(source, (first,)))

    def test_opposing_preferences_cancel_to_the_exact_ordinary_source(self):
        opposing = (preference('talent:a', OpposedSide.INITIATOR),
            preference('talent:b', OpposedSide.OPPONENT))
        for side in OpposedSide:
            source = ordinary(side)
            self.assertIs(compose_talent_tie_break(source, opposing), source)
            self.assertIs(compose_talent_tie_break(source, tuple(reversed(opposing))), source)
            # Additional supporters do not turn cancellation into majority voting.
            self.assertIs(compose_talent_tie_break(source, (*opposing,
                preference('talent:c', OpposedSide.OPPONENT))), source)

    def test_punctuation_cannot_alias_a_different_set_of_rule_sources(self):
        source = ordinary()
        first = compose_talent_tie_break(source,
            (preference('a|b'), preference('c')))
        second = compose_talent_tie_break(source,
            (preference('a'), preference('b|c')))
        self.assertNotEqual(first.rule_id, second.rule_id)

    def test_duplicate_sources_are_rejected_even_when_their_sides_disagree(self):
        source = ordinary()
        value = preference()
        invalid = ((value, value), (value, deepcopy(value)),
            (value, preference(value.rule_id, OpposedSide.INITIATOR)),
            (preference(source.rule_id),))
        for preferences in invalid:
            with self.subTest(preferences=preferences), self.assertRaises(ValueError):
                compose_talent_tie_break(source, preferences)

    def test_inputs_require_exact_typed_sources_and_an_exact_tuple(self):
        class AliasString(str):
            pass

        class AliasTie(TieBreak):
            pass

        class AliasTuple(tuple):
            pass

        for value in (None, True, 'initiator', ordinary().rule_id,
                AliasTie('alias', OpposedSide.INITIATOR)):
            with self.subTest(ordinary=value), self.assertRaises(TypeError):
                compose_talent_tie_break(value, ())
            with self.subTest(preference=value), self.assertRaises(TypeError):
                compose_talent_tie_break(ordinary(), (value,))
        for values in (None, True, [], [preference()], AliasTuple((preference(),))):
            with self.subTest(preferences=values), self.assertRaises(TypeError):
                compose_talent_tie_break(ordinary(), values)
        value = preference(AliasString('rule:alias'))
        with self.assertRaises(TypeError):
            compose_talent_tie_break(ordinary(), (value,))

    def test_cached_dataclasses_are_revalidated_before_fallback_or_composition(self):
        for field, value, error in (('winner', 'opponent', TypeError),
                ('winner', True, TypeError), ('rule_id', True, TypeError),
                ('rule_id', '', ValueError), ('rule_id', ' rule:alias ', ValueError)):
            damaged = preference()
            object.__setattr__(damaged, field, value)
            with self.subTest(field=field, value=value, role='preference'), self.assertRaises(error):
                compose_talent_tie_break(ordinary(), (damaged,))
            with self.subTest(field=field, value=value, role='ordinary'), self.assertRaises(error):
                compose_talent_tie_break(damaged, ())


class TalentTieResolutionTests(unittest.TestCase):
    def assert_four_actual_rolls(self, rng):
        self.assertEqual(rng.calls, [(1, 10)] * 4)

    def test_either_side_can_receive_a_one_sided_preference(self):
        cases = ((OpposedSide.INITIATOR, OpposedSide.OPPONENT),
            (OpposedSide.OPPONENT, OpposedSide.INITIATOR))
        for preferred, previous in cases:
            with self.subTest(preferred=preferred):
                tie = compose_talent_tie_break(ordinary(previous),
                    (preference('talent:preference', preferred),))
                _, result, rng = resolve(tie, [1, 10, 2, 10])
                self.assertIs(result.winner, preferred)
                self.assertIs(result.consequence, BasicOutcome.MARGINAL_SUCCESS)
                self.assert_four_actual_rolls(rng)

    def test_a_positive_tie_uses_the_composed_preference_and_marginal_success(self):
        tie = compose_talent_tie_break(ordinary(), (preference(),))
        source, result, rng = resolve(tie, [1, 10, 2, 10])
        self.assertIs(source.tie_break, tie)
        self.assertIs(result.outcome, OpposedOutcome.OPPONENT_WINS)
        self.assertIs(result.winner, OpposedSide.OPPONENT)
        self.assertIs(result.consequence, BasicOutcome.MARGINAL_SUCCESS)
        self.assertEqual(result.success_margin, 0)
        self.assertTrue(result.tie_break_applied)
        self.assertEqual(result.tie_break_rule_id, tie.rule_id)
        self.assertEqual(result.initiator.trace.request_id, source.initiator.id)
        self.assertEqual(result.opponent.trace.request_id, source.opponent.id)
        self.assert_four_actual_rolls(rng)

    def test_positive_tie_after_cancellation_uses_the_ordinary_rule_and_side(self):
        fallback = ordinary(OpposedSide.OPPONENT)
        tie = compose_talent_tie_break(fallback,
            (preference('a', OpposedSide.INITIATOR), preference('b', OpposedSide.OPPONENT)))
        _, result, rng = resolve(tie, [1, 10, 2, 10])
        self.assertIs(result.winner, fallback.winner)
        self.assertIs(result.consequence, BasicOutcome.MARGINAL_SUCCESS)
        self.assertEqual(result.tie_break_rule_id, fallback.rule_id)
        self.assert_four_actual_rolls(rng)

    def test_double_zero_is_both_fail_even_with_a_one_sided_preference(self):
        tie = compose_talent_tie_break(ordinary(), (preference(),))
        _, result, rng = resolve(tie, [10, 10, 10, 10])
        self.assertIs(result.outcome, OpposedOutcome.BOTH_FAIL)
        self.assertIsNone(result.winner)
        self.assertIsNone(result.consequence)
        self.assertEqual(result.success_margin, 0)
        self.assertFalse(result.tie_break_applied)
        self.assertIsNone(result.tie_break_rule_id)
        self.assert_four_actual_rolls(rng)

    def test_unequal_successes_are_identical_to_resolution_without_a_preference(self):
        for rolls, winner in (([1, 2, 1, 10], OpposedSide.INITIATOR),
                ([1, 10, 1, 2], OpposedSide.OPPONENT)):
            with self.subTest(winner=winner):
                fallback = ordinary(OpposedSide.INITIATOR)
                tie = compose_talent_tie_break(fallback, (preference(),))
                _, expected, baseline_rng = resolve(fallback, rolls)
                _, result, rng = resolve(tie, rolls)
                self.assertEqual(result, expected)
                self.assertIs(result.winner, winner)
                self.assertFalse(result.tie_break_applied)
                self.assertIsNone(result.tie_break_rule_id)
                self.assert_four_actual_rolls(baseline_rng)
                self.assert_four_actual_rolls(rng)
