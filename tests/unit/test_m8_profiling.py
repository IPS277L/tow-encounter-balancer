"""Deterministic developer-harness checks, without performance thresholds."""
from contextlib import redirect_stdout
import cProfile
from dataclasses import replace
from hashlib import sha256
from io import StringIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import tracemalloc
import unittest
from unittest.mock import patch

from tools import profile_m8
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome
from towr.simulation.npc_magic_models import (
    NpcMagicOutcomeCounts, NpcMagicSimulationRequest, NpcMagicSimulationResult, NpcMagicTrialRecord,
)
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation as summarize


def benchmark_request(trials=2):
    return profile_m8.benchmark_request('champion-pressure', trials=trials, master_seed=42, round_budget=4)


def swapped_records():
    """Different indexed observations with equal aggregate counts and totals."""
    request = benchmark_request()
    first = NpcMagicSimulationResult(request, (
        NpcMagicTrialRecord(request.scenario, 0, request.seed_for(0), Outcome.OBJECTIVE_ACHIEVED, 1, 1, 0),
        NpcMagicTrialRecord(request.scenario, 1, request.seed_for(1), Outcome.UNSUPPORTED_PATH, 0, 1, 0),
    ))
    second = NpcMagicSimulationResult(request, (
        replace(first.trials[0], outcome=Outcome.UNSUPPORTED_PATH, executed_action_count=0),
        replace(first.trials[1], outcome=Outcome.OBJECTIVE_ACHIEVED, executed_action_count=1),
    ))
    return (first, summarize(first)), (second, summarize(second))


def profiler_active():
    monitoring = getattr(sys, 'monitoring', None)
    return (sys.getprofile() is not None or monitoring is not None
            and monitoring.get_tool(monitoring.PROFILER_ID) is not None)


