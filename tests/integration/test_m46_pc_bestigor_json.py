"""Explicit Blood Rage and one-shot NPC Glorious through the current PC JSON1."""
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
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError,PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import validate_pc_melee_balance_document,validate_pc_melee_simulation_document
from towr.application.pc_melee_service import execute_pc_melee_balance
from towr.domain.pc_melee_models import PcMeleeScenario,PcMeleeWeapon
from towr.domain.pc_melee_result_models import PcAttackProof,PcRecoverProof,PcHelpProof,PcNpcHelpProof
from towr.domain.pc_bestigor_models import PcNpcBloodRageProof
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def bestigor_document(*,balance=False,selected=True):
    source=book_pc_scenario(bestigors=2 if balance else 1,footpads=1,townsfolk=0,pc_count=2,max_rounds=2)
    source=replace(source,npc_blood_rage_actor_ids=tuple(e.state.actor_id for e in source.enemies
        if e.state.actor_id.startswith('bestigor')) if selected else (),
        party=tuple(replace(m,pc=replace(m.pc,weapon=PcMeleeWeapon.AXE)) for m in source.party))
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            dict(group_id='bestigors',actor_ids=['bestigor1','bestigor2'],minimum_count=0,maximum_count=2),
            dict(group_id='footpads',actor_ids=['footpad1'],minimum_count=1,maximum_count=1)],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':3}
        raw['evaluation'].update(master_seed='42',trials_per_candidate=1,max_total_trials=3,top_k=2)
    else:
        raw['simulation'].update(master_seed='42',trials=2)
    return raw


