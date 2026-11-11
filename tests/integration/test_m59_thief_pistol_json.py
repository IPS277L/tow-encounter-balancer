"""Canonical Thief Stealth crosses the existing Pistol JSON/service boundary."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_pistol_scenarios import pistol_profile
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError, PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document, validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_balance_models import project_pc_melee_candidate
from towr.application.pc_melee_service import execute_pc_melee_balance, execute_pc_melee_simulation
from towr.domain.pc_melee_models import PcMeleeWeapon


def request_document(*, balance=False):
    source = book_pc_scenario(footpads=1,townsfolk=0,thieves=2,pc_count=1,max_rounds=4)
    source = replace(source,party=tuple(replace(member,pc=replace(member.pc,
        weapon=PcMeleeWeapon.PISTOL,ranged=pistol_profile())) for member in source.party))
    raw = document(balance=balance)
    raw['template' if balance else 'scenario'] = scenario_document(source)
    if balance:
        raw['generation'].update(groups=[
            {'group_id':'thieves','actor_ids':['thief1','thief2'],'minimum_count':0,'maximum_count':2},
            {'group_id':'footpads','actor_ids':['footpad1'],'minimum_count':1,'maximum_count':1}],
            facts=deepcopy(raw['template']['facts']),max_candidates=3)
        raw['evaluation'].update(trials_per_candidate=1,max_total_trials=3)
    else:
        raw['simulation']['trials'] = 2
    return raw


class ThiefPistolJsonTests(unittest.TestCase):
    def test_current_sources_roundtrip_without_new_policy_or_wire_fields(self):
        for balance in (False,True):
            raw = request_document(balance=balance)
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command = parse(json.dumps(raw))
            source = command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw[key])
            self.assertNotIn('npc_close_shooting_protection_policies',raw[key])
            self.assertEqual(raw['schema_version'],'1')
            self.assertEqual(source.enemy('thief1').definition.protection[0].test_profile.threshold,5)

    def test_forged_excluded_thief_cannot_bypass_complete_template_preflight(self):
        for kind in ('numeric','renamed','explicit_override'):
            raw = request_document(balance=True)
            raw['generation']['groups'][0]['maximum_count'] = 0
            enemy = next(enemy for enemy in raw['template']['enemies'] if enemy['actor_id']=='thief2')
            if kind=='numeric':
                enemy['definition']['protection']['test_profile']['threshold'] = 4
            elif kind=='renamed':
                enemy['definition']['id'] = 'authored:thief'
                enemy['definition']['source_rule_id'] = 'authored:thief'
            else:
                raw['template']['npc_close_shooting_protection_policies'] = [
                    {'actor_id':'thief2','skill':'stealth'}]
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                with self.subTest(kind=kind),self.assertRaises(PcMeleeBalanceInputError):
                    wire.parse_pc_melee_balance_request(json.dumps(raw))
                rng.assert_not_called()
        raw = request_document()
        raw['scenario']['enemies'][0]['definition']['protection']['test_profile']['pool_cap'] = 8
        with self.assertRaises(PcMeleeSimulationInputError):
            wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_subsets_preserve_full_thief_source_and_ordinary_non_thief_source(self):
        raw = request_document(balance=True)
        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
        for count in (0,1,2):
            candidate = project_pc_melee_candidate(command.request,(count,1)).scenario
            self.assertEqual(tuple(actor for actor in candidate.enemy_activation_order if actor.startswith('thief')),
                ('thief1','thief2')[:count])
            for actor in ('thief1','thief2')[:count]:
                self.assertEqual(candidate.enemy(actor),command.request.template.enemy(actor))
            self.assertNotIn('npc_close_shooting_protection_policies',scenario_document(candidate))
            self.assertEqual(candidate.enemy('footpad1'),command.request.template.enemy('footpad1'))
        self.assertEqual(scenario_document(command.request.template),raw['template'])

    def test_actual_services_preserve_root_and_full_candidate_sources(self):
        for balance in (False,True):
            raw = request_document(balance=balance)
            if balance:
                command = wire.parse_pc_melee_balance_request(json.dumps(raw))
                result = execute_pc_melee_balance(command)
                encoded = json.loads(wire.encode_pc_melee_balance_result(command,result))
                validate_pc_melee_balance_document(encoded,'result')
                for row in encoded['candidates']:
                    expected = project_pc_melee_candidate(command.request,tuple(row['counts'])).scenario
                    self.assertEqual(row['request']['scenario'],scenario_document(expected))
            else:
                command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
                result = execute_pc_melee_simulation(command)
                encoded = json.loads(wire.encode_pc_melee_simulation_result(command,result))
                validate_pc_melee_simulation_document(encoded,'result')
            self.assertEqual(encoded['request'],raw)


if __name__ == '__main__':
    unittest.main()
