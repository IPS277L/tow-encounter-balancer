"""Explicit natural Melee survives current JSON1, native trials and count search."""
from copy import deepcopy
from itertools import product
import json
from random import Random
import unittest
from unittest.mock import Mock, patch

from jsonschema import ValidationError

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError, PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document, validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_service import execute_pc_melee_balance
from towr.domain.pc_melee_result_models import PcAttackProof
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation, run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def chunk_document(*,balance=False):
    source=book_pc_scenario(horses=2 if balance else 1,wolves=1,boars=1,
        footpads=0,townsfolk=0,pc_count=2,max_rounds=3)
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            {'group_id':'horses','actor_ids':['horse1','horse2'],'minimum_count':1,'maximum_count':2},
            {'group_id':'wolves','actor_ids':['wolf1'],'minimum_count':0,'maximum_count':1},
            {'group_id':'boars','actor_ids':['boar1'],'minimum_count':0,'maximum_count':1}],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':8}
        raw['evaluation'].update(trials_per_candidate=2,max_total_trials=16,top_k=2)
    else:
        raw['simulation']['trials']=2
    return raw


class NaturalCreatureChunkIntegrationTests(unittest.TestCase):
    def test_current_json_roundtrip_keeps_explicit_null_and_fresh_unarmed_creatures(self):
        for balance in (False,True):
            raw=chunk_document(balance=balance)
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw[key])
            self.assertEqual(raw['schema_version'],'1')
            self.assertEqual(tuple(enemy.state.actor_id for enemy in source.enemies),
                ('horse1','horse2','wolf1','boar1') if balance else ('horse1','wolf1','boar1'))
            for raw_enemy,enemy in zip(raw[key]['enemies'],source.enemies,strict=True):
                self.assertIn('hands',raw_enemy['definition']['attack'])
                self.assertIsNone(raw_enemy['definition']['attack']['hands'])
                self.assertIsNone(enemy.definition.attacks[0].hands)
                self.assertIs(enemy.state.wields_weapon,False)
                self.assertIs(enemy.state.holds_shield,False)
                self.assertIs(enemy.definition.protection[0].skill,Skill.ATHLETICS)
                validate_pc_book_npc_definition(enemy.definition)

    def test_natural_null_is_distinct_from_missing_false_aliases_and_npc_defence(self):
        for balance in (False,True):
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            validate=validate_pc_melee_balance_document if balance else validate_pc_melee_simulation_document
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for hands in (False,True,0,1,'natural','unarmed','None','2H',[],{}):
                raw=chunk_document(balance=balance)
                raw[key]['enemies'][0]['definition']['attack']['hands']=hands
                with self.subTest(balance=balance,hands=hands):
                    with self.assertRaises(ValidationError):
                        validate(raw)
                    with self.assertRaises(error):
                        parse(json.dumps(raw))
            raw=chunk_document(balance=balance)
            del raw[key]['enemies'][0]['definition']['attack']['hands']
            with self.assertRaises(ValidationError):
                validate(raw)
            with self.assertRaises(error):
                parse(json.dumps(raw))
            raw=chunk_document(balance=balance)
            raw[key]['enemies'][0]['definition']['protection']['skill']='defence'
            with self.assertRaises(ValidationError):
                validate(raw)
            with self.assertRaises(error):
                parse(json.dumps(raw))
            for hands in ('1h','2h'):
                raw=chunk_document(balance=balance)
                raw[key]['enemies'][0]['definition']['attack']['hands']=hands
                with self.subTest(balance=balance,rewrite=hands),self.assertRaises(error):
                    parse(json.dumps(raw))

    def test_actual_native_and_trial_aggregates_preserve_natural_melee_and_full_source(self):
        raw=chunk_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        native=run_pc_melee_scenario(command.request.scenario,Random(command.request.seed_for(0)))
        observed=0
        enemies={enemy.state.actor_id:enemy for enemy in command.request.scenario.enemies}
        for step in native.steps:
            if not isinstance(step.proof,PcAttackProof):
                continue
            preparation=step.proof.protection.source_request
            self.assertIs(preparation.attack_skill,Skill.MELEE)
            if step.proof.request.target_id in enemies:
                observed+=1
                self.assertIs(preparation.defender_wields_weapon,False)
                self.assertIs(preparation.defender_holds_shield,False)
                self.assertIs(preparation.selected_skill,Skill.ATHLETICS)
            if step.proof.request.actor_id in enemies:
                expected=enemies[step.proof.request.actor_id].definition.attacks[0].test_profile
                self.assertEqual(preparation.attack.attacker_test.profile,expected)
        self.assertGreater(observed,0)
        simulation=run_pc_melee_simulation(command.request)
        summary=summarize_pc_melee_simulation(simulation)
        self.assertEqual(summary.source_request,command.request)
        self.assertEqual(summary.trials,2)
        self.assertEqual(tuple((item.actor_id,item.count) for item in summary.npc_exit_counts),
            (('horse1',0),('wolf1',0),('boar1',0)))
        result=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        validate_pc_melee_simulation_document(result,'result')
        self.assertEqual(result['request'],raw)
        self.assertEqual(result['schema_version'],'1')
        self.assertFalse(hasattr(summary,'records'))

    def test_count_search_keeps_eight_natural_prefixes_with_full_candidate_echoes(self):
        raw=chunk_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates),report.total_trials),(8,16))
        self.assertEqual(tuple(candidate.counts for candidate in report.candidates),tuple(product((1,2),(0,1),(0,1))))
        originals={enemy.state.actor_id:enemy.definition for enemy in command.request.template.enemies}
        for candidate in report.candidates:
            horses,wolves,boars=candidate.counts
            expected=tuple(f'horse{index+1}' for index in range(horses))+(
                ('wolf1',) if wolves else ())+ (('boar1',) if boars else ())
            source=candidate.source_request.scenario
            self.assertEqual(tuple(enemy.state.actor_id for enemy in source.enemies),expected)
            self.assertEqual(source.enemy_activation_order,expected)
            for member in source.party:
                self.assertEqual(member.target_priority,expected)
            for enemy in source.enemies:
                self.assertEqual(enemy.definition,originals[enemy.state.actor_id])
                self.assertIsNone(enemy.definition.attacks[0].hands)
                self.assertIs(enemy.state.wields_weapon,False)
                validate_pc_book_npc_definition(enemy.definition)
            self.assertEqual(tuple(item.actor_id for item in candidate.summary.npc_exit_counts),expected)
            self.assertFalse(hasattr(candidate.summary,'records'))
        result=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(result,'result')
        self.assertEqual(result['request'],raw)
        for candidate,typed in zip(result['candidates'],report.candidates,strict=True):
            self.assertEqual(candidate['request']['scenario'],scenario_document(typed.source_request.scenario))

    def test_cached_wrong_weapon_fact_and_equal_false_alias_cannot_become_observations(self):
        command=wire.parse_pc_melee_simulation_request(json.dumps(chunk_document()))
        for value in (True,0):
            forged=deepcopy(command.request)
            object.__setattr__(forged.scenario.enemies[0].state,'wields_weapon',value)
            if value==0:
                self.assertEqual(forged,command.request)
            runner=Mock(side_effect=AssertionError('inconsistent natural source must be refused before execution'))
            rng=Mock(side_effect=AssertionError('inconsistent natural source must not consume RNG'))
            with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',runner):
                with self.subTest(value=value),self.assertRaises((TypeError,ValueError)):
                    run_pc_melee_trial(forged,0,rng_factory=rng)
            runner.assert_not_called()
            rng.assert_not_called()

    def test_process_preserves_explicit_none_profiles_records_and_aggregates(self):
        request=wire.parse_pc_melee_simulation_request(json.dumps(chunk_document())).request
        sequential=run_pc_melee_simulation(request)
        process=run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(process,sequential)
        self.assertEqual(summarize_pc_melee_simulation(process),summarize_pc_melee_simulation(sequential))
        for record in process.records:
            for enemy in record.source_scenario.enemies:
                self.assertIsNone(enemy.definition.attacks[0].hands)
                self.assertIs(enemy.state.wields_weapon,False)


if __name__=='__main__':
    unittest.main()