class M8ProfilingTests(unittest.TestCase):
    def test_declared_cases_are_distinct_admitted_magic_requests(self):
        self.assertEqual(profile_m8.CASES, ('curse-routes', 'champion-pressure', 'missing-departure'))
        requests = tuple(profile_m8.benchmark_request(case, trials=2, master_seed=42, round_budget=4)
                         for case in profile_m8.CASES)
        for request in requests:
            self.assertIsInstance(request, NpcMagicSimulationRequest)
            self.assertEqual((request.trials, request.master_seed, request.scenario.max_rounds), (2, 42, 4))
        self.assertEqual(len({r.scenario.id for r in requests}), 3)

    def test_run_batch_is_the_public_simulation_and_aggregate_projection(self):
        request = profile_m8.benchmark_request('missing-departure', trials=1, master_seed=42, round_budget=1)
        result, summary = profile_m8.run_batch(request)
        self.assertEqual(result, run_npc_magic_simulation(request))
        self.assertEqual(summary, summarize(result))
        self.assertEqual(result.outcome_counts, NpcMagicOutcomeCounts(0, 0, 0, 1))
        self.assertEqual((result.total_action_count, result.total_started_round_count,
                          result.total_completed_round_count), (0, 1, 0))

    def test_real_measurement_has_separate_wall_memory_and_profile_runs(self):
        request = profile_m8.benchmark_request('missing-departure', trials=1, master_seed=42, round_budget=1)
        with patch.object(profile_m8, 'run_batch', wraps=profile_m8.run_batch) as run:
            measured = profile_m8.measure(request, repeats=2, top=2)
        self.assertEqual(run.call_count, 5)  # warm-up + 2 wall + trace + profile
        self.assertEqual(len(measured.wall_seconds), 2)
        self.assertIsInstance(measured.peak_python_bytes, int)
        self.assertGreaterEqual(measured.peak_python_bytes, 0)
        self.assertEqual(measured.result, run_npc_magic_simulation(request))
        self.assertEqual(measured.summary, summarize(measured.result))
        self.assertFalse(tracemalloc.is_tracing())
        self.assertIsNone(sys.getprofile())
        for report in (measured.profile_cumulative, measured.profile_self, measured.profile_replace_callers):
            self.assertIsInstance(report, str)

    def test_warmup_is_bounded_and_instrumentation_never_overlaps(self):
        same, _ = swapped_records()
        for trials in (2, 5):
            request = replace(same[0].source_request, trials=trials)
            # Synthetic observations make this a harness check, not a timing claim.
            result = NpcMagicSimulationResult(request, tuple(
                NpcMagicTrialRecord(request.scenario, i, request.seed_for(i), Outcome.UNSUPPORTED_PATH, 0, 1, 0)
                for i in range(trials)))
            observed = result, summarize(result)
            calls = []

            def batch(source):
                calls.append((source, tracemalloc.is_tracing(), profiler_active()))
                if source != request:
                    warmup = NpcMagicSimulationResult(source, tuple(
                        NpcMagicTrialRecord(source.scenario, i, source.seed_for(i), Outcome.UNSUPPORTED_PATH, 0, 1, 0)
                        for i in range(source.trials)))
                    return warmup, summarize(warmup)
                return observed

            with self.subTest(trials=trials), patch.object(profile_m8, 'run_batch', side_effect=batch):
                profile_m8.measure(request, repeats=3, top=1)
            self.assertEqual(len(calls), 6)
            self.assertEqual(calls[0][0], replace(request, trials=min(3, trials)))
            self.assertTrue(all(source is request for source, _, _ in calls[1:]))
            self.assertEqual(tuple((trace, prof) for _, trace, prof in calls), (
                (False, False), (False, False), (False, False), (False, False), (True, False), (False, True)))

    def test_full_record_difference_is_rejected_in_each_measurement_phase(self):
        same, changed = swapped_records()
        self.assertEqual(same[1], changed[1])
        self.assertEqual(same[0].outcome_counts, changed[0].outcome_counts)
        self.assertNotEqual(profile_m8.trial_digest(same[0]), profile_m8.trial_digest(changed[0]))
        for repeats, outputs in ((2, (same, same, changed)), (1, (same, same, changed)),
                                 (1, (same, same, same, changed))):
            with self.subTest(repeats=repeats, calls=len(outputs)), \
                    patch.object(profile_m8, 'run_batch', side_effect=outputs) as run:
                with self.assertRaisesRegex(ValueError, 'changed'):
                    profile_m8.measure(same[0].source_request, repeats=repeats, top=1)
            self.assertEqual(run.call_count, len(outputs))
            self.assertFalse(tracemalloc.is_tracing())
            self.assertIsNone(sys.getprofile())

    def test_summary_difference_is_rejected_even_when_full_result_is_equal(self):
        same, _ = swapped_records()
        changed_summary = replace(same[1], outcome_counts=NpcMagicOutcomeCounts(0, 1, 0, 1))
        changed = same[0], changed_summary
        for repeats, outputs in ((2, (same, same, changed)), (1, (same, same, changed)),
                                 (1, (same, same, same, changed))):
            with self.subTest(repeats=repeats, calls=len(outputs)), \
                    patch.object(profile_m8, 'run_batch', side_effect=outputs):
                with self.assertRaisesRegex(ValueError, 'changed'):
                    profile_m8.measure(same[0].source_request, repeats=repeats, top=1)
            self.assertFalse(tracemalloc.is_tracing())
            self.assertIsNone(sys.getprofile())

    def test_numeric_measure_args_distinguish_wrong_types_from_invalid_ranges(self):
        request = benchmark_request()
        with patch.object(profile_m8, 'run_batch') as run:
            for name in ('repeats', 'top'):
                for value in (True, False, 1.0, '1', None):
                    with self.subTest(name=name, value=value), self.assertRaises(TypeError):
                        profile_m8.measure(request, **{name: value})
                for value in (0, -1):
                    with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                        profile_m8.measure(request, **{name: value})
            for value in (None, {}, request.scenario):
                with self.subTest(request=type(value)), self.assertRaises(TypeError): profile_m8.measure(value)
        run.assert_not_called()

    def test_existing_tracer_is_rejected_and_left_running(self):
        tracemalloc.start()
        try:
            with patch.object(profile_m8, 'run_batch') as run:
                with self.assertRaises(RuntimeError): profile_m8.measure(benchmark_request())
                run.assert_not_called()
            self.assertTrue(tracemalloc.is_tracing())
        finally:
            tracemalloc.stop()

    def test_existing_profiler_is_rejected_before_warmup(self):
        with patch.object(profile_m8.sys, 'getprofile', return_value=object()), \
                patch.object(profile_m8, 'run_batch') as run:
            with self.assertRaises(RuntimeError): profile_m8.measure(benchmark_request())
            run.assert_not_called()

    def test_existing_real_cprofile_is_rejected_without_stopping_callers_profiler(self):
        request = benchmark_request()

        def nested_measurement():
            self.assertTrue(profiler_active())
            with patch.object(profile_m8, 'run_batch') as run:
                with self.assertRaises(RuntimeError): profile_m8.measure(request)
                run.assert_not_called()
            self.assertTrue(profiler_active())

        cProfile.Profile().runcall(nested_measurement)
        self.assertFalse(profiler_active())

    def test_instrumentation_cleanup_and_exception_identity_on_failure(self):
        same, _ = swapped_records()
        for stage in ('memory', 'profile'):
            for failure in (RuntimeError('injected instrumentation failure'), KeyboardInterrupt('interrupted')):
                prefix = (same, same) if stage == 'memory' else (same, same, same)
                with self.subTest(stage=stage, exception=type(failure)), \
                        patch.object(profile_m8, 'run_batch', side_effect=(*prefix, failure)) as run:
                    with self.assertRaises(type(failure)) as caught:
                        profile_m8.measure(same[0].source_request, repeats=1, top=1)
                self.assertIs(caught.exception, failure)
                self.assertEqual(run.call_count, len(prefix) + 1)
                self.assertFalse(tracemalloc.is_tracing())
                self.assertFalse(profiler_active())

    def test_first_timed_attempt_rejects_foreign_full_request_before_becoming_baseline(self):
        same, _ = swapped_records()
        source = same[0].source_request
        foreign_request = replace(source, master_seed=43)
        foreign = NpcMagicSimulationResult(foreign_request, tuple(
            replace(r, seed=foreign_request.seed_for(r.trial_index)) for r in same[0].trials))
        with patch.object(profile_m8, 'run_batch', side_effect=(same, (foreign, summarize(foreign)))) as run:
            with self.assertRaisesRegex(ValueError, 'source'): profile_m8.measure(source, repeats=1, top=1)
        self.assertEqual(run.call_count, 2)
        self.assertFalse(tracemalloc.is_tracing())
        self.assertFalse(profiler_active())

    def test_input_or_global_rng_mutation_is_detected_after_timing(self):
        from random import getstate, random, setstate
        same, _ = swapped_records()
        source = same[0].source_request
        initial_rng = getstate()
        original_seed = source.master_seed
        for mutation in ('input', 'global_rng'):
            calls = 0

            def batch(request):
                nonlocal calls
                calls += 1
                if calls == 2:
                    if mutation == 'input': object.__setattr__(request, 'master_seed', 43)
                    else: random()
                return same

            try:
                with self.subTest(mutation=mutation), patch.object(profile_m8, 'run_batch', side_effect=batch):
                    with self.assertRaisesRegex(ValueError, 'changed'):
                        profile_m8.measure(source, repeats=1, top=1)
                self.assertEqual(calls, 2)
            finally:
                object.__setattr__(source, 'master_seed', original_seed)
                setstate(initial_rng)

    def test_trial_digest_changes_when_either_round_counter_changes(self):
        same, _ = swapped_records()
        result = same[0]
        record = replace(result.trials[1], executed_action_count=2, started_round_count=2, completed_round_count=1)
        baseline = replace(result, trials=(result.trials[0], record))
        for changes in ({'started_round_count': 1}, {'completed_round_count': 2}):
            changed = replace(baseline, trials=(result.trials[0], replace(record, **changes)))
            self.assertNotEqual(profile_m8.trial_digest(baseline), profile_m8.trial_digest(changed))
        self.assertEqual(profile_m8.trial_digest(result), profile_m8.trial_digest(replace(result)))

    def test_trial_digest_has_explicit_canonical_seed_outcome_and_counter_encoding(self):
        same, _ = swapped_records()
        result = same[0]
        rows = tuple('|'.join(map(str, (r.trial_index, r.seed, r.outcome.value,
            r.executed_action_count, r.started_round_count, r.completed_round_count))) for r in result.trials)
        canonical = 'towr:npc-magic-trial:v1\n' + '\n'.join(rows)
        self.assertEqual(profile_m8.trial_digest(result), sha256(canonical.encode('ascii')).hexdigest())

    def test_source_digest_covers_all_sources_and_both_harness_files_only(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'src' / 'nested').mkdir(parents=True)
            (root / 'tools').mkdir()
            (root / 'tools' / 'profile_m8.py').write_text('profile', encoding='utf-8')
            fixture = root / 'tools' / 'm8_benchmark_fixtures.py'
            fixture.write_text('fixtures', encoding='utf-8')
            first = profile_m8.source_digest(root)
            source = root / 'src' / 'nested' / 'untracked.py'
            source.write_text('new source', encoding='utf-8')
            second = profile_m8.source_digest(root)
            self.assertNotEqual(first, second)
            for path in (root / 'src' / 'cache.pyc', root / 'tools' / 'unrelated.py', root / 'notes.md'):
                path.write_text('ignored', encoding='utf-8')
            self.assertEqual(second, profile_m8.source_digest(root))
            fixture.write_text('changed fixtures', encoding='utf-8')
            third = profile_m8.source_digest(root)
            self.assertNotEqual(second, third)
            (root / 'tools' / 'profile_m8.py').write_text('changed profile', encoding='utf-8')
            fourth = profile_m8.source_digest(root)
            self.assertNotEqual(third, fourth)
            source.rename(source.with_name('renamed.py'))
            self.assertNotEqual(fourth, profile_m8.source_digest(root))

    def test_report_contains_reproduction_source_and_all_magic_counters(self):
        same, _ = swapped_records()
        item = profile_m8.Measurement(same[0], same[1], (0.125, 0.25, 0.5), 1024,
                                      'cumulative evidence', 'self evidence', 'replace evidence')
        report = profile_m8.render_report((item,), command='replay command', revision='test revision', source_hash='test hash')
        for expected in ('replay command', 'test revision', 'test hash', 'not process RSS',
                         'dataclasses.replace callers', 'achieved/defeated/limit/unsupported',
                         profile_m8.trial_digest(same[0]), 'cumulative evidence', 'self evidence', 'replace evidence'):
            self.assertIn(expected, report)
        self.assertIn('towr:npc-magic-trial:v1', report)
        self.assertIn('Started', report)
        self.assertIn('Completed', report)

    def test_main_rejects_all_invalid_options_before_any_measurement(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'report.md'
            output.write_text('existing report', encoding='utf-8')
            for option, value in (('--trials', '0'), ('--master-seed', '-1'), ('--round-budget', '0'),
                                  ('--repeats', '0'), ('--top', '0')):
                argv = ['profile_m8.py', '--output', str(output), option, value]
                with self.subTest(option=option), patch.object(profile_m8.sys, 'argv', argv), \
                        patch.object(profile_m8, 'measure') as measure, redirect_stdout(StringIO()):
                    with self.assertRaises((ValueError, SystemExit)): profile_m8.main()
                    measure.assert_not_called()
                self.assertEqual(output.read_text(encoding='utf-8'), 'existing report')

    def test_main_admits_every_case_before_first_measurement(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'report.md'
            output.write_text('existing report', encoding='utf-8')
            source = benchmark_request()
            failure = ValueError('last fixture rejected')
            with patch.object(profile_m8.sys, 'argv', ['profile_m8.py', '--output', str(output)]), \
                    patch.object(profile_m8, 'benchmark_request', side_effect=(source, source, failure)) as build, \
                    patch.object(profile_m8, 'measure') as measure:
                with self.assertRaises(ValueError) as caught: profile_m8.main()
            self.assertIs(caught.exception, failure)
            self.assertEqual(build.call_count, 3)
            measure.assert_not_called()
            self.assertEqual(output.read_text(encoding='utf-8'), 'existing report')

    def test_main_rejects_active_instrumentation_before_measurement(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'report.md'
            output.write_text('existing report', encoding='utf-8')
            for module, attribute, value in ((profile_m8.tracemalloc, 'is_tracing', True),
                                             (profile_m8.sys, 'getprofile', object())):
                with self.subTest(attribute=attribute), \
                        patch.object(profile_m8.sys, 'argv', ['profile_m8.py', '--output', str(output)]), \
                        patch.object(module, attribute, return_value=value), \
                        patch.object(profile_m8, 'measure') as measure:
                    with self.assertRaises(RuntimeError): profile_m8.main()
                    measure.assert_not_called()
                self.assertEqual(output.read_text(encoding='utf-8'), 'existing report')

    def test_source_change_aborts_before_rendering_or_replacing_existing_report(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'report.md'
            output.write_text('existing report', encoding='utf-8')
            with patch.object(profile_m8.sys, 'argv', ['profile_m8.py', '--output', str(output)]), \
                    patch.object(profile_m8, 'source_digest', side_effect=('before', 'after')), \
                    patch.object(profile_m8, 'measure') as measure, \
                    patch.object(profile_m8, 'render_report') as render, redirect_stdout(StringIO()):
                with self.assertRaisesRegex(RuntimeError, 'source files changed'): profile_m8.main()
            self.assertEqual(measure.call_count, 3)
            render.assert_not_called()
            self.assertEqual(output.read_text(encoding='utf-8'), 'existing report')

    def test_measurement_failure_preserves_existing_report_and_stops_cases(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'report.md'
            output.write_text('existing report', encoding='utf-8')
            failure = RuntimeError('second case failed')
            with patch.object(profile_m8.sys, 'argv', ['profile_m8.py', '--output', str(output)]), \
                    patch.object(profile_m8, 'measure', side_effect=(object(), failure, object())) as measure, \
                    patch.object(profile_m8, 'render_report') as render, redirect_stdout(StringIO()):
                with self.assertRaises(RuntimeError) as caught: profile_m8.main()
            self.assertIs(caught.exception, failure)
            self.assertEqual(measure.call_count, 2)
            render.assert_not_called()
            self.assertEqual(output.read_text(encoding='utf-8'), 'existing report')

    def test_render_failure_preserves_existing_report(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'report.md'
            output.write_text('existing report', encoding='utf-8')
            failure = ValueError('render failed')
            with patch.object(profile_m8.sys, 'argv', ['profile_m8.py', '--output', str(output)]), \
                    patch.object(profile_m8, 'measure'), \
                    patch.object(profile_m8, 'render_report', side_effect=failure), redirect_stdout(StringIO()):
                with self.assertRaises(ValueError) as caught: profile_m8.main()
            self.assertIs(caught.exception, failure)
            self.assertEqual(output.read_text(encoding='utf-8'), 'existing report')

    def test_atomic_replace_failure_preserves_existing_report_and_removes_temporary(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'report.md'
            output.write_text('existing report', encoding='utf-8')
            failure = OSError('atomic replacement failed')
            with patch.object(profile_m8.sys, 'argv', ['profile_m8.py', '--output', str(output)]), \
                    patch.object(profile_m8, 'measure'), \
                    patch.object(profile_m8, 'render_report', return_value='new report'), \
                    patch.object(Path, 'replace', side_effect=failure), redirect_stdout(StringIO()):
                with self.assertRaises(OSError) as caught: profile_m8.main()
            self.assertIs(caught.exception, failure)
            self.assertEqual(output.read_text(encoding='utf-8'), 'existing report')
            self.assertEqual(tuple(Path(directory).iterdir()), (output,))
