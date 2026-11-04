"""Active Fate survives native execution, independent trials and count search."""
from fractions import Fraction
from copy import deepcopy
from dataclasses import replace
from random import Random
import unittest
from unittest.mock import patch

from tests.support.pc_near_miss_scenarios import active_near_miss_source
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10, first_wound_script
from towr.application.pc_melee_balance import evaluate_pc_melee_balance
from towr.application.pc_melee_balance_models import (
    PcMeleeBalanceRequest, PcMeleeCompositionGroup,
)
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.pc_melee_result_models import PcWoundCompletionProof
from towr.domain.pc_melee_models import PcFatePolicy, PcNearMissPolicy
from towr.domain.fate_models import FateNearMissBurnRequest, FateSessionState, FATE_NEAR_MISS_RULE_ID
from towr.domain.resolution_models import ConsumeWoundNegationRequest
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.rules.fate_resolution import burn_fate
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation, run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class PcNearMissIntegrationTests(unittest.TestCase):
    def test_independent_trials_count_actual_burn_proofs_and_preserve_initial_party(self):
        source = active_near_miss_source()
        request = PcMeleeSimulationRequest(source,42,4)
        batch = run_pc_melee_simulation(request)
        for record in batch.records:
            native = run_pc_melee_scenario(source,Random(record.seed))
            burns = [step.proof.completion.fate_burn for step in native.steps
                if isinstance(step.proof,PcWoundCompletionProof)
                and step.proof.completion.fate_burn is not None]
            for member, count in zip(source.party,record.near_miss_burn_counts,strict=True):
                actual = sum(burn.state.actor_id == member.actor_id for burn in burns)
                self.assertEqual(count.count,actual)
                self.assertGreaterEqual(native.state.participant(member.actor_id).fate.rating,1)
            self.assertEqual(native.source.party,source.party)
        summary = summarize_pc_melee_simulation(batch)
        self.assertGreater(summary.total_near_miss_burn_count,0)
        self.assertGreater(summary.near_miss_burn_trial_count,0)
        self.assertEqual(tuple(member.fate.rating for member in source.party),(3,3))
        self.assertTrue(all(not member.fate.burns for member in source.party))

    def test_real_process_matches_indexed_sequential_burns_and_summaries(self):
        request = PcMeleeSimulationRequest(active_near_miss_source(),42,4)
        sequential = run_pc_melee_simulation(request)
        process = run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(process,sequential)
        self.assertEqual(summarize_pc_melee_simulation(process),
            summarize_pc_melee_simulation(sequential))

    def test_corrupted_cached_fate_cannot_become_a_valid_compact_observation(self):
        request = PcMeleeSimulationRequest(active_near_miss_source(),42,1)
        native = run_pc_melee_scenario(request.scenario,Random(request.seed_for(0)))
        forged = deepcopy(native)
        fate = deepcopy(request.scenario.party[0].fate)
        object.__setattr__(fate,'burns',(object(),))
        object.__setattr__(forged.state.party[0],'fate',fate)
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',return_value=forged):
            with self.assertRaises((TypeError,ValueError)):
                run_pc_melee_trial(request,0)

    def test_supplied_previous_burn_is_preserved_but_excluded_from_battle_cost(self):
        source = make_pc_melee_scenario(max_rounds=1)
        old = burn_fate(FateNearMissBurnRequest('previous-burn',
            FateSessionState('session','pc',4,4),
            ConsumeWoundNegationRequest('previous-battle-wound',FATE_NEAR_MISS_RULE_ID))).state
        source = replace(source,party=(replace(source.party[0],fate=old,
            fate_policy=PcFatePolicy.NEAR_MISS_AT_THRESHOLD,
            near_miss_policy=PcNearMissPolicy(1,1)),))
        rng = ScriptedD10(first_wound_script(1))
        record = run_pc_melee_trial(PcMeleeSimulationRequest(source,42,1),0,
            rng_factory=lambda seed:rng)
        rng.assert_exhausted()
        self.assertEqual(record.near_miss_burn_counts[0].count,1)
        self.assertEqual(source.party[0].fate.burns,old.burns)
        self.assertEqual(source.party[0].fate.rating,3)

    def test_count_search_preserves_each_policy_and_reports_aggregate_resource_cost(self):
        source = active_near_miss_source()
        request = PcMeleeBalanceRequest(source,(
            PcMeleeCompositionGroup('minions',('minion1',),0,1),
            PcMeleeCompositionGroup('brutes',('brute1',),1,1)),source.facts,
            42,4,2,8,ObjectiveRateWindow(Fraction(0),Fraction(1,2),Fraction(1)),2)
        result = evaluate_pc_melee_balance(request,
            lambda trial:summarize_pc_melee_simulation(run_pc_melee_simulation(trial)))
        self.assertEqual(result.total_trials,8)
        for candidate in result.candidates:
            for actual,original in zip(candidate.summary.source_request.scenario.party,source.party,strict=True):
                self.assertEqual(actual.fate,original.fate)
                self.assertEqual(actual.fate_policy,original.fate_policy)
                self.assertEqual(actual.near_miss_policy,original.near_miss_policy)
            self.assertFalse(hasattr(candidate.summary,'records'))
            self.assertFalse(hasattr(candidate.summary,'fate'))
        self.assertTrue(any(candidate.summary.total_near_miss_burn_count
            for candidate in result.candidates))


if __name__ == '__main__':
    unittest.main()
