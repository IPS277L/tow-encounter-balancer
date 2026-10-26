"""Deterministic M8 comparison checks; no speed or timing thresholds."""
from contextlib import ExitStack, redirect_stdout
import cProfile
from dataclasses import replace
from hashlib import sha256
from io import StringIO
from pathlib import Path
from random import getstate, random, setstate
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.unit.test_m8_profiling import swapped_records
from tools import benchmark_m8_parallel as benchmark
from tools import profile_m8
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome
from towr.simulation.npc_magic_models import NpcMagicSimulationResult, NpcMagicTrialRecord
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation as summarize


def source(trials=5):
    return benchmark.benchmark_request('missing-departure', trials=trials, master_seed=42, round_budget=4)


def observations(request):
    return NpcMagicSimulationResult(request, tuple(
        NpcMagicTrialRecord(request.scenario, i, request.seed_for(i), Outcome.UNSUPPORTED_PATH, 0, 1, 0)
        for i in range(request.trials)))


def measured(request):
    result = observations(request)
    return benchmark.WallComparison(result, summarize(result), ((0, (1.0, 3.0, 2.0)),
                                                               (1, (4.0, 5.0, 6.0)),
                                                               (2, (0.5, 1.0, 1.5))))


class M8ParallelBenchmarkTests(unittest.TestCase):
    def test_three_repeats_alternate_modes_with_bounded_parent_warmup(self):
        for trials in (2, 5):
            request = source(trials)
            order, sequential_sources = [], []

            def sequential(actual):
                order.append(0)
                sequential_sources.append(actual)
                return observations(actual)

            def parallel(actual, *, workers, batch_size):
                self.assertIs(actual, request)
                self.assertEqual(batch_size, 32)
                order.append(workers)
                return observations(actual)

            with self.subTest(trials=trials), \
                    patch.object(benchmark, 'run_npc_magic_simulation', side_effect=sequential), \
                    patch.object(benchmark, 'run_npc_magic_simulation_parallel', side_effect=parallel), \
                    patch.object(benchmark, 'summarize_npc_magic_simulation', wraps=summarize) as projection:
                result = benchmark.measure_comparison(request, workers=(1, 2), batch_size=32, repeats=3)
            self.assertEqual(order, [0, 0, 1, 2, 2, 1, 0, 0, 1, 2])
            self.assertEqual(sequential_sources[0], replace(request, trials=min(3, trials)))
            self.assertIsNot(sequential_sources[0], request)
            self.assertTrue(all(item is request for item in sequential_sources[1:]))
            self.assertEqual(projection.call_count, 10)  # warm-up and nine full measured projections
            self.assertEqual(tuple((mode, len(times)) for mode, times in result.timings), ((0, 3), (1, 3), (2, 3)))
            self.assertEqual((result.result, result.summary), (observations(request), summarize(observations(request))))

    def test_runner_and_summary_are_inside_timer_and_collection_is_outside(self):
        request = source(2)
        running = False
        timed = []

        def clock():
            nonlocal running
            running = not running
            return 0.0 if running else 1.0

        def run(actual):
            timed.append(('run', running))
            return observations(actual)

        def project(result):
            timed.append(('summary', running))
            return summarize(result)

        def collect():
            self.assertFalse(running)

        with patch.object(benchmark, 'perf_counter', side_effect=clock) as counter, \
                patch.object(benchmark.gc, 'collect', side_effect=collect) as collection, \
                patch.object(benchmark, 'run_npc_magic_simulation', side_effect=run), \
                patch.object(benchmark, 'run_npc_magic_simulation_parallel', side_effect=lambda actual, **_: run(actual)), \
                patch.object(benchmark, 'summarize_npc_magic_simulation', side_effect=project):
            result = benchmark.measure_comparison(request, workers=(1,), batch_size=32, repeats=1)
        self.assertEqual(timed, [('run', False), ('summary', False), ('run', True), ('summary', True),
                                 ('run', True), ('summary', True)])
        self.assertEqual(counter.call_count, 4)
        self.assertEqual(collection.call_count, 2)
        self.assertEqual(result.timings, ((0, (1.0,)), (1, (1.0,))))

    def test_changed_indexed_records_are_rejected_even_with_equal_summary(self):
        same, changed = swapped_records()
        request = same[0].source_request
        self.assertEqual(same[1], changed[1])
        with patch.object(benchmark, 'run_npc_magic_simulation', side_effect=lambda actual: replace(same[0], source_request=actual)), \
                patch.object(benchmark, 'run_npc_magic_simulation_parallel', return_value=changed[0]):
            with self.assertRaisesRegex(ValueError, 'records or summaries differ'):
                benchmark.measure_comparison(request, workers=(1,), batch_size=32, repeats=1)

    def test_changed_summary_is_rejected_with_equal_records(self):
        request = source(2)
        result = observations(request)
        calls = 0

        def projection(actual):
            nonlocal calls
            calls += 1
            value = summarize(actual)
            return replace(value, total_action_count=1) if calls == 3 else value

        with patch.object(benchmark, 'run_npc_magic_simulation', side_effect=observations), \
                patch.object(benchmark, 'run_npc_magic_simulation_parallel', return_value=result), \
                patch.object(benchmark, 'summarize_npc_magic_simulation', side_effect=projection):
            with self.assertRaisesRegex(ValueError, 'records or summaries differ'):
                benchmark.measure_comparison(request, workers=(1,), batch_size=32, repeats=1)

    def test_equal_copies_of_result_summary_or_record_sources_are_rejected(self):
        request = source(2)
        result = observations(request)
        for field in ('result', 'summary', 'record'):
            foreign = replace(request)
            changed = (replace(result, source_request=foreign) if field == 'result' else
                       replace(result, trials=tuple(replace(t, source_scenario=replace(request.scenario))
                                                    for t in result.trials)) if field == 'record' else result)

            def projection(actual):
                value = summarize(actual)
                return replace(value, source_request=foreign) if field == 'summary' and actual is result else value

            with self.subTest(field=field), \
                    patch.object(benchmark, 'run_npc_magic_simulation', side_effect=observations), \
                    patch.object(benchmark, 'run_npc_magic_simulation_parallel', return_value=changed), \
                    patch.object(benchmark, 'summarize_npc_magic_simulation', side_effect=projection):
                with self.assertRaisesRegex(ValueError, 'exact parent source'):
                    benchmark.measure_comparison(request, workers=(1,), batch_size=32, repeats=1)

    def test_input_and_global_rng_mutations_during_warmup_or_measured_run_are_rejected(self):
        for stage in ('warmup', 'measured'):
            for mutation in ('input', 'global RNG'):
                request = source(2)
                seed, rng = request.master_seed, getstate()
                calls = 0

                def run(actual):
                    nonlocal calls
                    calls += 1
                    result = observations(actual)
                    if calls == (1 if stage == 'warmup' else 2):
                        if mutation == 'input': object.__setattr__(request, 'master_seed', seed + 1)
                        else: random()
                    return result

                try:
                    with self.subTest(stage=stage, mutation=mutation), \
                            patch.object(benchmark, 'run_npc_magic_simulation', side_effect=run), \
                            patch.object(benchmark, 'run_npc_magic_simulation_parallel') as parallel:
                        with self.assertRaisesRegex(ValueError, 'input or global RNG'):
                            benchmark.measure_comparison(request, workers=(1,), batch_size=32, repeats=1)
                        parallel.assert_not_called()
                finally:
                    object.__setattr__(request, 'master_seed', seed)
                    setstate(rng)

    def test_changed_active_children_are_rejected_after_warmup_or_measured_call(self):
        request = source(2)
        child = SimpleNamespace(pid=100)
        for children in (([], [child]), ([], [], [child])):
            with self.subTest(phase=len(children)), \
                    patch.object(benchmark, 'active_children', side_effect=children), \
                    patch.object(benchmark, 'run_npc_magic_simulation', side_effect=observations), \
                    patch.object(benchmark, 'run_npc_magic_simulation_parallel') as parallel:
                with self.assertRaisesRegex(ValueError, 'active children'):
                    benchmark.measure_comparison(request, workers=(1,), batch_size=32, repeats=1)
                parallel.assert_not_called()

    def test_invalid_options_fail_before_warmup_or_pool(self):
        request = source(2)
        options = {'workers': (1, 2), 'batch_size': 32, 'repeats': 3}
        cases = (({'workers': [1]}, TypeError), ({'workers': (True,)}, TypeError),
                 ({'workers': (1.0,)}, TypeError), ({'workers': ('1',)}, TypeError),
                 ({'batch_size': False}, TypeError), ({'repeats': 1.0}, TypeError),
                 ({'workers': ()}, ValueError), ({'workers': (1, 1)}, ValueError),
                 ({'workers': (0,)}, ValueError), ({'workers': (-1,)}, ValueError),
                 ({'batch_size': 0}, ValueError), ({'repeats': -1}, ValueError))
        with patch.object(benchmark, 'run_npc_magic_simulation') as run, \
                patch.object(benchmark, 'run_npc_magic_simulation_parallel') as parallel:
            for changes, exception in cases:
                with self.subTest(changes=changes), self.assertRaises(exception):
                    benchmark.measure_comparison(request, **{**options, **changes})
            for value in (None, {}, request.scenario):
                with self.subTest(request=type(value)), self.assertRaises(TypeError):
                    benchmark.measure_comparison(value, **options)
            run.assert_not_called()
            parallel.assert_not_called()

    def test_active_tracing_profiling_and_monitoring_slot_rejected_before_warmup(self):
        request = source(2)
        checks = ((profile_m8.tracemalloc, 'is_tracing', True), (profile_m8.sys, 'getprofile', object()),
                  (profile_m8.sys.monitoring, 'get_tool', 'existing profiler'))
        for module, name, value in checks:
            with self.subTest(name=name), patch.object(module, name, return_value=value), \
                    patch.object(benchmark, 'run_npc_magic_simulation') as run:
                with self.assertRaisesRegex(RuntimeError, 'no active tracemalloc/profiler'):
                    benchmark.measure_comparison(request, workers=(1,), batch_size=32, repeats=1)
                run.assert_not_called()

    def test_callers_real_cprofile_remains_active_after_rejection(self):
        def inside():
            with patch.object(benchmark, 'run_npc_magic_simulation') as run:
                with self.assertRaises(RuntimeError):
                    benchmark.measure_comparison(source(2), workers=(1,), batch_size=32, repeats=1)
                run.assert_not_called()
            monitoring = profile_m8.sys.monitoring
            self.assertTrue(profile_m8.sys.getprofile() is not None or
                            monitoring.get_tool(monitoring.PROFILER_ID) is not None)
        cProfile.Profile().runcall(inside)

    def test_runner_and_projection_failures_keep_original_exception_without_next_mode(self):
        for phase in ('warmup', 'sequential', 'parallel', 'summary'):
            request = source(2)
            failure = RuntimeError('comparison failed')
            calls = []

            def sequential(actual):
                calls.append('sequential')
                if phase == 'warmup' or phase == 'sequential' and len(calls) == 2: raise failure
                return observations(actual)

            def parallel(actual, **_):
                calls.append('parallel')
                if phase == 'parallel': raise failure
                return observations(actual)

            def projection(actual):
                if phase == 'summary': raise failure
                return summarize(actual)

            with self.subTest(phase=phase), \
                    patch.object(benchmark, 'run_npc_magic_simulation', side_effect=sequential), \
                    patch.object(benchmark, 'run_npc_magic_simulation_parallel', side_effect=parallel), \
                    patch.object(benchmark, 'summarize_npc_magic_simulation', side_effect=projection):
                with self.assertRaises(RuntimeError) as caught:
                    benchmark.measure_comparison(request, workers=(1, 2), batch_size=32, repeats=1)
            self.assertIs(caught.exception, failure)
            self.assertLessEqual(len(calls), 3)

    def test_manifest_uses_canonical_paths_and_bytes_and_all_four_scopes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'src' / 'nested').mkdir(parents=True)
            (root / 'tools').mkdir()
            paths = (root / 'src' / 'nested' / 'untracked.py', root / 'tools' / 'profile_m8.py',
                     root / 'tools' / 'm8_benchmark_fixtures.py', root / 'tools' / 'benchmark_m8_parallel.py')
            for index, path in enumerate(paths): path.write_bytes(f'content {index}'.encode())
            digest = sha256()
            for path in sorted(paths, key=lambda p: p.relative_to(root).as_posix()):
                digest.update(path.relative_to(root).as_posix().encode() + b'\0')
                digest.update(sha256(path.read_bytes()).digest())
            previous = benchmark.source_digest(root)
            self.assertEqual(previous, digest.hexdigest())
            for path in paths:
                path.write_bytes(path.read_bytes() + b' changed')
                current = benchmark.source_digest(root)
                self.assertNotEqual(current, previous)
                previous = current
            for path in (root / 'src' / 'cache.pyc', root / 'tools' / 'unrelated.py', root / 'notes.md'):
                path.write_bytes(b'ignored')
            self.assertEqual(benchmark.source_digest(root), previous)
            paths[0].rename(paths[0].with_name('renamed.py'))
            self.assertNotEqual(benchmark.source_digest(root), previous)

    def test_report_has_all_times_counters_digest_reproduction_and_scope(self):
        item = measured(source(2))
        report = benchmark.render_report((item,), command='exact replay', revision='revision dirty',
                                         source_hash='manifest hash', batch_size=32)
        for expected in ('exact replay', 'revision dirty', 'manifest hash', 'batch_size: 32',
                         'towr:npc-magic-trial:v1', '1.000000, 3.000000, 2.000000', '0.400',
                         'spawn, workers=1', 'spawn, workers=2', 'zero-action/zero-draw',
                         'Control is not averaged', 'Summary projection is inside timing',
                         'source validation/normalization and shutdown', 'RSS are not measured',
                         'achieved/defeated/limit/unsupported', 'actions: 0; started rounds: 2; completed rounds: 0',
                         benchmark.trial_digest(item.result), 'All 9 measured full results/summaries equal'):
            self.assertIn(expected, report)

    def _main_context(self, stack, output):
        stack.enter_context(patch.object(benchmark.platform, 'platform', return_value='test platform'))
        stack.enter_context(patch.object(benchmark.platform, 'processor', return_value='test processor'))
        stack.enter_context(patch.object(benchmark.sys, 'argv', ['benchmark', '--output', str(output)]))
        stack.enter_context(patch.object(benchmark.subprocess, 'run', side_effect=(
            SimpleNamespace(stdout='revision\n'), SimpleNamespace(stdout='?? tools/benchmark_m8_parallel.py\n'))))
        stack.enter_context(redirect_stdout(StringIO()))

    def test_main_admits_all_requests_before_first_measurement(self):
        with TemporaryDirectory() as directory, ExitStack() as stack:
            output = Path(directory) / 'report.md'
            output.write_text('old report')
            self._main_context(stack, output)
            failure = ValueError('third fixture rejected')
            stack.enter_context(patch.object(benchmark, 'benchmark_request', side_effect=(source(), source(), failure)))
            measure = stack.enter_context(patch.object(benchmark, 'measure_comparison'))
            with self.assertRaises(ValueError) as caught: benchmark.main()
            self.assertIs(caught.exception, failure)
            measure.assert_not_called()
            self.assertEqual(output.read_text(), 'old report')

    def test_main_invalid_options_preserve_old_report_before_measurement(self):
        for option, value in (('--trials', '0'), ('--master-seed', '-1'), ('--round-budget', '0'),
                              ('--workers', '0'), ('--batch-size', '0'), ('--repeats', '0')):
            with self.subTest(option=option), TemporaryDirectory() as directory:
                output = Path(directory) / 'report.md'
                output.write_text('old report')
                with patch.object(benchmark.sys, 'argv', ['benchmark', '--output', str(output), option, value]), \
                        patch.object(benchmark, 'measure_comparison') as measure:
                    with self.assertRaises((ValueError, SystemExit)): benchmark.main()
                    measure.assert_not_called()
                self.assertEqual(output.read_text(), 'old report')

    def test_main_success_passes_complete_settings_and_publishes_one_report(self):
        with TemporaryDirectory() as directory, ExitStack() as stack:
            output = Path(directory) / 'report.md'
            output.write_text('old report')
            self._main_context(stack, output)
            digest = stack.enter_context(patch.object(benchmark, 'source_digest', return_value='same manifest'))
            measure = stack.enter_context(patch.object(benchmark, 'measure_comparison', side_effect=lambda r, **_: measured(r)))
            benchmark.main()
            self.assertEqual(digest.call_count, 2)
            self.assertEqual(measure.call_count, 3)
            self.assertEqual(tuple(call.args[0].scenario.id.rsplit(':', 1)[-1] for call in measure.call_args_list),
                             benchmark.CASES)
            for call in measure.call_args_list:
                self.assertEqual(call.kwargs, {'workers': (1, 2), 'batch_size': 32, 'repeats': 3})
                self.assertEqual((call.args[0].trials, call.args[0].master_seed), (100, 20261026))
            report = output.read_text()
            self.assertIn('same manifest', report)
            self.assertIn('revision (src/tools have uncommitted changes)', report)
            self.assertEqual(tuple(Path(directory).iterdir()), (output,))

    def test_measurement_render_source_and_atomic_replace_failures_preserve_old_report(self):
        for phase in ('measurement', 'render', 'manifest', 'replace'):
            with self.subTest(phase=phase), TemporaryDirectory() as directory, ExitStack() as stack:
                output = Path(directory) / 'report.md'
                output.write_text('old report')
                self._main_context(stack, output)
                failure = OSError(f'{phase} failed')
                measure = stack.enter_context(patch.object(benchmark, 'measure_comparison',
                    side_effect=failure if phase == 'measurement' else lambda r, **_: measured(r)))
                stack.enter_context(patch.object(benchmark, 'source_digest',
                    side_effect=('before', 'after') if phase == 'manifest' else ('same', 'same')))
                if phase == 'render': stack.enter_context(patch.object(benchmark, 'render_report', side_effect=failure))
                if phase == 'replace': stack.enter_context(patch.object(Path, 'replace', side_effect=failure))
                with self.assertRaises(RuntimeError if phase == 'manifest' else OSError) as caught:
                    benchmark.main()
                if phase != 'manifest': self.assertIs(caught.exception, failure)
                if phase == 'measurement': self.assertEqual(measure.call_count, 1)
                self.assertEqual(output.read_text(), 'old report')
                self.assertEqual(tuple(Path(directory).iterdir()), (output,))
