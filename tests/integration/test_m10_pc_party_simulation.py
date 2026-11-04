"""One shared party battle reaches trials, aggregates and fixed-party search."""
from copy import deepcopy
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from tests.support.pc_melee_scripted import ScriptedD10, party_casualty_script, party_casualty_source
from tests.unit.test_m9_pc_melee_balance import request as balance_request
from towr.application.pc_melee_balance import evaluate_pc_melee_balance
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class PcPartySimulationIntegrationTests(unittest.TestCase):
    def test_completed_casualty_in_a_continuing_actual_battle_reaches_the_aggregate(self):
        source = PcMeleeSimulationRequest(party_casualty_source(),42,1)
        streams = []
        def fresh(seed):
            rng = ScriptedD10(party_casualty_script())
            streams.append(rng)
            return rng
        result = run_pc_melee_simulation(source,rng_factory=fresh)
        streams[0].assert_exhausted()
        self.assertEqual(result.records[0].defeated_pc_ids,('pc1',))
        self.assertEqual(result.records[0].executed_actions,10)
        summary = summarize_pc_melee_simulation(result)
        self.assertEqual(summary.outcome_counts.round_limit,1)
        self.assertEqual(summary.outcome_counts.party_defeated,0)
        self.assertEqual(summary.any_pc_defeated_count,1)
        self.assertEqual(tuple(item.count for item in summary.pc_defeat_counts),(1,0))

    def test_real_party_spawn_has_identical_sources_seeds_outcomes_and_loss_observations(self):
        source = PcMeleeSimulationRequest(make_pc_melee_party_scenario(enemy_count=3,max_rounds=4),42,5)
        before = deepcopy(source)
        sequential = run_pc_melee_simulation(source)
        parallel = run_pc_melee_simulation_parallel(source,workers=2,batch_size=3)
        self.assertEqual(parallel,sequential)
        summary = summarize_pc_melee_simulation(sequential)
        self.assertEqual(summarize_pc_melee_simulation(parallel),summary)
        self.assertEqual(source,before)
        self.assertEqual(tuple(item.actor_id for item in summary.pc_defeat_counts),('pc1','pc2'))
        self.assertEqual(summary.any_pc_defeated_count,
            sum(bool(record.defeated_pc_ids) for record in sequential.records))
        for item in summary.pc_defeat_counts:
            self.assertEqual(item.count,sum(item.actor_id in record.defeated_pc_ids for record in sequential.records))

    def test_actual_count_search_keeps_whole_party_and_only_aggregate_observations(self):
        source = balance_request(template=make_pc_melee_party_scenario(enemy_count=2,max_rounds=3),trials=3)
        before = deepcopy(source)
        result = evaluate_pc_melee_balance(source,
            lambda candidate: summarize_pc_melee_simulation(run_pc_melee_simulation(candidate)))
        self.assertEqual(result.total_trials,6)
        self.assertEqual(source,before)
        for candidate in result.candidates:
            scenario = candidate.source_request.scenario
            self.assertEqual(tuple(member.actor_id for member in scenario.party),('pc1','pc2'))
            self.assertEqual(scenario.enemy_target_priority,source.template.enemy_target_priority)
            self.assertEqual(candidate.summary.trials,3)
            self.assertFalse(hasattr(candidate.summary,'state'))
            self.assertFalse(hasattr(candidate.summary,'records'))
            if candidate.summary.outcome_counts.unsupported_path:
                self.assertNotIn(candidate.candidate_id,result.selected_candidate_ids)


if __name__ == '__main__':
    unittest.main()
