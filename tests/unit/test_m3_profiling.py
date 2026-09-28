import tracemalloc
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tools import profile_m3
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.simulation.npc_ranged_simulation import run_npc_ranged_simulation


class M3ProfilingTests(unittest.TestCase):
    def test_declared_cases_use_admitted_numeric_profiles_and_fixed_policies(self):
        for sizes in profile_m3.CASES:
            request = profile_m3.benchmark_request(sizes, trials=2, master_seed=42, round_budget=3)
            self.assertEqual(len(request.scenario.initial.current.actor_order), sum(sizes))
            for actor in request.scenario.initial.current.state.roster.participants:
                self.assertEqual(actor.definition.attacks[0].range_min, RangedWeaponRange.MEDIUM)
                self.assertEqual(actor.state.current_resilience.total, 4)
                self.assertEqual(actor.definition.attacks[0].damage.base, 3)
                self.assertTrue(all(d.gm_approved for d in request.scenario.policy_for(actor.state.actor_id).defeat_decisions))
        with self.assertRaises(ValueError):
            profile_m3.benchmark_request((0, 1), trials=2, master_seed=42, round_budget=3)

    def test_real_timing_memory_and_profile_runs_preserve_records_and_render_report(self):
        request = profile_m3.benchmark_request((1, 1), trials=1, master_seed=42, round_budget=1)
        with patch.object(profile_m3, "run_npc_ranged_simulation", wraps=run_npc_ranged_simulation) as run:
            measured = profile_m3.measure(request, repeats=2, top=2)
        # Warm-up, two normal repeats, one traced run and one separately profiled run.
        self.assertEqual(run.call_count, 5)
        self.assertEqual(len(measured.wall_seconds), 2)
        self.assertGreater(measured.peak_python_bytes, 0)
        self.assertEqual(measured.result, run_npc_ranged_simulation(request))
        self.assertFalse(tracemalloc.is_tracing())
        report = profile_m3.render_report((measured,), command="replay command", revision="test revision")
        for expected in ("replay command", "test revision", "not process RSS", "dataclasses.replace callers",
                         "achieved/defeated/limit/unsupported", profile_m3.trial_digest(measured.result)):
            self.assertIn(expected, report)

    def test_full_record_difference_is_detected_even_when_aggregates_match(self):
        request = profile_m3.benchmark_request((1, 1), trials=2, master_seed=42, round_budget=1)
        wound, miss = [1, 2, 10, 10, 10, 10], [10] * 6
        first = run_npc_ranged_simulation(request, rng_factory=lambda seed: SequenceRandom(
            wound if seed == request.seed_for(0) else miss + wound))
        second = run_npc_ranged_simulation(request, rng_factory=lambda seed: SequenceRandom(
            miss + wound if seed == request.seed_for(0) else wound))
        self.assertEqual(first.outcome_counts, second.outcome_counts)
        self.assertEqual(first.total_attack_count, second.total_attack_count)
        self.assertNotEqual(profile_m3.trial_digest(first), profile_m3.trial_digest(second))
        with patch.object(profile_m3, "run_npc_ranged_simulation", side_effect=(first, first, second)):
            with self.assertRaisesRegex(ValueError, "records changed"):
                profile_m3.measure(request, repeats=2)

    def test_invalid_measurements_fail_before_running_and_tracing_is_cleaned_on_error(self):
        request = profile_m3.benchmark_request((1, 1), trials=1, master_seed=42, round_budget=1)
        for changes in ({"repeats": 0}, {"repeats": True}, {"top": 0}):
            with patch.object(profile_m3, "run_npc_ranged_simulation") as run:
                with self.assertRaises(ValueError):
                    profile_m3.measure(request, **changes)
                run.assert_not_called()
        observed = run_npc_ranged_simulation(request)
        with patch.object(profile_m3, "run_npc_ranged_simulation",
                          side_effect=(observed, observed, RuntimeError("memory run failed"))):
            with self.assertRaisesRegex(RuntimeError, "memory run failed"):
                profile_m3.measure(request, repeats=1)
        self.assertFalse(tracemalloc.is_tracing())
