"""Named Miner grudges preserve their source and native costs through PC JSON1."""
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
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document,validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_service import execute_pc_melee_balance
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_models import PcMeleeScenario,PcMeleeWeapon
from towr.domain.pc_melee_result_models import PcAttackProof,PcRecoverProof
from towr.domain.pc_npc_grudge_policy_models import PcNpcGrudgePolicy
from towr.domain.pc_npc_grudge_models import PcNpcGrudgeEncounterProof,PcNpcGrudgeDistractionSource
from towr.domain.turn_models import CombatTurnStartResult
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def miner_document(*,balance=False,selected=True):
    source=book_pc_scenario(miners=2 if balance else 1,footpads=1,townsfolk=0,
        pc_count=2,max_rounds=2)
    policies=tuple(PcNpcGrudgePolicy(enemy.state.actor_id,'pc2') for enemy in source.enemies
        if enemy.state.actor_id.startswith('miner')) if selected else ()
    source=replace(source,npc_grudge_policies=policies,
        party=tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.AXE)) for member in source.party))
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            dict(group_id='miners',actor_ids=['miner1','miner2'],minimum_count=0,maximum_count=2),
            dict(group_id='footpads',actor_ids=['footpad1'],minimum_count=1,maximum_count=1)],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':3}
        raw['evaluation'].update(master_seed='42',trials_per_candidate=1,max_total_trials=3,top_k=2)
    else:
        raw['simulation'].update(master_seed='42',trials=2)
    return raw


