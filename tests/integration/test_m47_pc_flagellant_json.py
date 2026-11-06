"""Named Flagellant choices and real NPC Recover costs across PC JSON1/search."""
from copy import deepcopy
from dataclasses import fields,replace
from enum import Enum
import json
import unittest
from unittest.mock import Mock,patch

from jsonschema import ValidationError

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.unit.test_m9_pc_melee_json import document
from tests.unit.test_m47_pc_flagellant_execution import scene,WEAK
from tests.support.pc_melee_scripted import ScriptedD10
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError,PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import validate_pc_melee_balance_document,validate_pc_melee_simulation_document
from towr.application.pc_melee_service import execute_pc_melee_balance
from towr.domain.pc_flagellant_policy_models import PcFlagellantPolicy,PcFeelNoPainPolicy
from towr.domain.pc_flagellant_models import PcNpcRecoverProof
from towr.domain.pc_melee_models import PcMeleeScenario
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest,PcMeleeSimulationResult,PcNpcRecoverActionCount
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def flagellant_document(*,balance=False,selected=True):
    source=book_pc_scenario(flagellant_flails=2 if balance else 1,flagellant_hooks=1,
        footpads=0,townsfolk=0,pc_count=1,max_rounds=3)
    source=replace(source,npc_flagellant_policies=tuple(PcFlagellantPolicy(e.state.actor_id,
        PcFeelNoPainPolicy.WOUND_AT_ZERO,True) for e in source.enemies) if selected else ())
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            dict(group_id='flails',actor_ids=['flagellant_flails1','flagellant_flails2'],minimum_count=1,maximum_count=2),
            dict(group_id='hooks',actor_ids=['flagellant_hooks1'],minimum_count=0,maximum_count=1)],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':4}
        raw['evaluation'].update(master_seed='42',trials_per_candidate=1,max_total_trials=4,top_k=2)
    else:
        raw['simulation'].update(master_seed='42',trials=2)
    return raw


def scripted_simulation():
    request=PcMeleeSimulationRequest(scene(rounds=2),42,2)
    records=[]
    for index in range(2):
        rng=ScriptedD10(WEAK*2)
        records.append(run_pc_melee_trial(request,index,rng_factory=lambda seed:rng))
        rng.assert_exhausted()
    return PcMeleeSimulationResult(request,tuple(records))


