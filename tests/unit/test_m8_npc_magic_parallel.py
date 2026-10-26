"""ADR-0039 transport admission and bounded scheduling without real processes."""
from concurrent.futures import Future
from dataclasses import replace
import pickle
from random import Random
import unittest
from unittest.mock import Mock, patch

from tests.unit.test_m8_npc_magic_simulation_models import observations, request
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome
from towr.simulation import npc_magic_parallel as parallel
from towr.simulation.npc_magic_models import NpcMagicSimulationResult


class RecordingFactory:
    """Picklable factory whose calls remain visible in these parent-only tests."""
    def __init__(self):
        self.seeds = []

    def __call__(self, seed):
        self.seeds.append(seed)
        return Random(seed)


def records(source):
    templates = observations(replace(source, trials=max(4, source.trials)))
    return tuple(replace(templates[i % 4], trial_index=i, seed=source.seed_for(i))
                 for i in range(source.trials))


def transported(record, **changes):
    copied = pickle.loads(pickle.dumps(record))
    for name, value in changes.items():
        object.__setattr__(copied, name, value)
    return pickle.loads(pickle.dumps(copied))


class MagicParallelAdmissionTests(unittest.TestCase):
    def test_preflight_rejects_types_ranges_families_and_noncallable_before_pool(self):
        from tests.unit.test_m7_npc_mixed_simulation import request as mixed_request
        from tests.unit.test_m6_npc_melee_simulation import request as melee_request
        from tests.unit.test_m3_npc_ranged_simulation import request as ranged_request
        source = request()
        factory = RecordingFactory()
        with patch.object(parallel, 'ProcessPoolExecutor') as pool, \
                patch.object(parallel, 'run_npc_magic_trial') as trial:
            for name in ('workers', 'batch_size'):
                for value in (True, False, 1.0, '1', None):
                    with self.subTest(name=name, value=value), self.assertRaises(TypeError):
                        parallel.run_npc_magic_simulation_parallel(source, **{'workers': 2, name: value}, rng_factory=factory)
                for value in (0, -1):
                    with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                        parallel.run_npc_magic_simulation_parallel(source, **{'workers': 2, name: value}, rng_factory=factory)
            for value in (None, {}, source.scenario, mixed_request(), melee_request(), ranged_request()):
                with self.subTest(source=type(value)), self.assertRaises(TypeError):
                    parallel.run_npc_magic_simulation_parallel(value, workers=2, rng_factory=factory)
            for value in (None, 1, object()):
                with self.subTest(factory=type(value)), self.assertRaises(TypeError):
                    parallel.run_npc_magic_simulation_parallel(source, workers=2, rng_factory=value)
            pool.assert_not_called()
            trial.assert_not_called()
        self.assertEqual(factory.seeds, [])

    def test_pickle_failure_and_local_lambda_precede_pool_or_factory_calls(self):
        source, factory = request(), RecordingFactory()
        failure = pickle.PicklingError('unserializable source')
        with patch.object(parallel.pickle, 'dumps', side_effect=failure) as dump, \
                patch.object(parallel, 'ProcessPoolExecutor') as pool:
            with self.assertRaises(pickle.PicklingError) as caught:
                parallel.run_npc_magic_simulation_parallel(source, workers=1, rng_factory=factory)
            self.assertIs(caught.exception, failure)
            dump.assert_called_once_with((source, factory))
            pool.assert_not_called()
        with patch.object(parallel, 'ProcessPoolExecutor') as pool:
            with self.assertRaises((AttributeError, TypeError, pickle.PicklingError)):
                parallel.run_npc_magic_simulation_parallel(source, workers=1, rng_factory=lambda seed: Random(seed))
            pool.assert_not_called()
        self.assertEqual(factory.seeds, [])

    def test_batch_calls_existing_trial_with_full_request_and_absolute_indices(self):
        source, factory = request(7), RecordingFactory()
        expected = records(source)[3:6]
        with patch.object(parallel, 'run_npc_magic_trial', side_effect=expected) as trial:
            result = parallel._run_batch(source, range(3, 6), factory)
        self.assertEqual(result, expected)
        self.assertIsInstance(result, tuple)
        self.assertEqual(tuple(c.args[1] for c in trial.call_args_list), (3, 4, 5))
        self.assertTrue(all(c.args[0] is source for c in trial.call_args_list))
        self.assertTrue(all(c.kwargs['rng_factory'] is factory for c in trial.call_args_list))
        self.assertEqual(source.trials, 7)
        self.assertEqual(factory.seeds, [])

    def test_batch_exception_keeps_identity_and_adds_seed_note_without_next_trial(self):
        source = request()
        failure = ValueError('worker test failure')
        failure.add_note('original worker note')
        cause = RuntimeError('original cause')
        failure.__cause__ = cause
        with patch.object(parallel, 'run_npc_magic_trial', side_effect=(records(source)[1], failure)) as trial:
            with self.assertRaises(ValueError) as caught: parallel._run_batch(source, range(1, 4), Random)
        self.assertIs(caught.exception, failure)
        self.assertIs(caught.exception.__cause__, cause)
        self.assertEqual(caught.exception.__notes__, ['original worker note', f'M8 trial index=2, seed={source.seed_for(2)}'])
        self.assertEqual(tuple(c.args[1] for c in trial.call_args_list), (1, 2))

    def test_worker_baseexceptions_are_not_wrapped_or_given_gameplay_notes(self):
        source = request()
        for failure in (KeyboardInterrupt('interrupt'), SystemExit('exit')):
            with self.subTest(error=type(failure)), \
                    patch.object(parallel, 'run_npc_magic_trial', side_effect=failure) as trial:
                with self.assertRaises(type(failure)) as caught: parallel._run_batch(source, range(1, 4), Random)
            self.assertIs(caught.exception, failure)
            self.assertFalse(hasattr(failure, '__notes__'))
            self.assertEqual(trial.call_count, 1)