class PcMinerGrudgeJsonTests(unittest.TestCase):
    def test_selected_and_empty_policy_roundtrip_without_changing_target_priorities(self):
        for balance in (False,True):
            for selected in (False,True):
                raw=miner_document(balance=balance,selected=selected)
                key='template' if balance else 'scenario'
                parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
                command=parse(json.dumps(raw))
                source=command.request.template if balance else command.request.scenario
                self.assertEqual(scenario_document(source),raw[key])
                self.assertEqual(source.enemy_target_priority,('pc1','pc2'))
                self.assertEqual(tuple(p.focus_actor_id for p in source.npc_grudge_policies),
                    ('pc2',)*(2 if balance else 1) if selected else ())
                self.assertEqual(raw['schema_version'],'1')
                self.assertEqual(source.npc_extra_attack_actor_ids,())
                for enemy in source.enemies:
                    if enemy.state.actor_id.startswith('miner'):
                        self.assertEqual(enemy.definition.id,'pc-book-npc:dwarf_miner_pickaxe')
                        self.assertEqual(enemy.definition.source_rule_id,'BOOK-GM-GUIDE:1.1:p105:dwarf_miner_pickaxe')
                        self.assertFalse(enemy.state.injury.conditions.has(Condition.DISTRACTED))

    def test_policy_field_and_closed_exact_pairs_are_required_in_both_requests(self):
        malformed=(None,True,{},'miner1',[{}],
            [{'actor_id':'miner1'}],[{'actor_id':'miner1','focus_actor_id':'pc2','epoch':1}],
            [{'actor_id':1,'focus_actor_id':'pc2'}],
            [{'actor_id':'miner1','focus_actor_id':''}],
            [{'actor_id':'miner1','focus_actor_id':'pc2'}]*2)
        for balance in (False,True):
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            validate=validate_pc_melee_balance_document if balance else validate_pc_melee_simulation_document
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for value in malformed:
                raw=miner_document(balance=balance)
                raw[key]['npc_grudge_policies']=value
                with self.subTest(balance=balance,value=value):
                    with self.assertRaises(ValidationError):validate(raw)
                    with self.assertRaises(error):parse(json.dumps(raw))
            raw=miner_document(balance=balance)
            del raw[key]['npc_grudge_policies']
            with self.assertRaises(error):parse(json.dumps(raw))
        source=wire.parse_pc_melee_simulation_request(json.dumps(miner_document())).request.scenario
        native={item.name:getattr(source,item.name) for item in fields(source) if item.name!='npc_grudge_policies'}
        with self.assertRaises(TypeError):PcMeleeScenario(**native)
        with self.assertRaises(TypeError):replace(source,npc_grudge_policies=list(source.npc_grudge_policies))

    def test_roles_unknown_ids_other_profiles_and_multiple_foci_for_one_miner_are_rejected(self):
        for policies in ([{'actor_id':'pc1','focus_actor_id':'pc2'}],
                [{'actor_id':'footpad1','focus_actor_id':'pc2'}],
                [{'actor_id':'unknown','focus_actor_id':'pc2'}],
                [{'actor_id':'miner1','focus_actor_id':'footpad1'}],
                [{'actor_id':'miner1','focus_actor_id':'unknown'}],
                [{'actor_id':'miner1','focus_actor_id':'pc1'},
                 {'actor_id':'miner1','focus_actor_id':'pc2'}]):
            raw=miner_document()
            raw['scenario']['npc_grudge_policies']=policies
            validate_pc_melee_simulation_document(raw)
            with self.subTest(policies=policies),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_full_canonical_source_still_rejects_printed_aliases_gear_and_partial_renames(self):
        for path,value in (('definition.attack.test_profile.threshold',3.0),
                ('definition.attack.hands','1h'),('holds_shield',True),
                ('definition.id','authored:miner'),('definition.source_rule_id','authored:source')):
            raw=miner_document()
            target=raw['scenario']['enemies'][0]
            parts=path.split('.')
            for part in parts[:-1]:target=target[part]
            target[parts[-1]]=value
            with self.subTest(path=path),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_native_grudge_and_empty_opt_out_reach_compact_trials_without_extra_actions(self):
        for selected in (False,True):
            raw=miner_document(selected=selected)
            command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
            native=[]

            def observe(source,rng):
                result=run_pc_melee_scenario(source,rng)
                native.append(result)
                return result

            with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',side_effect=observe):
                result=run_pc_melee_simulation(command.request)
            summary=summarize_pc_melee_simulation(result)
            observed=any(step.state.enemy('miner1').state.injury.conditions.has(Condition.DISTRACTED)
                for battle in native for step in battle.steps)
            self.assertEqual(observed,selected)
            self.assertEqual((len(native),len(result.records),summary.trials),(2,2,2))
            for battle,record in zip(native,result.records,strict=True):
                encounters=tuple((index,step) for index,step in enumerate(battle.steps)
                    if type(step.proof) is PcNpcGrudgeEncounterProof)
                self.assertEqual(len(encounters),int(selected))
                if selected:
                    index,encounter=encounters[0]
                    self.assertEqual(encounter.proof.policy,command.request.scenario.npc_grudge_policies[0])
                    self.assertLess(index,next(i for i,step in enumerate(battle.steps)
                        if type(step.proof) is CombatTurnStartResult))
                    cause,=tuple(cause for cause in encounter.state.npc_distractions
                        if type(cause) is PcNpcGrudgeDistractionSource)
                    self.assertEqual((cause.actor_id,cause.focus_actor_id,cause.encounter_id),
                        ('miner1','pc2',encounter.proof.request_id))
                self.assertEqual(record.source_scenario,command.request.scenario)
                self.assertEqual(battle.source,record.source_scenario)
                self.assertEqual(record.outcome,battle.outcome)
                self.assertEqual(record.executed_actions,battle.executed_actions)
                self.assertEqual(record.executed_actions,
                    sum(type(step.proof) in (PcAttackProof,PcRecoverProof) for step in battle.steps))
                self.assertLessEqual(record.executed_actions,4*record.started_rounds)
                self.assertFalse(hasattr(record,'steps'))
            self.assertEqual(summary.total_action_count,sum(r.executed_actions for r in result.records))
            self.assertEqual((summary.total_npc_help_action_count,summary.total_npc_extra_attack_count),(0,0))
            encoded=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
            validate_pc_melee_simulation_document(encoded,'result')
            self.assertEqual(encoded['request'],raw)
            self.assertFalse(hasattr(summary,'records'))

    def test_count_projection_removes_missing_miner_policies_without_changing_focus(self):
        raw=miner_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates),report.total_trials),(3,3))
        self.assertEqual(tuple(candidate.counts for candidate in report.candidates),((0,1),(1,1),(2,1)))
        for candidate in report.candidates:
            source=candidate.source_request.scenario
            retained=tuple(enemy.state.actor_id for enemy in source.enemies)
            self.assertEqual(source.npc_grudge_policies,tuple(policy
                for policy in command.request.template.npc_grudge_policies if policy.actor_id in retained))
            self.assertEqual(source.enemy_target_priority,('pc1','pc2'))
            self.assertEqual(tuple((item.actor_id,item.count) for item in candidate.summary.npc_extra_attack_counts),
                tuple((actor,0) for actor in retained))
            self.assertEqual(candidate.summary.total_npc_extra_attack_count,0)
        encoded=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(encoded,'result')
        self.assertEqual(encoded['request'],raw)
        for item,candidate in zip(encoded['candidates'],report.candidates,strict=True):
            self.assertEqual(item['request']['scenario'],scenario_document(candidate.source_request.scenario))

    def test_cached_equal_policy_ids_are_rejected_before_rng_or_execution(self):
        class Alias(str,Enum):
            ACTOR='miner1'
            FOCUS='pc2'
        command=wire.parse_pc_melee_simulation_request(json.dumps(miner_document()))
        for field,value in (('actor_id',Alias.ACTOR),('focus_actor_id',Alias.FOCUS)):
            forged=deepcopy(command.request)
            object.__setattr__(forged.scenario.npc_grudge_policies[0],field,value)
            self.assertEqual(forged,command.request)
            rng=Mock(side_effect=AssertionError('malformed source cannot consume RNG'))
            runner=Mock(side_effect=AssertionError('malformed source cannot become an observation'))
            with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',runner):
                with self.subTest(field=field),self.assertRaises(TypeError):
                    run_pc_melee_trial(forged,0,rng_factory=rng)
            rng.assert_not_called()
            runner.assert_not_called()


if __name__=='__main__':
    unittest.main()
