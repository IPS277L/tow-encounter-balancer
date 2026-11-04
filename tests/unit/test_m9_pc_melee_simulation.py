"""Independent source/seed/accounting checks, without replaying combat logic."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.domain.pc_melee_result_models import PcMeleeOutcome as Outcome
from towr.simulation.pc_melee_models import (
    PcMeleeOutcomeCounts, PcMeleeSimulationRequest, PcMeleeSimulationResult,
    PcMeleeTrialRecord, PcNearMissBurnCount, PcGloriousSpendCount, pc_melee_trial_seed,
)
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
from towr.simulation.pc_melee_summary_models import PcMeleeDefeatCount, PcMeleeSimulationSummary


def record(request, index, outcome=Outcome.ROUND_LIMIT):
    return PcMeleeTrialRecord(request.scenario, index, request.seed_for(index), outcome,
        2 if outcome is Outcome.ROUND_LIMIT else 1, 1,
        1 if outcome is Outcome.ROUND_LIMIT else 0,
        tuple(member.actor_id for member in request.scenario.party)
        if outcome is Outcome.PARTY_DEFEATED else (),
        tuple(PcNearMissBurnCount(member.actor_id,0) for member in request.scenario.party),
        tuple(PcGloriousSpendCount(member.actor_id,0) for member in request.scenario.party))


class PcMeleeSimulationModelTests(unittest.TestCase):
    def setUp(self):
        self.request = PcMeleeSimulationRequest(make_pc_melee_scenario(max_rounds=1), 42, 4)

    def test_seed_golden_vectors_are_indexed_and_prefix_stable(self):
        self.assertEqual(pc_melee_trial_seed(0,0),
            int('d4624f0dc1cb43e83d42d2ab92af3d68fc4a62ef7d5ea8a342cf4aea78ee3720',16))
        self.assertEqual(self.request.seed_for(0),
            int('e9727affc720cf0ea6501eacec511248f26bed72861a81d51441771bbeb4f8f6',16))
        self.assertEqual(self.request.seed_for(1),
            int('24da1d4c041699f387974421cfa9f881e84ba7d1db307fce81a825cf394de6e7',16))
        longer=replace(self.request,trials=9)
        self.assertEqual([self.request.seed_for(i) for i in range(4)],
            [longer.seed_for(i) for i in range(4)])

    def test_numeric_boundaries_do_not_coerce_bools_or_invalid_indices(self):
        for value in (True,1.0,'1',None):
            with self.subTest(value=value),self.assertRaises(TypeError):
                replace(self.request,master_seed=value)
            with self.subTest(trials=value),self.assertRaises(TypeError):
                replace(self.request,trials=value)
        for value in (-1,1<<64):
            with self.assertRaises(ValueError):
                replace(self.request,master_seed=value)
        with self.assertRaises(ValueError):
            replace(self.request,trials=0)
        for value in (-1,4,1<<64):
            with self.assertRaises(ValueError):
                self.request.seed_for(value)

    def test_complete_four_outcomes_keep_unsupported_in_the_denominator(self):
        outcomes=(Outcome.OBJECTIVE_ACHIEVED,Outcome.PARTY_DEFEATED,Outcome.ROUND_LIMIT,Outcome.UNSUPPORTED_PATH)
        records=tuple(record(self.request,index,outcome) for index,outcome in enumerate(outcomes))
        result=PcMeleeSimulationResult(self.request,records[::-1])
        self.assertEqual(result.records,records)
        summary=summarize_pc_melee_simulation(result)
        self.assertEqual(summary.outcome_counts,PcMeleeOutcomeCounts(1,1,1,1))
        self.assertEqual((summary.trials,summary.total_action_count,summary.total_started_round_count,
            summary.total_completed_round_count),(4,5,4,1))
        self.assertIs(summary.source_request,self.request)
        self.assertFalse(hasattr(summary,'records'))
        self.assertFalse(hasattr(summary,'journal'))

    def test_batch_rejects_missing_duplicate_foreign_seed_and_foreign_full_source(self):
        records=tuple(record(self.request,index) for index in range(4))
        invalid=(records[:-1],records[:-1]+(records[0],),
            records[:-1]+(replace(records[-1],seed=9),),
            records[:-1]+(replace(records[-1],source_scenario=replace(self.request.scenario,id='other')),))
        for bad in invalid:
            with self.subTest(records=bad[-1].trial_index),self.assertRaises(ValueError):
                PcMeleeSimulationResult(self.request,bad)
        with self.assertRaises(TypeError):
            PcMeleeSimulationResult(self.request,iter(records))

    def test_record_counters_cannot_exceed_source_budget_or_fake_terminal(self):
        original=record(self.request,0)
        for changes in ({'started_rounds':2},{'completed_rounds':0},{'executed_actions':3},
                        {'started_rounds':0},{'executed_actions':-1}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                replace(original,**changes)
        with self.assertRaises(TypeError):
            replace(original,outcome='round_limit')
        with self.assertRaises(TypeError):
            replace(original,executed_actions=True)
        terminal=record(self.request,0,Outcome.PARTY_DEFEATED)
        with self.assertRaises(ValueError):
            replace(terminal,executed_actions=0)

    def test_summary_arithmetic_refuses_filtered_trials_and_false_round_limit(self):
        summary=PcMeleeSimulationSummary(self.request,PcMeleeOutcomeCounts(1,1,1,1),5,4,1,
            1,(PcMeleeDefeatCount('pc',1),),0,(PcNearMissBurnCount('pc',0),),
            0,(PcGloriousSpendCount('pc',0),))
        for changes in ({'outcome_counts':PcMeleeOutcomeCounts(1,1,1,0)},
                        {'total_started_round_count':3},{'total_completed_round_count':0},
                        {'total_completed_round_count':5},{'total_action_count':9}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                replace(summary,**changes)
        with self.assertRaises(TypeError):
            PcMeleeOutcomeCounts(True,1,1,1)

    def test_deep_readmission_catches_equal_bool_source_and_record_corruption(self):
        forged=deepcopy(self.request)
        object.__setattr__(forged.scenario.party[0].pc,'armour_bonus',False)
        self.assertEqual(forged,self.request)
        with self.assertRaises(TypeError):
            replace(forged)
        good=record(self.request,0)
        forged_record=deepcopy(good)
        object.__setattr__(forged_record,'started_rounds',True)
        self.assertEqual(forged_record,good)
        with self.assertRaises(TypeError):
            PcMeleeSimulationResult(replace(self.request,trials=1),(forged_record,))


if __name__=='__main__':
    unittest.main()
