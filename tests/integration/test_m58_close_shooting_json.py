"""Current policy echoes preserve special NPC sources and actor-bound choices."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_pistol_scenarios import pistol_profile
from tests.unit.test_m9_pc_melee_json import document
from tests.unit.test_m58_close_shooting_execution import PROFILES, special_scene
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
from towr.domain.pc_npc_grudge_policy_models import PcNpcGrudgePolicy
from towr.domain.test_models import Skill


NAME = 'npc_close_shooting_protection_policies'


def chunk_source():
    base = book_pc_scenario(footpads=1,townsfolk=0,skulkers=1,brewguards=1,
        miners=1,bestigors=1,pc_count=1,max_rounds=2)
    party = tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.PISTOL,
        ranged=pistol_profile())) for member in base.party)
    choices = tuple(Policy(actor,skill) for actor,skill in (
        ('skulker1',Skill.MELEE),('brewguard1',Skill.ATHLETICS),
        ('miner1',Skill.MELEE),('bestigor1',Skill.ATHLETICS)))
    return replace(base,party=party,npc_close_shooting_protection_policies=choices,
        npc_grudge_policies=(PcNpcGrudgePolicy('miner1','pc1'),),
        npc_blood_rage_actor_ids=('bestigor1',))


def request_document(*, balance=False):
    raw = document(balance=balance)
    raw['template' if balance else 'scenario'] = scenario_document(chunk_source())
    if balance:
        raw['generation']['groups'] = [
            {'group_id':name,'actor_ids':[actor],'minimum_count':minimum,'maximum_count':maximum}
            for name,actor,minimum,maximum in (
                ('skulker','skulker1',0,1),('brewguard','brewguard1',0,0),
                ('miner','miner1',0,1),('bestigor','bestigor1',0,0),
                ('footpads','footpad1',1,1))]
        raw['generation']['facts'] = deepcopy(raw['template']['facts'])
        raw['generation']['max_candidates'] = 4
        raw['evaluation'].update(trials_per_candidate=1,max_total_trials=4)
    else:
        raw['simulation']['trials'] = 2
    return raw


class SpecialCloseShootingJsonTests(unittest.TestCase):
    def test_all_four_profiles_and_both_choices_keep_current_source_roundtrip(self):
        for profile,_,_,_,_,_,_,_ in PROFILES:
            for skill in (Skill.MELEE,Skill.ATHLETICS):
                with self.subTest(profile=profile,skill=skill):
                    raw = document()
                    raw['scenario'] = scenario_document(special_scene(profile,skill))
                    command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
                    self.assertEqual(scenario_document(command.request.scenario),raw['scenario'])
                    self.assertEqual(raw['schema_version'],'1')
                    self.assertEqual(set(raw['scenario'][NAME][0]),{'actor_id','skill'})

    def test_subset_filters_grudge_and_protection_actors_without_reassignment(self):
        raw = request_document(balance=True)
        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
        choices = raw['template'][NAME]
        for counts,expected in (((0,0,0,0,1),None),((1,0,0,0,1),[choices[0]]),
                ((0,0,1,0,1),[choices[2]]),((1,0,1,0,1),[choices[0],choices[2]])):
            candidate = project_pc_melee_candidate(command.request,counts).scenario
            actual = scenario_document(candidate)
            if expected is None:
                self.assertIsNone(candidate.npc_close_shooting_protection_policies)
                self.assertNotIn(NAME,actual)
            else:
                self.assertEqual(actual[NAME],expected)
            self.assertEqual(actual['npc_grudge_policies'],
                raw['template']['npc_grudge_policies'] if counts[2] else [])
            self.assertEqual(actual['npc_blood_rage_actor_ids'],[])
            self.assertEqual(scenario_document(command.request.template),raw['template'])

    def test_full_template_book_forgery_and_arbitrary_protection_cap_fail_before_rng(self):
        for kind in ('attack','protection_cap','unsupported'):
            raw = request_document(balance=True)
            raw['generation']['groups'][0]['maximum_count'] = 0
            raw['generation']['groups'][2]['maximum_count'] = 0
            if kind=='attack':
                enemy = next(enemy for enemy in raw['template']['enemies'] if enemy['actor_id']=='bestigor1')
                enemy['definition']['attack']['test_profile']['dice'] = 4
            elif kind=='protection_cap':
                enemy = next(enemy for enemy in raw['template']['enemies'] if enemy['actor_id']=='miner1')
                enemy['definition']['protection']['test_profile']['pool_cap'] = 4
            else:
                raw['template'][NAME].append({'actor_id':'footpad1','skill':'athletics'})
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                with self.subTest(kind=kind),self.assertRaises(PcMeleeBalanceInputError):
                    wire.parse_pc_melee_balance_request(json.dumps(raw))
                rng.assert_not_called()

    def test_actual_services_keep_complete_source_and_filtered_candidate_choices(self):
        for balance in (False,True):
            raw = request_document(balance=balance)
            if balance:
                command = wire.parse_pc_melee_balance_request(json.dumps(raw))
                result = execute_pc_melee_balance(command)
                encoded = json.loads(wire.encode_pc_melee_balance_result(command,result))
                validate_pc_melee_balance_document(encoded,'result')
                choices = raw['template'][NAME]
                for row in encoded['candidates']:
                    first,_,miner,_,_ = row['counts']
                    expected = {(0,0):None,(1,0):[choices[0]],(0,1):[choices[2]],
                        (1,1):[choices[0],choices[2]]}[(first,miner)]
                    source = row['request']['scenario']
                    if expected is None:
                        self.assertNotIn(NAME,source)
                    else:
                        self.assertEqual(source[NAME],expected)
                    self.assertEqual(source['npc_grudge_policies'],
                        raw['template']['npc_grudge_policies'] if miner else [])
            else:
                command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
                result = execute_pc_melee_simulation(command)
                encoded = json.loads(wire.encode_pc_melee_simulation_result(command,result))
                validate_pc_melee_simulation_document(encoded,'result')
            self.assertEqual(encoded['request'],raw)


if __name__ == '__main__':
    unittest.main()
