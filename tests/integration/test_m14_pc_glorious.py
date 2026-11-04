"""Glorious and Near Miss coexist through indexed trials and count search."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from random import Random
import unittest
from unittest.mock import patch

from tests.support.pc_glorious_scenarios import active_glorious_source
from towr.application.pc_melee_balance import evaluate_pc_melee_balance
from towr.application.pc_melee_balance_models import PcMeleeBalanceRequest,PcMeleeCompositionGroup
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.fate_models import FateGloriousSpendRequest
from towr.domain.pc_melee_result_models import (
    PcAttackProof,PcEnduranceProof,PcTurnEndProof,PcIncapacitatedTurnEndProof,
)
from towr.domain.test_models import TestRequest
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.rules.fate_resolution import spend_fate_for_glorious
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def witnessed_spends(native):
    result = []
    for step in native.steps:
        proof = step.proof
        if isinstance(proof,(PcAttackProof,PcEnduranceProof)):
            if proof.glorious is not None:
                result.append(proof.glorious)
        elif isinstance(proof,(PcTurnEndProof,PcIncapacitatedTurnEndProof)):
            if proof.critical is not None and proof.critical.glorious is not None:
                result.append(proof.critical.glorious)
    return result


class PcGloriousIntegrationTests(unittest.TestCase):
    def test_trials_preserve_initial_history_and_count_only_new_actual_spends(self):
        source = active_glorious_source()
        member = source.party[0]
        old = spend_fate_for_glorious(FateGloriousSpendRequest('previous-spend',member.fate,
            TestRequest('previous-test',member.pc.melee_profile))).state
        source = replace(source,party=(replace(member,fate=old),source.party[1]))
        request = PcMeleeSimulationRequest(source,42,4)
        batch = run_pc_melee_simulation(request)
        for record in batch.records:
            native = run_pc_melee_scenario(source,Random(record.seed))
            actual = witnessed_spends(native)
            for member,count in zip(source.party,record.glorious_spend_counts,strict=True):
                self.assertEqual(count.count,sum(spend.state.actor_id == member.actor_id for spend in actual))
                final = native.state.participant(member.actor_id).fate
                self.assertEqual(final.spends[:len(member.fate.spends)],member.fate.spends)
                self.assertEqual(final.rating,member.fate.rating-
                    (len(final.burns)-len(member.fate.burns)))
        summary = summarize_pc_melee_simulation(batch)
        self.assertGreater(summary.total_glorious_spend_count,0)
        self.assertEqual(source.party[0].fate.spends,old.spends)
        self.assertEqual(source.party[0].fate.rating,3)
        self.assertFalse(hasattr(summary,'records'))

    def test_real_process_matches_indexed_sequential_spends_burns_and_summary(self):
        request = PcMeleeSimulationRequest(active_glorious_source(),42,4)
        sequential = run_pc_melee_simulation(request)
        process = run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(process,sequential)
        summary = summarize_pc_melee_simulation(sequential)
        self.assertEqual(summarize_pc_melee_simulation(process),summary)
        self.assertGreater(summary.total_glorious_spend_count,0)
        self.assertGreater(summary.total_near_miss_burn_count,0)

    def test_cached_malformed_spends_cannot_become_affordable_observations(self):
        request = PcMeleeSimulationRequest(active_glorious_source(),42,1)
        native = run_pc_melee_scenario(request.scenario,Random(request.seed_for(0)))
        forged = deepcopy(native)
        object.__setattr__(forged.state.party[0].fate,'spends',(object(),))
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',return_value=forged):
            with self.assertRaises((TypeError,ValueError)):
                run_pc_melee_trial(request,0)

    def test_search_keeps_both_policies_and_their_distinct_costs_in_aggregates(self):
        source = active_glorious_source()
        request = PcMeleeBalanceRequest(source,(
            PcMeleeCompositionGroup('minions',('minion1',),0,1),
            PcMeleeCompositionGroup('brutes',('brute1',),1,1)),source.facts,42,4,2,8,
            ObjectiveRateWindow(Fraction(0),Fraction(1,2),Fraction(1)),2)
        result = evaluate_pc_melee_balance(request,
            lambda trial:summarize_pc_melee_simulation(run_pc_melee_simulation(trial)))
        self.assertEqual(result.total_trials,8)
        for candidate in result.candidates:
            for actual,original in zip(candidate.summary.source_request.scenario.party,source.party,strict=True):
                self.assertEqual(actual.fate,original.fate)
                self.assertEqual(actual.glorious_policy,original.glorious_policy)
                self.assertEqual(actual.near_miss_policy,original.near_miss_policy)
            self.assertFalse(hasattr(candidate.summary,'records'))
        self.assertTrue(any(item.summary.total_glorious_spend_count for item in result.candidates))
        self.assertTrue(any(item.summary.total_near_miss_burn_count for item in result.candidates))


if __name__ == '__main__':
    unittest.main()
