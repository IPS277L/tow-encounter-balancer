from tests.support.pc_melee_fixtures import zero_npc_warped_form_counts
from tests.support.pc_melee_fixtures import zero_npc_recover_counts
"""Source-ordered actual NPC exits remain separate from defeat and victory."""
from tests.support.pc_melee_fixtures import zero_npc_extra_attack_counts
from tests.support.pc_melee_fixtures import zero_npc_help_counts
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from towr.domain.pc_melee_models import PcAdjacentNpcExitPolicy
from towr.domain.pc_melee_result_models import PcMeleeOutcome
from towr.simulation.pc_melee_models import (
    PcAllyRecoverActionCount, PcGloriousSpendCount, PcHelpActionCount,
    PcMeleeOutcomeCounts, PcMeleeSimulationRequest, PcMeleeSimulationResult,
    PcMeleeTrialRecord, PcNearMissBurnCount, PcNpcExitCount,
)
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def exit_source():
    source=book_pc_scenario(officials=2,footpads=1,townsfolk=0,pc_count=2,max_rounds=1)
    return replace(source,facts=replace(source.facts,can_leave_zone=True),
        npc_broken_exit_policy=PcAdjacentNpcExitPolicy('adjacent:exit',True,True))


def record(request,index,outcome,exits):
    source=request.scenario
    return PcMeleeTrialRecord(source,index,request.seed_for(index),outcome,2,1,
        int(outcome is PcMeleeOutcome.ROUND_LIMIT),
        tuple(member.actor_id for member in source.party) if outcome is PcMeleeOutcome.PARTY_DEFEATED else (),
        tuple(PcNearMissBurnCount(member.actor_id,0) for member in source.party),
        tuple(PcGloriousSpendCount(member.actor_id,0) for member in source.party),
        tuple(PcHelpActionCount(member.actor_id,0) for member in source.party),
        tuple(PcAllyRecoverActionCount(member.actor_id,0) for member in source.party),
        tuple(PcNpcExitCount(enemy.state.actor_id,count) for enemy,count in zip(source.enemies,exits,strict=True)), npc_help_action_counts=zero_npc_help_counts(source), npc_extra_attack_counts=zero_npc_extra_attack_counts(source), npc_recover_action_counts=zero_npc_recover_counts(source), npc_warped_form_counts=zero_npc_warped_form_counts(source))


def sample_result():
    request=PcMeleeSimulationRequest(exit_source(),42,4)
    return PcMeleeSimulationResult(request,tuple(record(request,index,outcome,exits)
        for index,(outcome,exits) in enumerate((
            (PcMeleeOutcome.OBJECTIVE_ACHIEVED,(1,0,0)),
            (PcMeleeOutcome.ROUND_LIMIT,(0,1,0)),
            (PcMeleeOutcome.UNSUPPORTED_PATH,(1,1,0)),
            (PcMeleeOutcome.PARTY_DEFEATED,(0,0,0))))))


