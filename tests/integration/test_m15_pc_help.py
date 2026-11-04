"""Help is a real action and an exact allied Test bonus, across trials/search."""
from copy import deepcopy
from fractions import Fraction
from random import Random
import unittest
from unittest.mock import patch

from tests.support.pc_help_scenarios import active_help_source
from towr.application.pc_melee_balance import evaluate_pc_melee_balance
from towr.application.pc_melee_balance_models import PcMeleeBalanceRequest,PcMeleeCompositionGroup
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.pc_melee_result_models import PcHelpProof,PcAttackProof
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class PcHelpIntegrationTests(unittest.TestCase):
    def test_trials_count_actual_help_and_apply_exact_earlier_ally_receipts(self):
        source = active_help_source()
        request = PcMeleeSimulationRequest(source,42,4)
        batch = run_pc_melee_simulation(request)
        applied = 0
        for record in batch.records:
            native = run_pc_melee_scenario(source,Random(record.seed))
            helpers = []
            for step in native.steps:
                if isinstance(step.proof,PcHelpProof):
                    helpers.append(step.proof)
                elif isinstance(step.proof,PcAttackProof):
                    for application in step.proof.help_applications:
                        self.assertIn(application.source_request.help,[proof.execution for proof in helpers])
                        self.assertEqual(application.source_request.beneficiary_id,step.proof.request.actor_id)
                        self.assertEqual(application.source_request.test.id,
                            step.proof.execution.resolution.attack.attacker_test.trace.request_id)
                        applied += 1
            for member,count in zip(source.party,record.help_action_counts,strict=True):
                self.assertEqual(count.count,sum(proof.request.actor_id==member.actor_id for proof in helpers))
            self.assertEqual(native.source,source)
        self.assertGreater(applied,0)
        summary = summarize_pc_melee_simulation(batch)
        self.assertGreater(summary.total_help_action_count,0)
        self.assertEqual(summary.help_action_counts[1].count,0)
        self.assertTrue(all(not member.fate.spends and not member.fate.burns for member in source.party))
        self.assertFalse(hasattr(summary,'records'))

    def test_real_process_matches_sequential_help_and_both_fate_costs(self):
        request = PcMeleeSimulationRequest(active_help_source(),42,4)
        sequential = run_pc_melee_simulation(request)
        process = run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(process,sequential)
        summary = summarize_pc_melee_simulation(sequential)
        self.assertEqual(summarize_pc_melee_simulation(process),summary)
        self.assertGreater(summary.total_help_action_count,0)
        self.assertGreater(summary.total_glorious_spend_count,0)
        self.assertGreater(summary.total_near_miss_burn_count,0)

    def test_cached_help_cannot_turn_a_forged_bonus_into_a_compact_action_count(self):
        request = PcMeleeSimulationRequest(active_help_source(),42,1)
        native = run_pc_melee_scenario(request.scenario,Random(request.seed_for(0)))
        forged = deepcopy(native)
        proof = next(step.proof for step in forged.steps if isinstance(step.proof,PcHelpProof))
        object.__setattr__(proof.execution.bonus,'bonus_dice',True)
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',return_value=forged):
            with self.assertRaises((TypeError,ValueError)):
                run_pc_melee_trial(request,0)

    def test_count_search_fixes_helper_role_and_exposes_only_aggregate_actions(self):
        source = active_help_source()
        request = PcMeleeBalanceRequest(source,(
            PcMeleeCompositionGroup('minions',('minion1',),0,1),
            PcMeleeCompositionGroup('brutes',('brute1',),1,1)),source.facts,42,4,2,8,
            ObjectiveRateWindow(Fraction(0),Fraction(1,2),Fraction(1)),2)
        result = evaluate_pc_melee_balance(request,
            lambda trial:summarize_pc_melee_simulation(run_pc_melee_simulation(trial)))
        self.assertEqual(result.total_trials,8)
        for candidate in result.candidates:
            for actual,original in zip(candidate.summary.source_request.scenario.party,source.party,strict=True):
                self.assertEqual(actual.policy,original.policy)
                self.assertEqual(actual.help_policy,original.help_policy)
                self.assertEqual(actual.fate,original.fate)
            self.assertFalse(hasattr(candidate.summary,'records'))
        self.assertTrue(any(candidate.summary.total_help_action_count for candidate in result.candidates))


if __name__ == '__main__':
    unittest.main()
