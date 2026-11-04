"""Current JSON1 carries the declared NPC route and distinct observed exits."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from jsonschema import ValidationError

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_m9_pc_melee_json import balance_result, document
from tests.unit.test_m24_pc_npc_exit_statistics import exit_source, sample_result
from towr.adapters import pc_melee_json as wire
from towr.adapters import pc_melee_json_schema as schema
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError, PcMeleeSimulationInputError
from towr.domain.pc_melee_models import PcAdjacentNpcExitPolicy
from towr.domain.pc_melee_result_models import PcMeleeOutcome
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_models import PcNpcExitCount
from towr.simulation.pc_melee_simulation import run_pc_melee_trial, run_pc_melee_simulation
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def exit_document(*,balance=False):
    raw=document(balance=balance)
    key='template' if balance else 'scenario'
    raw[key]=scenario_document(exit_source())
    if balance:
        raw['generation']={'groups':[
            {'group_id':'officials','actor_ids':['official1','official2'],'minimum_count':1,'maximum_count':2},
            {'group_id':'footpads','actor_ids':['footpad1'],'minimum_count':0,'maximum_count':1}],
            'facts':deepcopy(raw[key]['facts']),'max_candidates':4}
        raw['evaluation']['max_total_trials']=16
    return raw


class PcNpcExitJsonTests(unittest.TestCase):
    def test_process_preserves_nonzero_actual_exit_records_and_aggregates(self):
        request=PcMeleeSimulationRequest(replace(exit_source(),max_rounds=4),42,6)
        sequential=run_pc_melee_simulation(request)
        process=run_pc_melee_simulation_parallel(request,workers=2,batch_size=2)
        self.assertEqual(process,sequential)
        expected=summarize_pc_melee_simulation(sequential)
        self.assertGreater(expected.total_npc_exit_count,0)
        self.assertEqual(summarize_pc_melee_simulation(process),expected)

    def test_current_source_requires_explicit_null_or_complete_confirmed_route(self):
        for balance in (False,True):
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            raw=exit_document(balance=balance)
            key='template' if balance else 'scenario'
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw[key])
            self.assertEqual(source.npc_broken_exit_policy,PcAdjacentNpcExitPolicy('adjacent:exit',True,True))
            raw[key]['npc_broken_exit_policy']=None
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertIsNone(source.npc_broken_exit_policy)
            self.assertEqual(scenario_document(source),raw[key])

    def test_source_refuses_omitted_unconfirmed_alias_wrong_type_and_unavailable_routes(self):
        valid={'destination_zone_id':'adjacent:exit','path_clear_confirmed':True,'fastest_route_confirmed':True}
        invalid=(False,1,[],{},'adjacent:exit',
            dict(valid,extra=True),dict(valid,destination_zone_id=True),dict(valid,destination_zone_id=''),
            *({key:value for key,value in valid.items() if key!=missing} for missing in valid),
            *(dict(valid,**{field:value}) for field in ('path_clear_confirmed','fastest_route_confirmed')
                for value in (False,1,'true',None)))
        for balance in (False,True):
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            validate=schema.validate_pc_melee_balance_document if balance else schema.validate_pc_melee_simulation_document
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for policy in invalid:
                raw=exit_document(balance=balance)
                raw[key]['npc_broken_exit_policy']=policy
                with self.subTest(balance=balance,policy=policy):
                    with self.assertRaises(ValidationError):
                        validate(raw)
                    with self.assertRaises(error):
                        parse(json.dumps(raw))
            raw=exit_document(balance=balance)
            del raw[key]['npc_broken_exit_policy']
            with self.assertRaises(error):
                parse(json.dumps(raw))
            raw=exit_document(balance=balance)
            raw[key]['facts']['can_leave_zone']=False
            with self.assertRaises(ValidationError):
                validate(raw)
            with self.assertRaises(error):
                parse(json.dumps(raw))
            raw=exit_document(balance=balance)
            raw[key]['npc_broken_exit_policy']['destination_zone_id']=raw[key]['facts']['zone_id']
            with self.assertRaises(error):
                parse(json.dumps(raw))

    def test_summary_and_source_echo_include_required_metrics_and_every_candidate_zero(self):
        raw=exit_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        summary=summarize_pc_melee_simulation(sample_result())
        value=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        self.assertEqual(value['request'],raw)
        self.assertEqual({key:value['summary'][key] for key in ('npc_exit_trial_count',
            'total_npc_exit_count','objective_with_npc_exit_count')},
            {'npc_exit_trial_count':3,'total_npc_exit_count':4,'objective_with_npc_exit_count':1})
        self.assertEqual(value['summary']['npc_exit_counts'],[
            {'actor_id':'official1','count':2},{'actor_id':'official2','count':2},{'actor_id':'footpad1','count':0}])
        raw=exit_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=balance_result(command)
        value=json.loads(wire.encode_pc_melee_balance_result(command,report))
        self.assertEqual(value['request'],raw)
        for candidate,typed in zip(value['candidates'],report.candidates):
            self.assertEqual(candidate['request']['scenario'],scenario_document(typed.source_request.scenario))
            self.assertEqual(candidate['summary']['npc_exit_counts'],[
                {'actor_id':enemy.state.actor_id,'count':0} for enemy in typed.source_request.scenario.enemies])
            for key in ('npc_exit_trial_count','total_npc_exit_count','objective_with_npc_exit_count'):
                self.assertEqual(candidate['summary'][key],0)
            self.assertFalse(hasattr(typed.summary,'records'))

    def test_schema_requires_new_summary_fields_and_policy_in_every_result_source(self):
        for balance in (False,True):
            raw=exit_document(balance=balance)
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            value=json.loads(wire.encode_pc_melee_balance_result(command,balance_result(command)) if balance
                else wire.encode_pc_melee_simulation_result(command,summarize_pc_melee_simulation(sample_result())))
            validate=schema.validate_pc_melee_balance_document if balance else schema.validate_pc_melee_simulation_document
            summaries=[candidate['summary'] for candidate in value['candidates']] if balance else [value['summary']]
            for summary in summaries:
                for field in ('npc_exit_trial_count','npc_exit_counts','objective_with_npc_exit_count','total_npc_exit_count'):
                    saved=summary.pop(field)
                    with self.subTest(balance=balance,missing=field),self.assertRaises(ValidationError):
                        validate(value,'result')
                    for malformed in (True,-1,None) if field!='npc_exit_counts' else ([],None,[{'actor_id':'official1','count':True}]):
                        summary[field]=malformed
                        with self.subTest(balance=balance,field=field,value=malformed),self.assertRaises(ValidationError):
                            validate(value,'result')
                    summary[field]=saved
            sources=[value['request'][key]]
            if balance:
                sources.extend(candidate['request']['scenario'] for candidate in value['candidates'])
            for source in sources:
                saved=source.pop('npc_broken_exit_policy')
                with self.assertRaises(ValidationError):
                    validate(value,'result')
                source['npc_broken_exit_policy']=dict(saved,path_clear_confirmed=1)
                with self.assertRaises(ValidationError):
                    validate(value,'result')
                source['npc_broken_exit_policy']=saved

    def test_encoder_readmits_equal_cached_policy_and_summary_aliases(self):
        raw=exit_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        summary=summarize_pc_melee_simulation(sample_result())
        forged=deepcopy(command)
        object.__setattr__(forged.request.scenario.npc_broken_exit_policy,'path_clear_confirmed',1)
        self.assertEqual(forged,command)
        with self.assertRaises(TypeError):
            wire.encode_pc_melee_simulation_result(forged,summary)
        forged=deepcopy(summary)
        object.__setattr__(forged.npc_exit_counts[-1],'count',False)
        self.assertEqual(forged,summary)
        with self.assertRaises(TypeError):
            wire.encode_pc_melee_simulation_result(command,forged)

    def test_actual_exit_is_reported_as_objective_without_lethal_defeat_or_journal_retention(self):
        source=make_pc_melee_scenario(max_rounds=1)
        source=replace(source,enemies=(create_pc_book_npc(PcBookNpcProfile.EMPIRE_OFFICIAL_DAGGER,'minion1'),),
            facts=replace(source.facts,can_leave_zone=True),
            npc_broken_exit_policy=PcAdjacentNpcExitPolicy('adjacent:exit',True,True))
        raw=document()
        raw['scenario']=scenario_document(source)
        raw['simulation']['trials']=1
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        native_rng=ScriptedD10([1]*3+[10]*3)
        native=run_pc_melee_scenario(source,native_rng)
        native_rng.assert_exhausted()
        self.assertIs(native.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(native.exited_npc_ids,('minion1',))
        self.assertFalse(native.state.enemy('minion1').state.injury.defeated)
        trial_rng=ScriptedD10([1]*3+[10]*3)
        result=run_pc_melee_simulation(command.request,rng_factory=lambda seed:trial_rng)
        trial_rng.assert_exhausted()
        self.assertEqual(result.records[0].npc_exit_counts,(PcNpcExitCount('minion1',1),))
        summary=summarize_pc_melee_simulation(result)
        value=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        self.assertEqual((value['summary']['npc_exit_trial_count'],value['summary']['total_npc_exit_count'],
            value['summary']['objective_with_npc_exit_count']),(1,1,1))
        self.assertFalse(hasattr(summary,'records'))
        self.assertEqual(value['request'],raw)
        forged=deepcopy(native)
        object.__setattr__(forged.state.enemy('minion1').state.injury,'wounds',True)
        self.assertEqual(forged,native)
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',return_value=forged):
            with self.assertRaises((TypeError,ValueError)):
                run_pc_melee_trial(command.request,0)


if __name__=='__main__':
    unittest.main()
