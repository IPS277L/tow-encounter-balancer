"""Heavy PC injuries remain real game results through trials/balance/process."""
from fractions import Fraction
import unittest

from tests.support.pc_heavy_scenarios import (
    critical_encounter_source, critical_death_rng, forced_wound_rng, indexed_critical_rng,
)
from towr.application.pc_melee_balance import evaluate_pc_melee_balance
from towr.application.pc_melee_balance_models import PcMeleeBalanceRequest, PcMeleeCompositionGroup
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.attack_models import ImpactOutcome
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_result_models import PcAttackProof, PcMeleeOutcome
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class PcHeavyWoundIntegrationTests(unittest.TestCase):
    def test_failed_critical_test_then_actual_low_damage_unopposed_wound_keeps_player_lifecycle(self):
        rng = forced_wound_rng(0)
        result = run_pc_melee_scenario(critical_encounter_source(),rng)
        rng.assert_exhausted()
        self.assertIs(result.outcome,PcMeleeOutcome.PARTY_DEFEATED)
        self.assertEqual((result.executed_actions,result.started_rounds,result.completed_rounds),(6,2,1))
        proof = next(step.proof for step in result.steps if isinstance(step.proof,PcAttackProof)
            and step.source.round_state.round_number == 2 and step.proof.request.actor_id == 'minion2')
        attack = proof.execution.resolution.attack
        self.assertIs(attack.impact,ImpactOutcome.STAGGERED)
        self.assertEqual((attack.damage,attack.effective_resilience),(4,6))
        self.assertIsNone(attack.defender_test)
        self.assertIsNone(proof.fate_decline)
        self.assertIsNotNone(proof.execution.resolution.pending_character_wound)
        member = result.state.participant('pc')
        self.assertEqual(tuple(wound.table_total for wound in member.injury.wounds),(1,14,25))
        self.assertEqual(member.daily_wounds.wound_count,3)
        self.assertEqual(member.fate,result.source.party[0].fate)

    def test_failed_critical_test_on_empty_incapacity_turn_dies_without_a_new_wound(self):
        rng = critical_death_rng(0)
        result = run_pc_melee_scenario(critical_encounter_source(),rng)
        rng.assert_exhausted()
        self.assertIs(result.outcome,PcMeleeOutcome.PARTY_DEFEATED)
        self.assertEqual((result.executed_actions,result.started_rounds,result.completed_rounds),(8,3,2))
        self.assertFalse(any(isinstance(step.proof,PcAttackProof)
            and step.source.round_state.round_number == 3 for step in result.steps))
        member = result.state.participant('pc')
        self.assertTrue(member.injury.dead)
        self.assertTrue(member.injury.conditions.has(Condition.DEFENCELESS))
        self.assertEqual(tuple(wound.table_total for wound in member.injury.wounds),(1,14))
        self.assertEqual(member.daily_wounds.wound_count,2)
        self.assertEqual(result.defeated_pc_ids,('pc',))

    def test_actual_heavy_trials_real_spawn_and_aggregate_only_search_preserve_both_death_sources(self):
        source = critical_encounter_source()
        request = PcMeleeSimulationRequest(source,42,2)
        sequential = run_pc_melee_simulation(request,rng_factory=indexed_critical_rng)
        process = run_pc_melee_simulation_parallel(request,workers=2,batch_size=1,
            rng_factory=indexed_critical_rng)
        self.assertEqual(process,sequential)
        self.assertEqual((sequential.total_action_count,sequential.total_started_round_count,
            sequential.total_completed_round_count),(14,5,3))
        summary = summarize_pc_melee_simulation(sequential)
        self.assertEqual(summary.outcome_counts.party_defeated,2)
        self.assertEqual(summary.outcome_counts.unsupported_path,0)
        self.assertEqual(summary.any_pc_defeated_count,2)
        self.assertEqual(tuple(item.count for item in summary.pc_defeat_counts),(2,))
        balance = PcMeleeBalanceRequest(source,(
            PcMeleeCompositionGroup('minions',('minion1','minion2','minion3'),3,3),),
            source.facts,42,2,1,2,ObjectiveRateWindow(Fraction(0),Fraction(1,2),Fraction(1)),1)
        result = evaluate_pc_melee_balance(balance,lambda candidate:summarize_pc_melee_simulation(
            run_pc_melee_simulation(candidate,rng_factory=indexed_critical_rng)))
        self.assertEqual(result.total_trials,2)
        self.assertEqual(result.candidates[0].summary.outcome_counts,summary.outcome_counts)
        self.assertEqual(result.candidates[0].assessment.party_defeated_rate,Fraction(1))
        self.assertFalse(hasattr(result.candidates[0].summary,'records'))


if __name__ == '__main__':
    unittest.main()
