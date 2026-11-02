"""Actual K1 Wound10/Test completion and retained injury (ADR-0055)."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import pickle
from random import getstate
import unittest
from unittest.mock import patch

from towr.domain.crushed_rib_test_models import (
    CRUSHED_RIB_TEST_RULE_ID, CrushedRibTestPreparationRequest, CrushedRibCastingPreparationRequest,
    CrushedRibTestPreparationResult, CrushedRibCastingPreparationResult, CrushedRibTestResult, CrushedRibCastingResult,
)
from towr.domain.condition_models import Condition
from towr.domain.injury_models import CharacterInjuryState, CharacterWoundRequest, WoundEffectDuration
from towr.domain.magic_models import CastingTestRequest, WizardMagicState, MiscastPoolResolutionRequest
from towr.domain.test_models import (
    DiceModifier, InlineProfile, QualityModifier, RerollLock, SuccessModifier,
    TestProfile, TestQuality, TestRequest,
)
from towr.rules import crushed_rib_test_resolution as consumer
from towr.rules.casting_test_resolution import resolve_casting_test
from towr.rules.injury_resolution import resolve_character_wound
from towr.rules.miscast_pool_resolution import resolve_miscast_pool_increase
from towr.rules.test_resolution import resolve_test
from towr.rules.wound_effect_resolution import resolve_wound_effect


class Dice:
    def __init__(self, values):
        self.values = tuple(values)
        self.calls = 0

    def randint(self, start, end):
        assert (start, end) == (1, 10)
        value = self.values[self.calls]
        self.calls += 1
        return value


def injury(previous=0):
    state = CharacterInjuryState()
    for index in range(previous + 1):
        values = (1,) * (index + 1) if index < previous else (*((1,) * index), 10 - index)
        result = resolve_character_wound(CharacterWoundRequest(f'wound:{index}', state), Dice(values))
        state = resolve_wound_effect(result.effect_request, result.state).state
    return state


def request(*, previous=0, test=None):
    return CrushedRibTestPreparationRequest('prepare', 'wizard', injury(previous),
        test or TestRequest('test', InlineProfile(3, 5)))


def casting_request(*, test=None):
    return CrushedRibCastingPreparationRequest('prepare-casting', 'wizard', injury(),
        CastingTestRequest('cast-parent', 'wizard', 'lore', test or TestRequest('cast-test', InlineProfile(3, 9)),
                           WizardMagicState(casting_successes=2, casting_lore_id='lore', latest_casting_roll_successes=1)))


class CrushedRibTestResolutionTests(unittest.TestCase):
    def setUp(self):
        self.global_rng = getstate()

    def tearDown(self):
        self.assertEqual(getstate(), self.global_rng)

    def assert_consumed_only(self, source, result):
        self.assertEqual(result.state.wounds, source.state.wounds)
        self.assertEqual(result.state.conditions, source.state.conditions)
        self.assertTrue(result.state.conditions.has(Condition.DRAINED))
        self.assertEqual(result.state.active_wound_effects, source.state.active_wound_effects[:1])
        self.assertIs(result.state.active_wound_effects[0].duration, WoundEffectDuration.UNTIL_TREATED)
        self.assertEqual(result.consumed_effect, source.state.active_wound_effects[1])

    def test_preparation_is_pure_and_drained_removes_only_bonus_and_ordinary_glorious(self):
        test = TestRequest('modified', TestProfile(3, 5),
            dice_modifiers=(DiceModifier('bonus', 4), DiceModifier('penalty', -1), DiceModifier('bypass', 2, True)),
            quality_modifiers=(QualityModifier('existing-grim', TestQuality.GRIM),
                               QualityModifier('glorious', TestQuality.GLORIOUS)),
            success_modifiers=(SuccessModifier('fixed', 1),), reroll_locks=(RerollLock('locked-two', 2),))
        source = request(test=test)
        before = deepcopy(source)
        with patch('random.Random', side_effect=AssertionError('preparation has no RNG')):
            prepared = consumer.prepare_crushed_rib_test(source)
        self.assertEqual(prepared.drained.source_request.actor_id, source.actor_id)
        self.assertEqual(prepared.drained.source_request.conditions, source.state.conditions)
        self.assertEqual(prepared.drained.source_request.test.quality_modifiers,
                         (*test.quality_modifiers, QualityModifier(CRUSHED_RIB_TEST_RULE_ID, TestQuality.GRIM)))
        self.assertEqual(prepared.test.dice_modifiers, (test.dice_modifiers[1],))
        self.assertEqual(prepared.test.quality_modifiers, (test.quality_modifiers[0],
                         QualityModifier(CRUSHED_RIB_TEST_RULE_ID, TestQuality.GRIM)))
        self.assertEqual(prepared.test.success_modifiers, test.success_modifiers)
        self.assertEqual(prepared.test.reroll_locks, test.reroll_locks)
        self.assertEqual(prepared.drained.removed_bonus_modifiers, (test.dice_modifiers[0], test.dice_modifiers[2]))
        self.assertEqual(prepared.drained.removed_quality_modifiers, (test.quality_modifiers[1],))
        self.assertEqual(source, before)

    def test_actual_rolled_superficials_and_ten_preserve_all_records_and_consume_exact_source(self):
        for previous in (0, 1, 2, 3):
            source = request(previous=previous)
            before = deepcopy(source)
            prepared = consumer.prepare_crushed_rib_test(source)
            dice = Dice((1, 6, 2, 8, 3))
            result = consumer.resolve_crushed_rib_test(prepared, dice)
            self.assertEqual(dice.calls, 5)
            self.assertEqual(result.test.trace.final_values, (8, 6, 3))
            self.assertEqual(result.test.successes, 1)
            self.assertEqual(tuple(r.index for r in result.test.trace.rerolls), (0, 2))
            self.assertEqual(result.consumed_effect.wound_sequence, previous + 1)
            self.assert_consumed_only(source, result)
            self.assertIs(consumer.apply_crushed_rib_test_result('wizard', source.state, result), result.state)
            self.assertEqual(source, before)

    def test_zero_success_failed_rerolls_and_already_grim_all_complete_once(self):
        for values, existing in (((8, 9, 10), ()), ((1, 2, 10, 8, 9), ()),
                ((1, 10, 10, 8), (QualityModifier('existing-grim', TestQuality.GRIM),))):
            source = request(test=TestRequest('control', InlineProfile(3, 5), quality_modifiers=existing))
            dice = Dice(values)
            result = consumer.resolve_crushed_rib_test(consumer.prepare_crushed_rib_test(source), dice)
            self.assertEqual((dice.calls, result.test.successes), (len(values), 0))
            self.assertIs(result.test.trace.quality, TestQuality.GRIM)
            self.assertEqual(len(result.test.trace.rerolls), sum(v <= 5 for v in values[:3]))
            self.assert_consumed_only(source, result)

    def test_minimum_die_fixed_successes_and_reroll_locks_match_existing_kernel(self):
        cases = (
            (TestRequest('minimum', TestProfile(3, 5), dice_modifiers=(DiceModifier('penalty', -5),)), (1, 10)),
            (TestRequest('fixed', InlineProfile(3, 5), success_modifiers=(SuccessModifier('fixed', 2),)), (8, 9, 10)),
            (TestRequest('locked', InlineProfile(3, 5), reroll_locks=(RerollLock('locked-one', 1),)), (1, 2, 10, 8)),
        )
        for test, values in cases:
            source = request(test=test)
            prepared = consumer.prepare_crushed_rib_test(source)
            expected = resolve_test(prepared.test, Dice(values))
            actual = consumer.resolve_crushed_rib_test(prepared, Dice(values))
            self.assertEqual(actual.test, expected)
            self.assert_consumed_only(source, actual)
        self.assertTrue(consumer.resolve_crushed_rib_test(consumer.prepare_crushed_rib_test(request(test=cases[0][0])),
                                                      Dice(cases[0][1])).test.trace.minimum_die_rule_applied)

    def test_casting_owns_nine_lock_retains_parent_progress_and_actual_pool_followup(self):
        source = casting_request()
        before = deepcopy(source)
        prepared = consumer.prepare_crushed_rib_casting(source)
        self.assertEqual(prepared.casting, replace(source.casting, test=prepared.drained.test))
        self.assertFalse(prepared.casting.test.reroll_locks)
        dice = Dice((9, 1, 10, 9))
        result = consumer.resolve_crushed_rib_casting(prepared, dice)
        self.assertEqual(dice.calls, 4)
        self.assertEqual(result.casting.test.trace.final_values, (9, 9, 10))
        self.assertEqual(tuple(r.index for r in result.casting.test.trace.rerolls), (1,))
        self.assertEqual(result.casting.test.trace.applied_rule_ids,
                         (CRUSHED_RIB_TEST_RULE_ID, 'RULE-MAGIC-003:rule-of-nine'))
        self.assertEqual((result.casting.previous_casting_successes, result.casting.latest_roll_successes,
                          result.casting.state.casting_successes), (2, 2, 4))
        self.assertEqual(result.casting.miscast_dice_added, 2)
        self.assertEqual(len(result.casting.follow_ups), 1)
        pool = resolve_miscast_pool_increase(MiscastPoolResolutionRequest('pool', result.casting.follow_ups[0],
            result.casting.state, wizard_level=4))
        self.assertEqual(pool.state.miscast_dice, 2)
        self.assertEqual(source, before)
        self.assert_consumed_only(source, result)

    def test_completion_calls_no_executor_or_rng_and_preserves_completed_failure(self):
        ordinary = consumer.prepare_crushed_rib_test(request())
        casting = consumer.prepare_crushed_rib_casting(casting_request(test=TestRequest('failed-cast', InlineProfile(3, 5))))
        completed_test = resolve_test(ordinary.test, Dice((8, 9, 10)))
        completed_cast = resolve_casting_test(casting.casting, Dice((8, 10, 10)))
        with (patch.object(consumer, 'resolve_test', side_effect=AssertionError('no replay')),
              patch.object(consumer, 'resolve_casting_test', side_effect=AssertionError('no replay')),
              patch('random.Random', side_effect=AssertionError('no RNG'))):
            a = consumer.complete_crushed_rib_test(ordinary, completed_test)
            b = consumer.complete_crushed_rib_casting(casting, completed_cast)
            self.assertEqual(a.test.successes, 0)
            self.assertEqual(b.casting.latest_roll_successes, 0)
            self.assertFalse(b.casting.follow_ups)
            self.assert_consumed_only(ordinary.source_request, a)
            self.assert_consumed_only(casting.source_request, b)

    def test_each_executor_delegates_once_with_the_exact_prepared_request_and_rng(self):
        ordinary = consumer.prepare_crushed_rib_test(request())
        casting = consumer.prepare_crushed_rib_casting(casting_request())
        dice = Dice((8, 9, 10))
        with patch.object(consumer, 'resolve_test', wraps=resolve_test) as executor:
            consumer.resolve_crushed_rib_test(ordinary, dice)
            executor.assert_called_once_with(ordinary.test, dice)
        cast_dice = Dice((9, 1, 10, 9))
        with patch.object(consumer, 'resolve_casting_test', wraps=resolve_casting_test) as executor:
            consumer.resolve_crushed_rib_casting(casting, cast_dice)
            executor.assert_called_once_with(casting.casting, cast_dice)

    def test_rng_failure_returns_no_completion_and_does_not_mutate_pending_source(self):
        source = request()
        prepared = consumer.prepare_crushed_rib_test(source)
        before = deepcopy(prepared)
        with patch.object(consumer, 'complete_crushed_rib_test', wraps=consumer.complete_crushed_rib_test) as complete:
            with self.assertRaises(IndexError): consumer.resolve_crushed_rib_test(prepared, Dice((1, 2)))
            complete.assert_not_called()
        self.assertEqual(prepared, before)
        retried = consumer.resolve_crushed_rib_test(prepared, Dice((8, 9, 10)))
        self.assert_consumed_only(source, retried)

    def test_apply_rejects_actor_staleness_replay_and_never_restarts_next_test(self):
        source = request()
        result = consumer.resolve_crushed_rib_test(consumer.prepare_crushed_rib_test(source), Dice((8, 9, 10)))
        with self.assertRaises(ValueError): consumer.apply_crushed_rib_test_result('other', source.state, result)
        with self.assertRaises(ValueError): consumer.apply_crushed_rib_test_result('wizard', injury(1), result)
        applied = consumer.apply_crushed_rib_test_result('wizard', source.state, result)
        with self.assertRaises(ValueError): consumer.apply_crushed_rib_test_result('wizard', applied, result)
        with self.assertRaises(ValueError): replace(source, state=applied)
        self.assertIs(result.state.conditions, source.state.conditions)

    def test_six_models_remain_frozen_slotted_and_pickle_roundtrippable(self):
        a, b = request(), casting_request()
        pa, pb = consumer.prepare_crushed_rib_test(a), consumer.prepare_crushed_rib_casting(b)
        ra = consumer.resolve_crushed_rib_test(pa, Dice((8, 9, 10)))
        rb = consumer.resolve_crushed_rib_casting(pb, Dice((9, 1, 10, 9)))
        for obj, field in ((a, 'id'), (b, 'id'), (pa, 'test'), (pb, 'casting'), (ra, 'test'), (rb, 'casting')):
            self.assertFalse(hasattr(obj, '__dict__'))
            self.assertEqual(replace(obj), obj)
            self.assertEqual(replace(pickle.loads(pickle.dumps(obj))), obj)
            with self.assertRaises(FrozenInstanceError): setattr(obj, field, None)
        self.assertIsInstance(pa, CrushedRibTestPreparationResult)
        self.assertIsInstance(pb, CrushedRibCastingPreparationResult)
        self.assertIsInstance(ra, CrushedRibTestResult)
        self.assertIsInstance(rb, CrushedRibCastingResult)


if __name__ == '__main__':
    unittest.main()
