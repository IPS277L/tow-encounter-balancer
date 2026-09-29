from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from fractions import Fraction as F
import pickle
import unittest
from unittest.mock import patch

from tests.unit.test_m7_npc_mixed_simulation import request, observations
from tests.unit.test_m5_ranged_assessment import summary as ranged_summary
from tests.unit.test_m6_melee_assessment import summary as melee_summary
from towr.balance.melee_assessment_models import MeleeAssessmentStatus
from towr.domain.npc_mixed_scenario_result_models import NpcMixedScenarioResult
from towr.domain.npc_rounds_chain_summary_models import NpcRoundsChainSummary
from towr.balance.ranged_assessment_models import ObjectiveRateWindow as SharedWindow, RangedAssessmentStatus
from towr.balance.mixed_assessment import assess_mixed_candidate as assess
from towr.balance.mixed_assessment_models import ObjectiveRateWindow as Window, MixedAssessmentStatus as Status
from towr.simulation.npc_mixed_models import NpcMixedOutcomeCounts as Counts, NpcMixedSimulationResult, NpcMixedTrialSummary
from towr.simulation.npc_mixed_summary_models import NpcMixedSimulationSummary as Summary


def summary(counts=Counts(1, 1, 2, 0)):
    n = counts.objective_achieved + counts.side_defeated + counts.round_limit + counts.unsupported_path
    return Summary(request(trials=n), counts, counts.objective_achieved + counts.side_defeated, n)


