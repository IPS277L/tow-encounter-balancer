"""Actual allied condition changes share the ordinary action/round budget."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from towr.domain.pc_melee_models import PcAllyRecoverPolicy,PcHelpPolicy,PcHelpTarget,PcMeleePolicy
from towr.domain.pc_melee_result_models import PcMeleeOutcome as Outcome
from towr.domain.test_models import Skill
from towr.simulation.pc_melee_models import (
    PcMeleeSimulationRequest,PcMeleeSimulationResult,PcMeleeTrialRecord,PcMeleeOutcomeCounts,
    PcNearMissBurnCount,PcGloriousSpendCount,PcHelpActionCount,PcAllyRecoverActionCount,
)
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
from towr.simulation.pc_melee_summary_models import PcMeleeDefeatCount


def source():
    original=make_pc_melee_party_scenario(pc_count=3,enemy_count=2,max_rounds=1)
    return replace(original,pc_activation_order=('pc3','pc1','pc2'),party=tuple(replace(member,
        policy=PcMeleePolicy.RECOVER_ALLY_OR_ATTACK_OR_RECOVER_SELF,
        ally_recover_policy=PcAllyRecoverPolicy('pc3')) if member.actor_id!='pc3' else member
        for member in original.party))


def observed_batch():
    request=PcMeleeSimulationRequest(source(),42,4)
    rows=((Outcome.OBJECTIVE_ACHIEVED,(1,1,0)),(Outcome.PARTY_DEFEATED,(1,0,0)),
        (Outcome.ROUND_LIMIT,(0,0,0)),(Outcome.UNSUPPORTED_PATH,(0,1,0)))
    records=tuple(PcMeleeTrialRecord(request.scenario,index,request.seed_for(index),outcome,4,1,
        int(outcome is Outcome.ROUND_LIMIT),('pc1','pc2','pc3') if outcome is Outcome.PARTY_DEFEATED else (),
        tuple(PcNearMissBurnCount(m.actor_id,0) for m in request.scenario.party),
        tuple(PcGloriousSpendCount(m.actor_id,0) for m in request.scenario.party),
        tuple(PcHelpActionCount(m.actor_id,0) for m in request.scenario.party),
        tuple(PcAllyRecoverActionCount(m.actor_id,count)
            for m,count in zip(request.scenario.party,counts,strict=True)))
        for index,(outcome,counts) in enumerate(rows))
    return PcMeleeSimulationResult(request,records)


class PcAllyRecoverStatisticsTests(unittest.TestCase):
    def test_observed_prefix_keeps_full_denominator_and_costs_separate(self):
        summary=summarize_pc_melee_simulation(observed_batch())
        self.assertEqual(summary.trials,4)
        self.assertEqual(summary.ally_recover_action_trial_count,3)
        self.assertEqual(summary.total_ally_recover_action_count,4)
        self.assertEqual(tuple(c.count for c in summary.ally_recover_action_counts),(2,2,0))
        self.assertEqual(summary.total_help_action_count,0)
        self.assertEqual(summary.total_glorious_spend_count,0)
        self.assertFalse(hasattr(summary,'records'))

    def test_role_target_order_and_cycles_are_explicit(self):
        original=source()
        reverse=replace(original,pc_activation_order=('pc3','pc2','pc1'))
        self.assertEqual(reverse.party[0].ally_recover_policy.beneficiary_id,'pc3')
        cycle=replace(original,party=(replace(original.party[0],ally_recover_policy=PcAllyRecoverPolicy('pc2')),
            replace(original.party[1],ally_recover_policy=PcAllyRecoverPolicy('pc1')),original.party[2]))
        self.assertEqual(cycle.party[1].ally_recover_policy.beneficiary_id,'pc1')
        for target in ('pc1','foreign'):
            with self.assertRaises(ValueError):
                changed=replace(original.party[0],ally_recover_policy=PcAllyRecoverPolicy(target))
                replace(original,party=(changed,*original.party[1:]))
        with self.assertRaises((TypeError,ValueError)):
            replace(original.party[0],ally_recover_policy=None)
        with self.assertRaises(ValueError):
            replace(original.party[2],ally_recover_policy=PcAllyRecoverPolicy('pc1'))

    def test_record_requires_full_order_types_role_and_turn_budget(self):
        record=observed_batch().records[0]
        for counts in ((),tuple(reversed(record.ally_recover_action_counts)),
            (PcAllyRecoverActionCount('pc1',2),PcAllyRecoverActionCount('pc2',0),PcAllyRecoverActionCount('pc3',0)),
            (PcAllyRecoverActionCount('pc1',0),PcAllyRecoverActionCount('pc2',0),PcAllyRecoverActionCount('pc3',1))):
            with self.subTest(counts=counts),self.assertRaises(ValueError):
                replace(record,ally_recover_action_counts=counts)
        with self.assertRaises(TypeError):
            replace(record,ally_recover_action_counts=list(record.ally_recover_action_counts))
        forged=deepcopy(record)
        object.__setattr__(forged.ally_recover_action_counts[0],'count',True)
        with self.assertRaises(TypeError):
            replace(forged)

    def test_summary_types_union_and_round_allocation_are_not_coerced(self):
        summary=summarize_pc_melee_simulation(observed_batch())
        for value in (True,None,1.0,'1'):
            with self.assertRaises(TypeError):
                replace(summary,ally_recover_action_trial_count=value)
        for value in (0,1,5):
            with self.assertRaises(ValueError):
                replace(summary,ally_recover_action_trial_count=value)
        request=replace(summary.source_request,scenario=replace(summary.source_request.scenario,max_rounds=3))
        with self.assertRaises(ValueError):
            replace(summary,source_request=request,outcome_counts=PcMeleeOutcomeCounts(4,0,0,0),
                total_action_count=4,total_started_round_count=4,total_completed_round_count=0,
                any_pc_defeated_count=0,
                pc_defeat_counts=tuple(PcMeleeDefeatCount(m.actor_id,0) for m in request.scenario.party),
                ally_recover_action_trial_count=1,
                ally_recover_action_counts=(PcAllyRecoverActionCount('pc1',3),PcAllyRecoverActionCount('pc2',0),PcAllyRecoverActionCount('pc3',0)))

    def test_help_and_ally_recover_cannot_both_claim_one_action(self):
        record=observed_batch().records[0]
        first=replace(record.source_scenario.party[0],policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
            help_policy=PcHelpPolicy('pc3',PcHelpTarget.FIRST_INCOMING_PROTECTION,Skill.DEFENCE),ally_recover_policy=None)
        mixed=replace(record.source_scenario,party=(first,*record.source_scenario.party[1:]))
        with self.assertRaises(ValueError):
            replace(record,source_scenario=mixed,executed_actions=1,
                help_action_counts=(PcHelpActionCount('pc1',1),PcHelpActionCount('pc2',0),PcHelpActionCount('pc3',0)),
                ally_recover_action_counts=(PcAllyRecoverActionCount('pc1',0),PcAllyRecoverActionCount('pc2',1),PcAllyRecoverActionCount('pc3',0)))
        summary=summarize_pc_melee_simulation(observed_batch())
        request=replace(summary.source_request,scenario=mixed)
        with self.assertRaises(ValueError):
            replace(summary,source_request=request,outcome_counts=PcMeleeOutcomeCounts(4,0,0,0),
                total_action_count=4,total_started_round_count=4,total_completed_round_count=0,
                any_pc_defeated_count=0,
                pc_defeat_counts=tuple(PcMeleeDefeatCount(m.actor_id,0) for m in mixed.party),
                help_action_trial_count=2,
                help_action_counts=(PcHelpActionCount('pc1',2),PcHelpActionCount('pc2',0),PcHelpActionCount('pc3',0)),
                ally_recover_action_trial_count=3,
                ally_recover_action_counts=(PcAllyRecoverActionCount('pc1',0),PcAllyRecoverActionCount('pc2',3),PcAllyRecoverActionCount('pc3',0)))

    def test_cached_target_alias_is_refused_before_rng(self):
        original=source()
        forged=deepcopy(original)
        alias=Enum('ForeignString',{'VALUE':'pc3'},type=str).VALUE
        object.__setattr__(forged.party[0].ally_recover_policy,'beneficiary_id',alias)
        self.assertEqual(forged,original)
        with self.assertRaises(TypeError):
            PcMeleeSimulationRequest(forged,42,1)

    def test_healthy_ally_before_its_first_turn_cannot_generate_an_opening_recover(self):
        record=observed_batch().records[0]
        before=replace(record.source_scenario,pc_activation_order=('pc1','pc2','pc3'))
        with self.assertRaises(ValueError):
            replace(record,source_scenario=before)
        summary=summarize_pc_melee_simulation(observed_batch())
        with self.assertRaises(ValueError):
            replace(summary,source_request=replace(summary.source_request,scenario=before))


if __name__=='__main__':
    unittest.main()
