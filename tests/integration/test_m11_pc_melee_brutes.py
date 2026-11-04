"""Static profile Brutes reach ordinary party trials and fixed-party search."""
from copy import deepcopy
from fractions import Fraction
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_mixed_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.application.pc_melee_balance import evaluate_pc_melee_balance
from towr.application.pc_melee_balance_models import (
    PcMeleeBalanceRequest, PcMeleeCompositionGroup, project_pc_melee_candidate,
)
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def mixed_victory_rng(seed):
    # PC1 defeats the Minion, PC2 Wounds the Brute; it attacks/misses,
    # then PC1 inflicts its final Wound next round. Literal actual d10s.
    return ScriptedD10([1,1,1,10,10]
        + [1,1,1,1,10,10]
        + [10,10,1,1,1]
        + [1,1,1,1,10,10])


def balance_source():
    scenario = make_pc_melee_mixed_scenario(minion_count=2,brute_count=1,
        brute_wound_limit=2,max_rounds=3)
    return PcMeleeBalanceRequest(scenario,(
        PcMeleeCompositionGroup('minions',('minion2','minion1'),0,2),
        PcMeleeCompositionGroup('brutes',('brute1',),1,1)),
        deepcopy(scenario.facts),42,2,3,6,
        ObjectiveRateWindow(Fraction(0),Fraction(1,2),Fraction(1)),2)


class PcMeleeBruteIntegrationTests(unittest.TestCase):
    def test_actual_mixed_victory_and_real_spawn_preserve_full_sources_and_observations(self):
        request = PcMeleeSimulationRequest(make_pc_melee_mixed_scenario(
            brute_wound_limit=2,max_rounds=2),42,3)
        original = deepcopy(request)
        sequential = run_pc_melee_simulation(request,rng_factory=mixed_victory_rng)
        parallel = run_pc_melee_simulation_parallel(request,workers=2,batch_size=2,
            rng_factory=mixed_victory_rng)
        self.assertEqual(sequential,parallel)
        self.assertEqual(request,original)
        self.assertEqual(sequential.outcome_counts.objective_achieved,3)
        self.assertEqual(sequential.total_action_count,12)
        self.assertEqual(sequential.total_started_round_count,6)
        self.assertEqual(sequential.total_completed_round_count,3)
        self.assertEqual(summarize_pc_melee_simulation(sequential),summarize_pc_melee_simulation(parallel))
        self.assertTrue(all(record.defeated_pc_ids == () for record in sequential.records))

    def test_count_projection_keeps_profile_type_limit_and_all_party_sources(self):
        source = balance_source()
        original = deepcopy(source)
        for counts,ids in (((0,1),('brute1',)),((1,1),('minion2','brute1')),
                           ((2,1),('minion1','minion2','brute1'))):
            with self.subTest(counts=counts):
                scenario = project_pc_melee_candidate(source,counts).scenario
                self.assertEqual(tuple(enemy.state.actor_id for enemy in scenario.enemies),ids)
                brute = scenario.enemy('brute1')
                self.assertIs(brute.definition.injury_policy,TargetInjuryPolicy.BRUTE)
                self.assertEqual(brute.definition.wound_limit,2)
                self.assertEqual(brute.state.injury.wound_limit,2)
                self.assertEqual(brute,source.template.enemy('brute1'))
                self.assertEqual(scenario.pc_activation_order,source.template.pc_activation_order)
                self.assertEqual(scenario.enemy_target_priority,source.template.enemy_target_priority)
                for member,expected in zip(scenario.party,source.template.party):
                    self.assertEqual(member.pc,expected.pc)
                    self.assertEqual(member.fate,expected.fate)
                    self.assertEqual(tuple(item.target_id for item in member.defeat_decisions),member.target_priority)
        self.assertEqual(source,original)

    def test_actual_mixed_count_search_has_complete_aggregate_only_report(self):
        source = balance_source()
        result = evaluate_pc_melee_balance(source,
            lambda request: summarize_pc_melee_simulation(run_pc_melee_simulation(request)))
        self.assertEqual((result.candidate_count,result.planned_trials,result.total_trials),(3,6,6))
        self.assertEqual(tuple(candidate.counts for candidate in result.candidates),((0,1),(1,1),(2,1)))
        for candidate in result.candidates:
            self.assertEqual(candidate.summary.source_request,candidate.source_request)
            self.assertFalse(hasattr(candidate.summary,'steps'))
            self.assertFalse(hasattr(candidate.summary,'records'))
            if candidate.summary.outcome_counts.unsupported_path:
                self.assertNotIn(candidate.candidate_id,result.selected_candidate_ids)


if __name__ == '__main__':
    unittest.main()
