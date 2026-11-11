"""Current Close Shooting policy accepts the Orc chunk without a wire change."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_pistol_scenarios import pistol_profile
from tests.unit.test_m9_pc_melee_json import document
from tests.unit.test_m57_greenskin_close_shooting import PROFILES, greenskin_scene
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document, validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_balance_models import project_pc_melee_candidate
from towr.application.pc_melee_service import execute_pc_melee_balance, execute_pc_melee_simulation
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_npc_close_shooting_models import PcNpcCloseShootingProtectionPolicy as Policy
from towr.domain.test_models import Skill


NAME = 'npc_close_shooting_protection_policies'


def chunk_source():
    base = book_pc_scenario(footpads=1,townsfolk=0,orcs=1,unshielded_orcs=1,
        big_uns=1,unshielded_big_uns=1,pc_count=1,max_rounds=2)
    party = tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.PISTOL,
        ranged=pistol_profile())) for member in base.party)
    policies = tuple(Policy(actor,skill) for actor,skill in (
        ('orc1',Skill.MELEE),('unshielded_orc1',Skill.ATHLETICS),
        ('big_un1',Skill.ATHLETICS),('unshielded_big_un1',Skill.MELEE)))
    return replace(base,party=party,npc_close_shooting_protection_policies=policies)


def request_document(*, balance=False):
    raw = document(balance=balance)
    raw['template' if balance else 'scenario'] = scenario_document(chunk_source())
    if balance:
        raw['generation']['groups'] = [
            {'group_id':name,'actor_ids':[actor],'minimum_count':minimum,'maximum_count':maximum}
            for name,actor,minimum,maximum in (
                ('choppas','orc1',0,1),('spear','unshielded_orc1',0,1),
                ('big_choppas','big_un1',0,0),('big_spear','unshielded_big_un1',0,0),
                ('footpads','footpad1',1,1))]
        raw['generation']['facts'] = deepcopy(raw['template']['facts'])
        raw['generation']['max_candidates'] = 4
        raw['evaluation'].update(trials_per_candidate=1,max_total_trials=4)
    else:
        raw['simulation']['trials'] = 2
    return raw


class GreenskinCloseShootingJsonTests(unittest.TestCase):
    def test_all_four_profiles_and_both_choices_roundtrip_current_format(self):
        for profile,_,_,_ in PROFILES:
            for skill in (Skill.MELEE,Skill.ATHLETICS):
                with self.subTest(profile=profile,skill=skill):
                    raw = document()
                    raw['scenario'] = scenario_document(greenskin_scene(profile,skill))
                    command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
                    self.assertEqual(scenario_document(command.request.scenario),raw['scenario'])
                    self.assertEqual(raw['schema_version'],'1')
                    self.assertEqual(set(raw['scenario'][NAME][0]),{'actor_id','skill'})

    def test_count_projection_filters_only_removed_actors_without_changing_skills(self):
        raw = request_document(balance=True)
        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
        choices = raw['template'][NAME]
        for counts,expected in (((0,0,0,0,1),None),((1,0,0,0,1),[choices[0]]),
                ((0,1,0,0,1),[choices[1]]),((1,1,0,0,1),choices[:2])):
            projected = project_pc_melee_candidate(command.request,counts).scenario
            actual = scenario_document(projected)
            if expected is None:
                self.assertIsNone(projected.npc_close_shooting_protection_policies)
                self.assertNotIn(NAME,actual)
            else:
                self.assertEqual(actual[NAME],expected)
            self.assertEqual(scenario_document(command.request.template),raw['template'])

    def test_full_template_rejects_book_forgery_and_unsupported_override_before_rng(self):
        for kind in ('damage','unsupported'):
            raw = request_document(balance=True)
            raw['generation']['groups'][0]['maximum_count'] = 0
            raw['generation']['groups'][1]['maximum_count'] = 0
            if kind=='damage':
                enemy = next(enemy for enemy in raw['template']['enemies'] if enemy['actor_id']=='big_un1')
                enemy['definition']['attack']['damage']['base'] += 1
            else:
                raw['template'][NAME].append({'actor_id':'footpad1','skill':'athletics'})
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                with self.subTest(kind=kind),self.assertRaises(PcMeleeBalanceInputError):
                    wire.parse_pc_melee_balance_request(json.dumps(raw))
                rng.assert_not_called()

    def test_actual_services_preserve_complete_source_and_filtered_candidate_echoes(self):
        for balance in (False,True):
            raw = request_document(balance=balance)
            if balance:
                command = wire.parse_pc_melee_balance_request(json.dumps(raw))
                result = execute_pc_melee_balance(command)
                encoded = json.loads(wire.encode_pc_melee_balance_result(command,result))
                validate_pc_melee_balance_document(encoded,'result')
                choices = raw['template'][NAME]
                for row in encoded['candidates']:
                    expected = {(0,0):None,(1,0):[choices[0]],(0,1):[choices[1]],
                        (1,1):choices[:2]}[tuple(row['counts'][:2])]
                    scenario = row['request']['scenario']
                    if expected is None:
                        self.assertNotIn(NAME,scenario)
                    else:
                        self.assertEqual(scenario[NAME],expected)
            else:
                command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
                result = execute_pc_melee_simulation(command)
                encoded = json.loads(wire.encode_pc_melee_simulation_result(command,result))
                validate_pc_melee_simulation_document(encoded,'result')
            self.assertEqual(encoded['request'],raw)


if __name__ == '__main__':
    unittest.main()
