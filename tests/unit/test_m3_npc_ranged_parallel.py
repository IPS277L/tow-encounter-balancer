from concurrent.futures import Future
from dataclasses import replace
from random import Random
import pickle
import unittest
from unittest.mock import Mock, patch

from tests.unit.test_m3_npc_ranged_simulation import observations, request
from towr.simulation import npc_ranged_parallel as parallel
from towr.simulation.npc_ranged_models import NpcRangedSimulationResult


class M3ParallelTests(unittest.TestCase):
    def test_invalid_options_and_unpicklable_factory_fail_before_pool(self):
        source = request()
        with patch.object(parallel, "ProcessPoolExecutor") as pool:
            for name in ("workers", "batch_size"):
                for value in (0, -1, True, 1.5, "2", None):
                    with self.subTest(name=name, value=value), self.assertRaises((TypeError, ValueError)):
                        parallel.run_npc_ranged_simulation_parallel(source, **{"workers": 2, name: value})
            with self.assertRaises(TypeError):
                parallel.run_npc_ranged_simulation_parallel(None, workers=2)
            with self.assertRaises(TypeError):
                parallel.run_npc_ranged_simulation_parallel(source, workers=2, rng_factory=None)
            with self.assertRaises((AttributeError, TypeError, pickle.PicklingError)):
                parallel.run_npc_ranged_simulation_parallel(source, workers=2, rng_factory=lambda seed: Random(seed))
            pool.assert_not_called()

    def test_bounded_queue_out_of_order_batches_and_uneven_tail(self):
        source = request()
        records = observations(source)
        for batch_size in (1, 3, 9):
            with self.subTest(batch_size=batch_size), patch.object(parallel, "ProcessPoolExecutor") as factory:
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
                    self.assertLessEqual(len(outstanding), 2)
                    return future
                def reverse_finish(pending, **kwargs):
                    completed = max(pending, key=lambda f: f.first)
                    outstanding.remove(completed)
                    return {completed}, pending - {completed}
                pool.submit.side_effect = submit
                with patch.object(parallel, "wait", side_effect=reverse_finish):
                    result = parallel.run_npc_ranged_simulation_parallel(source, workers=1, batch_size=batch_size)
                self.assertEqual(result, NpcRangedSimulationResult(source, records))
                self.assertEqual(scheduled, list(range(source.trials)))
                self.assertEqual(factory.call_args.kwargs["mp_context"].get_start_method(), "spawn")

    def test_worker_error_cancels_pending_and_exits_pool_without_result(self):
        source = request()
        failed, waiting = Future(), Future()
        failed.set_exception(RuntimeError("worker failed"))
        with patch.object(parallel, "ProcessPoolExecutor") as factory, patch.object(
            parallel, "wait", return_value=({failed}, {waiting})
        ), patch.object(parallel, "NpcRangedSimulationResult") as result:
            pool = factory.return_value.__enter__.return_value
            pool.submit.side_effect = (failed, waiting)
            with self.assertRaisesRegex(RuntimeError, "worker failed"):
                parallel.run_npc_ranged_simulation_parallel(source, workers=1, batch_size=1)
            self.assertTrue(waiting.cancelled())
            self.assertEqual(pool.submit.call_count, 2)
            factory.return_value.__exit__.assert_called_once()
            result.assert_not_called()

    def test_foreign_or_missing_worker_records_use_existing_result_guards(self):
        source = request()
        valid = observations(source)
        for invalid in (valid[:-1], (replace(valid[0], seed=0), *valid[1:]), (valid[0], *valid[:-1])):
            with self.subTest(records=invalid), patch.object(parallel, "ProcessPoolExecutor") as factory:
                future = Future()
                future.set_result(invalid)
                factory.return_value.__enter__.return_value.submit.return_value = future
                with self.assertRaises(ValueError):
                    parallel.run_npc_ranged_simulation_parallel(source, workers=1)

    def test_batch_uses_absolute_indices_and_stops_on_error_with_seed_note(self):
        source = request()
        factory = Mock()
        with patch.object(parallel, "run_npc_ranged_trial", side_effect=(observations(source)[1], ValueError("bad dice"))) as run:
            with self.assertRaisesRegex(ValueError, "bad dice") as caught:
                parallel._run_batch(source, range(1, 4), factory)
        self.assertEqual([call.args[1] for call in run.call_args_list], [1, 2])
        self.assertTrue(all(call.kwargs["rng_factory"] is factory for call in run.call_args_list))
        self.assertIn(f"index=2, seed={source.seed_for(2)}", caught.exception.__notes__[0])