class PcNpcExitStatisticsTests(unittest.TestCase):
    def test_departures_cannot_exceed_the_actions_needed_to_cause_their_wounds(self):
        result=sample_result()
        with self.assertRaises(ValueError):
            replace(result.records[2],executed_actions=1)
        summary=summarize_pc_melee_simulation(result)
        with self.assertRaises(ValueError):
            replace(summary,total_action_count=4,npc_exit_counts=(
                PcNpcExitCount('official1',3),PcNpcExitCount('official2',3),
                PcNpcExitCount('footpad1',0)))

    def test_compact_records_and_summary_count_actual_exits_in_source_order(self):
        result=sample_result()
        summary=summarize_pc_melee_simulation(result)
        self.assertEqual(summary.outcome_counts,PcMeleeOutcomeCounts(1,1,1,1))
        self.assertEqual(summary.npc_exit_trial_count,3)
        self.assertEqual(summary.npc_exit_counts,(PcNpcExitCount('official1',2),
            PcNpcExitCount('official2',2),PcNpcExitCount('footpad1',0)))
        self.assertEqual(summary.total_npc_exit_count,4)
        self.assertEqual(summary.objective_with_npc_exit_count,1)
        self.assertFalse(hasattr(summary,'records'))
        self.assertFalse(hasattr(result.records[0],'state'))
        self.assertFalse(hasattr(result.records[0],'steps'))

    def test_exit_observations_can_precede_loss_limit_or_unsupported_without_implying_victory(self):
        source=exit_source()
        for outcome in PcMeleeOutcome:
            request=PcMeleeSimulationRequest(source,42,1)
            summary=summarize_pc_melee_simulation(PcMeleeSimulationResult(request,
                (record(request,0,outcome,(1,0,0)),)))
            self.assertEqual(summary.npc_exit_trial_count,1)
            self.assertEqual(summary.objective_with_npc_exit_count,int(outcome is PcMeleeOutcome.OBJECTIVE_ACHIEVED))

    def test_each_trial_has_binary_complete_ordered_npc_counts_and_eligible_sources(self):
        original=sample_result().records[0]
        for counts in ((PcNpcExitCount('official1',2),*original.npc_exit_counts[1:]),
                original.npc_exit_counts[::-1],original.npc_exit_counts[:-1],
                (*original.npc_exit_counts[:2],PcNpcExitCount('footpad1',1)),
                (PcNpcExitCount('foreign',1),*original.npc_exit_counts[1:])):
            with self.subTest(counts=counts),self.assertRaises(ValueError):
                replace(original,npc_exit_counts=counts)
        with self.assertRaises(TypeError):
            replace(original,npc_exit_counts=list(original.npc_exit_counts))
        with self.assertRaises(ValueError):
            replace(original,source_scenario=replace(original.source_scenario,npc_broken_exit_policy=None))
        zero=tuple(replace(item,count=0) for item in original.npc_exit_counts)
        self.assertEqual(replace(original,npc_exit_counts=zero,
            source_scenario=replace(original.source_scenario,npc_broken_exit_policy=None)).npc_exit_counts,zero)

    def test_summary_refuses_false_types_incomplete_source_and_inconsistent_exit_marginals(self):
        summary=summarize_pc_melee_simulation(sample_result())
        invalid=(dict(npc_exit_trial_count=True),dict(npc_exit_trial_count=-1),dict(npc_exit_trial_count=5),
            dict(npc_exit_trial_count=0),dict(npc_exit_trial_count=1),
            dict(npc_exit_counts=summary.npc_exit_counts[:-1]),
            dict(npc_exit_counts=summary.npc_exit_counts[::-1]),
            dict(npc_exit_counts=list(summary.npc_exit_counts)),
            dict(npc_exit_counts=(PcNpcExitCount('official1',4),*summary.npc_exit_counts[1:])),
            dict(npc_exit_counts=(*summary.npc_exit_counts[:2],PcNpcExitCount('footpad1',1))),
            dict(npc_exit_counts=tuple(replace(item,count=0) for item in summary.npc_exit_counts)),
            dict(objective_with_npc_exit_count=True),dict(objective_with_npc_exit_count=-1),
            dict(objective_with_npc_exit_count=2))
        for changes in invalid:
            with self.subTest(changes=changes),self.assertRaises((TypeError,ValueError)):
                replace(summary,**changes)
        no_policy=replace(summary.source_request,scenario=replace(summary.source_request.scenario,npc_broken_exit_policy=None))
        with self.assertRaises(ValueError):
            replace(summary,source_request=no_policy)

    def test_joint_count_uses_both_frechet_bounds_including_zero_and_full_overlap(self):
        summary=summarize_pc_melee_simulation(sample_result())
        changes=dict(outcome_counts=PcMeleeOutcomeCounts(3,1,0,0))
        for joint in (2,3):
            self.assertEqual(replace(summary,**changes,objective_with_npc_exit_count=joint).objective_with_npc_exit_count,joint)
        for joint in (0,1,4):
            with self.subTest(joint=joint),self.assertRaises(ValueError):
                replace(summary,**changes,objective_with_npc_exit_count=joint)
        self.assertEqual(replace(summary,objective_with_npc_exit_count=0).objective_with_npc_exit_count,0)

    def test_count_constructor_and_cached_aliases_are_readmitted(self):
        for actor,count in (('',0),(True,0),('npc',True),('npc',1.5),('npc',-1)):
            with self.subTest(actor=actor,count=count),self.assertRaises((TypeError,ValueError)):
                PcNpcExitCount(actor,count)
        summary=summarize_pc_melee_simulation(sample_result())
        alias=Enum('ForeignActor',{'OFFICIAL':'official1'},type=str).OFFICIAL
        forged=deepcopy(summary)
        object.__setattr__(forged.npc_exit_counts[0],'actor_id',alias)
        self.assertEqual(forged,summary)
        with self.assertRaises(TypeError):
            replace(forged)
        result=sample_result()
        forged=deepcopy(result)
        object.__setattr__(forged.records[0].npc_exit_counts[2],'count',False)
        self.assertEqual(forged,result)
        with self.assertRaises(TypeError):
            replace(forged)


if __name__=='__main__':
    unittest.main()