class MagicParallelNormalizationTests(unittest.TestCase):
    def test_equal_transported_sources_are_rebound_to_original_parent_identity(self):
        source = request()
        original = records(source)
        copied = pickle.loads(pickle.dumps(original))
        self.assertIsNot(copied[0].source_scenario, source.scenario)
        result = parallel._normalize_batch(source, range(4), copied)
        self.assertEqual(result, original)
        self.assertTrue(all(r.source_scenario is source.scenario for r in result))
        self.assertTrue(all(r.source_scenario is copied[0].source_scenario for r in copied))
        self.assertEqual(tuple((r.outcome, r.executed_action_count, r.started_round_count,
                                r.completed_round_count) for r in result),
                         tuple((r.outcome, r.executed_action_count, r.started_round_count,
                                r.completed_round_count) for r in original))

    def test_payload_requires_tuple_and_exact_assigned_cardinality(self):
        source = request()
        valid = records(source)
        for payload in (None, {}, list(valid), iter(valid), (r for r in valid), (None,) * 4):
            with self.subTest(payload=type(payload)), self.assertRaises(TypeError):
                parallel._normalize_batch(source, range(4), payload)
        for payload in ((), valid[:-1], (*valid, valid[0])):
            with self.subTest(length=len(payload)), self.assertRaises(ValueError):
                parallel._normalize_batch(source, range(4), payload)
        # len(range(2**64-1)) raises OverflowError on this platform; count must be arithmetic.
        with self.assertRaises(ValueError): parallel._normalize_batch(source, range(2**64-1), ())

    def test_foreign_source_is_rejected_before_any_rebinding_even_with_same_id(self):
        from tests.unit.test_m7_npc_mixed_simulation import request as mixed_request
        from towr.domain.test_models import InlineProfile
        source = request()
        valid = records(source)[0]
        foreign = replace(source.scenario, max_rounds=4)
        self.assertEqual(foreign.id, source.scenario.id)
        self.assertNotEqual(foreign, source.scenario)
        other_policy = replace(source.scenario, actors=tuple(
            replace(policy, willpower_profile=InlineProfile(2, 3)) if policy.actor_id == 'enemy' else policy
            for policy in source.scenario.actors))
        self.assertEqual(other_policy.max_rounds, source.scenario.max_rounds)
        self.assertEqual(other_policy.id, source.scenario.id)
        for value, error in ((None, TypeError), (mixed_request().scenario, TypeError),
                             (foreign, ValueError), (other_policy, ValueError)):
            payload = transported(valid, source_scenario=value)
            with self.subTest(source=type(value)), \
                    patch.object(parallel, 'replace', side_effect=AssertionError('must check source before replace')) as rebind:
                with self.assertRaises(error): parallel._normalize_batch(source, range(1), (payload,))
                rebind.assert_not_called()

    def test_transport_rejects_other_record_family_and_equal_enum_strings(self):
        from tests.unit.test_m7_npc_mixed_simulation import request as mixed_request, observations as mixed_records
        from towr.domain.npc_mixed_scenario_result_models import NpcMixedScenarioOutcome
        source = request()
        with self.assertRaises(TypeError):
            parallel._normalize_batch(source, range(4), mixed_records(mixed_request()))
        record = records(source)[0]
        self.assertEqual(record.outcome, NpcMixedScenarioOutcome.OBJECTIVE_ACHIEVED)
        for value in (record.outcome.value, NpcMixedScenarioOutcome.OBJECTIVE_ACHIEVED):
            with self.subTest(outcome=value), self.assertRaises(TypeError):
                parallel._normalize_batch(source, range(1), (transported(record, outcome=value),))

    def test_unpickle_forged_bool_fields_revalidate_before_equality_checks(self):
        source = request()
        record = records(source)[1]  # True would compare equal to this valid assigned index.
        for name in ('trial_index', 'seed', 'executed_action_count', 'started_round_count', 'completed_round_count'):
            with self.subTest(field=name), self.assertRaises(TypeError):
                parallel._normalize_batch(source, range(1, 2), (transported(record, **{name: True}),))

    def test_unpickle_forged_numeric_types_ranges_and_counter_consistency_fail(self):
        source = request()
        record = records(source)[0]
        invalid = (({'trial_index': 0.0}, TypeError), ({'seed': '1'}, TypeError),
                   ({'executed_action_count': 1.0}, TypeError), ({'started_round_count': '1'}, TypeError),
                   ({'completed_round_count': None}, TypeError), ({'seed': -1}, ValueError),
                   ({'seed': 2**256}, ValueError), ({'trial_index': -1}, ValueError),
                   ({'executed_action_count': -1}, ValueError), ({'started_round_count': 0}, ValueError),
                   ({'started_round_count': 4}, ValueError), ({'completed_round_count': 2}, ValueError),
                   ({'executed_action_count': 0}, ValueError), ({'executed_action_count': 4}, ValueError),
                   ({'outcome': Outcome.ROUND_LIMIT_REACHED}, ValueError))
        for changes, error in invalid:
            with self.subTest(changes=changes), self.assertRaises(error):
                parallel._normalize_batch(source, range(1), (transported(record, **changes),))

    def test_assigned_range_checks_index_order_duplicates_cross_batch_and_exact_seed(self):
        source = request()
        valid = records(source)
        for payload in ((valid[1], valid[0]), (valid[0], valid[0]), (valid[2], valid[3]),
                        (replace(valid[0], seed=source.seed_for(1)), valid[1])):
            with self.subTest(indices=tuple(r.trial_index for r in payload)), self.assertRaises(ValueError):
                parallel._normalize_batch(source, range(2), payload)
        self.assertEqual(parallel._normalize_batch(source, range(2, 4), valid[2:]), valid[2:])


