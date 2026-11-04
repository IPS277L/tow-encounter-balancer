"""Actual PC encounters, independent trials and real spawn without stale gates."""
from copy import deepcopy
from random import Random
import unittest
from unittest.mock import patch

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10, unavailable_arm_source, unavailable_arm_script
from towr.domain.pc_melee_result_models import PcMeleeOutcome as Outcome
from towr.simulation.pc_melee_models import PcMeleeOutcomeCounts, PcMeleeSimulationRequest, pc_melee_trial_seed
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def completed_outcomes_rng(seed):
    """Importable deterministic test stream selection, not a probability model."""
    mapping={pc_melee_trial_seed(42,index):value for index,value in enumerate((0,2,16))}
    return Random(mapping[seed])


def failing_rng(seed):
    raise RuntimeError('private M9 worker failure')


class PcMeleeSimulationIntegrationTests(unittest.TestCase):
    def test_actual_unavailable_anatomical_target_keeps_native_stop_in_all_trial_denominator(self):
        source=PcMeleeSimulationRequest(unavailable_arm_source(),42,1)
        original=deepcopy(source)
        streams=[]
        def fresh(seed):
            rng=ScriptedD10(unavailable_arm_script())
            streams.append((seed,rng))
            return rng
        result=run_pc_melee_simulation(source,rng_factory=fresh)
        streams[0][1].assert_exhausted()
        self.assertEqual(streams[0][0],source.seed_for(0))
        self.assertEqual(result.outcome_counts,PcMeleeOutcomeCounts(0,0,0,1))
        self.assertEqual((result.total_action_count,result.total_started_round_count,
            result.total_completed_round_count),(5,1,0))
        summary=summarize_pc_melee_simulation(result)
        self.assertEqual(summary.trials,1)
        self.assertEqual(summary.outcome_counts.unsupported_path,1)
        self.assertEqual(summary.any_pc_defeated_count,0)
        self.assertEqual(source,original)

    @classmethod
    def setUpClass(cls):
        cls.scenario=make_pc_melee_scenario(enemy_count=3,max_rounds=6)
        cls.original=deepcopy(cls.scenario)
        cls.request=PcMeleeSimulationRequest(cls.scenario,42,3)
        cls.streams=[]
        def fresh(seed):
            rng=completed_outcomes_rng(seed)
            cls.streams.append((seed,rng))
            return rng
        cls.sequential=run_pc_melee_simulation(cls.request,rng_factory=fresh)

    def test_completed_outcomes_share_full_source_fresh_rng_and_all_trial_denominator(self):
        result=self.sequential
        self.assertEqual(tuple(record.outcome for record in result.records),
            (Outcome.OBJECTIVE_ACHIEVED,Outcome.ROUND_LIMIT,Outcome.PARTY_DEFEATED))
        self.assertEqual(result.outcome_counts,PcMeleeOutcomeCounts(1,1,1,0))
        self.assertEqual((result.total_action_count,result.total_started_round_count,
            result.total_completed_round_count),(33,13,11))
        self.assertEqual([seed for seed,_ in self.streams],[self.request.seed_for(i) for i in range(3)])
        self.assertEqual(len({id(rng) for _,rng in self.streams}),3)
        self.assertEqual(self.scenario,self.original)
        self.assertTrue(all(record.source_scenario==self.original for record in result.records))
        summary=summarize_pc_melee_simulation(result)
        self.assertEqual(summary.trials,3)
        self.assertEqual(summary.outcome_counts.unsupported_path,0)
        self.assertFalse(hasattr(summary,'steps'))
        self.assertFalse(hasattr(summary,'records'))

    def test_real_spawn_uneven_batches_preserve_completed_outcomes_records_and_aggregate(self):
        parallel=run_pc_melee_simulation_parallel(self.request,workers=2,batch_size=2,
            rng_factory=completed_outcomes_rng)
        self.assertEqual(parallel,self.sequential)
        self.assertEqual(summarize_pc_melee_simulation(parallel),summarize_pc_melee_simulation(self.sequential))
        self.assertIs(parallel.source_request,self.request)
        self.assertEqual(self.scenario,self.original)

    def test_worker_exception_propagates_with_index_context_without_partial_result(self):
        with self.assertRaisesRegex(RuntimeError,'private M9 worker') as caught:
            run_pc_melee_simulation_parallel(self.request,workers=1,batch_size=2,rng_factory=failing_rng)
        self.assertTrue(any('M9 trial index=' in note for note in caught.exception.__notes__))
        self.assertEqual(self.scenario,self.original)

    def test_corrupted_equal_source_and_unpicklable_factory_fail_before_pool(self):
        forged=deepcopy(self.request)
        object.__setattr__(forged.scenario.facts,'no_ambush',1)
        self.assertEqual(forged,self.request)
        with patch('towr.simulation.pc_melee_parallel.ProcessPoolExecutor') as pool:
            with self.assertRaises(TypeError):
                run_pc_melee_simulation_parallel(forged,workers=1,rng_factory=completed_outcomes_rng)
            with self.assertRaises((AttributeError,TypeError)):
                run_pc_melee_simulation_parallel(self.request,workers=1,rng_factory=lambda seed:Random(seed))
            pool.assert_not_called()


if __name__=='__main__':
    unittest.main()
