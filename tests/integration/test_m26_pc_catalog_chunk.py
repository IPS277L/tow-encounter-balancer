"""One current-contract catalogue chunk across trials, count search and spawn."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
from itertools import product
import json
from random import Random
import unittest
from unittest.mock import Mock, patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document, validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_service import execute_pc_melee_balance
from towr.domain.condition_models import Condition
from towr.domain.injury_models import ProfileNpcType
from towr.domain.pc_melee_result_models import PcProfileWoundProof
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation, run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def chunk_document(*,balance=False):
    source=book_pc_scenario(merchants=2 if balance else 1,artisans=1,squires=1,
        footpads=0,townsfolk=0,pc_count=2,max_rounds=3)
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            {'group_id':'merchants','actor_ids':['merchant1','merchant2'],'minimum_count':1,'maximum_count':2},
            {'group_id':'artisans','actor_ids':['artisan1'],'minimum_count':0,'maximum_count':1},
            {'group_id':'squires','actor_ids':['squire1'],'minimum_count':0,'maximum_count':1}],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':8}
        raw['evaluation'].update(trials_per_candidate=2,max_total_trials=16,top_k=2)
    else:
        raw['simulation']['trials']=2
    return raw


class PcCatalogChunkIntegrationTests(unittest.TestCase):
    def test_current_json_roundtrip_actual_trials_and_source_ordered_aggregates(self):
        raw=chunk_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        source=command.request.scenario
        self.assertEqual(scenario_document(source),raw['scenario'])
        self.assertEqual(tuple(enemy.state.actor_id for enemy in source.enemies),
            ('merchant1','artisan1','squire1'))
        self.assertEqual(tuple(enemy.definition.id for enemy in source.enemies),
            ('pc-book-npc:elf_merchant_jewelled_blade','pc-book-npc:artisan',
             'pc-book-npc:bretonnian_squire_sword'))
        for enemy in source.enemies:
            validate_pc_book_npc_definition(enemy.definition)
            self.assertIs(enemy.definition.protection[0].skill,Skill.ATHLETICS)
        trials=run_pc_melee_simulation(command.request)
        summary=summarize_pc_melee_simulation(trials)
        self.assertEqual(summary.source_request,command.request)
        self.assertEqual(summary.trials,2)
        for record in trials.records:
            self.assertEqual(record.source_scenario,source)
            self.assertEqual(tuple(item.actor_id for item in record.npc_exit_counts),
                ('merchant1','artisan1','squire1'))
        self.assertEqual(tuple((item.actor_id,item.count) for item in summary.npc_exit_counts),
            (('merchant1',0),('artisan1',0),('squire1',0)))
        self.assertEqual(tuple(item.actor_id for item in summary.pc_defeat_counts),('pc1','pc2'))
        self.assertEqual((summary.npc_exit_trial_count,summary.total_npc_exit_count,
            summary.objective_with_npc_exit_count),(0,0,0))
        result=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        validate_pc_melee_simulation_document(result,'result')
        self.assertEqual(result['request'],raw)
        self.assertEqual((raw['schema_version'],result['schema_version']),('1','1'))
        self.assertFalse(hasattr(summary,'records'))

    def test_eight_candidate_prefixes_preserve_full_profiles_and_aggregate_only_results(self):
        raw=chunk_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates),report.planned_trials,report.total_trials),(8,16,16))
        self.assertEqual(tuple(candidate.counts for candidate in report.candidates),
            tuple(product((1,2),(0,1),(0,1))))
        template=command.request.template
        originals={enemy.state.actor_id:enemy.definition for enemy in template.enemies}
        for candidate in report.candidates:
            merchants,artisans,squires=candidate.counts
            expected=tuple(f'merchant{index+1}' for index in range(merchants))+(
                ('artisan1',) if artisans else ())+ (('squire1',) if squires else ())
            projected=candidate.source_request.scenario
            self.assertEqual(tuple(enemy.state.actor_id for enemy in projected.enemies),expected)
            self.assertEqual(projected.enemy_activation_order,expected)
            self.assertEqual(projected.facts,template.facts)
            self.assertEqual(projected.npc_broken_exit_policy,template.npc_broken_exit_policy)
            for member,original in zip(projected.party,template.party,strict=True):
                self.assertEqual(member.target_priority,expected)
                self.assertEqual(tuple(decision.target_id for decision in member.defeat_decisions),expected)
                self.assertEqual(replace(member,target_priority=original.target_priority,
                    defeat_decisions=original.defeat_decisions),original)
            for enemy in projected.enemies:
                self.assertEqual(enemy.definition,originals[enemy.state.actor_id])
                validate_pc_book_npc_definition(enemy.definition)
            self.assertEqual(candidate.summary.source_request,candidate.source_request)
            self.assertEqual(tuple(item.actor_id for item in candidate.summary.npc_exit_counts),expected)
            self.assertEqual(candidate.summary.objective_with_npc_exit_count,0)
            self.assertFalse(hasattr(candidate.summary,'records'))
            self.assertFalse(hasattr(candidate.summary,'steps'))
        result=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(result,'result')
        self.assertEqual(result['request'],raw)
        for candidate,typed in zip(result['candidates'],report.candidates,strict=True):
            self.assertEqual(candidate['request']['scenario'],scenario_document(typed.source_request.scenario))
        self.assertEqual((raw['schema_version'],result['schema_version']),('1','1'))

    def test_reserved_nested_sources_reject_renamed_and_rewritten_chunk_profiles(self):
        for index in range(3):
            for claimed in ('attack','protection'):
                raw=chunk_document()
                definition=raw['scenario']['enemies'][index]['definition']
                definition.update(id='authored:renamed',source_rule_id='authored:renamed-source')
                definition['attack']['damage']['base']+=1
                if claimed=='attack':
                    definition['protection']['source_rule_id']='authored:protection'
                else:
                    definition['attack']['source_rule_id']='authored:attack'
                with self.subTest(index=index,claimed=claimed),self.assertRaises(PcMeleeSimulationInputError):
                    wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_equal_cached_skill_aliases_are_refused_before_rng_or_observation(self):
        command=wire.parse_pc_melee_simulation_request(json.dumps(chunk_document()))
        alias=Enum('ForeignSkill',{'ATHLETICS':'athletics'},type=str).ATHLETICS
        for index in range(3):
            for value in ('athletics',alias):
                forged=deepcopy(command.request)
                object.__setattr__(forged.scenario.enemies[index].definition.protection[0],'skill',value)
                self.assertEqual(forged,command.request)
                with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario') as runner:
                    rng=Mock(side_effect=AssertionError('inadmissible source must not consume RNG'))
                    with self.subTest(index=index,value=value),self.assertRaises(TypeError):
                        run_pc_melee_trial(forged,0,rng_factory=rng)
                    rng.assert_not_called()
                    runner.assert_not_called()

    def test_process_matches_sequential_with_an_actual_merchant_first_wound(self):
        command=wire.parse_pc_melee_simulation_request(json.dumps(chunk_document()))
        request=PcMeleeSimulationRequest(command.request.scenario,42,2)
        sequential=run_pc_melee_simulation(request)
        first_wounds=0
        for record in sequential.records:
            native=run_pc_melee_scenario(request.scenario,Random(record.seed))
            for step in native.steps:
                if (isinstance(step.proof,PcProfileWoundProof)
                        and step.proof.source.npc_type is ProfileNpcType.BRUTE
                        and step.proof.source.previous_wounds==0 and step.proof.source.current_wounds==1
                        and step.state.enemy('merchant1').state.injury.wounds==1):
                    first_wounds+=1
                    self.assertFalse(step.state.enemy('merchant1').state.injury.defeated)
                    self.assertTrue(step.state.enemy('merchant1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertGreater(first_wounds,0,'representative spawn source must exercise Merchant first-Wound Staggered')
        process=run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(process,sequential)
        self.assertEqual(summarize_pc_melee_simulation(process),summarize_pc_melee_simulation(sequential))


if __name__=='__main__':
    unittest.main()
