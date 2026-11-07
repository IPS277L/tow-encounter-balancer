from tests.support.pc_melee_fixtures import zero_npc_warped_form_counts
from tests.support.pc_melee_fixtures import zero_npc_recover_counts
"""Source-ordered NPC Help actions retain stopped prefixes and share action budgets."""
from tests.support.pc_melee_fixtures import zero_npc_extra_attack_counts
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_fixtures import zero_npc_exit_counts
from towr.domain.pc_melee_models import PcMeleePolicy,PcHelpPolicy,PcHelpTarget,PcAllyRecoverPolicy
from towr.domain.pc_melee_result_models import PcMeleeOutcome as Outcome
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy
from towr.simulation.pc_melee_models import (
    PcMeleeSimulationRequest,PcMeleeSimulationResult,PcMeleeTrialRecord,
    PcNearMissBurnCount,PcGloriousSpendCount,PcHelpActionCount,PcAllyRecoverActionCount,PcNpcHelpActionCount,
)
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def source(*,pcs=2):
    original=book_pc_scenario(peasants=2,militia=1,empire_knights=1,footpads=0,townsfolk=0,
        pc_count=pcs,max_rounds=3)
    return replace(original,npc_help_policies=tuple(PcNpcHelpPolicy(actor,'empire_knight1')
        for actor in ('peasant1','peasant2','militia1')))


def record(request,index,outcome,counts,*,actions=4,started=1,completed=0):
    scenario=request.scenario
    return PcMeleeTrialRecord(scenario,index,request.seed_for(index),outcome,actions,started,completed,
        tuple(m.actor_id for m in scenario.party) if outcome is Outcome.PARTY_DEFEATED else (),
        tuple(PcNearMissBurnCount(m.actor_id,0) for m in scenario.party),
        tuple(PcGloriousSpendCount(m.actor_id,0) for m in scenario.party),
        tuple(PcHelpActionCount(m.actor_id,0) for m in scenario.party),
        tuple(PcAllyRecoverActionCount(m.actor_id,0) for m in scenario.party),
        zero_npc_exit_counts(scenario),
        tuple(PcNpcHelpActionCount(e.state.actor_id,count)
            for e,count in zip(scenario.enemies,counts,strict=True)), npc_extra_attack_counts=zero_npc_extra_attack_counts(scenario), npc_recover_action_counts=zero_npc_recover_counts(scenario), npc_warped_form_counts=zero_npc_warped_form_counts(scenario))


def observed_batch():
    request=PcMeleeSimulationRequest(source(),42,4)
    return PcMeleeSimulationResult(request,(
        record(request,0,Outcome.OBJECTIVE_ACHIEVED,(1,1,0,0)),
        record(request,1,Outcome.PARTY_DEFEATED,(1,0,0,0)),
        record(request,2,Outcome.ROUND_LIMIT,(2,0,1,0),actions=7,started=3,completed=3),
        record(request,3,Outcome.UNSUPPORTED_PATH,(0,0,0,0),actions=0)))


class PcNpcHelpStatisticsTests(unittest.TestCase):
    def test_stopped_prefixes_and_zero_helpers_keep_the_full_trial_denominator(self):
        result=observed_batch()
        summary=summarize_pc_melee_simulation(result)
        self.assertEqual(summary.trials,4)
        self.assertEqual(summary.npc_help_action_trial_count,3)
        self.assertEqual(summary.total_npc_help_action_count,6)
        self.assertEqual(summary.npc_help_action_counts,tuple(PcNpcHelpActionCount(actor,count)
            for actor,count in (('peasant1',4),('peasant2',1),('militia1',1),('empire_knight1',0))))
        self.assertEqual((summary.total_help_action_count,summary.total_ally_recover_action_count),(0,0))
        self.assertFalse(hasattr(summary,'records'))
        self.assertTrue(all(not hasattr(record,'state') for record in result.records))

    def test_record_requires_exact_source_order_eligible_role_and_per_round_bounds(self):
        original=observed_batch().records[0]
        for counts in ((),tuple(reversed(original.npc_help_action_counts)),
                (*original.npc_help_action_counts[:3],PcNpcHelpActionCount('empire_knight1',1)),
                (PcNpcHelpActionCount('peasant1',2),*original.npc_help_action_counts[1:]),
                (PcNpcHelpActionCount('unknown',1),*original.npc_help_action_counts[1:])):
            with self.subTest(counts=counts),self.assertRaises(ValueError):
                replace(original,npc_help_action_counts=counts)
        with self.assertRaises(ValueError):
            replace(original,source_scenario=replace(original.source_scenario,npc_help_policies=()))
        for counts in ([*original.npc_help_action_counts],(object(),)*4):
            with self.assertRaises(TypeError):
                replace(original,npc_help_action_counts=counts)
        forged=deepcopy(original)
        object.__setattr__(forged.npc_help_action_counts[0],'count',True)
        with self.assertRaises(TypeError):
            replace(forged)

    def test_summary_limits_union_trials_and_help_containing_started_rounds(self):
        summary=summarize_pc_melee_simulation(observed_batch())
        for value in (True,None,1.0,'1'):
            with self.subTest(value=value),self.assertRaises(TypeError):
                replace(summary,npc_help_action_trial_count=value)
        for changes in ({'npc_help_action_trial_count':0},{'npc_help_action_trial_count':5},
                {'npc_help_action_trial_count':1},
                {'npc_help_action_counts':tuple(reversed(summary.npc_help_action_counts))},
                {'npc_help_action_counts':(PcNpcHelpActionCount('peasant1',6),
                    *summary.npc_help_action_counts[1:])}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                replace(summary,**changes)
        # Two trials both started, but only one has Help and has at most one round.
        request=PcMeleeSimulationRequest(replace(source(),max_rounds=2),42,2)
        batch=PcMeleeSimulationResult(request,(
            record(request,0,Outcome.UNSUPPORTED_PATH,(1,0,0,0)),
            record(request,1,Outcome.UNSUPPORTED_PATH,(0,0,0,0),actions=0)))
        summary=summarize_pc_melee_simulation(batch)
        with self.assertRaises(ValueError):
            replace(summary,npc_help_action_counts=(PcNpcHelpActionCount('peasant1',2),
                *summary.npc_help_action_counts[1:]))

    def test_pc_help_ally_recover_and_npc_help_cannot_claim_the_same_action(self):
        scenario=source(pcs=3)
        first,second,third=scenario.party
        scenario=replace(scenario,party=(
            replace(first,policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
                help_policy=PcHelpPolicy('pc3',PcHelpTarget.MELEE_ATTACK,None)),
            replace(second,policy=PcMeleePolicy.RECOVER_ALLY_OR_ATTACK_OR_RECOVER_SELF,
                ally_recover_policy=PcAllyRecoverPolicy('pc3')),third))
        request=PcMeleeSimulationRequest(scenario,42,1)
        original=record(request,0,Outcome.UNSUPPORTED_PATH,(2,2,2,0),actions=9,started=2,completed=1)
        supported=replace(original,help_action_counts=(PcHelpActionCount('pc1',2),
            PcHelpActionCount('pc2',0),PcHelpActionCount('pc3',0)),
            ally_recover_action_counts=(PcAllyRecoverActionCount('pc1',0),
                PcAllyRecoverActionCount('pc2',1),PcAllyRecoverActionCount('pc3',0)))
        with self.assertRaisesRegex(ValueError,'same action'):
            replace(supported,executed_actions=8)


if __name__=='__main__':
    unittest.main()