class PcFlagellantJsonTests(unittest.TestCase):
    def test_both_loadouts_and_required_policy_fields_roundtrip_current_requests(self):
        for balance in (False,True):
            for selected in (False,True):
                raw=flagellant_document(balance=balance,selected=selected)
                parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
                command=parse(json.dumps(raw))
                source=command.request.template if balance else command.request.scenario
                self.assertEqual(scenario_document(source),raw['template' if balance else 'scenario'])
                self.assertEqual(raw['schema_version'],'1')
                self.assertEqual(len(source.npc_flagellant_policies),(3 if balance else 2) if selected else 0)
                self.assertTrue(all(p.feel_no_pain is PcFeelNoPainPolicy.WOUND_AT_ZERO and p.recover_when_wounded
                    for p in source.npc_flagellant_policies))
        raw=flagellant_document(balance=True);raw['template']['npc_flagellant_policies'].reverse()
        raw['template']['npc_flagellant_policies'][0].update(feel_no_pain='decline',recover_when_wounded=False)
        source=wire.parse_pc_melee_balance_request(json.dumps(raw)).request.template
        self.assertEqual(scenario_document(source),raw['template'])

    def test_missing_or_malformed_policy_shapes_are_rejected_in_both_families(self):
        malformed=(None,True,{},'flagellant_flails1',[{}],
            [{'actor_id':'flagellant_flails1','feel_no_pain':'wound_at_zero'}],
            [{'actor_id':'flagellant_flails1','feel_no_pain':True,'recover_when_wounded':True}],
            [{'actor_id':'flagellant_flails1','feel_no_pain':'wound_at_zero','recover_when_wounded':1}],
            [{'actor_id':'flagellant_flails1','feel_no_pain':'decline','recover_when_wounded':False,'extra':1}])
        for balance in (False,True):
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            validate=validate_pc_melee_balance_document if balance else validate_pc_melee_simulation_document
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for value in malformed:
                raw=flagellant_document(balance=balance);raw[key]['npc_flagellant_policies']=value
                with self.subTest(balance=balance,value=value):
                    with self.assertRaises(ValidationError):validate(raw)
                    with self.assertRaises(error):parse(json.dumps(raw))
            raw=flagellant_document(balance=balance);del raw[key]['npc_flagellant_policies']
            with self.assertRaises(error):parse(json.dumps(raw))
        source=wire.parse_pc_melee_simulation_request(json.dumps(flagellant_document())).request.scenario
        values={f.name:getattr(source,f.name) for f in fields(source) if f.name!='npc_flagellant_policies'}
        with self.assertRaises(TypeError):PcMeleeScenario(**values)
        with self.assertRaises(TypeError):replace(source,npc_flagellant_policies=list(source.npc_flagellant_policies))

    def test_wrong_actor_roles_duplicate_actors_and_changed_canonical_profiles_are_rejected(self):
        for actor in ('pc1','unknown'):
            raw=flagellant_document();raw['scenario']['npc_flagellant_policies'][0]['actor_id']=actor
            with self.assertRaises(PcMeleeSimulationInputError):wire.parse_pc_melee_simulation_request(json.dumps(raw))
        raw=flagellant_document();raw['scenario']['npc_flagellant_policies'].append(
            {'actor_id':'flagellant_flails1','feel_no_pain':'decline','recover_when_wounded':False})
        with self.assertRaises(PcMeleeSimulationInputError):wire.parse_pc_melee_simulation_request(json.dumps(raw))
        other=book_pc_scenario(flagellant_flails=1,footpads=1,townsfolk=0)
        with self.assertRaises(ValueError):replace(other,npc_flagellant_policies=(
            PcFlagellantPolicy('footpad1',PcFeelNoPainPolicy.WOUND_AT_ZERO,True),))
        for path,value in (('holds_shield',True),('definition.attack.test_profile.pool_cap',8),
                ('definition.attack.damage.base',7),('definition.source_rule_id','authored:source')):
            raw=flagellant_document();target=raw['scenario']['enemies'][0]
            parts=path.split('.')
            for part in parts[:-1]:target=target[part]
            target[parts[-1]]=value
            with self.subTest(path=path),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_literal_compact_observations_count_real_recover_actions_not_pc_benefits(self):
        result=scripted_simulation()
        self.assertEqual(tuple(r.npc_recover_action_counts for r in result.records),
            ((PcNpcRecoverActionCount('flagellant_flails1',2),),)*2)
        summary=summarize_pc_melee_simulation(result)
        self.assertEqual((summary.npc_recover_action_trial_count,summary.total_npc_recover_action_count,
            summary.total_action_count),(2,4,8))
        self.assertEqual(summary.npc_recover_action_counts,(PcNpcRecoverActionCount('flagellant_flails1',4),))
        self.assertEqual(summary.total_ally_recover_action_count,0)
        self.assertEqual(summary.total_glorious_spend_count,0)
        self.assertTrue(all(not hasattr(r,'steps') for r in result.records))

    def test_recover_record_and_summary_invariants_reject_bad_counts_roles_and_costs(self):
        result=scripted_simulation();record=result.records[0];summary=summarize_pc_melee_simulation(result)
        with self.assertRaises(ValueError):replace(record,executed_actions=3)
        with self.assertRaises(ValueError):replace(record,npc_recover_action_counts=(PcNpcRecoverActionCount('pc1',2),))
        with self.assertRaises(ValueError):replace(summary,npc_recover_action_trial_count=0)
        with self.assertRaises(ValueError):replace(summary,npc_recover_action_counts=(PcNpcRecoverActionCount('flagellant_flails1',0),))
        for value in (True,1.0,-1):
            with self.assertRaises((TypeError,ValueError)):PcNpcRecoverActionCount('flagellant_flails1',value)

    def test_real_trials_and_json_summary_preserve_explicit_npc_recover_rows(self):
        raw=flagellant_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        result=run_pc_melee_simulation(command.request)
        summary=summarize_pc_melee_simulation(result)
        self.assertEqual(summary.total_npc_recover_action_count,
            sum(item.count for r in result.records for item in r.npc_recover_action_counts))
        encoded=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        validate_pc_melee_simulation_document(encoded,'result')
        self.assertEqual(encoded['request'],raw)
        self.assertEqual(encoded['summary']['total_npc_recover_action_count'],summary.total_npc_recover_action_count)
        for field in ('npc_recover_action_trial_count','npc_recover_action_counts','total_npc_recover_action_count'):
            forged=deepcopy(encoded);del forged['summary'][field]
            with self.assertRaises(ValidationError):validate_pc_melee_simulation_document(forged,'result')

    def test_count_search_filters_policy_and_preserves_root_candidate_and_counter_sources(self):
        raw=flagellant_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates),report.total_trials),(4,4))
        self.assertEqual(tuple(c.counts for c in report.candidates),((1,0),(1,1),(2,0),(2,1)))
        encoded=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(encoded,'result')
        self.assertEqual(encoded['request'],raw)
        for item,candidate in zip(encoded['candidates'],report.candidates,strict=True):
            source=candidate.source_request.scenario
            self.assertEqual(source.npc_flagellant_policies,tuple(p for p in command.request.template.npc_flagellant_policies
                if p.actor_id in source.enemy_activation_order))
            self.assertEqual(item['request']['scenario'],scenario_document(source))
            self.assertEqual(tuple(c.actor_id for c in candidate.summary.npc_recover_action_counts),
                tuple(e.state.actor_id for e in source.enemies))
            self.assertEqual(item['summary']['total_npc_recover_action_count'],candidate.summary.total_npc_recover_action_count)

    def test_cached_equal_policy_and_counter_aliases_cannot_reach_rng_or_encoding(self):
        class Alias(str,Enum):
            ACTOR='flagellant_flails1'
        command=wire.parse_pc_melee_simulation_request(json.dumps(flagellant_document()))
        forged=deepcopy(command.request)
        object.__setattr__(forged.scenario.npc_flagellant_policies[0],'actor_id',Alias.ACTOR)
        self.assertEqual(forged,command.request)
        rng=Mock(side_effect=AssertionError('malformed source cannot consume RNG'))
        runner=Mock(side_effect=AssertionError('malformed source cannot enter runner'))
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',runner):
            with self.assertRaises(TypeError):run_pc_melee_trial(forged,0,rng_factory=rng)
        rng.assert_not_called();runner.assert_not_called()
        source=scripted_simulation();summary=summarize_pc_melee_simulation(source)
        bad=deepcopy(summary);object.__setattr__(bad.npc_recover_action_counts[0],'count',4.0)
        with self.assertRaises(TypeError):replace(bad)
