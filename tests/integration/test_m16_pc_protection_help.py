"""Exact Protection Help survives native trials, process execution and search."""
from copy import deepcopy
from fractions import Fraction
from random import Random
import unittest
from unittest.mock import patch

from tests.support.pc_protection_help_scenarios import active_protection_help_source
from towr.application.pc_melee_balance import evaluate_pc_melee_balance
from towr.application.pc_melee_balance_models import PcMeleeBalanceRequest,PcMeleeCompositionGroup
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.pc_melee_result_models import PcHelpProof,PcAttackProof
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class PcProtectionHelpIntegrationTests(unittest.TestCase):
    def test_actual_earlier_help_applies_only_to_named_incoming_protection(self):
        source = active_protection_help_source()
        request = PcMeleeSimulationRequest(source,42,4)
        batch = run_pc_melee_simulation(request)
        applications = 0
        for record in batch.records:
            native = run_pc_melee_scenario(source,Random(record.seed))
            helpers = []
            for step in native.steps:
                proof = step.proof
                if isinstance(proof,PcHelpProof):
                    helpers.append(proof)
                elif isinstance(proof,PcAttackProof):
                    for applied in proof.help_applications:
                        self.assertIn(proof.request.actor_id,source.enemy_activation_order)
                        self.assertIn(applied.source_request.help,[helper.execution for helper in helpers])
                        self.assertEqual(applied.source_request.beneficiary_id,proof.request.target_id)
                        self.assertEqual(applied.source_request.test.id,
                            proof.execution.resolution.attack.defender_test.trace.request_id)
                        self.assertIs(applied.source_request.beneficiary_skill,
                            proof.protection.source_request.selected_skill)
                        applications += 1
            self.assertEqual(sum(item.count for item in record.help_action_counts),len(helpers))
        self.assertGreater(applications,0)
        summary = summarize_pc_melee_simulation(batch)
        self.assertGreater(summary.total_help_action_count,0)
        self.assertEqual(summary.help_action_counts[1].count,0)

    def test_real_process_keeps_indexed_help_and_fate_observations_identical(self):
        request = PcMeleeSimulationRequest(active_protection_help_source(),42,4)
        sequential = run_pc_melee_simulation(request)
        process = run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(process,sequential)
        summary = summarize_pc_melee_simulation(sequential)
        self.assertEqual(summarize_pc_melee_simulation(process),summary)
        self.assertGreater(summary.total_help_action_count,0)
        self.assertGreater(summary.total_glorious_spend_count,0)
        self.assertGreater(summary.total_near_miss_burn_count,0)

    def test_cached_protection_skill_cannot_be_reinterpreted_as_an_action_observation(self):
        request = PcMeleeSimulationRequest(active_protection_help_source(),42,1)
        native = run_pc_melee_scenario(request.scenario,Random(request.seed_for(0)))
        forged = deepcopy(native)
        proof = next(step.proof for step in forged.steps if isinstance(step.proof,PcHelpProof))
        object.__setattr__(proof.execution.bonus,'beneficiary_skill',Skill.ATHLETICS)
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',return_value=forged):
            with self.assertRaises((TypeError,ValueError)):
                run_pc_melee_trial(request,0)

    def test_search_projects_enemies_without_rewriting_protection_help_choice(self):
        source = active_protection_help_source()
        request = PcMeleeBalanceRequest(source,(
            PcMeleeCompositionGroup('minions',('minion1',),0,1),
            PcMeleeCompositionGroup('brutes',('brute1',),1,1)),source.facts,42,4,2,8,
            ObjectiveRateWindow(Fraction(0),Fraction(1,2),Fraction(1)),2)
        result = evaluate_pc_melee_balance(request,
            lambda trial:summarize_pc_melee_simulation(run_pc_melee_simulation(trial)))
        self.assertEqual(result.total_trials,8)
        for candidate in result.candidates:
            actual = candidate.summary.source_request.scenario
            self.assertEqual(actual.party[0].help_policy,source.party[0].help_policy)
            self.assertEqual(actual.enemy_target_priority,source.enemy_target_priority)
            self.assertFalse(hasattr(candidate.summary,'records'))
        self.assertTrue(any(candidate.summary.total_help_action_count for candidate in result.candidates))


if __name__=='__main__':
    unittest.main()
