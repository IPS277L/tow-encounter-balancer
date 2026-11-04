"""Fixed book Halberd/Defence survives JSON, trials and aggregate-only count search."""
from copy import deepcopy
from dataclasses import replace
import json
from random import Random
import unittest
from unittest.mock import patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document,validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_service import execute_pc_melee_balance,execute_pc_melee_simulation
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


def trooper_document(*,balance=False):
    source=book_pc_scenario(troopers=2 if balance else 1,footpads=1,townsfolk=0,max_rounds=3)
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            {'group_id':'troopers','actor_ids':['trooper1','trooper2'],'minimum_count':1,'maximum_count':2},
            {'group_id':'footpads','actor_ids':['footpad1'],'minimum_count':0,'maximum_count':1}],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':4}
        raw['evaluation'].update(trials_per_candidate=2,max_total_trials=8,top_k=2)
    else:
        raw['simulation']['trials']=2
    return raw


class PcStateTrooperIntegrationTests(unittest.TestCase):
    def test_current_json_and_trials_preserve_two_handed_defence_and_full_request(self):
        raw=trooper_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        self.assertEqual(scenario_document(command.request.scenario),raw['scenario'])
        summary=execute_pc_melee_simulation(command)
        result=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        validate_pc_melee_simulation_document(result,'result')
        self.assertEqual(result['request'],raw)
        self.assertEqual(summary.trials,2)
        self.assertEqual(tuple((item.actor_id,item.count) for item in summary.npc_exit_counts),
            (('trooper1',0),('footpad1',0)))
        trooper=summary.source_request.scenario.enemies[0]
        self.assertIs(trooper.definition.protection[0].skill,Skill.DEFENCE)
        validate_pc_book_npc_definition(trooper.definition)

    def test_count_search_preserves_fixed_loadout_and_protection_without_journals(self):
        raw=trooper_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=execute_pc_melee_balance(command)
        result=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(result,'result')
        self.assertEqual(result['request'],raw)
        self.assertEqual((len(report.candidates),report.total_trials),(4,8))
        definitions={enemy.state.actor_id:enemy.definition for enemy in command.request.template.enemies}
        for candidate in report.candidates:
            self.assertFalse(hasattr(candidate.summary,'records'))
            for enemy in candidate.source_request.scenario.enemies:
                self.assertEqual(enemy.definition,definitions[enemy.state.actor_id])
                validate_pc_book_npc_definition(enemy.definition)
        for candidate in result['candidates']:
            self.assertEqual(candidate['summary']['total_npc_exit_count'],0)

    def test_known_identity_rejects_athletics_or_one_handed_rewrite_at_public_admission(self):
        for field,value in (('skill','athletics'),('threshold',3),('hands','1h')):
            raw=trooper_document()
            definition=raw['scenario']['enemies'][0]['definition']
            if field=='hands':
                definition['attack'][field]=value
            elif field=='skill':
                definition['protection'][field]=value
            else:
                definition['protection']['test_profile'][field]=value
            with self.subTest(field=field),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_equal_cached_armour_alias_cannot_become_a_trial_observation(self):
        command=wire.parse_pc_melee_simulation_request(json.dumps(trooper_document()))
        request=replace(command.request,trials=1)
        native=run_pc_melee_scenario(request.scenario,Random(request.seed_for(0)))
        forged=deepcopy(native)
        object.__setattr__(forged.source.enemies[0].definition.resilience,'bonus',True)
        self.assertEqual(forged,native)
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',return_value=forged):
            with self.assertRaises((TypeError,ValueError)):
                run_pc_melee_trial(request,0)


if __name__=='__main__':
    unittest.main()
