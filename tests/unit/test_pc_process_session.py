"""Deterministic scheduling and lifecycle tests, without starting processes."""
from contextlib import contextmanager
from dataclasses import replace
from threading import Event
import unittest
from unittest.mock import Mock, patch

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_process import PcMeleeProcessSession, PcMeleeSimulationCancelled
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation


MODULE = 'towr.simulation.pc_melee_process'


class FakeFuture:
    def __init__(self, request, indices, records, transform):
        self.request = request
        self.indices = indices
        self.records = records
        self.transform = transform
        self.delivered = False
        self.cancelled = False

    def result(self):
        return self.transform(self.records) if self.transform else self.records

    def cancel(self):
        self.cancelled = True
        return True


class FakePool:
    def __init__(self, results, transform=None):
        self.results = results
        self.transform = transform
        self.futures = []
        self.maximum_in_flight = 0
        self.shutdown_calls = []
        self.wait_sizes = []

    def submit(self, function, request, indices, rng_factory):
        records = tuple(self.results[request].records[index] for index in indices)
        future = FakeFuture(request, indices, records, self.transform)
        self.futures.append(future)
        self.maximum_in_flight = max(self.maximum_in_flight,
            sum(not item.delivered and not item.cancelled for item in self.futures))
        return future

    def wait_reverse(self, pending, **kwargs):
        self.wait_sizes.append(len(pending))
        # Return exactly one completed batch so arrival order is reproducible.
        done = max(pending, key=lambda future: future.indices.start)
        done.delivered = True
        return {done}, set(pending) - {done}

    def shutdown(self, *, wait, cancel_futures):
        self.shutdown_calls.append((wait, cancel_futures))


class PcMeleeProcessSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = PcMeleeSimulationRequest(make_pc_melee_scenario(max_rounds=1), 42, 7)
        cls.reference = run_pc_melee_simulation(cls.request)
        cls.other_request = PcMeleeSimulationRequest(
            replace(cls.request.scenario, id='another-candidate'), 73, 2)
        cls.other_reference = run_pc_melee_simulation(cls.other_request)

    @contextmanager
    def backend(self, *, transform=None):
        signal = Event()
        context = Mock()
        context.Event.return_value = signal
        pool = FakePool({self.request: self.reference,
            self.other_request: self.other_reference}, transform)
        with patch(MODULE + '.get_context', return_value=context) as get_context, patch(
                MODULE + '.ProcessPoolExecutor', return_value=pool) as factory, patch(
                MODULE + '.wait', side_effect=pool.wait_reverse):
            yield pool, signal, factory, context, get_context

    def test_bounded_reverse_arrival_progress_once_and_sorted_final_records(self):
        seen = []
        with self.backend() as (pool, signal, factory, context, get_context):
            with PcMeleeProcessSession(workers=2) as session:
                result = session.run(self.request, on_trial_complete=seen.append)
                self.assertEqual(result, self.reference)
                self.assertEqual(pool.maximum_in_flight, 4)
                self.assertEqual(pool.wait_sizes[0], 4)
                self.assertEqual([record.trial_index for record in seen], [3, 4, 5, 6, 2, 1, 0])
                self.assertEqual(set(seen), set(self.reference.records))
                self.assertEqual(len(seen), self.request.trials)
                self.assertEqual(tuple(record.trial_index for record in result.records), tuple(range(7)))
                self.assertFalse(signal.is_set())
            self.assertEqual(pool.shutdown_calls, [(True, True)])
            get_context.assert_called_once_with('spawn')
            context.Event.assert_called_once_with()
            self.assertEqual(factory.call_args.kwargs['max_workers'], 2)
            self.assertEqual(factory.call_args.kwargs['initargs'], (signal,))

    def test_same_pool_serves_distinct_candidates_and_close_is_idempotent(self):
        with self.backend() as (pool, signal, factory, context, _):
            session = PcMeleeProcessSession(workers=2, batch_size=2)
            with session:
                self.assertEqual(session.run(self.request), self.reference)
                self.assertEqual(session.run(self.other_request), self.other_reference)
                self.assertEqual(pool.shutdown_calls, [])
                factory.assert_called_once()
                context.Event.assert_called_once()
                self.assertFalse(signal.is_set())
            session.close()
            self.assertEqual(pool.shutdown_calls, [(True, True)])
            self.assertEqual(len(pool.futures), 5)
            with self.assertRaises(RuntimeError):
                session.run(self.request)

    def test_bad_batch_is_rejected_before_any_progress(self):
        # One worker and two batches: index2 is delivered first. Corrupt its
        # second record as well, proving the whole batch is admitted first.
        cases = {
            'missing': lambda rows: rows[:-1],
            'extra': lambda rows: rows + rows[:1],
            'list': lambda rows: list(rows),
            'untyped': lambda rows: (rows[0], object()),
            'duplicate': lambda rows: (rows[0], rows[0]),
            'foreign_index': lambda rows: (rows[0], replace(rows[1], trial_index=0)),
            'foreign_seed': lambda rows: (rows[0], replace(rows[1], seed=rows[1].seed ^ 1)),
            'foreign_source': lambda rows: (rows[0], replace(rows[1],
                source_scenario=replace(rows[1].source_scenario, id='foreign'))),
        }
        for name, transform in cases.items():
            with self.subTest(name=name), self.backend(transform=transform) as (pool, signal, _, _, _):
                seen = []
                session = PcMeleeProcessSession(workers=1, batch_size=2)
                with self.assertRaises((TypeError, ValueError)):
                    session.run(self.request, on_trial_complete=seen.append)
                self.assertEqual(seen, [])
                self.assertTrue(signal.is_set())
                self.assertEqual(pool.shutdown_calls, [(True, True)])
                self.assertTrue(all(future.cancelled for future in pool.futures if not future.delivered))
                with self.assertRaises(RuntimeError):
                    session.run(self.request)

    def test_worker_failure_preserves_error_cancels_pending_and_closes(self):
        failure = RuntimeError('worker failed')
        def fail(rows):
            raise failure
        with self.backend(transform=fail) as (pool, signal, _, _, _):
            seen = []
            session = PcMeleeProcessSession(workers=2)
            with self.assertRaises(RuntimeError) as caught:
                session.run(self.request, on_trial_complete=seen.append)
            self.assertIs(caught.exception, failure)
            self.assertEqual(seen, [])
            self.assertTrue(signal.is_set())
            self.assertEqual(len(pool.futures), 4)
            self.assertTrue(all(future.cancelled for future in pool.futures if not future.delivered))
            self.assertEqual(pool.shutdown_calls, [(True, True)])

    def test_observer_failure_preserves_error_and_never_refills_pool(self):
        failure = RuntimeError('observer failed')
        seen = []
        def observe(record):
            seen.append(record)
            raise failure
        with self.backend() as (pool, signal, _, _, _):
            session = PcMeleeProcessSession(workers=2)
            with self.assertRaises(RuntimeError) as caught:
                session.run(self.request, on_trial_complete=observe)
            self.assertIs(caught.exception, failure)
            self.assertEqual(len(seen), 1)
            self.assertEqual(len(pool.futures), 4)
            self.assertTrue(signal.is_set())
            self.assertTrue(all(future.cancelled for future in pool.futures if not future.delivered))
            self.assertEqual(pool.shutdown_calls, [(True, True)])

    def test_precancel_avoids_pickle_and_pool_startup(self):
        with self.backend() as (pool, _, factory, context, _), patch(MODULE + '.pickle.dumps') as serialize:
            session = PcMeleeProcessSession(workers=2, cancel_requested=lambda: True)
            with self.assertRaises(PcMeleeSimulationCancelled):
                session.run(self.request)
            serialize.assert_not_called()
            factory.assert_not_called()
            context.Event.assert_not_called()
            self.assertEqual(pool.futures, [])

    def test_cancel_before_second_candidate_closes_existing_pool_before_pickle(self):
        cancel = Event()
        with self.backend() as (pool, signal, _, _, _):
            session = PcMeleeProcessSession(workers=2, cancel_requested=cancel.is_set)
            self.assertEqual(session.run(self.request), self.reference)
            cancel.set()
            with patch(MODULE + '.pickle.dumps') as serialize:
                with self.assertRaises(PcMeleeSimulationCancelled):
                    session.run(self.other_request)
                serialize.assert_not_called()
            self.assertTrue(signal.is_set())
            self.assertEqual(pool.shutdown_calls, [(True, True)])

    def test_invalid_source_and_callbacks_fail_before_pickle_or_startup(self):
        invalid = object.__new__(PcMeleeSimulationRequest)
        for name, value in (('scenario', self.request.scenario), ('master_seed', 42), ('trials', 0)):
            object.__setattr__(invalid, name, value)
        cases = ((object(), {}), (invalid, {}),
            (self.request, dict(rng_factory=object())),
            (self.request, dict(on_trial_complete=object())))
        for request, options in cases:
            with self.subTest(options=options, request_type=type(request)), self.backend() as (
                    _, _, factory, context, _), patch(MODULE + '.pickle.dumps') as serialize:
                with self.assertRaises((TypeError, ValueError)):
                    PcMeleeProcessSession(workers=2).run(request, **options)
                serialize.assert_not_called()
                factory.assert_not_called()
                context.Event.assert_not_called()


if __name__ == '__main__':
    unittest.main()
