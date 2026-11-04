"""Help consumes ordinary action budget, independently of Fate costs."""
from tests.support.pc_melee_fixtures import zero_npc_exit_counts
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from towr.domain.pc_melee_models import PcHelpPolicy,PcHelpTarget,PcMeleePolicy
from towr.domain.pc_melee_result_models import PcMeleeOutcome as Outcome
from towr.simulation.pc_melee_models import (
    PcMeleeSimulationRequest,PcMeleeSimulationResult,PcMeleeTrialRecord,PcMeleeOutcomeCounts,
    PcNearMissBurnCount,PcGloriousSpendCount,PcHelpActionCount,PcAllyRecoverActionCount,
)
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
from towr.simulation.pc_melee_summary_models import PcMeleeDefeatCount


def source():
    original = make_pc_melee_party_scenario(pc_count=3,enemy_count=2,max_rounds=1)
    party = tuple(replace(member,policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
        help_policy=PcHelpPolicy('pc3',PcHelpTarget.MELEE_ATTACK,None)) if member.actor_id!='pc3' else member
        for member in original.party)
    return replace(original,party=party)


def observed_batch():
    request = PcMeleeSimulationRequest(source(),42,4)
    rows = ((Outcome.OBJECTIVE_ACHIEVED,(1,1,0)),(Outcome.PARTY_DEFEATED,(1,0,0)),
        (Outcome.ROUND_LIMIT,(0,0,0)),(Outcome.UNSUPPORTED_PATH,(0,1,0)))
    records = tuple(PcMeleeTrialRecord(request.scenario,index,request.seed_for(index),outcome,4,1,
        int(outcome is Outcome.ROUND_LIMIT),('pc1','pc2','pc3') if outcome is Outcome.PARTY_DEFEATED else (),
        tuple(PcNearMissBurnCount(member.actor_id,0) for member in request.scenario.party),
        tuple(PcGloriousSpendCount(member.actor_id,0) for member in request.scenario.party),
        tuple(PcHelpActionCount(member.actor_id,count)
            for member,count in zip(request.scenario.party,counts,strict=True)),
        tuple(PcAllyRecoverActionCount(member.actor_id,0) for member in request.scenario.party), zero_npc_exit_counts(request.scenario))
        for index,(outcome,counts) in enumerate(rows))
    return PcMeleeSimulationResult(request,records)


class PcHelpStatisticsTests(unittest.TestCase):
    def test_stopped_prefix_keeps_actual_actions_and_full_trial_denominator(self):
        summary = summarize_pc_melee_simulation(observed_batch())
        self.assertEqual(summary.trials,4)
        self.assertEqual(summary.help_action_trial_count,3)
        self.assertEqual(summary.total_help_action_count,4)
        self.assertEqual(summary.help_action_counts,
            (PcHelpActionCount('pc1',2),PcHelpActionCount('pc2',2),PcHelpActionCount('pc3',0)))
        self.assertEqual(summary.total_glorious_spend_count,0)
        self.assertEqual(summary.total_near_miss_burn_count,0)
        self.assertFalse(hasattr(summary,'records'))

    def test_record_rejects_wrong_party_role_and_more_helps_than_rounds_or_actions(self):
        record = observed_batch().records[0]
        for counts in ((),tuple(reversed(record.help_action_counts)),
            (PcHelpActionCount('pc1',2),PcHelpActionCount('pc2',0),PcHelpActionCount('pc3',0)),
            (PcHelpActionCount('pc1',0),PcHelpActionCount('pc2',0),PcHelpActionCount('pc3',1))):
            with self.subTest(counts=counts),self.assertRaises(ValueError):
                replace(record,help_action_counts=counts)
        with self.assertRaises(ValueError):
            replace(record,executed_actions=1)
        for counts in ([*record.help_action_counts],(object(),object(),object())):
            with self.assertRaises(TypeError):
                replace(record,help_action_counts=counts)
        forged = deepcopy(record)
        object.__setattr__(forged.help_action_counts[0],'count',True)
        with self.assertRaises(TypeError):
            replace(forged)

    def test_summary_requires_union_action_and_each_helper_turn_bounds(self):
        summary = summarize_pc_melee_simulation(observed_batch())
        for value in (True,None,1.0,'1'):
            with self.assertRaises(TypeError):
                replace(summary,help_action_trial_count=value)
        for changes in ({'help_action_trial_count':0},{'help_action_trial_count':5},
            {'help_action_trial_count':1},{'help_action_counts':tuple(reversed(summary.help_action_counts))},
            {'help_action_counts':(PcHelpActionCount('pc1',4),PcHelpActionCount('pc2',2),PcHelpActionCount('pc3',0))}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                replace(summary,**changes)

    def test_help_role_requires_distinct_later_ordinary_party_beneficiary(self):
        original = source()
        member = original.party[0]
        for beneficiary in ('pc1','unknown','pc2'):
            with self.subTest(beneficiary=beneficiary),self.assertRaises(ValueError):
                changed = replace(member,help_policy=PcHelpPolicy(beneficiary,PcHelpTarget.MELEE_ATTACK,None))
                replace(original,party=(changed,*original.party[1:]))
        with self.assertRaises(ValueError):
            replace(original,pc_activation_order=('pc3','pc1','pc2'))
        with self.assertRaises((TypeError,ValueError)):
            replace(member,help_policy=None)
        with self.assertRaises(ValueError):
            replace(original.party[2],help_policy=PcHelpPolicy('pc1',PcHelpTarget.MELEE_ATTACK,None))

    def test_no_help_trials_cannot_lend_their_mandatory_rounds_to_help_counters(self):
        summary = summarize_pc_melee_simulation(observed_batch())
        request = replace(summary.source_request,scenario=replace(summary.source_request.scenario,max_rounds=3))
        with self.assertRaises(ValueError):
            replace(summary,source_request=request,outcome_counts=PcMeleeOutcomeCounts(4,0,0,0),
                total_action_count=4,total_started_round_count=4,total_completed_round_count=0,
                any_pc_defeated_count=0,
                pc_defeat_counts=tuple(PcMeleeDefeatCount(member.actor_id,0) for member in request.scenario.party),
                help_action_trial_count=1,
                help_action_counts=(PcHelpActionCount('pc1',3),PcHelpActionCount('pc2',0),PcHelpActionCount('pc3',0)))

    def test_cached_foreign_help_target_and_boolean_counts_are_not_coerced(self):
        original = source()
        foreign = Enum('ForeignString',{'TARGET':'pc3'},type=str).TARGET
        forged = deepcopy(original)
        object.__setattr__(forged.party[0].help_policy,'beneficiary_id',foreign)
        self.assertEqual(forged,original)
        with self.assertRaises(TypeError):
            PcMeleeSimulationRequest(forged,42,1)
        for count in (True,1.0,'1',None):
            with self.assertRaises(TypeError):
                PcHelpActionCount('pc1',count)
        with self.assertRaises(ValueError):
            PcHelpActionCount('pc1',-1)


if __name__ == '__main__':
    unittest.main()
