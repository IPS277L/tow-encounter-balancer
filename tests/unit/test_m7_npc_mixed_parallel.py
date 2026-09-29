from concurrent.futures import Future
from dataclasses import replace
from random import Random
import pickle
import unittest
from unittest.mock import Mock, patch

from tests.unit.test_m7_npc_mixed_simulation import observations, request
from tests.unit.test_m3_npc_ranged_simulation import request as ranged_request
from tests.unit.test_m6_npc_melee_simulation import request as melee_request
from towr.simulation import npc_mixed_parallel as parallel
from towr.simulation.npc_mixed_models import NpcMixedSimulationResult


class M7ParallelTests(unittest.TestCase):
    def test_invalid_options_and_unpicklable_factory_fail_before_pool(self):
        source = request()
        with patch.object(parallel, "ProcessPoolExecutor") as pool:
            for name in ("workers", "batch_size"):
                for value in (0, -1, True, False, 1.5, "2", None):
                    error = ValueError if type(value) is int else TypeError
                    with self.subTest(name=name, value=value), self.assertRaises(error):
                        parallel.run_npc_mixed_simulation_parallel(source, **{"workers": 2, name: value})
            with self.assertRaises(TypeError):
                parallel.run_npc_mixed_simulation_parallel(None, workers=2)
            with self.assertRaises(TypeError):
                parallel.run_npc_mixed_simulation_parallel(ranged_request(), workers=2)
            with self.assertRaises(TypeError):
                parallel.run_npc_mixed_simulation_parallel(melee_request(), workers=2)
            with self.assertRaises(TypeError):
                parallel.run_npc_mixed_simulation_parallel(source, workers=2, rng_factory=None)
            with self.assertRaises((AttributeError, TypeError, pickle.PicklingError)):
                parallel.run_npc_mixed_simulation_parallel(source, workers=2, rng_factory=lambda seed: Random(seed))
            pool.assert_not_called()

    def test_request_serialization_failure_precedes_pool(self):
        source = request()
        with patch.object(parallel.pickle, "dumps", side_effect=pickle.PicklingError("bad source")) as dump, patch.object(
            parallel, "ProcessPoolExecutor"
        ) as pool:
            with self.assertRaisesRegex(pickle.PicklingError, "bad source"):
                parallel.run_npc_mixed_simulation_parallel(source, workers=2)
            dump.assert_called_once_with((source, Random))
            pool.assert_not_called()

    def test_bounded_queue_out_of_order_batches_and_uneven_tail(self):
        source = request()
        records = observations(source)
        for workers, batch_size in ((1, 1), (1, 3), (2, 1), (2, 3), (2, 9)):
            with self.subTest(workers=workers, batch_size=batch_size), patch.object(parallel, "ProcessPoolExecutor") as factory:
                pool = factory.return_value.__enter__.return_value
                outstanding = set()
                scheduled = []
                def submit(fn, actual, indices, rng_factory):
                    self.assertIs(fn, parallel._run_batch)
                    self.assertIs(actual, source)
                    self.assertIs(rng_factory, Random)
                    future = Future()
                    future.set_result(tuple(records[i] for i in indices))
                    future.first = indices.start
                    scheduled.extend(indices)
                    outstanding.add(future)
                    self.assertLessEqual(len(outstanding), 2 * workers)
                    return future
                def reverse_finish(pending, **kwargs):
                    self.assertEqual(kwargs, {"return_when": parallel.FIRST_COMPLETED})
                    completed = max(pending, key=lambda f: f.first)
                    outstanding.remove(completed)
                    return {completed}, pending - {completed}
                pool.submit.side_effect = submit
                with patch.object(parallel, "wait", side_effect=reverse_finish):
                    result = parallel.run_npc_mixed_simulation_parallel(source, workers=workers, batch_size=batch_size)
                self.assertEqual(result, NpcMixedSimulationResult(source, records))
                self.assertIs(result.source_request, source)
                self.assertEqual(scheduled, list(range(source.trials)))
                self.assertEqual(factory.call_args.kwargs["max_workers"], workers)
                self.assertEqual(factory.call_args.kwargs["mp_context"].get_start_method(), "spawn")

    def test_worker_error_cancels_pending_and_exits_pool_without_result(self):
        source = request()
        failed, waiting = Future(), Future()
        failed.set_exception(RuntimeError("worker failed"))
        with patch.object(parallel, "ProcessPoolExecutor") as factory, patch.object(
            parallel, "wait", return_value=({failed}, {waiting})
        ), patch.object(parallel, "NpcMixedSimulationResult") as result:
            pool = factory.return_value.__enter__.return_value
            pool.submit.side_effect = (failed, waiting)
            with self.assertRaisesRegex(RuntimeError, "worker failed"):
                parallel.run_npc_mixed_simulation_parallel(source, workers=1, batch_size=1)
            self.assertTrue(waiting.cancelled())
            self.assertEqual(pool.submit.call_count, 2)
            factory.return_value.__exit__.assert_called_once()
            result.assert_not_called()

    def test_submission_and_wait_failures_cancel_outstanding_without_result(self):
        source = request()
        for stage in ("initial_submit", "wait", "refill_submit"):
            with self.subTest(stage=stage), patch.object(parallel, "ProcessPoolExecutor") as factory, patch.object(
                parallel, "wait"
            ) as wait, patch.object(parallel, "NpcMixedSimulationResult") as result:
                waiting, completed = Future(), Future()
                completed.set_result(observations(source)[:1])
                error = RuntimeError(stage)
                pool = factory.return_value.__enter__.return_value
                if stage == "initial_submit":
                    pool.submit.side_effect = (waiting, error)
                elif stage == "wait":
                    pool.submit.side_effect = (completed, waiting)
                    wait.side_effect = error
                else:
                    pool.submit.side_effect = (completed, waiting, error)
                    wait.return_value = ({completed}, {waiting})
                with self.assertRaisesRegex(RuntimeError, stage) as caught:
                    parallel.run_npc_mixed_simulation_parallel(source, workers=1, batch_size=1)
                self.assertIs(caught.exception, error)
                self.assertTrue(waiting.cancelled())
                factory.return_value.__exit__.assert_called_once()
                result.assert_not_called()

    def test_foreign_or_missing_worker_records_use_existing_result_guards(self):
        source = request()
        valid = observations(source)
        for invalid in (valid[:-1], (replace(valid[0], seed=0), *valid[1:]), (valid[0], *valid[:-1]),
                        (replace(valid[0], executed_attack_count=4), *valid[1:]),
                        (replace(valid[0], visited_round_count=2), *valid[1:]), (None, *valid[1:])):
            with self.subTest(records=invalid), patch.object(parallel, "ProcessPoolExecutor") as factory:
                future = Future()
                future.set_result(invalid)
                factory.return_value.__enter__.return_value.submit.return_value = future
                with self.assertRaises((TypeError, ValueError)):
                    parallel.run_npc_mixed_simulation_parallel(source, workers=1)
                factory.return_value.__exit__.assert_called_once()

    def test_batch_uses_absolute_indices_and_stops_on_error_with_seed_note(self):
        source = request()
        factory = Mock()
        with patch.object(parallel, "run_npc_mixed_trial", side_effect=(observations(source)[1], ValueError("bad dice"))) as run:
            with self.assertRaisesRegex(ValueError, "bad dice") as caught:
                parallel._run_batch(source, range(1, 4), factory)
        self.assertEqual([call.args[1] for call in run.call_args_list], [1, 2])
        self.assertTrue(all(call.args[0] is source for call in run.call_args_list))
        self.assertTrue(all(call.kwargs["rng_factory"] is factory for call in run.call_args_list))
        self.assertIn(f"index=2, seed={source.seed_for(2)}", caught.exception.__notes__[0])

    def test_batch_returns_only_compact_records_and_does_not_wrap_base_exceptions(self):
        source = request()
        records = observations(source)
        with patch.object(parallel, "run_npc_mixed_trial", side_effect=records[1:]) as run:
            self.assertEqual(parallel._run_batch(source, range(1, 4), Random), records[1:])
            self.assertEqual([call.args[1] for call in run.call_args_list], [1, 2, 3])
        for error in (KeyboardInterrupt(), SystemExit()):
            with self.subTest(error=type(error)), patch.object(parallel, "run_npc_mixed_trial", side_effect=error) as run:
                with self.assertRaises(type(error)) as caught:
                    parallel._run_batch(source, range(1, 4), Random)
                self.assertIs(caught.exception, error)
                self.assertFalse(hasattr(error, "__notes__"))
                self.assertEqual(run.call_count, 1)

    def test_enormous_request_schedules_only_bounded_prefix_before_failure(self):
        source = request(trials=2**64 - 1)
        waiting = []
        with patch.object(parallel, "ProcessPoolExecutor") as factory, \
             patch.object(parallel, "wait", side_effect=RuntimeError("stop after initial fill")), \
             patch.object(parallel, "NpcMixedSimulationResult") as result:
            pool = factory.return_value.__enter__.return_value
            def submit(fn, actual, indices, rng_factory):
                self.assertIs(actual, source)
                self.assertIsInstance(indices, range)
                waiting.append(Future())
                return waiting[-1]
            pool.submit.side_effect = submit
            with self.assertRaisesRegex(RuntimeError, "stop after initial fill"):
                parallel.run_npc_mixed_simulation_parallel(source, workers=2, batch_size=3)
            self.assertEqual([tuple(c.args[2]) for c in pool.submit.call_args_list],
                             [tuple(range(i, i + 3)) for i in (0, 3, 6, 9)])
            self.assertTrue(all(f.cancelled() for f in waiting))
            result.assert_not_called()
            factory.return_value.__exit__.assert_called_once()

    def test_all_done_results_are_read_before_refill_and_interrupts_close_pool(self):
        source = request()
        for error in (RuntimeError("second done failed"), KeyboardInterrupt(), SystemExit()):
            first, failed = Future(), Future()
            first.set_result(observations(source)[:1])
            failed.set_exception(error)
            with self.subTest(error=type(error)), patch.object(parallel, "ProcessPoolExecutor") as factory, \
                 patch.object(parallel, "wait", return_value=((first, failed), set())), \
                 patch.object(parallel, "NpcMixedSimulationResult") as result:
                pool = factory.return_value.__enter__.return_value
                pool.submit.side_effect = (first, failed)
                with self.assertRaises(type(error)) as caught:
                    parallel.run_npc_mixed_simulation_parallel(source, workers=1, batch_size=1)
                self.assertIs(caught.exception, error)
                self.assertEqual(pool.submit.call_count, 2)
                result.assert_not_called()
                factory.return_value.__exit__.assert_called_once()
        waiting = Future()
        with patch.object(parallel, "ProcessPoolExecutor") as factory, \
             patch.object(parallel, "wait", side_effect=KeyboardInterrupt()):
            factory.return_value.__enter__.return_value.submit.return_value = waiting
            with self.assertRaises(KeyboardInterrupt):
                parallel.run_npc_mixed_simulation_parallel(source, workers=1, batch_size=8)
            self.assertTrue(waiting.cancelled())
            factory.return_value.__exit__.assert_called_once()

    def test_pool_start_and_final_constructor_failures_propagate_without_retry(self):
        source = request()
        error = RuntimeError("pool startup")
        with patch.object(parallel, "ProcessPoolExecutor", side_effect=error) as factory, \
             patch.object(parallel, "run_npc_mixed_trial") as trial:
            with self.assertRaises(RuntimeError) as caught:
                parallel.run_npc_mixed_simulation_parallel(source, workers=1)
            self.assertIs(caught.exception, error)
            factory.assert_called_once()
            trial.assert_not_called()
        done = Future()
        done.set_result(observations(source))
        error = ValueError("final constructor")
        with patch.object(parallel, "ProcessPoolExecutor") as factory, \
             patch.object(parallel, "NpcMixedSimulationResult", side_effect=error) as result:
            factory.return_value.__enter__.return_value.submit.return_value = done
            with self.assertRaises(ValueError) as caught:
                parallel.run_npc_mixed_simulation_parallel(source, workers=1)
            self.assertIs(caught.exception, error)
            factory.return_value.__exit__.assert_called_once()
            result.assert_called_once_with(source, observations(source))
