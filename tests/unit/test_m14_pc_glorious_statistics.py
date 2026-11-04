"""Ordinary session spends have distinct budgets from permanent Fate burns."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_glorious_scenarios import active_glorious_source
from towr.domain.pc_melee_models import PcGloriousPolicy
from towr.domain.pc_melee_result_models import PcMeleeOutcome as Outcome
from towr.domain.test_models import Skill
from towr.simulation.pc_melee_models import (
    PcMeleeSimulationRequest,PcMeleeSimulationResult,PcMeleeTrialRecord,
    PcNearMissBurnCount,PcGloriousSpendCount,
)
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def observed_batch():
    request = PcMeleeSimulationRequest(replace(active_glorious_source(),max_rounds=1),42,4)
    rows = ((Outcome.OBJECTIVE_ACHIEVED,(2,0)),(Outcome.PARTY_DEFEATED,(1,1)),
        (Outcome.ROUND_LIMIT,(0,0)),(Outcome.UNSUPPORTED_PATH,(0,1)))
    records = tuple(PcMeleeTrialRecord(request.scenario,index,request.seed_for(index),outcome,4,1,
        int(outcome is Outcome.ROUND_LIMIT),('pc1','pc2') if outcome is Outcome.PARTY_DEFEATED else (),
        tuple(PcNearMissBurnCount(member.actor_id,0) for member in request.scenario.party),
        tuple(PcGloriousSpendCount(member.actor_id,count)
            for member,count in zip(request.scenario.party,counts,strict=True)))
        for index,(outcome,counts) in enumerate(rows))
    return PcMeleeSimulationResult(request,records)


class PcGloriousStatisticsTests(unittest.TestCase):
    def test_spends_include_stopped_prefix_without_filtering_trials_or_adding_burns(self):
        summary = summarize_pc_melee_simulation(observed_batch())
        self.assertEqual(summary.trials,4)
        self.assertEqual(summary.glorious_spend_trial_count,3)
        self.assertEqual(summary.total_glorious_spend_count,5)
        self.assertEqual(summary.glorious_spend_counts,
            (PcGloriousSpendCount('pc1',3),PcGloriousSpendCount('pc2',2)))
        self.assertEqual(summary.total_near_miss_burn_count,0)
        self.assertFalse(hasattr(summary,'records'))

    def test_record_counters_require_full_party_order_and_available_spending_budget(self):
        record = observed_batch().records[0]
        for counts in ((),tuple(reversed(record.glorious_spend_counts)),
            (PcGloriousSpendCount('foreign',0),PcGloriousSpendCount('pc2',0)),
            (PcGloriousSpendCount('pc1',3),PcGloriousSpendCount('pc2',0))):
            with self.subTest(counts=counts),self.assertRaises(ValueError):
                replace(record,glorious_spend_counts=counts)
        for counts in ([*record.glorious_spend_counts],(object(),object())):
            with self.assertRaises(TypeError):
                replace(record,glorious_spend_counts=counts)
        forged = deepcopy(record)
        object.__setattr__(forged.glorious_spend_counts[0],'count',True)
        with self.assertRaises(TypeError):
            replace(forged)

    def test_near_miss_only_and_exhausted_session_reserve_cannot_report_spending(self):
        record = observed_batch().records[0]
        source = record.source_scenario
        for party in (tuple(replace(member,glorious_policy=None) for member in source.party),
            tuple(replace(member,glorious_policy=replace(member.glorious_policy,
                minimum_remaining_spends=member.fate.remaining_spends)) for member in source.party)):
            with self.assertRaises(ValueError):
                replace(record,source_scenario=replace(source,party=party))

    def test_summary_checks_exact_types_union_and_each_pc_session_budget(self):
        summary = summarize_pc_melee_simulation(observed_batch())
        for value in (True,None,1.0,'1'):
            with self.assertRaises(TypeError):
                replace(summary,glorious_spend_trial_count=value)
        for changes in ({'glorious_spend_trial_count':0},{'glorious_spend_trial_count':5},
            {'glorious_spend_trial_count':1},
            {'glorious_spend_counts':tuple(reversed(summary.glorious_spend_counts))},
            {'glorious_spend_counts':(PcGloriousSpendCount('pc1',7),PcGloriousSpendCount('pc2',2))}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                replace(summary,**changes)

    def test_critical_and_wound_tests_do_not_share_an_ordinary_attack_count_limit(self):
        record = observed_batch().records[0]
        # A compact observation cannot infer the number of Endurance Tests from
        # ordinary action counts. The resource cap is still enforced per PC.
        changed = replace(record,executed_actions=1)
        self.assertEqual(sum(item.count for item in changed.glorious_spend_counts),2)

    def test_policy_criteria_are_explicit_and_cached_skill_types_are_readmitted(self):
        source = active_glorious_source()
        for skills in ((),(Skill.MELEE,Skill.MELEE),('melee',),(Skill.SHOOTING,)):
            with self.assertRaises((TypeError,ValueError)):
                PcGloriousPolicy(skills,0,0)
        for value in (True,None,1.0,'1',-1):
            for name in ('maximum_initial_successes','minimum_remaining_spends'):
                with self.subTest(name=name,value=value),self.assertRaises((TypeError,ValueError)):
                    replace(source.party[0].glorious_policy,**{name:value})
        forged = deepcopy(source)
        object.__setattr__(forged.party[0].glorious_policy,'skills',('melee','defence','athletics','endurance'))
        self.assertEqual(forged,source)
        with self.assertRaises(TypeError):
            PcMeleeSimulationRequest(forged,42,1)
        forged = deepcopy(source)
        object.__setattr__(forged.party[0].glorious_policy,'skills',list(source.party[0].glorious_policy.skills))
        with self.assertRaises(TypeError):
            PcMeleeSimulationRequest(forged,42,1)


if __name__ == '__main__':
    unittest.main()
