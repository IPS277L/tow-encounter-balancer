"""ADR-0038 aggregate-only projection and necessary arithmetic bounds."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
import unittest
from unittest.mock import patch

from tests.unit.test_m8_npc_magic_simulation_models import observations, request
from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult
from towr.simulation.npc_magic_models import (
    NpcMagicOutcomeCounts as Counts, NpcMagicSimulationResult, NpcMagicTrialRecord,
)
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation as summarize
from towr.simulation.npc_magic_summary_models import NpcMagicSimulationSummary as Summary


def summary():
    source = request()
    return summarize(NpcMagicSimulationResult(source, observations(source)))


class MagicSimulationSummaryTests(unittest.TestCase):
    def test_projection_preserves_full_request_all_outcomes_and_three_totals(self):
        source = request()
        result = NpcMagicSimulationResult(source, observations(source))
        before = deepcopy(result)
        aggregate = summarize(result)
        self.assertIs(aggregate.source_request, source)
        self.assertEqual(aggregate.outcome_counts, Counts(1, 1, 1, 1))
        self.assertEqual((aggregate.trials, aggregate.total_action_count, aggregate.total_started_round_count,
                          aggregate.total_completed_round_count), (4, 6, 6, 4))
        self.assertEqual(result, before)

    def test_aggregate_only_fields_and_no_nested_records_results_or_journals(self):
        aggregate = summary()
        self.assertEqual(tuple(f.name for f in fields(aggregate)), ('source_request', 'outcome_counts',
            'total_action_count', 'total_started_round_count', 'total_completed_round_count'))
        pending, seen = [aggregate], set()
        while pending:
            value = pending.pop()
            if id(value) in seen: continue
            seen.add(id(value))
            self.assertNotIsInstance(value, (NpcMagicSimulationResult, NpcMagicTrialRecord, NpcMagicScenarioResult))
            if is_dataclass(value): pending.extend(getattr(value, f.name) for f in fields(value))
            elif isinstance(value, (tuple, list)): pending.extend(value)
        self.assertFalse(hasattr(aggregate, 'mean_action_count'))
        self.assertFalse(hasattr(aggregate, 'objective_rate'))

    def test_projection_never_calls_engine_rng_batch_or_process_pool(self):
        source = request()
        result = NpcMagicSimulationResult(source, observations(source))
        with patch('towr.engine.npc_magic_scenario_runner.run_npc_magic_scenario', side_effect=AssertionError), \
                patch('towr.simulation.npc_magic_simulation.run_npc_magic_simulation', side_effect=AssertionError), \
                patch('random.Random', side_effect=AssertionError), \
                patch('concurrent.futures.ProcessPoolExecutor', side_effect=AssertionError):
            self.assertEqual(summarize(result), summarize(result))

    def test_constructor_and_projection_require_exact_magic_families(self):
        from tests.unit.test_m7_npc_mixed_simulation import request as mixed_request, observations as mixed_observations
        from towr.simulation.npc_mixed_models import NpcMixedSimulationResult
        source = request()
        foreign_request = mixed_request()
        foreign = NpcMixedSimulationResult(foreign_request, mixed_observations(foreign_request))
        for value in (None, {}, source, observations(source), foreign):
            with self.subTest(type=type(value)), self.assertRaises(TypeError): summarize(value)
        for value in (None, {}, source.scenario, foreign_request):
            with self.subTest(source=type(value)), self.assertRaises(TypeError):
                Summary(value, Counts(1, 1, 1, 1), 6, 6, 4)
        for value in (None, (1, 1, 1, 1), foreign.outcome_counts):
            with self.subTest(counts=type(value)), self.assertRaises(TypeError):
                Summary(source, value, 6, 6, 4)

    def test_counts_must_account_for_every_trial_including_unsupported(self):
        valid = summary()
        for counts in (Counts(0, 0, 0, 0), Counts(1, 1, 1, 0), Counts(1, 1, 1, 2)):
            with self.subTest(counts=counts), self.assertRaises(ValueError): replace(valid, outcome_counts=counts)
        unsupported = Summary(request(), Counts(0, 0, 0, 4), 0, 4, 0)
        self.assertEqual((unsupported.trials, unsupported.outcome_counts.unsupported_path), (4, 4))

    def test_totals_reject_bool_float_string_null_and_negative(self):
        valid = summary()
        for name in ('total_action_count', 'total_started_round_count', 'total_completed_round_count'):
            for value in (True, False, 1.0, '1', None, float('nan'), float('inf')):
                with self.subTest(name=name, value=value), self.assertRaises(TypeError):
                    replace(valid, **{name: value})
            with self.assertRaises(ValueError): replace(valid, **{name: -1})

    def test_started_completed_and_action_bounds_reject_inconsistent_aggregates(self):
        valid = summary()
        for changes in ({'total_started_round_count': 5}, {'total_started_round_count': 13},
                        {'total_completed_round_count': 2}, {'total_completed_round_count': 7},
                        {'total_started_round_count': 7, 'total_completed_round_count': 3},
                        {'total_action_count': 3},
                        {'total_action_count': 4, 'total_completed_round_count': 3},
                        {'total_action_count': 19}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): replace(valid, **changes)

    def test_all_limit_trials_require_full_rounds_and_at_least_one_action_per_round(self):
        source = request()
        valid = Summary(source, Counts(0, 0, 4, 0), 12, 12, 12)
        self.assertEqual(valid.trials, 4)
        for changes in ({'total_started_round_count': 11, 'total_completed_round_count': 11},
                        {'total_completed_round_count': 11}, {'total_action_count': 11}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): replace(valid, **changes)
        self.assertEqual(replace(valid, total_action_count=36).total_action_count, 36)

    def test_terminal_counts_add_to_round_limit_minimum_actions(self):
        source = request()
        # Two completed limit runs need 6 actions, and each terminal run needs one.
        valid = Summary(source, Counts(1, 1, 2, 0), 8, 8, 6)
        with self.assertRaises(ValueError): replace(valid, total_action_count=7)
        self.assertEqual(valid.total_action_count, 8)

    def test_full_source_is_identity_and_replacement_rechecks_source_budget(self):
        valid = summary()
        renamed = replace(valid, source_request=replace(valid.source_request, master_seed=43))
        self.assertNotEqual(valid, renamed)
        with self.assertRaises(ValueError):
            replace(valid, source_request=replace(valid.source_request, trials=5))
        with self.assertRaises(ValueError):
            replace(valid, source_request=replace(valid.source_request,
                scenario=replace(valid.source_request.scenario, max_rounds=4)))

    def test_summary_is_frozen_slotted_and_trials_cannot_be_supplied(self):
        valid = summary()
        self.assertFalse(hasattr(valid, '__dict__'))
        for field in fields(valid):
            with self.assertRaises(FrozenInstanceError): setattr(valid, field.name, getattr(valid, field.name))
        with self.assertRaises(TypeError): replace(valid, trials=4)
