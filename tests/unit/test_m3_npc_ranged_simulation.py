from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_m2_npc_ranged_scenario import scenario
from towr.domain.npc_ranged_scenario_result_models import NpcRangedScenarioOutcome as Outcome, NpcRangedScenarioResult
from towr.domain.npc_rounds_chain_summary_models import NpcRoundsChainSummary
from towr.engine.npc_rounds_runner import run_npc_rounds
from towr.simulation.npc_ranged_models import (
    NpcRangedOutcomeCounts, NpcRangedSimulationRequest, NpcRangedSimulationResult,
    NpcRangedTrialSummary, npc_ranged_trial_seed,
)
from towr.simulation import npc_ranged_simulation as simulation


def request(trials=4):
    source = scenario(sizes=(1, 1))
    return NpcRangedSimulationRequest(replace(source, initial=replace(source.initial, max_rounds=1)), 42, trials)


def observations(source):
    return tuple(NpcRangedTrialSummary(index, source.seed_for(index), outcome, attacks, 1)
                 for index, (outcome, attacks) in enumerate((
                     (Outcome.OBJECTIVE_ACHIEVED, 1), (Outcome.SIDE_DEFEATED, 2),
                     (Outcome.ROUND_LIMIT, 2), (Outcome.UNSUPPORTED_PATH, 0))))