class PcBestigorJsonTests(unittest.TestCase):
    def test_required_list_and_exact_canonical_profiles_roundtrip_both_requests(self):
        for balance in (False,True):
            for selected in (False,True):
                raw=bestigor_document(balance=balance,selected=selected)
                key='template' if balance else 'scenario'
                parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
                command=parse(json.dumps(raw))
                source=command.request.template if balance else command.request.scenario
                self.assertEqual(scenario_document(source),raw[key])
                self.assertEqual(raw['schema_version'],'1')
                self.assertEqual(source.npc_blood_rage_actor_ids,
                    tuple(f'bestigor{i+1}' for i in range(2 if balance else 1)) if selected else ())
                self.assertEqual(source.enemies[0].definition.attacks[0].test_profile.pool_cap,8)
                self.assertIsNone(source.enemies[0].definition.protection[0].test_profile.pool_cap)
        raw=bestigor_document(balance=True)
        raw['template']['npc_blood_rage_actor_ids'].reverse()
        source=wire.parse_pc_melee_balance_request(json.dumps(raw)).request.template
        self.assertEqual(source.npc_blood_rage_actor_ids,('bestigor2','bestigor1'))
        self.assertEqual(scenario_document(source),raw['template'])

    def test_omission_wrong_shapes_duplicates_and_alias_values_are_rejected(self):
        for balance in (False,True):
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            validate=validate_pc_melee_balance_document if balance else validate_pc_melee_simulation_document
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for value in (None,True,{},'bestigor1',[1],[''],['bestigor1','bestigor1']):
                raw=bestigor_document(balance=balance);raw[key]['npc_blood_rage_actor_ids']=value
                with self.subTest(balance=balance,value=value):
                    with self.assertRaises(ValidationError):validate(raw)
                    with self.assertRaises(error):parse(json.dumps(raw))
            raw=bestigor_document(balance=balance);del raw[key]['npc_blood_rage_actor_ids']
            with self.assertRaises(error):parse(json.dumps(raw))
        source=wire.parse_pc_melee_simulation_request(json.dumps(bestigor_document())).request.scenario
        values={f.name:getattr(source,f.name) for f in fields(source) if f.name!='npc_blood_rage_actor_ids'}
        with self.assertRaises(TypeError):PcMeleeScenario(**values)
        with self.assertRaises(TypeError):replace(source,npc_blood_rage_actor_ids=['bestigor1'])

    def test_wrong_roles_unknown_and_other_profile_ids_do_not_enable_rage(self):
        for actor in ('pc1','unknown','footpad1'):
            raw=bestigor_document();raw['scenario']['npc_blood_rage_actor_ids']=[actor]
            validate_pc_melee_simulation_document(raw)
            with self.subTest(actor=actor),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_full_source_cap_gear_and_numeric_guards_are_preserved(self):
        for path,value in (('definition.attack.test_profile.pool_cap',None),
                ('definition.protection.test_profile.pool_cap',8),('holds_shield',True),
                ('definition.attack.test_profile.dice',4),('definition.attack.test_profile.threshold',4.0),
                ('definition.id','authored:bestigor'),('definition.source_rule_id','authored:source')):
            raw=bestigor_document();target=raw['scenario']['enemies'][0]
            parts=path.split('.')
            for part in parts[:-1]:target=target[part]
            target[parts[-1]]=value
            with self.subTest(path=path),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))
        raw=bestigor_document();raw['scenario']['enemies'][1]['definition']['attack']['test_profile']['pool_cap']=8
        with self.assertRaises(PcMeleeSimulationInputError):wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_native_rage_steps_and_glorious_do_not_become_actions_fate_spends_or_worker_journals(self):
        for selected in (False,True):
            raw=bestigor_document(selected=selected)
            command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
            native=[]
            def observe(source,rng):
                result=run_pc_melee_scenario(source,rng);native.append(result);return result
            with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',side_effect=observe):
                result=run_pc_melee_simulation(command.request)
            summary=summarize_pc_melee_simulation(result)
            for battle,record in zip(native,result.records,strict=True):
                self.assertEqual(record.executed_actions,battle.executed_actions)
                self.assertEqual(record.executed_actions,sum(type(s.proof) in
                    (PcAttackProof,PcRecoverProof,PcHelpProof,PcNpcHelpProof) for s in battle.steps))
                self.assertEqual(record.source_scenario,command.request.scenario)
                self.assertFalse(hasattr(record,'steps'))
                for step in battle.steps:
                    if type(step.proof) is PcNpcBloodRageProof:
                        self.assertIn(step.proof.actor_id,command.request.scenario.npc_blood_rage_actor_ids)
                        self.assertEqual(step.source.round_state,step.state.round_state)
            self.assertEqual(summary.total_glorious_spend_count,0)
            self.assertEqual(summary.total_action_count,sum(r.executed_actions for r in result.records))
            encoded=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
            validate_pc_melee_simulation_document(encoded,'result')
            self.assertEqual(encoded['request'],raw)

    def test_count_search_filters_rage_list_without_reassignment_and_keeps_full_echoes(self):
        raw=bestigor_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates),report.total_trials),(3,3))
        self.assertEqual(tuple(c.counts for c in report.candidates),((0,1),(1,1),(2,1)))
        encoded=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(encoded,'result')
        self.assertEqual(encoded['request'],raw)
        for item,candidate in zip(encoded['candidates'],report.candidates,strict=True):
            source=candidate.source_request.scenario
            self.assertEqual(source.npc_blood_rage_actor_ids,tuple(actor
                for actor in command.request.template.npc_blood_rage_actor_ids if actor in source.enemy_activation_order))
            self.assertEqual(item['request']['scenario'],scenario_document(source))

    def test_cached_equal_rage_alias_is_rejected_before_rng_or_observation(self):
        class Alias(str,Enum):
            ACTOR='bestigor1'
        command=wire.parse_pc_melee_simulation_request(json.dumps(bestigor_document()))
        forged=deepcopy(command.request)
        object.__setattr__(forged.scenario,'npc_blood_rage_actor_ids',(Alias.ACTOR,))
        self.assertEqual(forged,command.request)
        rng=Mock(side_effect=AssertionError('malformed source cannot consume RNG'))
        runner=Mock(side_effect=AssertionError('malformed source cannot enter runner'))
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',runner):
            with self.assertRaises(TypeError):run_pc_melee_trial(forged,0,rng_factory=rng)
        rng.assert_not_called();runner.assert_not_called()
