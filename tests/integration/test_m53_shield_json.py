"""Current JSON1 shield source, strict preflight and actual service echoes."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from tests.support.pc_shield_scenarios import make_pc_shield_scenario
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import parse_scenario, scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError, PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document, validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_balance_models import project_pc_melee_candidate
from towr.application.pc_melee_service import execute_pc_melee_balance, execute_pc_melee_simulation
from towr.domain.pc_melee_models import PcWeaponHand
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


def shield_document(*, balance=False):
    raw = document(balance=balance)
    raw['template' if balance else 'scenario'] = scenario_document(
        make_pc_shield_scenario(enemy_count=2 if balance else 1))
    if balance:
        raw['evaluation'].update(trials_per_candidate=1, max_total_trials=2)
    else:
        raw['simulation']['trials'] = 2
    return raw


class ShieldJsonTests(unittest.TestCase):
    def test_both_request_families_roundtrip_full_source_and_absence_is_omitted(self):
        for balance in (False, True):
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            for shield in (False, True):
                raw = shield_document(balance=balance) if shield else document(balance=balance)
                command = parse(json.dumps(raw))
                source = command.request.template if balance else command.request.scenario
                self.assertEqual(scenario_document(source), raw[key])
                self.assertEqual('shield' in raw[key]['party'][0], shield)
                self.assertEqual(raw['schema_version'], '1')
                if shield:
                    self.assertEqual(raw[key]['party'][0]['shield'], {
                        'initial_hand': 'left', 'hand_conflict_policy': 'weapon_first',
                        'recovery_policy': 'restore_before_attack'})

    def test_required_closed_object_and_invalid_aliases_fail_before_rng(self):
        changes = [([], None), ([], False), ([], []), ([], 'shield'),
            (['initial_hand'], 'both'), (['initial_hand'], 'right'), (['initial_hand'], True),
            (['initial_hand'], None), (['hand_conflict_policy'], 'shield_first'),
            (['hand_conflict_policy'], True), (['recovery_policy'], 'restore_with_standard_recover'),
            (['recovery_policy'], None), (['unknown'], True)]
        for balance in (False, True):
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error = PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            base = shield_document(balance=balance)
            malformed = []
            for field in base[key]['party'][0]['shield']:
                raw = deepcopy(base)
                del raw[key]['party'][0]['shield'][field]
                malformed.append(raw)
            for path, value in changes:
                raw = deepcopy(base)
                if path:
                    raw[key]['party'][0]['shield'][path[0]] = value
                else:
                    raw[key]['party'][0]['shield'] = value
                malformed.append(raw)
            with patch('towr.engine.pc_melee_runner.run_pc_melee_scenario') as runner:
                for raw in malformed:
                    with self.subTest(balance=balance, shield=raw[key]['party'][0]['shield']), self.assertRaises(error):
                        parse(json.dumps(raw))
                runner.assert_not_called()

    def test_codec_rejects_partial_or_null_shield_even_without_schema_wrapper(self):
        base = shield_document()['scenario']
        for invalid in (None, {}, dict(base['party'][0]['shield'], extra=True)):
            raw = deepcopy(base)
            raw['party'][0]['shield'] = invalid
            with self.subTest(value=invalid), self.assertRaises(PcMeleeSimulationInputError):
                parse_scenario(raw, path_prefix='/scenario', error_type=PcMeleeSimulationInputError)

    def test_two_handed_backup_and_fake_shield_sources_are_rejected(self):
        for mutate in (
                lambda member: member.update(initial_weapon_hand='both'),
                lambda member: member['pc'].update(weapon='greataxe'),
                lambda member: member.update(backup_weapon_policy={'weapon': 'dagger', 'preferred_hand': 'left'}),
                lambda member: member.update(holds_shield=True),
                lambda member: member['shield'].update(armour_bonus=1)):
            raw = shield_document()
            mutate(raw['scenario']['party'][0])
            with self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_candidate_projection_preserves_shield_and_authored_armour(self):
        raw = shield_document(balance=True)
        raw['template']['party'][0]['pc']['armour_bonus'] = 2
        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
        for count in (1, 2):
            request = project_pc_melee_candidate(command.request, (count,))
            original = command.request.template.party[0]
            projected = request.scenario.party[0]
            selected = {enemy.state.actor_id for enemy in request.scenario.enemies}
            expected = replace(original,
                target_priority=tuple(actor for actor in original.target_priority if actor in selected),
                defeat_decisions=tuple(decision for decision in original.defeat_decisions if decision.target_id in selected))
            self.assertEqual(projected, expected)
            self.assertEqual(scenario_document(request.scenario)['party'][0]['shield'], raw['template']['party'][0]['shield'])
            self.assertEqual(projected.pc.armour_bonus, 2)

    def test_native_shield_forgery_is_rejected_before_rng_factory(self):
        request = PcMeleeSimulationRequest(make_pc_shield_scenario(), 42, 1)
        forged = deepcopy(request)
        object.__setattr__(forged.scenario.party[0].shield, 'initial_hand', PcWeaponHand.RIGHT)
        with patch('towr.simulation.pc_melee_simulation.Random') as rng:
            with self.assertRaises(ValueError):
                run_pc_melee_trial(forged, 0, rng_factory=rng)
            rng.assert_not_called()

    def test_actual_results_preserve_root_and_full_candidate_shield_echoes(self):
        for balance in (False, True):
            raw = shield_document(balance=balance)
            if balance:
                command = wire.parse_pc_melee_balance_request(json.dumps(raw))
                report = execute_pc_melee_balance(command)
                encoded = json.loads(wire.encode_pc_melee_balance_result(command, report))
                validate_pc_melee_balance_document(encoded, 'result')
                for row, candidate in zip(encoded['candidates'], report.candidates, strict=True):
                    self.assertEqual(row['request']['scenario'], scenario_document(candidate.source_request.scenario))
                    self.assertEqual(row['request']['scenario']['party'][0]['shield'], raw['template']['party'][0]['shield'])
                    self.assertEqual(row['request']['scenario']['party'][0]['pc'], raw['template']['party'][0]['pc'])
            else:
                command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
                result = execute_pc_melee_simulation(command)
                encoded = json.loads(wire.encode_pc_melee_simulation_result(command, result))
                validate_pc_melee_simulation_document(encoded, 'result')
            self.assertEqual(encoded['request'], raw)