class M7MixedAssessmentTests(unittest.TestCase):
    def test_all_rates_use_all_trials_including_round_limit(self):
        source = summary()
        actual = assess(source.source_request, source, Window(F(1, 4), F(1, 3), F(1, 2)))
        self.assertEqual((actual.objective_achieved_rate, actual.side_defeated_rate,
                          actual.round_limit_rate, actual.unsupported_path_rate), (F(1, 4), F(1, 4), F(1, 2), F(0)))
        self.assertIs(actual.status, Status.ELIGIBLE)
        self.assertIs(actual.window_match, True)
        self.assertIs(actual.summary, source)
        self.assertIs(actual.source_request, source.source_request)
        self.assertEqual(actual.summary.mean_attack_count, 0.5)

    def test_inclusive_window_bounds_and_exact_single_point(self):
        window = Window(F(1, 4), F(1, 2), F(3, 4))
        for achieved, match in ((0, False), (1, True), (2, True), (3, True), (4, False)):
            source = summary(Counts(achieved, 4-achieved, 0, 0))
            with self.subTest(achieved=achieved):
                self.assertIs(assess(source.source_request, source, window).window_match, match)
        for achieved in (0, 1, 4):
            source = summary(Counts(achieved, 4-achieved, 0, 0))
            rate = F(achieved, 4)
            self.assertIs(assess(source.source_request, source, Window(rate, rate, rate)).window_match, True)

    def test_unsupported_keeps_shares_and_has_no_window_match_even_in_range(self):
        for counts in (Counts(1, 1, 1, 1), Counts(0, 0, 0, 4)):
            source = summary(counts)
            actual = assess(source.source_request, source, Window(F(0), F(1, 2), F(1)))
            self.assertIs(actual.status, Status.UNSUPPORTED_OBSERVATIONS)
            self.assertIsNone(actual.window_match)
            self.assertEqual(actual.objective_achieved_rate, F(counts.objective_achieved, 4))
            self.assertEqual(actual.unsupported_path_rate, F(counts.unsupported_path, 4))
            self.assertEqual(sum((actual.objective_achieved_rate, actual.side_defeated_rate,
                                  actual.round_limit_rate, actual.unsupported_path_rate)), 1)
            self.assertEqual(actual.summary.outcome_counts, counts)

    def test_all_round_limit_is_eligible_zero_goal_rate_not_renormalized(self):
        source = summary(Counts(0, 0, 4, 0))
        actual = assess(source.source_request, source, Window(F(0), F(0), F(0)))
        self.assertEqual((actual.objective_achieved_rate, actual.side_defeated_rate, actual.round_limit_rate), (0, 0, 1))
        self.assertIs(actual.status, Status.ELIGIBLE)
        self.assertIs(actual.window_match, True)

    def test_comparison_does_not_round_rates_to_float(self):
        n = 2**60 + 1
        source = summary(Counts(n//2, n-n//2, 0, 0))
        actual = assess(source.source_request, source, Window(F(1, 2), F(1, 2), F(1)))
        self.assertEqual(float(actual.objective_achieved_rate), 0.5)
        self.assertLess(actual.objective_achieved_rate, F(1, 2))
        self.assertIs(actual.window_match, False)

    def test_shared_window_preserves_class_and_pickle_path_with_separate_status(self):
        self.assertIs(Window, SharedWindow)
        self.assertEqual(Window.__module__, "towr.balance.ranged_assessment_models")
        window = SharedWindow(F(0), F(1, 2), F(1))
        source = summary()
        actual = assess(source.source_request, source, window)
        self.assertIs(actual.window, window)
        self.assertIsNot(Status, MeleeAssessmentStatus)
        self.assertNotIsInstance(actual.status, MeleeAssessmentStatus)
        self.assertIsNot(Status, RangedAssessmentStatus)
        self.assertNotIsInstance(actual.status, RangedAssessmentStatus)
        restored = pickle.loads(pickle.dumps(actual))
        self.assertEqual(restored, actual)
        self.assertIs(type(restored.window), SharedWindow)
        self.assertIs(restored.status, Status.ELIGIBLE)

    def test_typed_inputs_and_exact_source_are_required(self):
        source = summary()
        window = Window(F(0), F(1, 2), F(1))
        full_source = request()
        full_result = NpcMixedSimulationResult(full_source, observations(full_source))
        ranged = ranged_summary()
        melee = melee_summary()
        for position, values in ((0, (None, {}, source, ranged.source_request, melee.source_request)), (1, (None, {}, full_result, ranged, melee)),
                                 (2, (None, {}, (F(0), F(1, 2), F(1))))):
            for value in values:
                args = [source.source_request, source, window]
                args[position] = value
                with self.subTest(position=position, value=type(value)), self.assertRaises(TypeError):
                    assess(*args)
        for foreign in (replace(source.source_request, master_seed=43), replace(source.source_request, trials=5),
                        replace(source.source_request, scenario=replace(source.source_request.scenario,
                            initial=replace(source.source_request.scenario.initial, max_rounds=2))),
                        replace(source.source_request, scenario=replace(source.source_request.scenario,
                            actor_policies=tuple(replace(p, can_leave_zone=not p.can_leave_zone)
                                for p in source.source_request.scenario.actor_policies))),
                        replace(source.source_request, scenario=replace(source.source_request.scenario,
                            actor_policies=tuple(replace(p, outnumbering_bonus_approved=False)
                                for p in source.source_request.scenario.actor_policies))),
                        replace(source.source_request, scenario=replace(source.source_request.scenario,
                            pair_ranges=source.source_request.scenario.pair_ranges[::-1]))):
            with self.subTest(foreign=foreign), self.assertRaises(ValueError):
                assess(foreign, source, window)
        copy = deepcopy(source.source_request)
        self.assertIsNot(copy, source.source_request)
        actual = assess(copy, source, window)
        self.assertIs(actual.source_request, copy)
        self.assertIs(actual.summary, source)

    def test_frozen_derived_assessment_cannot_accept_forged_rates_or_status(self):
        source = summary()
        before = deepcopy(source)
        window = Window(F(0), F(1, 2), F(1))
        actual = assess(source.source_request, source, window)
        self.assertFalse(hasattr(actual, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            actual.window = None
        with self.assertRaises(FrozenInstanceError):
            window.minimum = F(1)
        for field in ("objective_achieved_rate", "side_defeated_rate", "round_limit_rate", "unsupported_path_rate",
                      "status", "window_match"):
            with self.subTest(field=field), self.assertRaises(TypeError):
                replace(actual, **{field: False})
        with self.assertRaises(ValueError):
            replace(actual, source_request=replace(source.source_request, master_seed=43))
        self.assertIs(replace(actual, window=Window(F(1), F(1), F(1))).window_match, False)
        self.assertEqual(source, before)

    def test_assessment_retains_no_trial_records_and_executes_no_rng_or_runner(self):
        source = summary()
        with patch("random.Random", side_effect=AssertionError), \
                patch("towr.simulation.npc_mixed_simulation.run_npc_mixed_simulation", side_effect=AssertionError), \
                patch("towr.simulation.npc_mixed_parallel.run_npc_mixed_simulation_parallel", side_effect=AssertionError), \
                patch("towr.engine.npc_mixed_scenario_runner.run_npc_mixed_scenario", side_effect=AssertionError), \
                patch("concurrent.futures.ProcessPoolExecutor", side_effect=AssertionError), \
                patch("json.loads", side_effect=AssertionError):
            actual = assess(source.source_request, source, Window(F(0), F(1, 2), F(1)))
            self.assertIs(actual.window_match, True)
        pending, seen = [actual], set()
        while pending:
            item = pending.pop()
            if id(item) in seen:
                continue
            seen.add(id(item))
            self.assertNotIsInstance(item, (NpcMixedSimulationResult, NpcMixedTrialSummary,
                                           NpcMixedScenarioResult, NpcRoundsChainSummary))
            if is_dataclass(item):
                pending.extend(getattr(item, field.name) for field in fields(item))
            elif isinstance(item, (tuple, list)):
                pending.extend(item)
