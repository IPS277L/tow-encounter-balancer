"""Resource observations remain bounded by each PC's explicit battle budget."""
from tests.support.pc_melee_fixtures import zero_npc_exit_counts
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from tests.support.pc_near_miss_scenarios import active_near_miss_source
from towr.domain.pc_melee_result_models import PcMeleeOutcome as Outcome
from towr.simulation.pc_melee_models import (
    PcMeleeSimulationRequest, PcMeleeSimulationResult, PcMeleeTrialRecord,
    PcNearMissBurnCount, PcGloriousSpendCount, PcHelpActionCount, PcAllyRecoverActionCount,
)
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def observed_batch():
    scenario = replace(active_near_miss_source(),max_rounds=1)
    source = PcMeleeSimulationRequest(scenario,42,4)
    rows = ((Outcome.OBJECTIVE_ACHIEVED,(2,0)),
        (Outcome.PARTY_DEFEATED,(1,1)),(Outcome.ROUND_LIMIT,(0,0)),
        (Outcome.UNSUPPORTED_PATH,(0,1)))
    records = tuple(PcMeleeTrialRecord(source.scenario,index,source.seed_for(index),outcome,
        4,1,int(outcome is Outcome.ROUND_LIMIT),
        ('pc1','pc2') if outcome is Outcome.PARTY_DEFEATED else (),
        tuple(PcNearMissBurnCount(member.actor_id,count)
            for member,count in zip(source.scenario.party,counts,strict=True)),
        tuple(PcGloriousSpendCount(member.actor_id,0) for member in source.scenario.party),
        tuple(PcHelpActionCount(member.actor_id,0) for member in source.scenario.party),
        tuple(PcAllyRecoverActionCount(member.actor_id,0) for member in source.scenario.party), zero_npc_exit_counts(source.scenario))
        for index,(outcome,counts) in enumerate(rows))
    return PcMeleeSimulationResult(source,records)


class PcNearMissStatisticsTests(unittest.TestCase):
    def test_counts_include_actual_prefix_of_stopped_trials_and_full_denominator(self):
        summary = summarize_pc_melee_simulation(observed_batch())
        self.assertEqual(summary.trials,4)
        self.assertEqual(summary.near_miss_burn_trial_count,3)
        self.assertEqual(summary.total_near_miss_burn_count,5)
        self.assertEqual(summary.near_miss_burn_counts,
            (PcNearMissBurnCount('pc1',3),PcNearMissBurnCount('pc2',2)))
        self.assertFalse(hasattr(summary,'records'))
        self.assertFalse(hasattr(summary,'fate'))

    def test_record_rejects_wrong_party_order_types_and_unaffordable_burns(self):
        record = observed_batch().records[0]
        for counts in ((),tuple(reversed(record.near_miss_burn_counts)),
            (PcNearMissBurnCount('foreign',0),PcNearMissBurnCount('pc2',0)),
            (PcNearMissBurnCount('pc1',3),PcNearMissBurnCount('pc2',0))):
            with self.subTest(counts=counts),self.assertRaises(ValueError):
                replace(record,near_miss_burn_counts=counts)
        for counts in ([*record.near_miss_burn_counts],(object(),object())):
            with self.assertRaises(TypeError):
                replace(record,near_miss_burn_counts=counts)
        forged = deepcopy(record)
        object.__setattr__(forged.near_miss_burn_counts[0],'count',True)
        with self.assertRaises(TypeError):
            replace(forged)

    def test_decline_and_reserve_exhaustion_forbid_positive_burn_counts(self):
        record = observed_batch().records[0]
        decline = make_pc_melee_party_scenario(enemy_count=2,max_rounds=1)
        with self.assertRaises(ValueError):
            replace(record,source_scenario=decline)
        source = active_near_miss_source(minimum_rating_to_keep=3)
        with self.assertRaises(ValueError):
            replace(record,source_scenario=source)

    def test_summary_checks_union_resource_and_action_bounds_without_journal(self):
        summary = summarize_pc_melee_simulation(observed_batch())
        for changes in ({'near_miss_burn_trial_count':0},
            {'near_miss_burn_trial_count':5},{'near_miss_burn_trial_count':1},
            {'near_miss_burn_counts':(PcNearMissBurnCount('pc1',0),PcNearMissBurnCount('pc2',0))},
            {'near_miss_burn_counts':tuple(reversed(summary.near_miss_burn_counts))},
            {'near_miss_burn_counts':(PcNearMissBurnCount('pc1',7),PcNearMissBurnCount('pc2',2))}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                replace(summary,**changes)
        for value in (True,None,1.0,'1'):
            with self.assertRaises(TypeError):
                replace(summary,near_miss_burn_trial_count=value)
        for value in (True,1.0,'1'):
            with self.assertRaises(TypeError):
                PcNearMissBurnCount('pc1',value)
        with self.assertRaises(ValueError):
            PcNearMissBurnCount('pc1',-1)


if __name__ == '__main__':
    unittest.main()
