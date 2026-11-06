"""Greenskin dice/free-success Help uses the existing PC JSON1 policy and counters."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
from itertools import product
import json
import unittest
from unittest.mock import Mock,patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document,validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_service import execute_pc_melee_balance
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


HELPER_VARIANTS=(('goblins','goblin1'),('night_goblins','night_goblin1'),
                 ('orcs','orc1'),('big_uns','big_un1'))


def _set_knight_first(source,helper):
    priority=('empire_knight1',helper)
    return replace(source,enemy_activation_order=(helper,'empire_knight1'),
        npc_help_policies=(PcNpcHelpPolicy(helper,'empire_knight1'),),
        party=tuple(replace(member,target_priority=priority,
            defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority))
            for member in source.party))


def greenskin_help_document(*,balance=False):
    """Mixed three-helper example; source order deliberately differs from activation."""
    source=book_pc_scenario(goblins=1,night_goblins=1,orcs=1,big_uns=1,
        footpads=0,townsfolk=0,pc_count=1,max_rounds=2)
    priority=('big_un1','goblin1','night_goblin1','orc1')
    source=replace(source,enemy_activation_order=('goblin1','night_goblin1','orc1','big_un1'),
        npc_help_policies=tuple(PcNpcHelpPolicy(actor,'big_un1')
            for actor in ('goblin1','night_goblin1','orc1')),
        party=tuple(replace(member,target_priority=priority,
            defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority))
            for member in source.party))
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            {'group_id':'goblins','actor_ids':['goblin1'],'minimum_count':1,'maximum_count':1},
            {'group_id':'night_goblins','actor_ids':['night_goblin1'],'minimum_count':0,'maximum_count':1},
            {'group_id':'big_uns','actor_ids':['big_un1'],'minimum_count':0,'maximum_count':1},
            {'group_id':'orcs','actor_ids':['orc1'],'minimum_count':0,'maximum_count':1}],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':8}
        raw['evaluation'].update(trials_per_candidate=1,max_total_trials=8,top_k=2)
    else:
        raw['simulation']['trials']=2
    return raw


class GreenskinHelpJsonTests(unittest.TestCase):
    def test_all_four_printed_helper_variants_roundtrip_without_new_wire_fields(self):
        for keyword,actor in HELPER_VARIANTS:
            source=book_pc_scenario(**{keyword:1},empire_knights=1,footpads=0,townsfolk=0,
                pc_count=1,max_rounds=1)
            source=_set_knight_first(source,actor)
            raw=document()
            raw['scenario']=scenario_document(source)
            command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
            with self.subTest(helper=keyword):
                self.assertEqual(command.request.scenario,source)
                self.assertEqual(scenario_document(command.request.scenario),raw['scenario'])
                self.assertEqual(raw['scenario']['npc_help_policies'],
                    [{'helper_id':actor,'beneficiary_id':'empire_knight1'}])
                self.assertEqual(raw['schema_version'],'1')
        for balance in (False,True):
            raw=greenskin_help_document(balance=balance)
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw[key])
            self.assertEqual(tuple(enemy.state.actor_id for enemy in source.enemies),
                ('goblin1','night_goblin1','big_un1','orc1'))
            self.assertEqual(source.enemy_activation_order,('goblin1','night_goblin1','orc1','big_un1'))

    def test_real_mixed_help_trials_keep_actual_costs_and_source_ordered_counts(self):
        raw=greenskin_help_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        result=run_pc_melee_simulation(command.request)
        summary=summarize_pc_melee_simulation(result)
        self.assertGreater(summary.total_npc_help_action_count,0)
        self.assertEqual(summary.npc_help_action_trial_count,2)
        expected=('goblin1','night_goblin1','big_un1','orc1')
        for record in result.records:
            self.assertEqual(tuple(c.actor_id for c in record.npc_help_action_counts),expected)
            self.assertEqual(record.npc_help_action_counts[2].count,0)
            self.assertGreaterEqual(record.npc_help_action_counts[3].count,1)
            self.assertLessEqual(sum(c.count for c in record.npc_help_action_counts),record.executed_actions)
            self.assertFalse(hasattr(record,'steps'))
        output=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        validate_pc_melee_simulation_document(output,'result')
        self.assertEqual(output['request'],raw)
        self.assertEqual(output['summary']['npc_help_action_counts'],
            [{'actor_id':c.actor_id,'count':c.count} for c in summary.npc_help_action_counts])
        self.assertEqual(output['summary']['total_npc_help_action_count'],summary.total_npc_help_action_count)
        self.assertFalse(hasattr(summary,'records'))

    def test_count_search_filters_both_pair_endpoints_without_changing_caller_orders(self):
        raw=greenskin_help_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates),report.total_trials),(8,8))
        self.assertEqual(tuple(c.counts for c in report.candidates),
            tuple(product((1,),(0,1),(0,1),(0,1))))
        template=command.request.template
        for candidate in report.candidates:
            source=candidate.source_request.scenario
            retained=tuple(enemy.state.actor_id for enemy in source.enemies)
            expected_policies=tuple(policy for policy in template.npc_help_policies
                if policy.helper_id in retained and policy.beneficiary_id in retained)
            self.assertEqual(source.npc_help_policies,expected_policies)
            self.assertEqual(source.enemy_activation_order,
                tuple(actor for actor in template.enemy_activation_order if actor in retained))
            self.assertEqual(source.party[0].target_priority,
                tuple(actor for actor in template.party[0].target_priority if actor in retained))
            self.assertEqual(tuple(c.actor_id for c in candidate.summary.npc_help_action_counts),retained)
            configured={policy.helper_id for policy in expected_policies}
            self.assertTrue(all(c.count==0 for c in candidate.summary.npc_help_action_counts
                if c.actor_id not in configured))
            if 'big_un1' not in retained:
                self.assertEqual(expected_policies,())
                self.assertEqual(candidate.summary.total_npc_help_action_count,0)
            self.assertFalse(hasattr(candidate.summary,'records'))
        output=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(output,'result')
        self.assertEqual(output['request'],raw)
        for candidate,typed in zip(output['candidates'],report.candidates,strict=True):
            self.assertEqual(candidate['request']['scenario'],scenario_document(typed.source_request.scenario))

    def test_greenskin_pairs_keep_existing_role_endpoint_and_no_chain_guards(self):
        pairs=(
            [('goblin1','goblin1')],[('unknown','big_un1')],[('goblin1','pc')],
            [('big_un1','orc1')],
            [('goblin1','big_un1'),('goblin1','orc1')],
            [('goblin1','orc1'),('orc1','big_un1')])
        for policies in pairs:
            raw=greenskin_help_document()
            raw['scenario']['npc_help_policies']=[{'helper_id':helper,'beneficiary_id':beneficiary}
                for helper,beneficiary in policies]
            with self.subTest(policies=policies),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_cached_equal_aliases_for_each_new_helper_fail_before_rng(self):
        aliases=Enum('HelperAlias',{actor:actor for _,actor in HELPER_VARIANTS},type=str)
        for keyword,actor in HELPER_VARIANTS:
            source=book_pc_scenario(**{keyword:1},empire_knights=1,footpads=0,townsfolk=0,
                pc_count=1,max_rounds=1)
            raw=document()
            raw['scenario']=scenario_document(_set_knight_first(source,actor))
            command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
            forged=deepcopy(command.request)
            object.__setattr__(forged.scenario.npc_help_policies[0],'helper_id',aliases(actor))
            self.assertEqual(forged,command.request)
            rng=Mock(side_effect=AssertionError('malformed source cannot consume RNG'))
            runner=Mock(side_effect=AssertionError('malformed source cannot become an observation'))
            with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',runner):
                with self.subTest(helper=keyword),self.assertRaises(TypeError):
                    run_pc_melee_trial(forged,0,rng_factory=rng)
            rng.assert_not_called()
            runner.assert_not_called()

    def test_empty_pair_list_keeps_all_greenskins_on_existing_attack_strategy(self):
        raw=greenskin_help_document()
        raw['scenario']['npc_help_policies']=[]
        raw['simulation']['trials']=1
        raw['scenario']['max_rounds']=1
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        summary=summarize_pc_melee_simulation(run_pc_melee_simulation(command.request))
        self.assertEqual((summary.npc_help_action_trial_count,summary.total_npc_help_action_count),(0,0))
        self.assertEqual(tuple((item.actor_id,item.count) for item in summary.npc_help_action_counts),
            (('goblin1',0),('night_goblin1',0),('big_un1',0),('orc1',0)))


if __name__=='__main__':
    unittest.main()
