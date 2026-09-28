from copy import deepcopy
from functools import partial
import unittest

from tests.integration.test_m3_npc_ranged_parallel import exact_rng
from tests.unit.test_m2_npc_ranged_scenario import scenario
from towr.simulation.npc_ranged_models import NpcRangedSimulationRequest
from towr.simulation.npc_ranged_parallel import run_npc_ranged_simulation_parallel
from towr.simulation.npc_ranged_simulation import run_npc_ranged_simulation
from towr.simulation.npc_ranged_summary import summarize_npc_ranged_simulation as summarize


class M3RangedSummaryIntegrationTests(unittest.TestCase):
    def test_real_sequential_and_spawn_project_identical_aggregates(self):
        source = NpcRangedSimulationRequest(scenario(sizes=(1, 1)), 123, 3)
        before = deepcopy(source)
        factory = partial(exact_rng, seeds=tuple(source.seed_for(i) for i in range(source.trials)))
        sequential = run_npc_ranged_simulation(source, rng_factory=factory)
        process = run_npc_ranged_simulation_parallel(source, workers=2, batch_size=2, rng_factory=factory)
        actual = summarize(process)
        self.assertEqual(actual, summarize(sequential))
        self.assertIs(actual.source_request, source)
        self.assertEqual(actual.outcome_counts, sequential.outcome_counts)
        self.assertEqual((actual.outcome_counts.objective_achieved, actual.outcome_counts.side_defeated,
                          actual.outcome_counts.round_limit, actual.outcome_counts.unsupported_path), (1, 1, 1, 0))
        self.assertEqual(actual.mean_attack_count, sequential.mean_attack_count)
        self.assertEqual(actual.mean_visited_round_count, sequential.mean_visited_round_count)
        self.assertEqual(source, before)
