"""Current JSON1 Pistol+Shield admission and complete actual service echoes."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import json
import unittest
from unittest.mock import patch

from tests.support.pc_pistol_scenarios import make_pc_pistol_scenario
from tests.support.pc_shield_scenarios import shield_loadout
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import parse_scenario, scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError, PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document, validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_balance_models import project_pc_melee_candidate
from towr.application.pc_melee_service import execute_pc_melee_balance, execute_pc_melee_simulation
from towr.domain.pc_melee_models import (
    PcAllyRecoverPolicy, PcBackupWeaponPolicy, PcHelpPolicy, PcHelpTarget,
    PcMeleePolicy, PcMeleeWeapon, PcWeaponHand, validate_pc_melee_scenario_admission,
)
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


def pistol_shield_source(*, enemies=1, hand=PcWeaponHand.RIGHT):
    source = make_pc_pistol_scenario(enemy_count=enemies, max_rounds=5)
    opposite = PcWeaponHand.LEFT if hand is PcWeaponHand.RIGHT else PcWeaponHand.RIGHT
    member = replace(source.party[0], initial_weapon_hand=hand, shield=shield_loadout(opposite))
    return replace(source, party=(member,))


def pistol_shield_document(*, balance=False):
    raw = document(balance=balance)
    raw['template' if balance else 'scenario'] = scenario_document(
        pistol_shield_source(enemies=2 if balance else 1))
    if balance:
        raw['evaluation'].update(trials_per_candidate=1, max_total_trials=2)
    else:
        raw['simulation']['trials'] = 2
    return raw


class PistolShieldJsonTests(unittest.TestCase):
    def test_complete_typed_sources_allow_both_opposite_hand_pairs(self):
        for hand in (PcWeaponHand.LEFT, PcWeaponHand.RIGHT):
            source = pistol_shield_source(hand=hand)
            validate_pc_melee_scenario_admission(source)
            member = source.party[0]
            self.assertIs(member.pc.weapon, PcMeleeWeapon.PISTOL)
            self.assertIsNot(member.shield.initial_hand, member.initial_weapon_hand)
            self.assertEqual(member.pc.ranged.reload_hand_policy.value, 'two_available_hands')
            self.assertEqual(member.shield.recovery_policy.value, 'restore_before_attack')
            self.assertEqual(member.shield.hand_conflict_policy.value, 'weapon_first')

    def test_typed_combination_keeps_hand_role_and_nested_type_restrictions(self):
        class Alias(str, Enum):
            RIGHT = 'right'
        member = pistol_shield_source().party[0]
        changes = (
            {'initial_weapon_hand': member.shield.initial_hand},
            {'initial_weapon_hand': Alias.RIGHT},
            {'shield': {'initial_hand': 'left'}},
            {'pc': replace(member.pc,strength=1),
                'backup_weapon_policy': PcBackupWeaponPolicy(PcMeleeWeapon.DAGGER, PcWeaponHand.RIGHT)},
            {'policy': PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
                'help_policy': PcHelpPolicy('ally', PcHelpTarget.MELEE_ATTACK, None)},
            {'policy': PcMeleePolicy.RECOVER_ALLY_OR_ATTACK_OR_RECOVER_SELF,
                'ally_recover_policy': PcAllyRecoverPolicy('ally')},
        )
        for change in changes:
            with self.subTest(change=change), self.assertRaises((TypeError, ValueError)):
                replace(member, **change)
        with self.assertRaises(TypeError):
            replace(member, pc=replace(member.pc, ranged=None))

    def test_full_requests_roundtrip_without_new_wire_fields_or_default_shield(self):
        for balance in (False, True):
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            for shield in (False, True):
                raw = pistol_shield_document(balance=balance)
                if not shield:
                    del raw[key]['party'][0]['shield']
                command = parse(json.dumps(raw))
                source = command.request.template if balance else command.request.scenario
                self.assertEqual(scenario_document(source), raw[key])
                self.assertEqual('shield' in scenario_document(source)['party'][0], shield)
                self.assertEqual(raw['schema_version'], '1')
                self.assertEqual(source.party[0].pc.ranged, pistol_shield_source().party[0].pc.ranged)

    def test_closed_combined_source_rejects_invalid_hand_policy_and_profile_before_rng(self):
        def overcarry_backup(member):
            member['pc']['strength'] = 1
            member['backup_weapon_policy'] = {'weapon': 'dagger', 'preferred_hand': 'right'}
        changes = (
            lambda member: member.update(initial_weapon_hand='left'),
            lambda member: member.update(shield=None),
            lambda member: member['shield'].pop('initial_hand'),
            lambda member: member['shield'].update(recovery_policy='leave_dropped'),
            lambda member: member['shield'].update(reload_priority=True),
            lambda member: member['pc']['ranged'].update(reload_hand_policy='weapon_hand_only'),
            lambda member: member['pc']['ranged'].pop('has_blackpowder_kit'),
            lambda member: member['pc']['ranged'].update(initially_loaded=False),
            overcarry_backup,
        )
        for balance in (False, True):
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error = PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                for mutate in changes:
                    raw = pistol_shield_document(balance=balance)
                    mutate(raw[key]['party'][0])
                    with self.subTest(balance=balance, member=raw[key]['party'][0]), self.assertRaises(error):
                        parse(json.dumps(raw))
                rng.assert_not_called()

    def test_codec_without_schema_keeps_complete_shield_and_pistol_admission(self):
        base = pistol_shield_document()['scenario']
        for field, value in (('shield', None), ('shield', {}), ('ranged', None), ('ranged', {})):
            raw = deepcopy(base)
            if field == 'shield':
                raw['party'][0][field] = value
            else:
                raw['party'][0]['pc'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(PcMeleeSimulationInputError):
                parse_scenario(raw, path_prefix='/scenario', error_type=PcMeleeSimulationInputError)

    def test_native_forged_hand_and_lore_are_readmitted_before_rng(self):
        request = PcMeleeSimulationRequest(pistol_shield_source(), 42, 1)
        for field in ('shield_hand', 'kit'):
            forged = deepcopy(request)
            member = forged.scenario.party[0]
            if field == 'shield_hand':
                object.__setattr__(member.shield, 'initial_hand', member.initial_weapon_hand)
            else:
                object.__setattr__(member.pc.ranged, 'has_blackpowder_kit', False)
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                with self.subTest(field=field), self.assertRaises((TypeError, ValueError)):
                    run_pc_melee_trial(forged, 0, rng_factory=rng)
                rng.assert_not_called()

    def test_shield_does_not_relax_full_template_enemy_shooting_protection(self):
        raw = pistol_shield_document(balance=True)
        enemy = raw['template']['enemies'][1]
        enemy['definition']['protection']['skill'] = 'defence'
        raw['generation']['groups'] = [
            {'group_id': 'legal', 'actor_ids': ['minion1'], 'minimum_count': 1, 'maximum_count': 1},
            {'group_id': 'excluded', 'actor_ids': ['minion2'], 'minimum_count': 0, 'maximum_count': 0},
        ]
        with patch('towr.simulation.pc_melee_simulation.Random') as rng:
            with self.assertRaises(PcMeleeBalanceInputError):
                wire.parse_pc_melee_balance_request(json.dumps(raw))
            rng.assert_not_called()

    def test_candidate_projection_preserves_both_equipment_sources_and_armour(self):
        raw = pistol_shield_document(balance=True)
        raw['template']['party'][0]['pc']['armour_bonus'] = 2
        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
        for count in (1, 2):
            source = project_pc_melee_candidate(command.request, (count,)).scenario
            member = source.party[0]
            self.assertEqual(member.pc, command.request.template.party[0].pc)
            self.assertEqual(member.shield, command.request.template.party[0].shield)
            self.assertEqual(member.pc.armour_bonus, 2)
            self.assertEqual(scenario_document(source)['party'][0]['shield'], raw['template']['party'][0]['shield'])
        self.assertEqual(scenario_document(command.request.template), raw['template'])

    def test_actual_services_keep_full_root_and_candidate_equipment_echoes(self):
        for balance in (False, True):
            raw = pistol_shield_document(balance=balance)
            if balance:
                command = wire.parse_pc_melee_balance_request(json.dumps(raw))
                report = execute_pc_melee_balance(command)
                encoded = json.loads(wire.encode_pc_melee_balance_result(command, report))
                validate_pc_melee_balance_document(encoded, 'result')
                for row, candidate in zip(encoded['candidates'], report.candidates, strict=True):
                    self.assertEqual(row['request']['scenario'], scenario_document(candidate.source_request.scenario))
                    member = row['request']['scenario']['party'][0]
                    self.assertEqual(member['pc'], raw['template']['party'][0]['pc'])
                    self.assertEqual(member['shield'], raw['template']['party'][0]['shield'])
            else:
                command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
                result = execute_pc_melee_simulation(command)
                encoded = json.loads(wire.encode_pc_melee_simulation_result(command, result))
                validate_pc_melee_simulation_document(encoded, 'result')
            self.assertEqual(encoded['request'], raw)
