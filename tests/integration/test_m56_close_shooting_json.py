"""Optional explicit Close Shooting choices, strict preflight and full echoes."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import json
import unittest
from unittest.mock import patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_pistol_scenarios import pistol_profile
from tests.unit.test_m9_pc_melee_json import document
from tests.integration.test_m55_pistol_shield_json import pistol_shield_document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import parse_scenario, scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError, PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document, validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_balance_models import project_pc_melee_candidate
from towr.application.pc_melee_service import execute_pc_melee_balance, execute_pc_melee_simulation
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_npc_close_shooting_models import PcNpcCloseShootingProtectionPolicy as Policy
from towr.domain.test_models import Skill
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


NAME = 'npc_close_shooting_protection_policies'


def source():
    base = book_pc_scenario(footpads=1,townsfolk=0,troopers=1,spear_troopers=1,
        empire_knights=1,wolf_knights=1,pc_count=1,max_rounds=3)
    party = tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.PISTOL,
        pistol=pistol_profile())) for member in base.party)
    choices = tuple(Policy(actor,skill) for actor,skill in (
        ('trooper1',Skill.MELEE),('spear_trooper1',Skill.ATHLETICS),
        ('empire_knight1',Skill.ATHLETICS),('wolf_knight1',Skill.MELEE)))
    return replace(base,party=party,npc_close_shooting_protection_policies=choices)


def request_document(*, balance=False):
    raw = document(balance=balance)
    raw['template' if balance else 'scenario'] = scenario_document(source())
    if balance:
        raw['generation']['groups'] = [
            {'group_id':name,'actor_ids':[actor],'minimum_count':minimum,'maximum_count':maximum}
            for name,actor,minimum,maximum in (
                ('halberd','trooper1',0,1),('spear','spear_trooper1',0,1),
                ('empire','empire_knight1',0,0),('wolf','wolf_knight1',0,0),
                ('footpads','footpad1',1,1))]
        raw['generation']['facts'] = deepcopy(raw['template']['facts'])
        raw['generation']['max_candidates'] = 4
        raw['evaluation'].update(trials_per_candidate=1,max_total_trials=4)
    else:
        raw['simulation']['trials'] = 2
    return raw


class CloseShootingJsonTests(unittest.TestCase):
    def test_optional_absence_and_complete_choice_roundtrip(self):
        for balance in (False,True):
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            key = 'template' if balance else 'scenario'
            for raw in (pistol_shield_document(balance=balance),request_document(balance=balance)):
                command = parse(json.dumps(raw))
                actual = command.request.template if balance else command.request.scenario
                self.assertEqual(scenario_document(actual),raw[key])
                self.assertEqual(NAME in scenario_document(actual),NAME in raw[key])
                self.assertEqual(raw['schema_version'],'1')

    def test_closed_optional_field_rejects_null_empty_aliases_and_numeric_overrides(self):
        malformed = (None,[],{},'melee',True,[{}],
            [{'actor_id':'trooper1','skill':'defence'}],
            [{'actor_id':'trooper1','skill':'melee','pool_cap':6}],
            [{'actor_id':'trooper1','skill':True}],
            [{'actor_id':True,'skill':'melee'}])
        for balance in (False,True):
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error = PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                for policies in malformed:
                    raw = request_document(balance=balance)
                    raw[key][NAME] = policies
                    with self.subTest(policies=policies,balance=balance),self.assertRaises(error):
                        parse(json.dumps(raw))
                rng.assert_not_called()

    def test_codec_without_schema_keeps_closed_nonempty_policy_guards(self):
        for invalid in (None,[],{},[{}],[{'actor_id':'trooper1','skill':'melee','dice':3}]):
            raw = scenario_document(source())
            raw[NAME] = invalid
            with self.subTest(invalid=invalid),self.assertRaises(PcMeleeSimulationInputError):
                parse_scenario(raw,path_prefix='/scenario',error_type=PcMeleeSimulationInputError)

    def test_duplicate_unknown_pc_and_unsupported_book_actors_are_rejected(self):
        for choices in (
            [{'actor_id':'trooper1','skill':'melee'},{'actor_id':'trooper1','skill':'athletics'}],
            [{'actor_id':'missing','skill':'melee'}],
            [{'actor_id':'pc1','skill':'melee'}],
            [{'actor_id':'footpad1','skill':'athletics'}]):
            raw = request_document()
            raw['scenario'][NAME] = choices
            with self.subTest(choices=choices),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_full_template_cannot_hide_missing_or_invalid_policy_in_zero_count(self):
        for mutate in ('missing','unsupported'):
            raw = request_document(balance=True)
            raw['generation']['groups'][0]['maximum_count'] = 0
            if mutate=='missing':
                del raw['template'][NAME]
            else:
                raw['template'][NAME][0]['skill'] = 'stealth'
            with self.subTest(mutate=mutate),self.assertRaises(PcMeleeBalanceInputError):
                wire.parse_pc_melee_balance_request(json.dumps(raw))

    def test_subset_filters_actor_choices_without_reassignment_and_omits_empty_field(self):
        raw = request_document(balance=True)
        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
        choices = raw['template'][NAME]
        for counts,expected in (((0,0,0,0,1),None),((1,0,0,0,1),[choices[0]]),
                ((0,1,0,0,1),[choices[1]]),((1,1,0,0,1),choices[:2])):
            candidate = project_pc_melee_candidate(command.request,counts).scenario
            actual = scenario_document(candidate)
            if expected is not None:
                self.assertEqual(actual[NAME],expected)
            else:
                self.assertIsNone(candidate.npc_close_shooting_protection_policies)
                self.assertNotIn(NAME,actual)
            self.assertEqual(candidate.party[0].pc,command.request.template.party[0].pc)
            self.assertEqual(scenario_document(command.request.template),raw['template'])

    def test_native_cached_skill_alias_and_numeric_book_forgery_rejected_before_rng(self):
        class Alias(str,Enum):
            MELEE = 'melee'
        request = PcMeleeSimulationRequest(source(),42,1)
        for kind in ('alias','cap'):
            forged = deepcopy(request)
            if kind=='alias':
                object.__setattr__(forged.scenario.npc_close_shooting_protection_policies[0],'skill',Alias.MELEE)
            else:
                object.__setattr__(forged.scenario.enemies[0].definition.protection[0].test_profile,'pool_cap',6)
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                with self.subTest(kind=kind),self.assertRaises((ValueError,TypeError)):
                    run_pc_melee_trial(forged,0,rng_factory=rng)
                rng.assert_not_called()

    def test_actual_services_preserve_full_root_and_filtered_candidate_choices(self):
        for balance in (False,True):
            raw = request_document(balance=balance)
            if balance:
                command = wire.parse_pc_melee_balance_request(json.dumps(raw))
                result = execute_pc_melee_balance(command)
                encoded = json.loads(wire.encode_pc_melee_balance_result(command,result))
                validate_pc_melee_balance_document(encoded,'result')
                for row in encoded['candidates']:
                    choices = raw['template'][NAME]
                    expected = {(0,0):None,(1,0):[choices[0]],(0,1):[choices[1]],
                        (1,1):choices[:2]}[tuple(row['counts'][:2])]
                    scenario = row['request']['scenario']
                    if expected is not None:
                        self.assertEqual(scenario[NAME],expected)
                    else:
                        self.assertNotIn(NAME,scenario)
            else:
                command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
                result = execute_pc_melee_simulation(command)
                encoded = json.loads(wire.encode_pc_melee_simulation_result(command,result))
                validate_pc_melee_simulation_document(encoded,'result')
            self.assertEqual(encoded['request'],raw)


if __name__ == '__main__':
    unittest.main()
