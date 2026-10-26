"""ADR-0040 pure source-bound magic assessment, without simulation execution."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from fractions import Fraction as F
import pickle
import unittest
from unittest.mock import patch

from tests.unit.test_m5_ranged_assessment import summary as ranged_summary
from tests.unit.test_m6_melee_assessment import summary as melee_summary
from tests.unit.test_m7_mixed_assessment import summary as mixed_summary
from tests.unit.test_m8_npc_magic_simulation_models import request, observations
from towr.balance.magic_assessment import assess_magic_candidate as assess
from towr.balance.magic_assessment_models import (
    MagicCandidateAssessment, MagicAssessmentStatus as Status, ObjectiveRateWindow as Window,
)
from towr.balance.melee_assessment_models import MeleeAssessmentStatus
from towr.balance.mixed_assessment_models import MixedAssessmentStatus
from towr.balance.ranged_assessment_models import ObjectiveRateWindow as SharedWindow, RangedAssessmentStatus
from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult
from towr.domain.test_models import InlineProfile
from towr.simulation.npc_magic_models import (
    NpcMagicOutcomeCounts as Counts, NpcMagicSimulationResult, NpcMagicTrialRecord,
)
from towr.simulation.npc_magic_summary_models import NpcMagicSimulationSummary as Summary


def summary(counts=Counts(1, 1, 2, 0)):
    n = counts.objective_achieved + counts.perspective_defeated + counts.round_limit_reached + counts.unsupported_path
    source = request(trials=n)
    completed = counts.round_limit_reached * source.scenario.max_rounds
    return Summary(source, counts, counts.objective_achieved + counts.perspective_defeated + completed,
                   completed + n - counts.round_limit_reached, completed)


class MagicAssessmentTests(unittest.TestCase):
    def test_native_rates_use_all_trials_and_preserve_summary_counters(self):
        source = summary()
        window = Window(F(1, 4), F(1, 3), F(1, 2))
        actual = assess(source.source_request, source, window)
        self.assertIsInstance(actual, MagicCandidateAssessment)
        rates = (actual.objective_achieved_rate, actual.perspective_defeated_rate,
                 actual.round_limit_rate, actual.unsupported_path_rate)
        self.assertEqual(rates, (F(1, 4), F(1, 4), F(1, 2), F(0)))
        self.assertTrue(all(isinstance(rate, F) for rate in rates))
        self.assertEqual(sum(rates), 1)
        self.assertIs(actual.status, Status.ELIGIBLE)
        self.assertIs(actual.window_match, True)
        self.assertIs(actual.summary, source)
        self.assertIs(actual.source_request, source.source_request)
        self.assertIs(actual.window, window)
        self.assertEqual((actual.summary.total_action_count, actual.summary.total_started_round_count,
                          actual.summary.total_completed_round_count), (8, 8, 6))
        self.assertFalse(hasattr(actual, 'side_defeated_rate'))

    def test_inclusive_bounds_point_windows_and_outside_eligibility(self):
        window = Window(F(1, 4), F(1, 2), F(3, 4))
        for achieved, expected in ((0, False), (1, True), (2, True), (3, True), (4, False)):
            value = summary(Counts(achieved, 4 - achieved, 0, 0))
            with self.subTest(achieved=achieved):
                actual = assess(value.source_request, value, window)
                self.assertIs(actual.status, Status.ELIGIBLE)
                self.assertIs(actual.window_match, expected)
        for achieved in (0, 1, 4):
            value = summary(Counts(achieved, 4 - achieved, 0, 0))
            rate = F(achieved, 4)
            self.assertIs(assess(value.source_request, value, Window(rate, rate, rate)).window_match, True)

    def test_unsupported_prevents_window_match_without_filtering_any_rate(self):
        for counts in (Counts(1, 1, 1, 1), Counts(0, 0, 0, 4)):
            value = summary(counts)
            actual = assess(value.source_request, value, Window(F(0), F(1, 2), F(1)))
            with self.subTest(counts=counts):
                self.assertIs(actual.status, Status.UNSUPPORTED_OBSERVATIONS)
                self.assertIsNone(actual.window_match)
                self.assertEqual(actual.objective_achieved_rate, F(counts.objective_achieved, 4))
                self.assertEqual(actual.unsupported_path_rate, F(counts.unsupported_path, 4))
                self.assertEqual(sum((actual.objective_achieved_rate, actual.perspective_defeated_rate,
                                      actual.round_limit_rate, actual.unsupported_path_rate)), 1)
                self.assertIs(actual.summary.outcome_counts, counts)
        self.assertEqual(value.total_action_count, 0)  # all unsupported may have no executed actions
        self.assertEqual((value.total_started_round_count, value.total_completed_round_count), (4, 0))

    def test_all_round_limit_remains_eligible_zero_goal_and_full_denominator(self):
        value = summary(Counts(0, 0, 4, 0))
        actual = assess(value.source_request, value, Window(F(0), F(0), F(0)))
        self.assertEqual((actual.objective_achieved_rate, actual.perspective_defeated_rate,
                          actual.round_limit_rate, actual.unsupported_path_rate), (0, 0, 1, 0))
        self.assertIs(actual.status, Status.ELIGIBLE)
        self.assertIs(actual.window_match, True)

    def test_large_rates_are_compared_exactly_without_float_rounding(self):
        n = 2**60 + 1
        value = summary(Counts(n // 2, n - n // 2, 0, 0))
        actual = assess(value.source_request, value, Window(F(1, 2), F(1, 2), F(1)))
        self.assertEqual(float(actual.objective_achieved_rate), 0.5)
        self.assertLess(actual.objective_achieved_rate, F(1, 2))
        self.assertIs(actual.status, Status.ELIGIBLE)
        self.assertIs(actual.window_match, False)

    def test_shared_window_pickle_paths_and_native_status_identity(self):
        self.assertIs(Window, SharedWindow)
        self.assertEqual(Window.__module__, 'towr.balance.ranged_assessment_models')
        value = summary()
        actual = assess(value.source_request, value, Window(F(0), F(1, 2), F(1)))
        for other in (RangedAssessmentStatus, MeleeAssessmentStatus, MixedAssessmentStatus):
            self.assertEqual(actual.status, other.ELIGIBLE)  # string-valued Enums can compare equal
            self.assertIsNot(Status, other)
            self.assertNotIsInstance(actual.status, other)
        restored = pickle.loads(pickle.dumps(actual))
        self.assertEqual(restored, actual)
        self.assertIs(type(restored.window), SharedWindow)
        self.assertIs(restored.status, Status.ELIGIBLE)

    def test_typed_arguments_reject_other_families_and_full_result(self):
        value = summary()
        full_source = request()
        full_result = NpcMagicSimulationResult(full_source, observations(full_source))
        foreign = (ranged_summary(), melee_summary(), mixed_summary())
        window = Window(F(0), F(1, 2), F(1))
        invalid = ((0, (None, {}, value, value.source_request.scenario, *(s.source_request for s in foreign))),
                   (1, (None, {}, value.outcome_counts, full_result, *foreign)),
                   (2, (None, {}, (F(0), F(1, 2), F(1)), 'window', F(1, 2))))
        for position, values in invalid:
            for wrong in values:
                args = [value.source_request, value, window]
                args[position] = wrong
                with self.subTest(position=position, wrong=type(wrong)), self.assertRaises(TypeError):
                    assess(*args)

    def test_full_source_equality_rejects_same_id_foreign_requests(self):
        value = summary()
        source, scenario = value.source_request, value.source_request.scenario
        wizard = replace(scenario.initial.wizard,
                         caster=replace(scenario.initial.wizard.caster, wizard_level=3))
        changed_level = replace(scenario, initial=replace(scenario.initial, wizard=wizard))
        changed_profile = replace(scenario, actors=tuple(
            replace(actor, willpower_profile=InlineProfile(2, 3)) if actor.actor_id == 'enemy' else actor
            for actor in scenario.actors))
        changed_departures = replace(scenario, scene_frames=tuple(replace(frame, attack_departures=tuple(
            replace(fact, can_leave_zone=False) for fact in frame.attack_departures)) for frame in scenario.scene_frames))
        variants = (replace(source, master_seed=43), replace(source, trials=source.trials + 1),
                    replace(source, scenario=replace(scenario, max_rounds=4)),
                    replace(source, scenario=replace(scenario, activation_order=('ally', 'wizard', 'enemy'))),
                    replace(source, scenario=replace(scenario, actors=tuple(
                        replace(actor, zone_priorities=actor.zone_priorities[::-1])
                        if actor.actor_id == 'wizard' else actor for actor in scenario.actors))),
                    replace(source, scenario=changed_profile), replace(source, scenario=changed_departures),
                    replace(source, scenario=changed_level))
        for foreign in variants:
            with self.subTest(foreign=foreign), self.assertRaises(ValueError):
                self.assertEqual(foreign.scenario.id, scenario.id)
                assess(foreign, value, Window(F(0), F(1, 2), F(1)))

    def test_equal_full_source_copy_is_accepted_without_rebinding_inputs(self):
        value = summary()
        equal_copy = deepcopy(value.source_request)
        self.assertIsNot(equal_copy, value.source_request)
        self.assertIsNot(equal_copy.scenario, value.source_request.scenario)
        actual = assess(equal_copy, value, Window(F(0), F(1, 2), F(1)))
        self.assertIs(actual.source_request, equal_copy)
        self.assertIs(actual.summary, value)
        self.assertIs(actual.summary.source_request, value.source_request)
        self.assertEqual(actual.source_request, actual.summary.source_request)

    def test_frozen_fields_and_derived_values_require_constructor_guards(self):
        value = summary()
        before = deepcopy(value)
        window = Window(F(0), F(1, 2), F(1))
        actual = assess(value.source_request, value, window)
        self.assertEqual(tuple(f.name for f in fields(actual)), ('source_request', 'summary', 'window'))
        self.assertFalse(hasattr(actual, '__dict__'))
        with self.assertRaises(FrozenInstanceError): actual.summary = None
        with self.assertRaises(FrozenInstanceError): window.minimum = F(1)
        for name in ('objective_achieved_rate', 'perspective_defeated_rate', 'round_limit_rate',
                     'unsupported_path_rate', 'status', 'window_match'):
            with self.subTest(name=name), self.assertRaises(TypeError): replace(actual, **{name: False})
        with self.assertRaises(ValueError):
            replace(actual, source_request=replace(value.source_request, master_seed=43))
        with self.assertRaises(TypeError): replace(actual, summary=None)
        self.assertIs(replace(actual, window=Window(F(1), F(1), F(1))).window_match, False)
        self.assertEqual(value, before)

    def test_pure_assessment_executes_no_rng_runner_pool_or_json_and_retains_no_records(self):
        value = summary()
        with ExitStack() as stack:
            for target in ('random.Random', 'towr.simulation.npc_magic_simulation.Random',
                           'towr.simulation.npc_magic_simulation.run_npc_magic_simulation',
                           'towr.simulation.npc_magic_parallel.run_npc_magic_simulation_parallel',
                           'towr.engine.npc_magic_scenario_runner.run_npc_magic_scenario',
                           'concurrent.futures.ProcessPoolExecutor', 'json.loads'):
                stack.enter_context(patch(target, side_effect=AssertionError('assessment must stay pure')))
            actual = assess(value.source_request, value, Window(F(0), F(1, 2), F(1)))
            self.assertIs(actual.window_match, True)
        pending, seen = [actual], set()
        while pending:
            item = pending.pop()
            if id(item) in seen: continue
            seen.add(id(item))
            self.assertNotIsInstance(item, (NpcMagicSimulationResult, NpcMagicTrialRecord, NpcMagicScenarioResult))
            if is_dataclass(item): pending.extend(getattr(item, f.name) for f in fields(item))
            elif isinstance(item, (tuple, list)): pending.extend(item)
