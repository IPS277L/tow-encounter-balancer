from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tests.unit.test_m7_npc_mixed_simulation import observations, request
from tools import benchmark_m7_parallel as benchmark
from towr.simulation.npc_mixed_models import NpcMixedSimulationResult
from towr.simulation.npc_mixed_summary import summarize_npc_mixed_simulation as summarize


class M7ParallelBenchmarkTests(unittest.TestCase):
    def test_all_modes_repeats_summary_and_alternating_order(self):
        source = request()
        result = NpcMixedSimulationResult(source, observations(source))
        order = []
        def sequential(actual):
            order.append(0)
            return result
        def parallel(actual, *, workers, batch_size):
            self.assertIs(actual, source)
            self.assertEqual(batch_size, 3)
            order.append(workers)
            return result
        with patch.object(benchmark, "run_npc_mixed_simulation", side_effect=sequential) as run, patch.object(
            benchmark, "run_npc_mixed_simulation_parallel", side_effect=parallel
        ), patch.object(benchmark, "summarize_npc_mixed_simulation", wraps=summarize) as projection:
            measured = benchmark.measure_comparison(source, workers=(1, 2), batch_size=3, repeats=2)
        self.assertEqual(order, [0, 0, 1, 2, 2, 1, 0])  # warm-up then alternating modes
        self.assertEqual(run.call_args_list[0].args[0], replace(source, trials=3))
        self.assertEqual(projection.call_count, 6)
        self.assertEqual([len(times) for _, times in measured.timings], [2, 2, 2])
        self.assertEqual(measured.result, result)
        self.assertEqual(measured.summary, summarize(result))

    def test_changed_records_fail_even_when_aggregates_match(self):
        source = request()
        result = NpcMixedSimulationResult(source, observations(source))
        records = result.trials
        changed = NpcMixedSimulationResult(source, (
            replace(records[0], executed_attack_count=2),
            replace(records[1], executed_attack_count=1), *records[2:]))
        self.assertEqual(summarize(changed), summarize(result))
        with patch.object(benchmark, "run_npc_mixed_simulation", return_value=result), patch.object(
            benchmark, "run_npc_mixed_simulation_parallel", return_value=changed
        ):
            with self.assertRaisesRegex(ValueError, "records or summaries differ"):
                benchmark.measure_comparison(source, workers=(2,), batch_size=3, repeats=1)

    def test_changed_summary_or_foreign_source_is_rejected(self):
        source = request()
        result = NpcMixedSimulationResult(source, observations(source))
        summary = summarize(result)
        with patch.object(benchmark, "run_npc_mixed_simulation", return_value=result), patch.object(
            benchmark, "run_npc_mixed_simulation_parallel", return_value=result
        ), patch.object(benchmark, "summarize_npc_mixed_simulation", side_effect=(
            summary, replace(summary, total_attack_count=summary.total_attack_count + 1)
        )):
            with self.assertRaisesRegex(ValueError, "records or summaries differ"):
                benchmark.measure_comparison(source, workers=(2,), batch_size=3, repeats=1)
        with patch.object(benchmark, "run_npc_mixed_simulation", return_value=result), patch.object(
            benchmark, "run_npc_mixed_simulation_parallel", return_value=replace(result, source_request=replace(source))
        ):
            with self.assertRaisesRegex(ValueError, "exact source"):
                benchmark.measure_comparison(source, workers=(2,), batch_size=3, repeats=1)

    def test_invalid_options_and_instrumented_runtime_fail_before_execution(self):
        source = request()
        for changes in ({"workers": ()}, {"workers": (1, 1)}, {"workers": (True,)}, {"workers": (-1,)},
                        {"batch_size": 0}, {"batch_size": "2"}, {"repeats": False}, {"repeats": 1.5}):
            with self.subTest(changes=changes), patch.object(benchmark, "run_npc_mixed_simulation") as run:
                with self.assertRaises(ValueError):
                    benchmark.measure_comparison(source, **{"workers": (2,), "batch_size": 3, "repeats": 1, **changes})
                run.assert_not_called()
        with patch.object(benchmark, "run_npc_mixed_simulation") as run:
            with self.assertRaises(TypeError):
                benchmark.measure_comparison(None, workers=(2,), batch_size=3, repeats=1)
            for module, name in ((benchmark.sys, "getprofile"), (benchmark.tracemalloc, "is_tracing")):
                with patch.object(module, name, return_value=True), self.assertRaises(RuntimeError):
                    benchmark.measure_comparison(source, workers=(2,), batch_size=3, repeats=1)
            run.assert_not_called()

    def test_digest_covers_sources_and_both_harnesses_including_untracked_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "tools").mkdir()
            paths = (root / "src" / "new.py", root / "tools" / "profile_m7.py",
                     root / "tools" / "benchmark_m7_parallel.py")
            for path in paths:
                path.write_text("original", encoding="utf-8")
            previous = benchmark.source_digest(root)
            for path in paths:
                path.write_text("changed", encoding="utf-8")
                current = benchmark.source_digest(root)
                self.assertNotEqual(current, previous)
                previous = current
            (root / "src" / "new.pyc").write_bytes(b"ignored")
            self.assertEqual(benchmark.source_digest(root), previous)
            (root / "src" / "untracked.py").write_text("new", encoding="utf-8")
            self.assertNotEqual(benchmark.source_digest(root), previous)

    @patch.object(benchmark.platform, "platform", lambda: "test platform")
    @patch.object(benchmark.platform, "processor", lambda: "test processor")
    def test_report_and_source_change_failure_preserve_existing_output(self):
        source = request()
        result = NpcMixedSimulationResult(source, observations(source))
        measured = benchmark.WallComparison(result, summarize(result), ((0, (1.0,)), (1, (2.0,))))
        with TemporaryDirectory() as directory:
            output = Path(directory) / "report.md"
            argv = ["benchmark", "--trials", "4", "--workers", "1", "--repeats", "1", "--output", str(output)]
            with patch.object(benchmark.sys, "argv", argv), patch.object(benchmark, "measure_comparison", return_value=measured), patch.object(
                benchmark, "source_digest", return_value="same hash"
            ) as digest, patch.object(benchmark.subprocess, "check_output", side_effect=("revision", "")), patch("builtins.print"):
                benchmark.main()
                self.assertEqual(digest.call_count, 2)
            report = output.read_text(encoding="utf-8")
            for expected in ("same hash", "revision", "spawn, workers=1", "0.500", "Summary projection is inside",
                             "not measured", benchmark.trial_digest(result)):
                self.assertIn(expected, report)
            with patch.object(benchmark.sys, "argv", argv), patch.object(benchmark, "measure_comparison", return_value=measured), patch.object(
                benchmark, "source_digest", side_effect=("before", "after")
            ), patch.object(benchmark.subprocess, "check_output", side_effect=("revision", "")), patch("builtins.print"):
                with self.assertRaisesRegex(RuntimeError, "source files changed"):
                    benchmark.main()
            self.assertEqual(output.read_text(encoding="utf-8"), report)
