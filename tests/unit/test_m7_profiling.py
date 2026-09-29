import tracemalloc
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tools import profile_m7
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.test_models import Skill
from towr.domain.npc_mixed_scenario_result_models import NpcMixedScenarioOutcome
from towr.simulation.npc_mixed_simulation import run_npc_mixed_simulation
from towr.simulation.npc_mixed_summary import summarize_npc_mixed_simulation as summarize


class M7ProfilingTests(unittest.TestCase):
    def test_declared_cases_use_admitted_numeric_profiles_and_fixed_policies(self):
        for sizes in profile_m7.CASES:
            request = profile_m7.benchmark_request(sizes, trials=2, master_seed=42, round_budget=3)
            self.assertEqual(len(request.scenario.initial.current.actor_order), sum(sizes))
            scenario = request.scenario
            actors = scenario.initial.current.state.roster.participants
            self.assertEqual(sum(a.definition.attacks[0].skill is Skill.SHOOTING for a in actors),
                             2 if sizes == (2, 2) else 1)
            self.assertEqual(len(scenario.pair_ranges), sizes[0] * sizes[1])
            for actor in actors:
                bow = actor.definition.attacks[0].skill is Skill.SHOOTING
                self.assertEqual(actor.definition.attacks[0].range_min,
                                 RangedWeaponRange.MEDIUM if bow else RangedWeaponRange.CLOSE)
                self.assertEqual(actor.state.current_resilience.total, 4 if bow else 3)
                self.assertEqual(actor.definition.attacks[0].damage.base, 3 if bow else 2)
                policy = scenario.policy_for(actor.state.actor_id)
                self.assertTrue(policy.outnumbering_bonus_approved)
                self.assertFalse(policy.can_leave_zone)
                self.assertTrue(all(d.gm_approved for d in policy.defeat_decisions))
        with self.assertRaises(ValueError):
            profile_m7.benchmark_request((0, 1), trials=2, master_seed=42, round_budget=3)

    def test_real_timing_memory_and_profile_runs_preserve_records_and_render_report(self):
        request = profile_m7.benchmark_request((2, 1), trials=1, master_seed=42, round_budget=1)
        with patch.object(profile_m7, "run_batch", wraps=profile_m7.run_batch) as run:
            measured = profile_m7.measure(request, repeats=2, top=2)
        # Warm-up, two normal repeats, one traced run and one separately profiled run.
        self.assertEqual(run.call_count, 5)
        self.assertEqual(len(measured.wall_seconds), 2)
        self.assertGreater(measured.peak_python_bytes, 0)
        self.assertEqual(measured.result, run_npc_mixed_simulation(request))
        self.assertEqual(measured.summary, summarize(measured.result))
        self.assertFalse(tracemalloc.is_tracing())
        report = profile_m7.render_report((measured,), command="replay command", revision="test revision", source_hash="test hash")
        for expected in ("replay command", "test revision", "test hash", "not process RSS", "dataclasses.replace callers",
                         "achieved/defeated/limit/unsupported", profile_m7.trial_digest(measured.result)):
            self.assertIn(expected, report)

    def test_source_digest_includes_new_sources_and_harness_but_not_bytecode(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "tools").mkdir()
            script = root / "tools" / "profile_m7.py"
            script.write_text("original", encoding="utf-8")
            first = profile_m7.source_digest(root)
            (root / "src" / "untracked.py").write_text("new source", encoding="utf-8")
            second = profile_m7.source_digest(root)
            self.assertNotEqual(first, second)
            (root / "src" / "cache.pyc").write_bytes(b"ignored")
            self.assertEqual(second, profile_m7.source_digest(root))
            script.write_text("changed", encoding="utf-8")
            self.assertNotEqual(second, profile_m7.source_digest(root))

    def test_full_record_difference_is_detected_even_when_aggregates_match(self):
        request = profile_m7.benchmark_request((2, 1), trials=2, master_seed=42, round_budget=1)
        wound, miss = [1, 2, 10, 10, 10, 10], [10] * 6
        first = run_npc_mixed_simulation(request, rng_factory=lambda seed: SequenceRandom(
            wound if seed == request.seed_for(0) else miss + wound))
        second = run_npc_mixed_simulation(request, rng_factory=lambda seed: SequenceRandom(
            miss + wound if seed == request.seed_for(0) else wound))
        self.assertEqual(first.outcome_counts, second.outcome_counts)
        self.assertEqual(first.total_attack_count, second.total_attack_count)
        self.assertNotEqual(profile_m7.trial_digest(first), profile_m7.trial_digest(second))
        same, changed = (first, summarize(first)), (second, summarize(second))
        for repeats, outputs in ((2, (same, same, changed)), (1, (same, same, changed)),
                                 (1, (same, same, same, changed))):
            with self.subTest(repeats=repeats, calls=len(outputs)):
                with patch.object(profile_m7, "run_batch", side_effect=outputs):
                    with self.assertRaisesRegex(ValueError, "records changed"):
                        profile_m7.measure(request, repeats=repeats)
                self.assertFalse(tracemalloc.is_tracing())

    def test_invalid_measurements_fail_before_running_and_tracing_is_cleaned_on_error(self):
        request = profile_m7.benchmark_request((2, 1), trials=1, master_seed=42, round_budget=1)
        for changes in ({"repeats": 0}, {"repeats": True}, {"top": 0}):
            with patch.object(profile_m7, "run_batch") as run:
                with self.assertRaises(ValueError):
                    profile_m7.measure(request, **changes)
                run.assert_not_called()
        with patch.object(profile_m7.sys, "getprofile", return_value=object()):
            with patch.object(profile_m7, "run_batch") as run:
                with self.assertRaises(RuntimeError):
                    profile_m7.measure(request)
                run.assert_not_called()
        observed = profile_m7.run_batch(request)
        with patch.object(profile_m7, "run_batch",
                          side_effect=(observed, observed, RuntimeError("memory run failed"))):
            with self.assertRaisesRegex(RuntimeError, "memory run failed"):
                profile_m7.measure(request, repeats=1)
        self.assertFalse(tracemalloc.is_tracing())

    def test_real_unsupported_trial_is_retained_in_records_and_summary(self):
        request = profile_m7.benchmark_request((2, 2), trials=1, master_seed=42, round_budget=5)
        result = run_npc_mixed_simulation(request, rng_factory=lambda seed: SequenceRandom([1, 2, 10, 10, 10, 10]))
        self.assertIs(result.trials[0].outcome, NpcMixedScenarioOutcome.UNSUPPORTED_PATH)
        self.assertEqual(result.total_attack_count, 1)
        self.assertEqual(result.total_visited_round_count, 1)
        self.assertEqual(summarize(result).outcome_counts.unsupported_path, 1)
        self.assertEqual(summarize(result).outcome_counts.objective_achieved, 0)

    def test_source_change_aborts_before_replacing_existing_report(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "report.md"
            output.write_text("existing report", encoding="utf-8")
            with patch.object(profile_m7.sys, "argv", ["profile_m7.py", "--output", str(output)]), \
                 patch.object(profile_m7, "source_digest", side_effect=("before", "after")), \
                 patch.object(profile_m7, "measure") as measure, \
                 patch.object(profile_m7, "render_report") as render:
                with self.assertRaisesRegex(RuntimeError, "source files changed"):
                    profile_m7.main()
                self.assertEqual(measure.call_count, 3)
                render.assert_not_called()
            self.assertEqual(output.read_text(encoding="utf-8"), "existing report")
