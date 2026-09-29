from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
import unittest
from unittest.mock import patch

from tests.unit.test_m7_npc_mixed_simulation import request, observations
from towr.domain.npc_mixed_scenario_result_models import NpcMixedScenarioOutcome as Outcome
from towr.domain.npc_mixed_scenario_result_models import NpcMixedScenarioResult
from towr.domain.npc_rounds_chain_summary_models import NpcRoundsChainSummary
from towr.simulation.npc_mixed_models import (
    NpcMixedOutcomeCounts, NpcMixedSimulationResult, NpcMixedTrialSummary,
)
from towr.simulation.npc_mixed_summary import summarize_npc_mixed_simulation as summarize
from towr.simulation.npc_mixed_summary_models import NpcMixedSimulationSummary as Summary


def source_with_budget(budget=3):
    source = request()
    return replace(source, scenario=replace(source.scenario,
        initial=replace(source.scenario.initial, max_rounds=budget)))


class M7MixedSummaryTests(unittest.TestCase):
    def test_projection_preserves_all_outcomes_source_and_existing_means(self):
        source = source_with_budget()
        records = tuple(replace(item, visited_round_count=3) if item.outcome is Outcome.ROUND_LIMIT
                        else item for item in observations(source))
        result = NpcMixedSimulationResult(source, records)
        summary = summarize(result)
        self.assertFalse(hasattr(summary, '__dict__'))
        self.assertIs(summary.source_request, source)
        self.assertEqual(summary.outcome_counts, NpcMixedOutcomeCounts(1, 1, 1, 1))
        self.assertEqual((summary.trials, summary.total_attack_count, summary.total_visited_round_count), (4, 5, 6))
        self.assertEqual(summary.mean_attack_count, result.mean_attack_count)
        self.assertEqual(summary.mean_visited_round_count, result.mean_visited_round_count)
        self.assertEqual((summary.mean_attack_count, summary.mean_visited_round_count), (1.25, 1.5))

    def test_inputs_and_summary_are_frozen_and_means_cannot_be_supplied(self):
        source = request()
        result = NpcMixedSimulationResult(source, observations(source))
        before = deepcopy(result)
        summary = summarize(result)
        for field, value in (("total_attack_count", 0), ("source_request", None)):
            with self.subTest(field=field), self.assertRaises(FrozenInstanceError):
                setattr(summary, field, value)
        with self.assertRaises(FrozenInstanceError):
            summary.outcome_counts.round_limit = 0
        for field in ("trials", "mean_attack_count", "mean_visited_round_count"):
            with self.subTest(field=field), self.assertRaises(TypeError):
                replace(summary, **{field: 99})
        self.assertEqual(result, before)

    def test_summary_does_not_retain_result_or_any_trial_records(self):
        source = request()
        result = NpcMixedSimulationResult(source, observations(source))
        pending = [summarize(result)]
        seen = set()
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

    def test_projection_never_executes_rng_runner_or_pool(self):
        source = request()
        result = NpcMixedSimulationResult(source, observations(source))
        with patch("towr.simulation.npc_mixed_simulation.run_npc_mixed_simulation", side_effect=AssertionError), \
                patch("towr.engine.npc_mixed_scenario_runner.run_npc_mixed_scenario", side_effect=AssertionError), \
                patch("random.Random", side_effect=AssertionError), \
                patch("concurrent.futures.ProcessPoolExecutor", side_effect=AssertionError):
            self.assertEqual(summarize(result), summarize(result))

    def test_projection_and_constructor_require_typed_sources_and_counts(self):
        source = request()
        for value in (None, {}, source, observations(source)):
            with self.subTest(value=type(value)), self.assertRaises(TypeError):
                summarize(value)
        for value in (None, {}, source.scenario):
            with self.subTest(value=type(value)), self.assertRaises(TypeError):
                Summary(value, NpcMixedOutcomeCounts(1, 1, 1, 1), 5, 4)
        with self.assertRaises(TypeError):
            Summary(source, (1, 1, 1, 1), 5, 4)

    def test_counts_and_totals_reject_missing_trials_and_numeric_coercion(self):
        valid = Summary(request(), NpcMixedOutcomeCounts(1, 1, 1, 1), 5, 4)
        for counts in (NpcMixedOutcomeCounts(0, 0, 0, 0), NpcMixedOutcomeCounts(1, 1, 1, 0),
                       NpcMixedOutcomeCounts(1, 1, 1, 2)):
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                replace(valid, outcome_counts=counts)
        for name in ("total_attack_count", "total_visited_round_count"):
            for value in (-1, True, False, 4.0, "4", None, float("nan"), float("inf")):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    replace(valid, **{name: value})

    def test_round_bounds_include_full_budget_for_each_round_limit(self):
        valid = Summary(source_with_budget(), NpcMixedOutcomeCounts(1, 1, 1, 1), 2, 6)
        self.assertEqual(replace(valid, total_visited_round_count=12).mean_visited_round_count, 3)
        for rounds in (0, 4, 5, 13):
            with self.subTest(rounds=rounds), self.assertRaises(ValueError):
                replace(valid, total_visited_round_count=rounds)
        self.assertEqual(Summary(valid.source_request, NpcMixedOutcomeCounts(0, 0, 4, 0), 0, 12).trials, 4)
        with self.assertRaises(ValueError):
            Summary(valid.source_request, NpcMixedOutcomeCounts(0, 0, 4, 0), 0, 11)

    def test_attack_bounds_preserve_zero_unsupported_and_terminal_minimum(self):
        source = source_with_budget()
        counts = NpcMixedOutcomeCounts(1, 1, 1, 1)
        self.assertEqual(Summary(source, counts, 2, 6).total_attack_count, 2)
        self.assertEqual(Summary(source, counts, 18, 6).total_attack_count, 18)
        for attacks in (0, 1, 19):
            with self.subTest(attacks=attacks), self.assertRaises(ValueError):
                Summary(source, counts, attacks, 6)
        unsupported = Summary(source, NpcMixedOutcomeCounts(0, 0, 0, 4), 0, 4)
        self.assertEqual((unsupported.mean_attack_count, unsupported.mean_visited_round_count), (0, 1))

    def test_source_is_part_of_summary_identity_and_replace_rechecks_budget(self):
        source = request()
        summary = summarize(NpcMixedSimulationResult(source, observations(source)))
        other_source = replace(source, master_seed=43)
        other = summarize(NpcMixedSimulationResult(other_source, observations(other_source)))
        self.assertNotEqual(summary, other)
        self.assertIs(other.source_request, other_source)
        with self.assertRaises(ValueError):
            replace(summary, source_request=replace(source, trials=5))
        with self.assertRaises(ValueError):
            replace(summary, source_request=source_with_budget())
