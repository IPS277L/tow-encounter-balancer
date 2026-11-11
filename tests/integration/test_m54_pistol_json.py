"""Current JSON1 complete Pistol sources, admission and actual service echoes."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from tests.support.pc_pistol_scenarios import make_pc_pistol_scenario
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import parse_scenario, scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError, PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document, validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_balance_models import project_pc_melee_candidate
from towr.application.pc_melee_service import execute_pc_melee_balance, execute_pc_melee_simulation
from towr.domain.pc_melee_models import PcFatePolicy, PcGloriousPolicy
from towr.domain.test_models import Skill


def pistol_document(*, balance=False):
    raw = document(balance=balance)
    raw['template' if balance else 'scenario'] = scenario_document(
        make_pc_pistol_scenario(enemy_count=2 if balance else 1, max_rounds=4))
    if balance:
        raw['evaluation'].update(trials_per_candidate=1, max_total_trials=2)
    else:
        raw['simulation']['trials'] = 2
    return raw


class PistolJsonTests(unittest.TestCase):
    def test_both_request_families_roundtrip_full_profile_and_old_absence(self):
        for balance in (False, True):
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            for pistol in (False, True):
                raw = pistol_document(balance=balance) if pistol else document(balance=balance)
                command = parse(json.dumps(raw))
                source = command.request.template if balance else command.request.scenario
                self.assertEqual(scenario_document(source), raw[key])
                self.assertEqual('ranged' in raw[key]['party'][0]['pc'], pistol)
                self.assertEqual(raw['schema_version'], '1')
                if pistol:
                    self.assertEqual(raw[key]['party'][0]['pc']['weapon'], 'pistol')
                    self.assertEqual(raw[key]['party'][0]['pc']['ranged'], {
                        'ballistic_skill': 3, 'shooting': 4, 'initiative': 3, 'dexterity': 4,
                        'has_blackpowder_lore': True, 'has_blackpowder_kit': True,
                        'ammunition_supply_confirmed': True, 'initially_loaded': True,
                        'reload_hand_policy': 'two_available_hands'})

    def test_closed_required_profile_and_exact_scalars_are_rejected_before_runner(self):
        changes = [(None, value) for value in (None, False, [], 'pistol', {})]
        for field in ('ballistic_skill', 'shooting', 'initiative', 'dexterity'):
            changes.extend((field, value) for value in (None, True, '3', 0))
        changes.extend((field, 11) for field in ('shooting', 'dexterity'))
        for field in ('has_blackpowder_lore', 'has_blackpowder_kit',
                'ammunition_supply_confirmed', 'initially_loaded'):
            changes.extend((field, value) for value in (False, None, 1, 'true'))
        changes.extend((('reload_hand_policy', 'weapon_hand_only'), ('reload_hand_policy', None),
            ('damage', 5), ('rapid_reload', True)))
        for balance in (False, True):
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error = PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            base = pistol_document(balance=balance)
            malformed = []
            for field in base[key]['party'][0]['pc']['ranged']:
                raw = deepcopy(base)
                del raw[key]['party'][0]['pc']['ranged'][field]
                malformed.append(raw)
            for field, value in changes:
                raw = deepcopy(base)
                if field is None:
                    raw[key]['party'][0]['pc']['ranged'] = value
                else:
                    raw[key]['party'][0]['pc']['ranged'][field] = value
                malformed.append(raw)
            with patch('towr.engine.pc_melee_runner.run_pc_melee_scenario') as runner:
                for raw in malformed:
                    with self.subTest(balance=balance, profile=raw[key]['party'][0]['pc']['ranged']), self.assertRaises(error):
                        parse(json.dumps(raw))
                runner.assert_not_called()

    def test_codec_alone_requires_complete_profile_and_actual_pistol_weapon(self):
        base = pistol_document()['scenario']
        malformed = []
        for value in (None, {}, dict(base['party'][0]['pc']['ranged'], extra=True)):
            raw = deepcopy(base)
            raw['party'][0]['pc']['ranged'] = value
            malformed.append(raw)
        raw = deepcopy(base)
        del raw['party'][0]['pc']['ranged']
        malformed.append(raw)
        raw = deepcopy(base)
        raw['party'][0]['pc']['weapon'] = 'sword'
        malformed.append(raw)
        for raw in malformed:
            with self.subTest(pc=raw['party'][0]['pc']), self.assertRaises(PcMeleeSimulationInputError):
                parse_scenario(raw, path_prefix='/scenario', error_type=PcMeleeSimulationInputError)

    def test_pistol_same_hand_shield_overcarry_backup_help_and_old_pc_pistol_backup_rejected(self):
        def help_policy(member):
            member.update(policy='help_ally_or_attack_or_recover_self',
                help_policy={'beneficiary_id': 'ally', 'target': 'melee_attack', 'protection_skill': None})
        def ally_policy(member):
            member.update(policy='recover_ally_or_attack_or_recover_self',
                ally_recover_policy={'beneficiary_id': 'ally'})
        def overcarry_backup(member):
            member['pc']['strength'] = 1
            member['backup_weapon_policy'] = {'weapon': 'sword', 'preferred_hand': 'right'}
        for mutate in (lambda m: m.update(initial_weapon_hand='both'),
                lambda m: m.update(shield={'initial_hand': 'left', 'hand_conflict_policy': 'weapon_first',
                    'recovery_policy': 'restore_before_attack'}),
                overcarry_backup,
                help_policy, ally_policy):
            raw = pistol_document()
            mutate(raw['scenario']['party'][0])
            with self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))
        raw = document()
        raw['scenario']['party'][0]['pc']['weapon'] = 'greataxe'
        raw['scenario']['party'][0].update(initial_weapon_hand='both',
            backup_weapon_policy={'weapon': 'pistol', 'preferred_hand': 'right'})
        with self.assertRaises(PcMeleeSimulationInputError):
            wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_illegal_protection_rejected_for_entire_template_even_excluded_reserve(self):
        for balance in (False, True):
            raw = pistol_document(balance=balance)
            key = 'template' if balance else 'scenario'
            enemy = raw[key]['enemies'][-1]
            enemy['definition']['id'] = 'authored:unshielded'
            enemy['definition']['protection']['skill'] = 'defence'
            if balance:
                raw['generation']['groups'] = [
                    {'group_id': 'legal', 'actor_ids': ['minion1'], 'minimum_count': 1, 'maximum_count': 1},
                    {'group_id': 'excluded', 'actor_ids': ['minion2'], 'minimum_count': 0, 'maximum_count': 0}]
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error = PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                with self.assertRaises(error):
                    parse(json.dumps(raw))
                rng.assert_not_called()

    def test_shooting_and_dexterity_glorious_roundtrip_and_candidate_source(self):
        raw = pistol_document(balance=True)
        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
        original = command.request.template.party[0]
        member = replace(original, fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.SHOOTING, Skill.DEXTERITY), 1, 0))
        template = replace(command.request.template, party=(member,))
        raw['template'] = scenario_document(template)
        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
        for count in (1, 2):
            request = project_pc_melee_candidate(command.request, (count,))
            self.assertEqual(request.scenario.party[0].pc, original.pc)
            self.assertEqual(scenario_document(request.scenario)['party'][0]['pc'], raw['template']['party'][0]['pc'])
            self.assertEqual(request.scenario.party[0].glorious_policy, member.glorious_policy)

    def test_actual_services_preserve_root_and_full_candidate_pistol_echoes(self):
        for balance in (False, True):
            raw = pistol_document(balance=balance)
            if balance:
                command = wire.parse_pc_melee_balance_request(json.dumps(raw))
                report = execute_pc_melee_balance(command)
                encoded = json.loads(wire.encode_pc_melee_balance_result(command, report))
                validate_pc_melee_balance_document(encoded, 'result')
                for row, candidate in zip(encoded['candidates'], report.candidates, strict=True):
                    self.assertEqual(row['request']['scenario'], scenario_document(candidate.source_request.scenario))
                    self.assertEqual(row['request']['scenario']['party'][0]['pc'], raw['template']['party'][0]['pc'])
            else:
                command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
                result = execute_pc_melee_simulation(command)
                encoded = json.loads(wire.encode_pc_melee_simulation_result(command, result))
                validate_pc_melee_simulation_document(encoded, 'result')
            self.assertEqual(encoded['request'], raw)
