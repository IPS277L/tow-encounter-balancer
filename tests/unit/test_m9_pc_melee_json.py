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
from towr.simulation.pc_melee_models import PcMeleeOutcomeCounts, PcNearMissBurnCount
from towr.simulation.pc_melee_summary_models import PcMeleeDefeatCount, PcMeleeSimulationSummary


def document(*, balance=False, party_size=1, mixed=False):
    scenario = scenario_document(make_pc_melee_scenario(enemy_count=2 if balance or mixed else 1, max_rounds=2))
    for index in range(1, party_size):
        member=deepcopy(scenario['party'][0])
        actor=f'pc{index+1}'
        member['actor_id']=actor
        member['pc']['id']=f'pc-profile{index+1}'
        member['pc']['weapon']='sword'
        member['fate']['actor_id']=actor
        member['fate']['rating']=member['fate']['session_spend_limit']=index
        for decision in member['defeat_decisions']:
            decision['attacker_id']=actor
        scenario['party'].append(member)
        scenario['pc_activation_order'].insert(0,actor)
        scenario['enemy_target_priority'].append(actor)
    if mixed:
        enemy=scenario['enemies'][1]
        old_actor=enemy['actor_id']
        enemy['actor_id']='brute1'
        enemy['definition'].update(id='brute-profile',source_rule_id='authored:brute',
            injury_policy='brute',wound_limit=3)
        enemy['definition']['attack']['source_rule_id']='authored:brute:club'
        enemy['definition']['protection']['source_rule_id']='authored:brute:defence'
        scenario['enemy_activation_order']=[enemy['actor_id'] for enemy in scenario['enemies']]
        for member in scenario['party']:
            member['target_priority']=['brute1' if actor==old_actor else actor for actor in member['target_priority']]
            for decision in member['defeat_decisions']:
                if decision['target_id']==old_actor:
                    decision['target_id']='brute1'
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
    if balance and mixed:
        result['generation']['groups']=[
            {'group_id':'guards','actor_ids':['minion1'],'minimum_count':0,'maximum_count':1},
            {'group_id':'brutes','actor_ids':['brute1'],'minimum_count':1,'maximum_count':1},
        ]
    return result


