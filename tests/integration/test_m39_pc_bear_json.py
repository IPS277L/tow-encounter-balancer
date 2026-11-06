"""Explicit Bear second-Attack permission and compact costs use current PC JSON1."""
from copy import deepcopy
from dataclasses import fields,replace
from enum import Enum
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
from towr.domain.pc_melee_models import PcMeleeScenario,PcMeleeWeapon
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def bear_document(*,balance=False,enabled=True):
    source=book_pc_scenario(bears=2 if balance else 1,footpads=1,townsfolk=0,pc_count=2,max_rounds=2)
    selected=('bear1','bear2') if balance else ('bear1',)
    source=replace(source,npc_extra_attack_actor_ids=selected if enabled else (),
        party=tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.AXE))
            for member in source.party))
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            {'group_id':'bears','actor_ids':['bear1','bear2'],'minimum_count':0,'maximum_count':2},
            {'group_id':'footpads','actor_ids':['footpad1'],'minimum_count':1,'maximum_count':1}],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':3}
        raw['evaluation'].update(trials_per_candidate=1,max_total_trials=3,top_k=2)
    else:
        raw['simulation']['trials']=2
    return raw


class PcBearJsonTests(unittest.TestCase):
    def test_enabled_and_empty_policy_roundtrip_without_changing_other_source_fields(self):
        for balance in (False,True):
            for enabled in (False,True):
                raw=bear_document(balance=balance,enabled=enabled)
                key='template' if balance else 'scenario'
                parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
                command=parse(json.dumps(raw))
                source=command.request.template if balance else command.request.scenario
                self.assertEqual(scenario_document(source),raw[key])
                expected=(('bear1','bear2') if balance else ('bear1',)) if enabled else ()
                self.assertEqual(source.npc_extra_attack_actor_ids,expected)
                self.assertEqual(raw['schema_version'],'1')
                self.assertEqual(source.npc_help_policies,())
        raw=bear_document(balance=True)
        raw['template']['npc_extra_attack_actor_ids']=['bear2','bear1']
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        self.assertEqual(command.request.template.npc_extra_attack_actor_ids,('bear2','bear1'))
        self.assertEqual(scenario_document(command.request.template),raw['template'])

    def test_policy_is_required_in_native_and_wire_and_has_closed_exact_actor_types(self):
        for balance in (False,True):
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            validate=validate_pc_melee_balance_document if balance else validate_pc_melee_simulation_document
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for value in (None,True,{},'bear1',[None],[1],[''],['bear1','bear1']):
                raw=bear_document(balance=balance)
                raw[key]['npc_extra_attack_actor_ids']=value
                with self.subTest(balance=balance,value=value):
                    with self.assertRaises(ValidationError):validate(raw)
                    with self.assertRaises(error):parse(json.dumps(raw))
            raw=bear_document(balance=balance)
            del raw[key]['npc_extra_attack_actor_ids']
            with self.assertRaises(error):parse(json.dumps(raw))
        source=wire.parse_pc_melee_simulation_request(json.dumps(bear_document())).request.scenario
        native={item.name:getattr(source,item.name) for item in fields(source)
            if item.name!='npc_extra_attack_actor_ids'}
        with self.assertRaises(TypeError):PcMeleeScenario(**native)
        with self.assertRaises(TypeError):replace(source,npc_extra_attack_actor_ids=['bear1'])

    def test_semantic_policy_admission_requires_canonical_opposition_bears(self):
        for actors in (['pc1'],['footpad1'],['unknown'],['bear1','footpad1']):
            raw=bear_document()
            raw['scenario']['npc_extra_attack_actor_ids']=actors
            validate_pc_melee_simulation_document(raw)
            with self.subTest(actors=actors),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))
        raw=bear_document()
        raw['scenario']['enemies'][0]['definition'].update(id='authored:renamed',source_rule_id='authored:source')
        with self.assertRaises(PcMeleeSimulationInputError):
            wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_actual_second_attack_counts_extend_costs_and_survive_full_result_echo(self):
        raw=bear_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        result=run_pc_melee_simulation(command.request)
        summary=summarize_pc_melee_simulation(result)
        self.assertGreater(summary.total_npc_extra_attack_count,0,'representative fixture must execute a second Attack')
        self.assertEqual(summary.npc_extra_attack_trial_count,
            sum(any(item.count for item in record.npc_extra_attack_counts) for record in result.records))
        for record in result.records:
            self.assertEqual(record.source_scenario,command.request.scenario)
            self.assertEqual(tuple(item.actor_id for item in record.npc_extra_attack_counts),('bear1','footpad1'))
            self.assertEqual(record.npc_extra_attack_counts[1].count,0)
            total=sum(item.count for item in record.npc_extra_attack_counts)
            ordinary=(len(record.source_scenario.party)+len(record.source_scenario.enemies))*record.started_rounds
            self.assertLessEqual(record.executed_actions,ordinary+total)
            self.assertGreaterEqual(record.executed_actions,2*total)
            self.assertFalse(hasattr(record,'steps'))
        encoded=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        validate_pc_melee_simulation_document(encoded,'result')
        self.assertEqual(encoded['request'],raw)
        self.assertEqual(encoded['summary']['npc_extra_attack_counts'],
            [{'actor_id':item.actor_id,'count':item.count} for item in summary.npc_extra_attack_counts])
        self.assertEqual(encoded['summary']['total_npc_extra_attack_count'],summary.total_npc_extra_attack_count)
        self.assertFalse(hasattr(summary,'records'))
        for field in ('npc_extra_attack_trial_count','npc_extra_attack_counts','total_npc_extra_attack_count'):
            malformed=deepcopy(encoded)
            del malformed['summary'][field]
            with self.subTest(missing=field),self.assertRaises(ValidationError):
                validate_pc_melee_simulation_document(malformed,'result')

    def test_explicit_opt_out_preserves_one_ordinary_action_and_zero_extra_counts(self):
        raw=bear_document(enabled=False)
        raw['simulation']['trials']=1
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        result=run_pc_melee_simulation(command.request)
        summary=summarize_pc_melee_simulation(result)
        self.assertEqual((summary.npc_extra_attack_trial_count,summary.total_npc_extra_attack_count),(0,0))
        self.assertEqual(tuple((item.actor_id,item.count) for item in summary.npc_extra_attack_counts),
            (('bear1',0),('footpad1',0)))
        for record in result.records:
            ordinary=(len(record.source_scenario.party)+len(record.source_scenario.enemies))*record.started_rounds
            self.assertLessEqual(record.executed_actions,ordinary)

    def test_count_projection_filters_removed_bears_without_reassigning_permission(self):
        raw=bear_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates),report.total_trials),(3,3))
        self.assertEqual(tuple(candidate.counts for candidate in report.candidates),((0,1),(1,1),(2,1)))
        template=command.request.template
        for candidate in report.candidates:
            source=candidate.source_request.scenario
            retained=tuple(enemy.state.actor_id for enemy in source.enemies)
            self.assertEqual(source.npc_extra_attack_actor_ids,
                tuple(actor for actor in template.npc_extra_attack_actor_ids if actor in retained))
            self.assertEqual(source.enemy_activation_order,retained)
            self.assertEqual(tuple(item.actor_id for item in candidate.summary.npc_extra_attack_counts),retained)
            if candidate.counts[0]==0:
                self.assertEqual(source.npc_extra_attack_actor_ids,())
                self.assertEqual(candidate.summary.total_npc_extra_attack_count,0)
            self.assertFalse(hasattr(candidate.summary,'records'))
        encoded=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(encoded,'result')
        self.assertEqual(encoded['request'],raw)
        for item,candidate in zip(encoded['candidates'],report.candidates,strict=True):
            self.assertEqual(item['request']['scenario'],scenario_document(candidate.source_request.scenario))

    def test_cached_equal_actor_alias_is_rejected_before_rng_or_native_execution(self):
        class Alias(str,Enum):
            BEAR='bear1'
        command=wire.parse_pc_melee_simulation_request(json.dumps(bear_document()))
        forged=deepcopy(command.request)
        object.__setattr__(forged.scenario,'npc_extra_attack_actor_ids',(Alias.BEAR,))
        self.assertEqual(forged,command.request)
        rng=Mock(side_effect=AssertionError('malformed source cannot consume RNG'))
        runner=Mock(side_effect=AssertionError('malformed source cannot become an observation'))
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',runner):
            with self.assertRaises(TypeError):run_pc_melee_trial(forged,0,rng_factory=rng)
        rng.assert_not_called()
        runner.assert_not_called()


if __name__=='__main__':
    unittest.main()