class M3NpcRangedSimulationTests(unittest.TestCase):
    def test_seed_v1_golden_vectors_and_prefix_independence(self):
        # Public compatibility vectors for the versioned byte encoding, not Monte Carlo expectations.
        for seed, index, expected in (
            (0, 0, "fd3e0c219d02adf86b0f5f73f643c564dfe3d3cca315f0fadab9125926c3c385"),
            (42, 7, "cd435132d433d5eb4614dca418e939c43c36cccedb4ebd3a41840a179e6e3f07"),
            (2**64-1, 2**64-1, "41911f1f2c441aa6589ca9875c8e0f5e05b280bb26e1b2d8f9e2095bf3333a63"),
        ):
            with self.subTest(seed=seed, index=index):
                self.assertEqual(npc_ranged_trial_seed(seed, index), int(expected, 16))
        source = request()
        self.assertEqual(source.seed_for(3), replace(source, trials=9).seed_for(3))
        self.assertNotEqual(source.seed_for(0), source.seed_for(1))
        self.assertNotEqual(source.seed_for(0), replace(source, master_seed=43).seed_for(0))

    def test_request_and_index_validation_happen_before_rng_creation(self):
        source = request()
        for name in ("master_seed", "trials"):
            for value in (-1, 2**64, True, False, 1.2, "1", None):
                with self.subTest(name=name, value=value), self.assertRaises((TypeError, ValueError)):
                    replace(source, **{name: value})
        with self.assertRaises(ValueError):
            replace(source, trials=0)
        with self.assertRaises(TypeError):
            replace(source, scenario=None)
        factory = Mock()
        for index in (-1, source.trials, 2**64, True, 1.2, None):
            with self.subTest(index=index), self.assertRaises((ValueError, TypeError)):
                simulation.run_npc_ranged_trial(source, index, rng_factory=factory)
        with self.assertRaises(TypeError):
            simulation.run_npc_ranged_simulation(None, rng_factory=factory)
        with self.assertRaises(TypeError):
            simulation.run_npc_ranged_trial(None, 0, rng_factory=factory)
        factory.assert_not_called()

    def test_aggregates_four_outcomes_separately_and_normalizes_record_order(self):
        source = request()
        records = list(observations(source)[::-1])
        result = NpcRangedSimulationResult(source, records)
        records.clear()
        self.assertEqual(result.trials, observations(source))
        self.assertEqual(result.outcome_counts, NpcRangedOutcomeCounts(1, 1, 1, 1))
        self.assertEqual(result.total_attack_count, 5)
        self.assertEqual(result.total_visited_round_count, 4)
        self.assertEqual(result.mean_attack_count, 1.25)
        self.assertEqual(result.mean_visited_round_count, 1.0)
        with self.assertRaises(FrozenInstanceError):
            result.trials = ()
        with self.assertRaises(FrozenInstanceError):
            result.trials[0].seed = 0

    def test_rejects_missing_duplicate_foreign_records_and_inconsistent_budget(self):
        source = request()
        records = observations(source)
        for invalid in (records[:-1], (*records, records[0]), (records[0], *records[:-1]),
                        (replace(records[0], seed=0), *records[1:]),
                        (replace(records[0], trial_index=8), *records[1:]),
                        (replace(records[0], executed_attack_count=3), *records[1:]),
                        (replace(records[0], visited_round_count=2), *records[1:])):
            with self.subTest(records=invalid), self.assertRaises(ValueError):
                NpcRangedSimulationResult(source, invalid)
        longer = replace(source, scenario=replace(source.scenario, initial=replace(source.scenario.initial, max_rounds=2)))
        with self.assertRaisesRegex(ValueError, "ROUND_LIMIT"):
            NpcRangedSimulationResult(longer, records)
        with self.assertRaises(TypeError):
            NpcRangedSimulationResult(None, records)
        with self.assertRaises(TypeError):
            NpcRangedSimulationResult(source, (None,) * 4)

    def test_trial_and_counter_contracts_reject_invalid_types_and_impossible_terminal(self):
        record = observations(request())[0]
        for name, value in (("outcome", "round_limit"), ("seed", True), ("seed", -1), ("seed", 2**256),
                            ("executed_attack_count", True), ("executed_attack_count", -1),
                            ("executed_attack_count", 0), ("visited_round_count", 0), ("visited_round_count", 1.5)):
            with self.subTest(name=name, value=value), self.assertRaises((TypeError, ValueError)):
                replace(record, **{name: value})
        with self.assertRaises(ValueError):
            NpcRangedOutcomeCounts(0, -1, 0, 0)

    def test_genuine_unsupported_stop_is_counted_separately(self):
        source = request(1)
        provider = Mock()
        provider.get_candidates.side_effect = lambda context, spatial: context
        blocked = run_npc_rounds(source.scenario.initial, provider, Mock(), Mock())
        stopped = NpcRangedScenarioResult(source.scenario, NpcRoundsChainSummary((blocked,)))
        with patch.object(simulation, "run_npc_ranged_scenario", return_value=stopped):
            result = simulation.run_npc_ranged_simulation(source, rng_factory=Mock())
        self.assertEqual(result.outcome_counts, NpcRangedOutcomeCounts(0, 0, 0, 1))
        self.assertEqual(result.total_attack_count, 0)
        self.assertEqual(result.total_visited_round_count, 1)

    def test_execution_error_stops_batch_without_returning_partial_success(self):
        source = request(3)
        first_rng = SequenceRandom([1, 2, 10, 10, 10, 10])
        factory = Mock(side_effect=[first_rng, RuntimeError("RNG unavailable"), Mock()])
        with self.assertRaisesRegex(RuntimeError, "RNG unavailable"):
            simulation.run_npc_ranged_simulation(source, rng_factory=factory)
        self.assertEqual(factory.call_count, 2)
        rng = Mock()
        rng.randint.side_effect = RuntimeError("broken dice")
        with self.assertRaisesRegex(RuntimeError, "broken dice"):
            simulation.run_npc_ranged_trial(source, 0, rng_factory=lambda seed: rng)

    def test_wrong_runner_source_or_result_type_is_not_aggregated(self):
        source = request(1)
        other = scenario(sizes=(2, 1))
        foreign = simulation.run_npc_ranged_scenario(other, SequenceRandom([1, 2, 10, 10, 10, 10]))
        for value, exception in ((foreign, ValueError), (None, TypeError)):
            with patch.object(simulation, "run_npc_ranged_scenario", return_value=value):
                with self.assertRaises(exception):
                    simulation.run_npc_ranged_simulation(source)