class MagicParallelSchedulerTests(unittest.TestCase):
    def test_bounded_reverse_completion_uneven_tail_large_batch_and_excess_workers(self):
        source = request(7)
        valid = records(source)
        for workers, batch_size in ((1, 1), (1, 3), (2, 1), (2, 3), (2, 32), (8, 9)):
            with self.subTest(workers=workers, batch_size=batch_size), \
                    patch.object(parallel, 'ProcessPoolExecutor') as factory:
                pool = factory.return_value.__enter__.return_value
                outstanding, scheduled = set(), []

                def submit(fn, actual, indices, rng_factory):
                    self.assertIs(fn, parallel._run_batch)
                    self.assertIs(actual, source)
                    self.assertIsInstance(indices, range)
                    self.assertIs(rng_factory, Random)
                    future = Future()
                    future.set_result(pickle.loads(pickle.dumps(tuple(valid[i] for i in indices))))
                    future.first_index = indices.start
                    scheduled.extend(indices)
                    outstanding.add(future)
                    self.assertLessEqual(len(outstanding), 2 * workers)
                    return future

                def reverse_finish(pending, **kwargs):
                    self.assertEqual(kwargs, {'return_when': parallel.FIRST_COMPLETED})
                    self.assertEqual(set(pending), outstanding)
                    completed = max(pending, key=lambda f: f.first_index)
                    outstanding.remove(completed)
                    return {completed}, set(pending) - {completed}

                pool.submit.side_effect = submit
                with patch.object(parallel, 'wait', side_effect=reverse_finish):
                    result = parallel.run_npc_magic_simulation_parallel(source, workers=workers, batch_size=batch_size)
                self.assertEqual(result, NpcMagicSimulationResult(source, valid))
                self.assertIs(result.source_request, source)
                self.assertTrue(all(r.source_scenario is source.scenario for r in result.trials))
                self.assertEqual(scheduled, list(range(7)))
                self.assertEqual(factory.call_args.kwargs['max_workers'], workers)
                self.assertEqual(factory.call_args.kwargs['mp_context'].get_start_method(), 'spawn')
                factory.return_value.__exit__.assert_called_once()

    def test_default_batch_size_is_32_and_does_not_call_parent_factory(self):
        source, rng_factory = request(34), RecordingFactory()
        valid = records(source)
        with patch.object(parallel, 'ProcessPoolExecutor') as factory:
            pool = factory.return_value.__enter__.return_value

            def submit(fn, actual, indices, supplied_factory):
                future = Future()
                future.set_result(tuple(valid[i] for i in indices))
                return future

            pool.submit.side_effect = submit
            result = parallel.run_npc_magic_simulation_parallel(source, workers=1, rng_factory=rng_factory)
        self.assertEqual(tuple(c.args[2] for c in pool.submit.call_args_list), (range(32), range(32, 34)))
        self.assertTrue(all(c.args[3] is rng_factory for c in pool.submit.call_args_list))
        self.assertEqual(rng_factory.seeds, [])
        self.assertEqual(len(result.trials), 34)

    def test_enormous_uint64_input_materializes_only_bounded_initial_prefix(self):
        source = request(2**64-1)
        for batch_size, expected in ((3, (range(0, 3), range(3, 6), range(6, 9), range(9, 12))),
                                     (2**64-1, (range(2**64-1),))):
            waiting = []
            failure = RuntimeError('stop after bounded initial fill')
            with self.subTest(batch_size=batch_size), patch.object(parallel, 'ProcessPoolExecutor') as factory, \
                    patch.object(parallel, 'wait', side_effect=failure), \
                    patch.object(parallel, 'NpcMagicSimulationResult') as final:
                pool = factory.return_value.__enter__.return_value

                def submit(fn, actual, indices, rng_factory):
                    self.assertIs(actual, source)
                    self.assertIsInstance(indices, range)
                    future = Future()
                    waiting.append(future)
                    return future

                pool.submit.side_effect = submit
                with self.assertRaises(RuntimeError) as caught:
                    parallel.run_npc_magic_simulation_parallel(source, workers=2, batch_size=batch_size)
                self.assertIs(caught.exception, failure)
                self.assertEqual(tuple(c.args[2] for c in pool.submit.call_args_list), expected)
                self.assertTrue(all(f.cancelled() for f in waiting))
                final.assert_not_called()
                factory.return_value.__exit__.assert_called_once()

    def test_entire_done_group_is_validated_before_any_refill(self):
        source = request()
        valid = records(source)
        first, second = Future(), Future()
        first.set_result(valid[:1])
        second.set_result(valid[:1])  # Valid record, but assigned to range(1,2).
        with patch.object(parallel, 'ProcessPoolExecutor') as factory, \
                patch.object(parallel, 'wait', return_value=((first, second), set())), \
                patch.object(parallel, 'NpcMagicSimulationResult') as final:
            pool = factory.return_value.__enter__.return_value
            pool.submit.side_effect = (first, second)
            with self.assertRaises(ValueError):
                parallel.run_npc_magic_simulation_parallel(source, workers=1, batch_size=1)
            self.assertEqual(pool.submit.call_count, 2)
            final.assert_not_called()
            factory.return_value.__exit__.assert_called_once()

    def test_multidone_worker_failure_or_interrupt_never_refills_or_returns_partial(self):
        source = request()
        for failure in (RuntimeError('second done failed'), KeyboardInterrupt(), SystemExit()):
            first, second = Future(), Future()
            first.set_result(records(source)[:1])
            second.set_exception(failure)
            with self.subTest(error=type(failure)), patch.object(parallel, 'ProcessPoolExecutor') as factory, \
                    patch.object(parallel, 'wait', return_value=((first, second), set())), \
                    patch.object(parallel, 'NpcMagicSimulationResult') as final:
                pool = factory.return_value.__enter__.return_value
                pool.submit.side_effect = (first, second)
                with self.assertRaises(type(failure)) as caught:
                    parallel.run_npc_magic_simulation_parallel(source, workers=1, batch_size=1)
                self.assertIs(caught.exception, failure)
                self.assertEqual(pool.submit.call_count, 2)
                final.assert_not_called()
                factory.return_value.__exit__.assert_called_once()

    def test_submit_wait_result_and_normalization_failures_cancel_pending(self):
        source = request()
        for stage in ('initial_submit', 'wait', 'refill_submit', 'result', 'normalize'):
            waiting, completed = Future(), Future()
            failure = RuntimeError(stage)
            completed.set_exception(failure) if stage == 'result' else completed.set_result(records(source)[:1])
            with self.subTest(stage=stage), patch.object(parallel, 'ProcessPoolExecutor') as factory, \
                    patch.object(parallel, 'wait') as wait, \
                    patch.object(parallel, 'NpcMagicSimulationResult') as final, \
                    patch.object(parallel, '_normalize_batch', wraps=parallel._normalize_batch) as normalize:
                pool = factory.return_value.__enter__.return_value
                if stage == 'initial_submit': pool.submit.side_effect = (waiting, failure)
                elif stage == 'refill_submit': pool.submit.side_effect = (completed, waiting, failure)
                else: pool.submit.side_effect = (completed, waiting)
                if stage == 'wait': wait.side_effect = failure
                else: wait.return_value = ({completed}, {waiting})
                if stage == 'normalize': normalize.side_effect = failure
                with self.assertRaises(RuntimeError) as caught:
                    parallel.run_npc_magic_simulation_parallel(source, workers=1, batch_size=1)
                self.assertIs(caught.exception, failure)
                self.assertTrue(waiting.cancelled())
                final.assert_not_called()
                factory.return_value.__exit__.assert_called_once()

    def test_wait_baseexception_cancels_pending_without_note_or_retry(self):
        source = request()
        for failure in (KeyboardInterrupt('stop'), SystemExit('stop')):
            waiting = Future()
            with self.subTest(error=type(failure)), patch.object(parallel, 'ProcessPoolExecutor') as factory, \
                    patch.object(parallel, 'wait', side_effect=failure):
                pool = factory.return_value.__enter__.return_value
                pool.submit.return_value = waiting
                with self.assertRaises(type(failure)) as caught:
                    parallel.run_npc_magic_simulation_parallel(source, workers=1)
                self.assertIs(caught.exception, failure)
                self.assertTrue(waiting.cancelled())
                self.assertFalse(hasattr(failure, '__notes__'))
                self.assertEqual(pool.submit.call_count, 1)
                factory.return_value.__exit__.assert_called_once()

    def test_cancellation_errors_try_remaining_futures_and_preserve_original_context(self):
        source = request()
        original = RuntimeError('wait failed')
        first_error, second_error = ValueError('first cancellation failed'), OSError('second cancellation failed')
        futures = tuple(Mock(spec=Future) for _ in range(4))
        futures[0].cancel.side_effect = first_error
        futures[1].cancel.side_effect = second_error
        with patch.object(parallel, 'ProcessPoolExecutor') as factory, \
                patch.object(parallel, 'wait', side_effect=original), \
                patch.object(parallel, 'NpcMagicSimulationResult') as final:
            pool = factory.return_value.__enter__.return_value
            pool.submit.side_effect = futures
            with self.assertRaises(ValueError) as caught:
                parallel.run_npc_magic_simulation_parallel(source, workers=2, batch_size=1)
            self.assertIs(caught.exception, first_error)
            self.assertIs(caught.exception.__context__, original)
            self.assertTrue(any('second cancellation failed' in note for note in first_error.__notes__))
            self.assertTrue(all(f.cancel.call_count == 1 for f in futures))
            final.assert_not_called()
            factory.return_value.__exit__.assert_called_once()

    def test_pool_startup_and_enter_failures_propagate_without_trial_or_retry(self):
        source = request()
        for stage in ('construct', 'enter'):
            failure = RuntimeError(stage)
            with self.subTest(stage=stage), patch.object(parallel, 'ProcessPoolExecutor') as factory, \
                    patch.object(parallel, 'run_npc_magic_trial') as trial:
                if stage == 'construct': factory.side_effect = failure
                else: factory.return_value.__enter__.side_effect = failure
                with self.assertRaises(RuntimeError) as caught:
                    parallel.run_npc_magic_simulation_parallel(source, workers=1)
                self.assertIs(caught.exception, failure)
                factory.assert_called_once()
                trial.assert_not_called()
                factory.return_value.__exit__.assert_not_called()

    def test_final_result_constructor_failure_happens_after_pool_shutdown(self):
        source = request()
        completed = Future()
        completed.set_result(records(source))
        failure = ValueError('final result failed')

        def after_shutdown(*args):
            factory.return_value.__exit__.assert_called_once()
            raise failure

        with patch.object(parallel, 'ProcessPoolExecutor') as factory, \
                patch.object(parallel, 'NpcMagicSimulationResult', side_effect=after_shutdown) as final:
            pool = factory.return_value.__enter__.return_value
            pool.submit.return_value = completed
            with self.assertRaises(ValueError) as caught:
                parallel.run_npc_magic_simulation_parallel(source, workers=1)
            self.assertIs(caught.exception, failure)
            factory.return_value.__exit__.assert_called_once()
            final.assert_called_once_with(source, records(source))

    def test_pool_exit_error_is_not_retried_or_reported_as_completed_result(self):
        source = request()
        completed = Future()
        completed.set_result(records(source))
        failure = RuntimeError('shutdown failed')
        with patch.object(parallel, 'ProcessPoolExecutor') as factory, \
                patch.object(parallel, 'NpcMagicSimulationResult') as final:
            pool = factory.return_value.__enter__.return_value
            pool.submit.return_value = completed
            factory.return_value.__exit__.side_effect = failure
            with self.assertRaises(RuntimeError) as caught:
                parallel.run_npc_magic_simulation_parallel(source, workers=1)
            self.assertIs(caught.exception, failure)
            final.assert_not_called()
            self.assertEqual(pool.submit.call_count, 1)
            factory.return_value.__exit__.assert_called_once()