def aggregate(request, *, unsupported=False):
    trials=request.trials
    counts=PcMeleeOutcomeCounts(0 if unsupported else trials,0,0,trials if unsupported else 0)
    return PcMeleeSimulationSummary(request,counts,0 if unsupported else trials,trials,0,0,
        tuple(PcMeleeDefeatCount(member.actor_id,0) for member in request.scenario.party),0,
        tuple(PcNearMissBurnCount(member.actor_id,0) for member in request.scenario.party))


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
    def test_near_miss_strategy_and_resource_metrics_survive_simulation_and_candidate_echo(self):
        for balance in (False,True):
            raw=document(balance=balance,party_size=2)
            source_key='template' if balance else 'scenario'
            first=raw[source_key]['party'][0]
            first.update(fate_policy='near_miss_at_threshold',near_miss_policy={
                'minimum_table_total':16,'minimum_rating_to_keep':1})
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            if balance:
                result=balance_result(command)
                encoded=json.loads(wire.encode_pc_melee_balance_result(command,result))
                sources=[item['request']['scenario'] for item in encoded['candidates']]
                summaries=[item['summary'] for item in encoded['candidates']]
            else:
                summary=replace(aggregate(command.request),near_miss_burn_trial_count=2,
                    near_miss_burn_counts=(PcNearMissBurnCount('pc',2),PcNearMissBurnCount('pc2',0)))
                encoded=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
                sources=[encoded['request']['scenario']]
                summaries=[encoded['summary']]
                self.assertEqual(encoded['summary']['total_near_miss_burn_count'],2)
                self.assertEqual(encoded['summary']['near_miss_burn_trial_count'],2)
            self.assertEqual(encoded['request'],raw)
            for source in sources:
                self.assertEqual(source['party'][0]['near_miss_policy'],first['near_miss_policy'])
                self.assertEqual(source['party'][0]['fate_policy'],'near_miss_at_threshold')
                self.assertIsNone(source['party'][1]['near_miss_policy'])
            for summary in summaries:
                self.assertEqual(summary['near_miss_burn_counts'][1],{'actor_id':'pc2','count':0})
                self.assertEqual(summary['total_near_miss_burn_count'],
                    sum(item['count'] for item in summary['near_miss_burn_counts']))

    def test_near_miss_policy_is_required_correlated_and_has_no_implicit_criteria(self):
        for value in (None,{},True,{'minimum_table_total':16},
                {'minimum_table_total':16,'minimum_rating_to_keep':0,'spend_fate':True}):
            raw=document()
            raw['scenario']['party'][0].update(fate_policy='near_miss_at_threshold',near_miss_policy=value)
            with self.subTest(value=value),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))
        raw=document()
        del raw['scenario']['party'][0]['near_miss_policy']
        with self.assertRaises(PcMeleeSimulationInputError):
            wire.parse_pc_melee_simulation_request(json.dumps(raw))
        raw=document()
        raw['scenario']['party'][0]['near_miss_policy']={
            'minimum_table_total':16,'minimum_rating_to_keep':0}
        with self.assertRaises(PcMeleeSimulationInputError):
            wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_near_miss_criteria_reject_bool_string_negative_and_noninteger_tokens(self):
        for field,values in (('minimum_table_total',(True,'16',0,-1,16.0)),
                             ('minimum_rating_to_keep',(False,'0',-1,0.0))):
            for value in values:
                raw=document()
                policy={'minimum_table_total':16,'minimum_rating_to_keep':0,field:value}
                raw['scenario']['party'][0].update(fate_policy='near_miss_at_threshold',near_miss_policy=policy)
                with self.subTest(field=field,value=value),self.assertRaises(PcMeleeSimulationInputError):
                    wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_near_miss_unreachable_threshold_and_large_reserve_are_explicit_valid_strategies(self):
        raw=document()
        raw['scenario']['party'][0].update(fate_policy='near_miss_at_threshold',near_miss_policy={
            'minimum_table_total':100,'minimum_rating_to_keep':100})
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        encoded=json.loads(wire.encode_pc_melee_simulation_result(command,aggregate(command.request)))
        self.assertEqual(encoded['request'],raw)
        self.assertEqual(encoded['summary']['total_near_miss_burn_count'],0)

    def test_heavy_wound_and_side_policies_are_required_current_fields_with_exact_echo(self):
        for balance in (False,True):
            raw=document(balance=balance,party_size=2,mixed=True)
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            encode=wire.encode_pc_melee_balance_result if balance else wire.encode_pc_melee_simulation_result
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertTrue(all(member.heavy_wound_policy.value=='continue_fighting' for member in source.party))
            self.assertTrue(all(member.random_side_policy.value=='d10_low_left_high_right' for member in source.party))
            result=balance_result(command) if balance else aggregate(command.request)
            with patch('random.Random',side_effect=AssertionError('encoding never creates RNG')):
                encoded=json.loads(encode(command,result))
            self.assertEqual(encoded['request'],raw)

    def test_missing_invalid_legacy_and_equal_untyped_heavy_policies_are_refused(self):
        for field in ('random_side_policy','heavy_wound_policy'):
            raw=document(party_size=2)
            del raw['scenario']['party'][1][field]
            with self.subTest(missing=field),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))
            for value in (True,None,'invented'):
                raw=document(party_size=2)
                raw['scenario']['party'][1][field]=value
                with self.subTest(field=field,value=value),self.assertRaises(PcMeleeSimulationInputError) as caught:
                    wire.parse_pc_melee_simulation_request(json.dumps(raw))
                self.assertEqual(caught.exception.path,f'/scenario/party/1/{field}')
        raw=document(party_size=2)
        second=raw['scenario']['party'][1]
        second['random_hand_policy']=second.pop('random_side_policy')
        with self.assertRaises(PcMeleeSimulationInputError):
            wire.parse_pc_melee_simulation_request(json.dumps(raw))
        command=wire.parse_pc_melee_simulation_request(json.dumps(document(party_size=2)))
        for field in ('random_side_policy','heavy_wound_policy'):
            forged=deepcopy(command)
            member=forged.request.scenario.party[1]
            object.__setattr__(member,field,getattr(member,field).value)
            self.assertEqual(forged,command)
            with self.subTest(forged=field),self.assertRaises(TypeError):
                wire.encode_pc_melee_simulation_result(forged,aggregate(command.request))

    def test_mixed_npc_types_and_limits_survive_exact_sources_candidates_and_result_echo(self):
        raw=document(balance=True,party_size=2,mixed=True)
        before=deepcopy(raw)
        with patch('random.Random',side_effect=AssertionError('codec creates no RNG')):
            command=wire.parse_pc_melee_balance_request(json.dumps(raw))
            encoded=json.loads(wire.encode_pc_melee_balance_result(command,balance_result(command)))
        self.assertEqual(raw,before)
        self.assertEqual(encoded['request'],raw)
        self.assertEqual(tuple((enemy.definition.injury_policy.value,enemy.definition.wound_limit,
            enemy.state.injury.wound_limit) for enemy in command.request.template.enemies),
            (('minion',1,1),('brute',3,3)))
        for candidate in encoded['candidates']:
            enemies=candidate['request']['scenario']['enemies']
            brute=next(enemy for enemy in enemies if enemy['actor_id']=='brute1')
            self.assertEqual(brute,raw['template']['enemies'][1])
            decisions=candidate['request']['scenario']['party'][1]['defeat_decisions']
            self.assertTrue(all(item['attacker_id']=='pc2' and item['gm_approved'] for item in decisions))
            projected=parse_scenario(candidate['request']['scenario'],path_prefix='/candidate',
                error_type=PcMeleeBalanceInputError)
            self.assertEqual(projected.enemies[-1].definition.injury_policy.value,'brute')
        validate_pc_melee_balance_document(encoded,'result')

    def test_npc_policy_and_profile_limit_are_required_typed_and_source_bound(self):
        for missing in ('injury_policy','wound_limit'):
            raw=document(mixed=True)
            del raw['scenario']['enemies'][1]['definition'][missing]
            with self.subTest(missing=missing),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))
        for field,value in (('injury_policy','champion'),('injury_policy','monstrosity'),
                            ('injury_policy',True),('wound_limit',True),('wound_limit',None),
                            ('wound_limit',0),('wound_limit',-1)):
            raw=document(mixed=True)
            raw['scenario']['enemies'][1]['definition'][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(PcMeleeSimulationInputError) as caught:
                wire.parse_pc_melee_simulation_request(json.dumps(raw))
            self.assertEqual(caught.exception.path,'/scenario/enemies/1/definition/'+field)
        raw=document()
        raw['scenario']['enemies'][0]['definition']['wound_limit']=2
        with self.assertRaises(PcMeleeSimulationInputError) as caught:
            wire.parse_pc_melee_simulation_request(json.dumps(raw))
        self.assertEqual(caught.exception.path,'/scenario/enemies/0/definition/wound_limit')

    def test_simulation_result_echoes_every_source_field_without_rng_or_trial_replay(self):
        raw=document(party_size=2)
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
            'objective_achieved':4,'party_defeated':0,'round_limit':0,'unsupported_path':0})
        self.assertEqual(value['summary']['any_pc_defeated_count'],0)
        self.assertEqual(value['summary']['pc_defeat_counts'],[
            {'actor_id':'pc','count':0},{'actor_id':'pc2','count':0}])
        self.assertEqual(value['request']['scenario']['pc_activation_order'],['pc2','pc'])
        self.assertNotIn('trials',value)
        self.assertNotIn('journal',encoded)
        self.assertEqual(wire.parse_pc_melee_simulation_request(json.dumps(value['request'])),command)
        validate_pc_melee_simulation_document(value,'result')

    def test_balance_echoes_full_grid_exact_candidate_sources_rates_and_selection(self):
        raw=document(balance=True,party_size=2)
        with patch('random.Random',side_effect=AssertionError('encoder must not replay trials')):
            command=wire.parse_pc_melee_balance_request(json.dumps(raw))
            result=balance_result(command)
            encoded=wire.encode_pc_melee_balance_result(command,result)
        value=json.loads(encoded)
        self.assertEqual(value['request'],raw)
        self.assertEqual((value['candidate_count'],value['planned_trials'],value['total_trials']),(2,8,8))
        self.assertEqual(value['candidates'][0]['request']['scenario']['party'][0]['target_priority'],['minion2'])
        self.assertEqual(value['candidates'][1]['request']['scenario']['party'][0]['target_priority'],['minion1','minion2'])
        self.assertEqual(value['candidates'][0]['request']['scenario']['party'][1]['target_priority'],['minion2'])
        self.assertEqual(value['candidates'][0]['request']['scenario']['enemy_target_priority'],['pc','pc2'])
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
        scenario=replace(scenario,party=(replace(scenario.party[0],fate=fate),),enemies=enemies)
        raw=scenario_document(scenario)
        decoded=parse_scenario(raw,path_prefix='/scenario',error_type=PcMeleeSimulationInputError)
        self.assertEqual(decoded,scenario)
        self.assertEqual(raw['party'][0]['fate']['resource_event_ids'],['refresh','burn'])
        self.assertEqual(raw['party'][0]['fate']['rating'],2)
        self.assertEqual(raw['party'][0]['fate']['spends'][0]['kind'],'glorious_test')
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

    def test_party_roundtrip_keeps_individual_profiles_fate_hands_and_priorities(self):
        raw=document(balance=True,party_size=2)
        first,second=raw['template']['party']
        second['initial_weapon_hand']='right'
        second['target_priority'].reverse()
        second['defeat_decisions'].reverse()
        second['pc']['armour_bonus']=2
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        one,two=command.request.template.party
        self.assertEqual((one.fate.actor_id,one.fate.rating,two.fate.actor_id,two.fate.rating),('pc',3,'pc2',1))
        self.assertEqual((one.pc.weapon.value,two.pc.weapon.value),('staff','sword'))
        self.assertEqual(two.initial_weapon_hand.value,'right')
        encoded=json.loads(wire.encode_pc_melee_balance_result(command,balance_result(command)))
        self.assertEqual(encoded['request'],raw)
        self.assertEqual(encoded['candidates'][1]['request']['scenario']['party'][1]['target_priority'],['minion2','minion1'])

    def test_summary_preserves_confirmed_party_and_individual_loss_counts(self):
        command=wire.parse_pc_melee_simulation_request(json.dumps(document(party_size=2)))
        summary=PcMeleeSimulationSummary(command.request,PcMeleeOutcomeCounts(3,1,0,0),4,4,0,
            2,(PcMeleeDefeatCount('pc',1),PcMeleeDefeatCount('pc2',2)),0,
            (PcNearMissBurnCount('pc',0),PcNearMissBurnCount('pc2',0)))
        value=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        self.assertEqual(value['summary']['outcome_counts']['party_defeated'],1)
        self.assertEqual(value['summary']['any_pc_defeated_count'],2)
        self.assertEqual(value['summary']['pc_defeat_counts'],[
            {'actor_id':'pc','count':1},{'actor_id':'pc2','count':2}])

    def test_legacy_single_shape_and_invalid_party_partitions_are_refused(self):
        raw=document()
        member=raw['scenario'].pop('party')[0]
        raw['scenario'].update(member)
        del raw['scenario']['pc_activation_order']
        del raw['scenario']['enemy_target_priority']
        with self.assertRaises(PcMeleeSimulationInputError):
            wire.parse_pc_melee_simulation_request(json.dumps(raw))
        for change in (
            lambda scene:scene.update(party=[]),
            lambda scene:scene.update(pc_activation_order=['pc','pc']),
            lambda scene:scene.update(enemy_target_priority=['pc2']),
            lambda scene:scene['party'][1]['fate'].update(actor_id='pc'),
            lambda scene:scene['party'][1]['defeat_decisions'][0].update(attacker_id='pc'),
        ):
            raw=document(party_size=2)
            change(raw['scenario'])
            with self.subTest(change=change),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

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
            (('scenario','mystery'),True), (('scenario','party',0,'pc','wound_limit'),1),
            (('scenario','party',0,'fate','invented'),True), (('scenario','facts','extra'),True),
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
            lambda raw:raw['scenario']['party'][0]['pc'].update(weapon_skill=True),
            lambda raw:raw['simulation'].update(trials=True),
            lambda raw:raw['scenario']['party'][0]['fate'].update(actor_id='foreign'),
            lambda raw:raw['scenario']['party'][0].update(target_priority=['foreign']),
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
        command=wire.parse_pc_melee_simulation_request(json.dumps(document(party_size=2)))
        foreign=replace(command.request,scenario=replace(command.request.scenario,day_id='other'))
        with self.assertRaises(ValueError):
            wire.encode_pc_melee_simulation_result(command,aggregate(foreign))
        forged=deepcopy(command)
        object.__setattr__(forged.request.scenario.party[1].pc,'armour_bonus',False)
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
