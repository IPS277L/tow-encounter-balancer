import tracemalloc
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tools import profile_m6
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.simulation.npc_melee_simulation import run_npc_melee_simulation
from towr.simulation.npc_melee_summary import summarize_npc_melee_simulation as summarize


class M6ProfilingTests(unittest.TestCase):
    def test_declared_cases_use_admitted_numeric_profiles_and_fixed_policies(self):
        for sizes in profile_m6.CASES:
            request = profile_m6.benchmark_request(sizes, trials=2, master_seed=42, round_budget=3)
            self.assertEqual(len(request.scenario.initial.current.actor_order), sum(sizes))
            for actor in request.scenario.initial.current.state.roster.participants:
                self.assertEqual(actor.definition.attacks[0].range_min, RangedWeaponRange.CLOSE)
                self.assertEqual(actor.state.current_resilience.total, 3)
                self.assertEqual(actor.definition.attacks[0].damage.base, 2)
                self.assertTrue(request.scenario.facts.all_opponents_in_close_range)
                self.assertTrue(request.scenario.policy_for(actor.state.actor_id).outnumbering_bonus_approved)
                self.assertTrue(all(d.gm_approved for d in request.scenario.policy_for(actor.state.actor_id).defeat_decisions))
        with self.assertRaises(ValueError):
            profile_m6.benchmark_request((0, 1), trials=2, master_seed=42, round_budget=3)

    def test_real_timing_memory_and_profile_runs_preserve_records_and_render_report(self):
        request = profile_m6.benchmark_request((1, 1), trials=1, master_seed=42, round_budget=1)
        with patch.object(profile_m6, "run_batch", wraps=profile_m6.run_batch) as run:
            measured = profile_m6.measure(request, repeats=2, top=2)
        # Warm-up, two normal repeats, one traced run and one separately profiled run.
        self.assertEqual(run.call_count, 5)
        self.assertEqual(len(measured.wall_seconds), 2)
        self.assertGreater(measured.peak_python_bytes, 0)
        self.assertEqual(measured.result, run_npc_melee_simulation(request))
        self.assertEqual(measured.summary, summarize(measured.result))
        self.assertFalse(tracemalloc.is_tracing())
        report = profile_m6.render_report((measured,), command="replay command", revision="test revision", source_hash="test hash")
        for expected in ("replay command", "test revision", "test hash", "not process RSS", "dataclasses.replace callers",
                         "achieved/defeated/limit/unsupported", profile_m6.trial_digest(measured.result)):
            self.assertIn(expected, report)

    def test_source_digest_includes_new_sources_and_harness_but_not_bytecode(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "tools").mkdir()
            script = root / "tools" / "profile_m6.py"
            script.write_text("original", encoding="utf-8")
            first = profile_m6.source_digest(root)
            (root / "src" / "untracked.py").write_text("new source", encoding="utf-8")
            second = profile_m6.source_digest(root)
            self.assertNotEqual(first, second)
            (root / "src" / "cache.pyc").write_bytes(b"ignored")
            self.assertEqual(second, profile_m6.source_digest(root))
            script.write_text("changed", encoding="utf-8")
            self.assertNotEqual(second, profile_m6.source_digest(root))

    def test_full_record_difference_is_detected_even_when_aggregates_match(self):
        request = profile_m6.benchmark_request((1, 1), trials=2, master_seed=42, round_budget=1)
        wound, miss = [1, 2, 10, 10, 10, 10], [10] * 6
        first = run_npc_melee_simulation(request, rng_factory=lambda seed: SequenceRandom(
            wound if seed == request.seed_for(0) else miss + wound))
        second = run_npc_melee_simulation(request, rng_factory=lambda seed: SequenceRandom(
            miss + wound if seed == request.seed_for(0) else wound))
        self.assertEqual(first.outcome_counts, second.outcome_counts)
        self.assertEqual(first.total_attack_count, second.total_attack_count)
        self.assertNotEqual(profile_m6.trial_digest(first), profile_m6.trial_digest(second))
        same, changed = (first, summarize(first)), (second, summarize(second))
        for repeats, outputs in ((2, (same, same, changed)), (1, (same, same, changed)),
                                 (1, (same, same, same, changed))):
            with self.subTest(repeats=repeats, calls=len(outputs)):
                with patch.object(profile_m6, "run_batch", side_effect=outputs):
                    with self.assertRaisesRegex(ValueError, "records changed"):
                        profile_m6.measure(request, repeats=repeats)
                self.assertFalse(tracemalloc.is_tracing())

    def test_invalid_measurements_fail_before_running_and_tracing_is_cleaned_on_error(self):
        request = profile_m6.benchmark_request((1, 1), trials=1, master_seed=42, round_budget=1)
        for changes in ({"repeats": 0}, {"repeats": True}, {"top": 0}):
            with patch.object(profile_m6, "run_batch") as run:
                with self.assertRaises(ValueError):
                    profile_m6.measure(request, **changes)
                run.assert_not_called()
        with patch.object(profile_m6.sys, "getprofile", return_value=object()):
            with patch.object(profile_m6, "run_batch") as run:
                with self.assertRaises(RuntimeError):
                    profile_m6.measure(request)
                run.assert_not_called()
        observed = profile_m6.run_batch(request)
        with patch.object(profile_m6, "run_batch",
                          side_effect=(observed, observed, RuntimeError("memory run failed"))):
            with self.assertRaisesRegex(RuntimeError, "memory run failed"):
                profile_m6.measure(request, repeats=1)
        self.assertFalse(tracemalloc.is_tracing())
