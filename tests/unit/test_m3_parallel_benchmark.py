from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.unit.test_m3_npc_ranged_simulation import observations, request
from tools import benchmark_m3_parallel as benchmark
from towr.simulation.npc_ranged_models import NpcRangedSimulationResult


class M3ParallelBenchmarkTests(unittest.TestCase):
    def test_compares_each_mode_and_repeat_and_rejects_changed_records(self):
        source = request()
        result = NpcRangedSimulationResult(source, observations(source))
        with patch.object(benchmark, "run_npc_ranged_simulation", return_value=result) as sequential, patch.object(
            benchmark, "run_npc_ranged_simulation_parallel", return_value=result
        ) as parallel:
            measured = benchmark.measure_comparison(source, workers=(1, 2), batch_size=3, repeats=2)
            self.assertEqual(sequential.call_count, 3)  # warm-up plus timed repeats
            self.assertEqual([call.kwargs["workers"] for call in parallel.call_args_list], [1, 2, 2, 1])
            self.assertEqual([len(times) for _, times in measured.timings], [2, 2, 2])
            self.assertEqual(measured.result, result)
            parallel.return_value = NpcRangedSimulationResult(source, (
                replace(result.trials[0], executed_attack_count=2), *result.trials[1:]))
            with self.assertRaisesRegex(ValueError, "records differ"):
                benchmark.measure_comparison(source, workers=(2,), batch_size=3, repeats=1)

    def test_invalid_benchmark_options_fail_before_execution(self):
        source = request()
        for change in ({"workers": ()}, {"workers": (1, 1)}, {"workers": (True,)},
                       {"batch_size": 0}, {"repeats": 0}):
            with self.subTest(change=change), patch.object(benchmark, "run_npc_ranged_simulation") as run:
                with self.assertRaises(ValueError):
                    benchmark.measure_comparison(source, **{"workers": (2,), "batch_size": 3, "repeats": 1, **change})
                run.assert_not_called()
