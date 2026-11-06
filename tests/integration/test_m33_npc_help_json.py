"""Explicit multiple NPC Help pairs and source-ordered action metrics in PC JSON1."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
from itertools import product
import json
import unittest
from unittest.mock import Mock,patch

from jsonschema import ValidationError

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeSimulationInputError,PcMeleeBalanceInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document,validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_service import execute_pc_melee_balance
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def help_document(*,balance=False):
    source=book_pc_scenario(peasants=2,militia=1,empire_knights=1,footpads=0,townsfolk=0,
        pc_count=1,max_rounds=2)
    priority=('empire_knight1','peasant1','peasant2','militia1')
    source=replace(source,npc_help_policies=tuple(PcNpcHelpPolicy(actor,'empire_knight1')
        for actor in ('peasant1','peasant2','militia1')),
        party=tuple(replace(member,target_priority=priority,
            defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority)) for member in source.party))
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            {'group_id':'peasants','actor_ids':['peasant1','peasant2'],'minimum_count':1,'maximum_count':2},
            {'group_id':'militia','actor_ids':['militia1'],'minimum_count':0,'maximum_count':1},
            {'group_id':'knight','actor_ids':['empire_knight1'],'minimum_count':1,'maximum_count':1}],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':4}
        raw['evaluation'].update(trials_per_candidate=2,max_total_trials=8,top_k=2)
    else:
        raw['simulation']['trials']=2
    return raw


class PcNpcHelpJsonTests(unittest.TestCase):
    def test_explicit_multi_helper_pairs_roundtrip_and_empty_policy_retains_opt_out(self):
        for balance in (False,True):
            raw=help_document(balance=balance)
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw[key])
            self.assertEqual(tuple((p.helper_id,p.beneficiary_id) for p in source.npc_help_policies),
                (('peasant1','empire_knight1'),('peasant2','empire_knight1'),('militia1','empire_knight1')))
            self.assertEqual(raw['schema_version'],'1')
            raw[key]['npc_help_policies']=[]
            opted_out=parse(json.dumps(raw))
            source=opted_out.request.template if balance else opted_out.request.scenario
            self.assertEqual(source.npc_help_policies,())
            self.assertEqual(scenario_document(source),raw[key])

    def test_policy_field_and_closed_pair_objects_are_required_at_both_entries(self):
        bad_values=(None,False,{},'peasant1',
            [{'helper_id':'peasant1'}],[{'beneficiary_id':'empire_knight1'}],
            [{'helper_id':1,'beneficiary_id':'empire_knight1'}],
            [{'helper_id':'peasant1','beneficiary_id':None}],
            [{'helper_id':'peasant1','beneficiary_id':'empire_knight1','extra':True}])
        for balance in (False,True):
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            validate=validate_pc_melee_balance_document if balance else validate_pc_melee_simulation_document
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for value in bad_values:
                raw=help_document(balance=balance)
                raw[key]['npc_help_policies']=value
                with self.subTest(balance=balance,value=value):
                    with self.assertRaises(ValidationError):validate(raw)
                    with self.assertRaises(error):parse(json.dumps(raw))
            raw=help_document(balance=balance)
            del raw[key]['npc_help_policies']
            with self.assertRaises(error):parse(json.dumps(raw))

    def test_source_refuses_unknown_roles_self_help_earlier_recipient_duplicates_and_chains(self):
        invalid=(
            [('pc','empire_knight1')],[('unknown','empire_knight1')],
            [('empire_knight1','peasant1')],[('peasant1','peasant1')],
            [('militia1','peasant1')],
            [('peasant1','empire_knight1'),('peasant1','militia1')],
            [('peasant1','empire_knight1'),('peasant1','empire_knight1')],
            [('peasant1','militia1'),('militia1','empire_knight1')])
        for pairs in invalid:
            raw=help_document()
            raw['scenario']['npc_help_policies']=[{'helper_id':helper,'beneficiary_id':target}
                for helper,target in pairs]
            with self.subTest(pairs=pairs),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_actual_trials_encode_three_required_metrics_without_retaining_native_journals(self):
        raw=help_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        result=run_pc_melee_simulation(command.request)
        summary=summarize_pc_melee_simulation(result)
        self.assertEqual(summary.source_request,command.request)
        self.assertEqual(summary.npc_help_action_trial_count,2)
        self.assertGreaterEqual(summary.total_npc_help_action_count,6)
        for record in result.records:
            self.assertEqual(tuple(c.actor_id for c in record.npc_help_action_counts),
                ('peasant1','peasant2','militia1','empire_knight1'))
            self.assertEqual(record.npc_help_action_counts[-1].count,0)
            self.assertFalse(hasattr(record,'state'))
        output=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        validate_pc_melee_simulation_document(output,'result')
        self.assertEqual(output['request'],raw)
        self.assertEqual(output['summary']['npc_help_action_trial_count'],2)
        self.assertEqual(output['summary']['total_npc_help_action_count'],summary.total_npc_help_action_count)
        self.assertEqual(output['summary']['npc_help_action_counts'],
            [{'actor_id':item.actor_id,'count':item.count} for item in summary.npc_help_action_counts])
        self.assertFalse(hasattr(summary,'records'))
        for field in ('npc_help_action_trial_count','npc_help_action_counts','total_npc_help_action_count'):
            malformed=deepcopy(output)
            del malformed['summary'][field]
            with self.subTest(missing=field),self.assertRaises(ValidationError):
                validate_pc_melee_simulation_document(malformed,'result')

    def test_count_search_filters_each_pair_by_both_retained_ids_and_preserves_summary_source_order(self):
        raw=help_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates),report.total_trials),(4,8))
        self.assertEqual(tuple(c.counts for c in report.candidates),tuple(product((1,2),(0,1),(1,))))
        template=command.request.template
        for candidate in report.candidates:
            source=candidate.source_request.scenario
            retained=tuple(e.state.actor_id for e in source.enemies)
            self.assertEqual(source.npc_help_policies,tuple(p for p in template.npc_help_policies
                if p.helper_id in retained and p.beneficiary_id in retained))
            self.assertEqual(tuple(c.actor_id for c in candidate.summary.npc_help_action_counts),retained)
            self.assertGreater(candidate.summary.total_npc_help_action_count,0)
            self.assertEqual(candidate.summary.npc_help_action_counts[-1].count,0)
            self.assertFalse(hasattr(candidate.summary,'records'))
        output=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(output,'result')
        self.assertEqual(output['request'],raw)
        for candidate,typed in zip(output['candidates'],report.candidates,strict=True):
            self.assertEqual(candidate['request']['scenario'],scenario_document(typed.source_request.scenario))
            self.assertEqual(candidate['summary']['total_npc_help_action_count'],typed.summary.total_npc_help_action_count)

    def test_cached_equal_policy_alias_is_rejected_before_rng_and_native_execution(self):
        class Alias(str,Enum):
            PEASANT='peasant1'
        command=wire.parse_pc_melee_simulation_request(json.dumps(help_document()))
        forged=deepcopy(command.request)
        object.__setattr__(forged.scenario.npc_help_policies[0],'helper_id',Alias.PEASANT)
        self.assertEqual(forged,command.request)
        rng=Mock(side_effect=AssertionError('malformed source cannot consume RNG'))
        runner=Mock(side_effect=AssertionError('malformed source cannot become an observation'))
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',runner):
            with self.assertRaises(TypeError):run_pc_melee_trial(forged,0,rng_factory=rng)
        rng.assert_not_called()
        runner.assert_not_called()

    def test_process_matches_sequential_for_real_npc_help_policies_and_compact_counts(self):
        request=wire.parse_pc_melee_simulation_request(json.dumps(help_document())).request
        sequential=run_pc_melee_simulation(request)
        self.assertGreater(sum(item.count for record in sequential.records
            for item in record.npc_help_action_counts),0)
        parallel=run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(parallel,sequential)
        self.assertEqual(summarize_pc_melee_simulation(parallel),summarize_pc_melee_simulation(sequential))
        source_order=tuple(enemy.state.actor_id for enemy in request.scenario.enemies)
        for record in parallel.records:
            self.assertEqual(tuple(item.actor_id for item in record.npc_help_action_counts),source_order)
            self.assertFalse(hasattr(record,'state'))
            self.assertFalse(hasattr(record,'steps'))


if __name__=='__main__':
    unittest.main()
