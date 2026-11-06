"""Second-slot NPC Attack observations extend action bounds only by actual counts."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_fixtures import zero_npc_exit_counts,zero_npc_help_counts,zero_npc_recover_counts
from towr.domain.pc_melee_models import PcMeleePolicy,PcHelpPolicy,PcHelpTarget,PcAllyRecoverPolicy
from towr.domain.pc_melee_result_models import PcMeleeOutcome as Outcome
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy
from towr.simulation.pc_melee_models import (
    PcMeleeSimulationRequest,PcMeleeSimulationResult,PcMeleeTrialRecord,
    PcNearMissBurnCount,PcGloriousSpendCount,PcHelpActionCount,PcAllyRecoverActionCount,
    PcNpcHelpActionCount,PcNpcExtraAttackCount,
)
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def source():
    return replace(book_pc_scenario(bears=2,footpads=1,townsfolk=0,pc_count=2,max_rounds=2),
        npc_extra_attack_actor_ids=('bear1',))


def record(request,index,outcome,extras,*,actions=6,started=1,completed=0):
    scenario=request.scenario
    return PcMeleeTrialRecord(scenario,index,request.seed_for(index),outcome,actions,started,completed,
        tuple(member.actor_id for member in scenario.party) if outcome is Outcome.PARTY_DEFEATED else (),
        tuple(PcNearMissBurnCount(member.actor_id,0) for member in scenario.party),
        tuple(PcGloriousSpendCount(member.actor_id,0) for member in scenario.party),
        tuple(PcHelpActionCount(member.actor_id,0) for member in scenario.party),
        tuple(PcAllyRecoverActionCount(member.actor_id,0) for member in scenario.party),
        zero_npc_exit_counts(scenario),zero_npc_help_counts(scenario),
        tuple(PcNpcExtraAttackCount(enemy.state.actor_id,count)
            for enemy,count in zip(scenario.enemies,extras,strict=True)),
        npc_recover_action_counts=zero_npc_recover_counts(scenario))


def observed_batch():
    request=PcMeleeSimulationRequest(source(),42,4)
    return PcMeleeSimulationResult(request,(
        record(request,0,Outcome.UNSUPPORTED_PATH,(1,0,0)),
        record(request,1,Outcome.PARTY_DEFEATED,(2,0,0),actions=9,started=2,completed=1),
        record(request,2,Outcome.ROUND_LIMIT,(0,0,0),actions=10,started=2,completed=2),
        record(request,3,Outcome.UNSUPPORTED_PATH,(0,0,0),actions=0)))


class PcExtraAttackStatisticsTests(unittest.TestCase):
    def test_stopped_prefixes_keep_actual_extra_costs_and_all_source_npcs_in_order(self):
        result=observed_batch()
        summary=summarize_pc_melee_simulation(result)
        self.assertEqual((summary.trials,summary.npc_extra_attack_trial_count,
            summary.total_npc_extra_attack_count),(4,2,3))
        self.assertEqual(summary.npc_extra_attack_counts,(PcNpcExtraAttackCount('bear1',3),
            PcNpcExtraAttackCount('bear2',0),PcNpcExtraAttackCount('footpad1',0)))
        self.assertEqual(summary.total_action_count,25)
        self.assertFalse(hasattr(summary,'records'))

    def test_only_actual_extra_counts_extend_the_ordinary_action_budget(self):
        original=observed_batch().records[0]
        self.assertEqual(original.executed_actions,6)
        ordinary=len(original.source_scenario.party)+len(original.source_scenario.enemies)
        self.assertEqual(ordinary,5)
        with self.assertRaises(ValueError):
            replace(original,npc_extra_attack_counts=tuple(PcNpcExtraAttackCount(item.actor_id,0)
                for item in original.npc_extra_attack_counts))
        with self.assertRaises(ValueError):replace(original,executed_actions=7)
        with self.assertRaises(ValueError):replace(original,executed_actions=1)

    def test_record_counts_require_exact_source_order_configuration_and_round_bounds(self):
        original=observed_batch().records[0]
        for counts in ((),tuple(reversed(original.npc_extra_attack_counts)),
                (PcNpcExtraAttackCount('bear1',0),PcNpcExtraAttackCount('bear2',1),PcNpcExtraAttackCount('footpad1',0)),
                (PcNpcExtraAttackCount('bear1',0),PcNpcExtraAttackCount('bear2',0),PcNpcExtraAttackCount('footpad1',1)),
                (PcNpcExtraAttackCount('bear1',2),*original.npc_extra_attack_counts[1:])):
            with self.subTest(counts=counts),self.assertRaises(ValueError):
                replace(original,npc_extra_attack_counts=counts)
        for counts in ([*original.npc_extra_attack_counts],(object(),)*3):
            with self.assertRaises(TypeError):replace(original,npc_extra_attack_counts=counts)
        forged=deepcopy(original)
        object.__setattr__(forged.npc_extra_attack_counts[0],'count',True)
        with self.assertRaises(TypeError):replace(forged)
        with self.assertRaises(ValueError):
            replace(original,source_scenario=replace(original.source_scenario,npc_extra_attack_actor_ids=()))

    def test_summary_enforces_extra_trial_union_and_extra_containing_round_bounds(self):
        summary=summarize_pc_melee_simulation(observed_batch())
        for value in (None,True,2.0,'2'):
            with self.subTest(value=value),self.assertRaises(TypeError):
                replace(summary,npc_extra_attack_trial_count=value)
        for changes in ({'npc_extra_attack_trial_count':0},{'npc_extra_attack_trial_count':1},
                {'npc_extra_attack_trial_count':5},
                {'npc_extra_attack_counts':tuple(reversed(summary.npc_extra_attack_counts))}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):replace(summary,**changes)
        request=PcMeleeSimulationRequest(source(),42,2)
        batch=PcMeleeSimulationResult(request,(
            record(request,0,Outcome.UNSUPPORTED_PATH,(1,0,0)),
            record(request,1,Outcome.UNSUPPORTED_PATH,(0,0,0),actions=0)))
        summary=summarize_pc_melee_simulation(batch)
        with self.assertRaises(ValueError):
            replace(summary,npc_extra_attack_counts=(PcNpcExtraAttackCount('bear1',2),
                *summary.npc_extra_attack_counts[1:]))

    def test_support_and_required_primary_attacks_cannot_share_extra_action_costs(self):
        original=book_pc_scenario(bears=2,peasants=1,footpads=0,townsfolk=0,pc_count=3,max_rounds=2)
        first,second,third=original.party
        scenario=replace(original,npc_extra_attack_actor_ids=('bear1',),
            enemy_activation_order=('peasant1','bear1','bear2'),
            npc_help_policies=(PcNpcHelpPolicy('peasant1','bear1'),),
            party=(replace(first,policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
                help_policy=PcHelpPolicy('pc3',PcHelpTarget.MELEE_ATTACK,None)),
                replace(second,policy=PcMeleePolicy.RECOVER_ALLY_OR_ATTACK_OR_RECOVER_SELF,
                    ally_recover_policy=PcAllyRecoverPolicy('pc3')),third))
        request=PcMeleeSimulationRequest(scenario,42,1)
        base=record(request,0,Outcome.UNSUPPORTED_PATH,(2,0,0),actions=9,started=2,completed=1)
        supported=replace(base,
            help_action_counts=(PcHelpActionCount('pc1',2),PcHelpActionCount('pc2',0),PcHelpActionCount('pc3',0)),
            ally_recover_action_counts=(PcAllyRecoverActionCount('pc1',0),
                PcAllyRecoverActionCount('pc2',1),PcAllyRecoverActionCount('pc3',0)),
            npc_help_action_counts=(PcNpcHelpActionCount('bear1',0),PcNpcHelpActionCount('bear2',0),
                PcNpcHelpActionCount('peasant1',2)))
        with self.assertRaisesRegex(ValueError,'same action'):replace(supported,executed_actions=8)


if __name__=='__main__':
    unittest.main()
