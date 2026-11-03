"""Pure PC JSON1 source mapping, aggregate encoding and boundary errors."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import parse_scenario, scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError, PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document, validate_pc_melee_simulation_document,
)
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.application.pc_melee_balance_models import (
    PcMeleeBalanceResult, PcMeleeCandidateResult, pc_melee_count_vectors,
    project_pc_melee_candidate, select_pc_melee_candidate_ids,
)
from towr.application.pc_melee_commands import PcMeleeCommandExecutionError
from towr.balance.pc_melee_assessment import PcMeleeCandidateAssessment
from towr.domain.fate_models import (
    FATE_GLORIOUS_RULE_ID, FateBurnKind, FateBurnRecord, FateRefreshRecord,
    FateSessionState, FateSpendKind, FateSpendRecord,
)
from towr.simulation.pc_melee_models import PcMeleeOutcomeCounts
from towr.simulation.pc_melee_summary_models import PcMeleeSimulationSummary


def document(*, balance=False):
    scenario = scenario_document(make_pc_melee_scenario(enemy_count=2 if balance else 1, max_rounds=2))
    result = {'schema_version':'1', 'kind':'pc_melee_balance' if balance else 'pc_melee_simulation',
        'request_id':'request:pc', 'ruleset':'towr-pg1.4-gmg1.1', 'execution':{'mode':'sequential'}}
    if balance:
        result.update(template=scenario, generation={
            'groups':[{'group_id':'guards', 'actor_ids':['minion2','minion1'],
                       'minimum_count':0, 'maximum_count':2}],
            'facts':deepcopy(scenario['facts']), 'max_candidates':2},
            evaluation={'master_seed':'42', 'trials_per_candidate':4, 'max_total_trials':8,
                'window':{'minimum':{'numerator':0,'denominator':1},
                          'target':{'numerator':1,'denominator':2},
                          'maximum':{'numerator':1,'denominator':1}}, 'top_k':1})
    else:
        result.update(scenario=scenario, simulation={'master_seed':'42','trials':4})
    return result


def aggregate(request, *, unsupported=False):
    trials=request.trials
    counts=PcMeleeOutcomeCounts(0 if unsupported else trials,0,0,trials if unsupported else 0)
    return PcMeleeSimulationSummary(request,counts,0 if unsupported else trials,trials,0)


def balance_result(command):
    candidates=[]
    for index,counts in enumerate(pc_melee_count_vectors(command.request)):
        source=project_pc_melee_candidate(command.request,counts)
        summary=aggregate(source,unsupported=index==1)
        assessment=PcMeleeCandidateAssessment(source,summary,command.request.window)
        candidates.append(PcMeleeCandidateResult(source.scenario.id,counts,source,summary,assessment))
    candidates=tuple(candidates)
    return PcMeleeBalanceResult(command.request,candidates,select_pc_melee_candidate_ids(candidates,command.request.top_k))


class PcMeleeJsonTests(unittest.TestCase):
    def test_simulation_result_echoes_every_source_field_without_rng_or_trial_replay(self):
        raw=document()
        raw['request_id']='запрос:ёлка'
        raw['scenario']['facts']['zone_id']='арена'
        before=deepcopy(raw)
        with patch('random.Random',side_effect=AssertionError('wire must not create RNG')):
            command=wire.parse_pc_melee_simulation_request(json.dumps(raw,ensure_ascii=False).encode())
            summary=aggregate(command.request)
            encoded=wire.encode_pc_melee_simulation_result(command,summary)
        self.assertEqual(raw,before)
        value=json.loads(encoded)
        self.assertEqual(value['request'],raw)
        self.assertEqual(value['summary']['trials'],4)
        self.assertEqual(value['summary']['outcome_counts'],{
            'objective_achieved':4,'pc_defeated':0,'round_limit':0,'unsupported_path':0})
        self.assertNotIn('trials',value)
        self.assertNotIn('journal',encoded)
        self.assertEqual(wire.parse_pc_melee_simulation_request(json.dumps(value['request'])),command)
        validate_pc_melee_simulation_document(value,'result')

    def test_balance_echoes_full_grid_exact_candidate_sources_rates_and_selection(self):
        raw=document(balance=True)
        with patch('random.Random',side_effect=AssertionError('encoder must not replay trials')):
            command=wire.parse_pc_melee_balance_request(json.dumps(raw))
            result=balance_result(command)
            encoded=wire.encode_pc_melee_balance_result(command,result)
        value=json.loads(encoded)
        self.assertEqual(value['request'],raw)
        self.assertEqual((value['candidate_count'],value['planned_trials'],value['total_trials']),(2,8,8))
        self.assertEqual(value['candidates'][0]['request']['scenario']['target_priority'],['minion2'])
        self.assertEqual(value['candidates'][1]['request']['scenario']['target_priority'],['minion1','minion2'])
        assessment=value['candidates'][1]['assessment']
        self.assertEqual((assessment['status'],assessment['window_match']),('unsupported_observations',None))
        self.assertEqual(assessment['unsupported_path_rate'],{'numerator':1,'denominator':1})
        self.assertEqual(value['selected_candidate_ids'],[value['candidates'][0]['candidate_id']])
        self.assertNotIn('stage_reports',value)
        validate_pc_melee_balance_document(value,'result')

    def test_scenario_roundtrip_retains_fate_history_and_numeric_minion_details(self):
        scenario=make_pc_melee_scenario(enemy_count=2)
        spend=FateSpendRecord('spend','session','pc',FateSpendKind.GLORIOUS_TEST,'oldtest',FATE_GLORIOUS_RULE_ID)
        refresh=FateRefreshRecord('refresh','session','pc','break','gm',1,3,4)
        burn=FateBurnRecord('burn','session','pc',FateBurnKind.NEAR_MISS,'oldwound',3,2,4,3,True)
        fate=FateSessionState('session','pc',2,3,(spend,),False,(refresh,),(burn,),('refresh','burn'))
        definition=replace(scenario.enemies[0].definition,
            resilience=replace(scenario.enemies[0].definition.resilience,bonus=2))
        enemies=tuple(replace(enemy,definition=definition,
            state=replace(enemy.state,current_resilience=definition.resilience)) for enemy in scenario.enemies)
        scenario=replace(scenario,fate=fate,enemies=enemies)
        raw=scenario_document(scenario)
        decoded=parse_scenario(raw,path_prefix='/scenario',error_type=PcMeleeSimulationInputError)
        self.assertEqual(decoded,scenario)
        self.assertEqual(raw['fate']['resource_event_ids'],['refresh','burn'])
        self.assertEqual(raw['fate']['rating'],2)
        self.assertEqual(raw['fate']['spends'][0]['kind'],'glorious_test')
        self.assertIsNone(raw['enemies'][0]['definition']['attack']['test_profile']['pool_cap'])
        self.assertEqual(raw['enemies'][0]['definition']['resilience']['bonus'],2)
        self.assertEqual(raw['enemies'][0]['definition']['attack']['damage']['success_multiplier'],1)

    def test_process_options_and_large_seed_survive_source_encoding(self):
        raw=document()
        raw['simulation']['master_seed']=str(2**64-1)
        raw['execution']={'mode':'process','workers':2,'batch_size':3}
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        value=json.loads(wire.encode_pc_melee_simulation_result(command,aggregate(command.request)))
        self.assertEqual(value['request'],raw)
        self.assertEqual(command.request.master_seed,2**64-1)
        raw['simulation']['master_seed']=str(2**64)
        with self.assertRaises(PcMeleeSimulationInputError) as caught:
            wire.parse_pc_melee_simulation_request(json.dumps(raw))
        self.assertEqual((caught.exception.request_id,caught.exception.path),('request:pc','/simulation/master_seed'))

    def test_only_canonical_seed_and_reduced_window_spellings_are_admitted(self):
        for value in ('00','042','+42',' 42','42 '):
            raw=document()
            raw['simulation']['master_seed']=value
            with self.subTest(seed=value),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))
        for name,value in (('minimum',{'numerator':0,'denominator':3}),
                           ('target',{'numerator':2,'denominator':4}),
                           ('maximum',{'numerator':4,'denominator':4})):
            raw=document(balance=True)
            raw['evaluation']['window'][name]=value
            with self.subTest(name=name),self.assertRaises(PcMeleeBalanceInputError) as caught:
                wire.parse_pc_melee_balance_request(json.dumps(raw))
            self.assertEqual((caught.exception.path,caught.exception.request_id),
                ('/evaluation/window/'+name,'request:pc'))

    def test_lexical_failures_do_not_trust_request_ids(self):
        for parser,error_type in ((wire.parse_pc_melee_simulation_request,PcMeleeSimulationInputError),
                                  (wire.parse_pc_melee_balance_request,PcMeleeBalanceInputError)):
            for text in (b'\xff', '{', '{"request_id":"untrusted","x":1.0}',
                         '{"request_id":"untrusted","x":1e0}', '{"x":NaN}',
                         '{"request_id":"untrusted","x":1,"x":2}',
                         '{"request_id":"untrusted","x":"\\ud800"}'):
                with self.subTest(parser=parser.__name__,text=text),self.assertRaises(error_type) as caught:
                    parser(text)
                self.assertIsNone(caught.exception.request_id)

    def test_unknown_versions_and_wrong_kinds_use_current_family_error(self):
        for balance in (False,True):
            parser=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            encoder=wire.encode_pc_melee_balance_error if balance else wire.encode_pc_melee_simulation_error
            error_type=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for version in ('0','2','6'):
                raw=dict(document(balance=balance),schema_version=version)
                with self.assertRaises(error_type) as caught:
                    parser(json.dumps(raw))
                value=json.loads(encoder(caught.exception))
                self.assertEqual((value['schema_version'],value['request_id'],value['error']['code']),
                    ('1','request:pc','unsupported_version'))
            raw=dict(document(balance=balance),kind='pc_melee_simulation' if balance else 'pc_melee_balance')
            with self.assertRaises(error_type) as caught:
                parser(json.dumps(raw))
            self.assertEqual(caught.exception.code,Code.INVALID_INPUT)

    def test_nested_unknown_fields_pool_caps_and_derived_state_overrides_are_refused(self):
        for path,value in (
            (('scenario','mystery'),True), (('scenario','pc','wound_limit'),1),
            (('scenario','fate','invented'),True), (('scenario','facts','extra'),True),
            (('scenario','enemies',0,'state'),{}),
            (('scenario','enemies',0,'definition','attack','ignores_armour'),False),
            (('scenario','enemies',0,'definition','attack','test_profile','pool_cap'),4),
            (('scenario','enemies',0,'definition','protection','skill'),'defence'),
        ):
            raw=document()
            target=raw
            for key in path[:-1]:
                target=target[key]
            target[path[-1]]=value
            with self.subTest(path=path),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_bool_and_semantic_inconsistencies_are_refused_before_execution(self):
        for mutate in (
            lambda raw:raw['scenario']['pc'].update(weapon_skill=True),
            lambda raw:raw['simulation'].update(trials=True),
            lambda raw:raw['scenario']['fate'].update(actor_id='foreign'),
            lambda raw:raw['scenario'].update(target_priority=['foreign']),
            lambda raw:raw['scenario']['enemies'][0]['definition']['attack']['damage'].update(base=True),
            lambda raw:raw['scenario'].update(max_rounds=False),
        ):
            raw=document()
            mutate(raw)
            with self.subTest(mutate=mutate),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))
        raw=document(balance=True)
        raw['generation']['facts']['outnumbering_bonus_approved']=False
        with self.assertRaises(PcMeleeBalanceInputError) as caught:
            wire.parse_pc_melee_balance_request(json.dumps(raw))
        self.assertEqual((caught.exception.path,caught.exception.request_id),('/generation/facts','request:pc'))

    def test_encoder_refuses_foreign_summary_corrupt_full_source_and_partial_reports(self):
        command=wire.parse_pc_melee_simulation_request(json.dumps(document()))
        foreign=replace(command.request,scenario=replace(command.request.scenario,day_id='other'))
        with self.assertRaises(ValueError):
            wire.encode_pc_melee_simulation_result(command,aggregate(foreign))
        forged=deepcopy(command)
        object.__setattr__(forged.request.scenario.pc,'armour_bonus',False)
        self.assertEqual(forged,command)
        with self.assertRaises(TypeError):
            wire.encode_pc_melee_simulation_result(forged,aggregate(command.request))
        balance=wire.parse_pc_melee_balance_request(json.dumps(document(balance=True)))
        result=balance_result(balance)
        forged=deepcopy(result)
        object.__setattr__(forged,'candidates',forged.candidates[:1])
        with self.assertRaises(ValueError):
            wire.encode_pc_melee_balance_result(balance,forged)

    def test_runtime_errors_are_safe_current_and_family_bound(self):
        for family,phase in (('simulation','simulation'),('balance','generation'),('balance','evaluation')):
            context={'candidate_id':'candidate','candidate_index':2} if phase=='evaluation' else {}
            error=PcMeleeCommandExecutionError('trusted',family,phase,**context)
            error.__cause__=RuntimeError('private cause')
            error.add_note('private note')
            error.args=('private exception message',)
            encoder=wire.encode_pc_melee_simulation_error if family=='simulation' else wire.encode_pc_melee_balance_error
            encoded=encoder(error)
            value=json.loads(encoded)
            self.assertNotIn('private',encoded)
            self.assertNotIn('summary',value)
            self.assertEqual(value['error']['phase'],phase)
            self.assertEqual(value['error']['code'],phase+'_failed')
        with self.assertRaises(TypeError):
            wire.encode_pc_melee_simulation_error(PcMeleeCommandExecutionError('trusted','balance','generation'))
        for encoder in (wire.encode_pc_melee_simulation_error,wire.encode_pc_melee_balance_error):
            with self.assertRaises(TypeError):
                encoder(RuntimeError('private'))
        escaped=wire.encode_pc_melee_simulation_error(PcMeleeSimulationInputError(Code.INVALID_JSON,'bad\ud800'))
        escaped.encode('utf-8')


if __name__=='__main__':
    unittest.main()
