"""Pistol/melee backup admits full carried sources without a new wire format."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import json
import unittest
from unittest.mock import patch

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
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


BACKUPS = (PcMeleeWeapon.DAGGER,PcMeleeWeapon.STAFF,PcMeleeWeapon.AXE,
    PcMeleeWeapon.SWORD,PcMeleeWeapon.WARHAMMER,PcMeleeWeapon.MORNING_STAR)


def backup_source(*, weapon=PcMeleeWeapon.SWORD, shield=False,
        hand=PcWeaponHand.RIGHT, enemies=1):
    source = make_pc_pistol_scenario(enemy_count=enemies,max_rounds=3)
    opposite = PcWeaponHand.LEFT if hand is PcWeaponHand.RIGHT else PcWeaponHand.RIGHT
    member = replace(source.party[0],pc=replace(source.party[0].pc,strength=2),
        initial_weapon_hand=hand,backup_weapon_policy=PcBackupWeaponPolicy(weapon,hand),
        shield=shield_loadout(opposite) if shield else None)
    return replace(source,party=(member,))


def request_document(*, balance=False, weapon=PcMeleeWeapon.SWORD, shield=True):
    raw = document(balance=balance)
    raw['template' if balance else 'scenario'] = scenario_document(backup_source(
        weapon=weapon,shield=shield,enemies=2 if balance else 1))
    if balance:
        raw['evaluation'].update(trials_per_candidate=1,max_total_trials=2)
    else:
        raw['simulation']['trials'] = 2
    return raw


class PistolBackupJsonTests(unittest.TestCase):
    def test_six_melee_backups_with_optional_shield_and_both_initial_hands(self):
        for weapon in BACKUPS:
            for shield in (False,True):
                for hand in (PcWeaponHand.LEFT,PcWeaponHand.RIGHT):
                    with self.subTest(weapon=weapon,shield=shield,hand=hand):
                        source = backup_source(weapon=weapon,shield=shield,hand=hand)
                        validate_pc_melee_scenario_admission(source)
                        member = source.party[0]
                        self.assertEqual(member.pc.strength,2)
                        self.assertEqual(member.backup_weapon_policy,PcBackupWeaponPolicy(weapon,hand))
                        self.assertEqual(member.shield is not None,shield)
                        self.assertTrue(member.pc.ranged.initially_loaded)

    def test_typed_source_keeps_carry_primary_role_and_hand_restrictions(self):
        class Alias(str,Enum):
            RIGHT = 'right'
        member = backup_source(shield=True).party[0]
        changes = (
            {'pc':replace(member.pc,strength=1)},
            {'initial_weapon_hand':member.shield.initial_hand},
            {'backup_weapon_policy':{'weapon':'sword','preferred_hand':'right'}},
            {'policy':PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
                'help_policy':PcHelpPolicy('ally',PcHelpTarget.MELEE_ATTACK,None)},
            {'policy':PcMeleePolicy.RECOVER_ALLY_OR_ATTACK_OR_RECOVER_SELF,
                'ally_recover_policy':PcAllyRecoverPolicy('ally')},
        )
        for change in changes:
            with self.subTest(change=change),self.assertRaises((TypeError,ValueError)):
                replace(member,**change)
        with self.assertRaises(TypeError):
            PcBackupWeaponPolicy(PcMeleeWeapon.SWORD,Alias.RIGHT)
        for weapon in (PcMeleeWeapon.PISTOL,PcMeleeWeapon.GREATAXE):
            with self.subTest(weapon=weapon),self.assertRaises(ValueError):
                PcBackupWeaponPolicy(weapon,PcWeaponHand.RIGHT)
        melee = make_pc_melee_scenario(weapon=PcMeleeWeapon.SWORD).party[0]
        with self.assertRaises(ValueError):
            replace(melee,backup_weapon_policy=member.backup_weapon_policy)
        with self.assertRaises(ValueError):
            replace(melee,shield=shield_loadout(PcWeaponHand.RIGHT),
                backup_weapon_policy=member.backup_weapon_policy)

    def test_old_two_handed_backup_and_null_pistol_source_remain_admitted(self):
        old = make_pc_melee_scenario(weapon=PcMeleeWeapon.PICKAXE)
        old = replace(old,party=(replace(old.party[0],backup_weapon_policy=
            PcBackupWeaponPolicy(PcMeleeWeapon.SWORD,PcWeaponHand.LEFT)),))
        validate_pc_melee_scenario_admission(old)
        plain = make_pc_pistol_scenario()
        validate_pc_melee_scenario_admission(plain)
        self.assertIsNone(plain.party[0].backup_weapon_policy)
        with self.assertRaises(ValueError):
            replace(old.party[0],shield=shield_loadout())

    def test_current_json_roundtrips_all_backups_without_new_fields(self):
        for balance in (False,True):
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            for weapon in BACKUPS:
                for shield in (False,True):
                    raw = request_document(balance=balance,weapon=weapon,shield=shield)
                    command = parse(json.dumps(raw))
                    source = command.request.template if balance else command.request.scenario
                    self.assertEqual(scenario_document(source),raw[key])
                    self.assertEqual(raw['schema_version'],'1')
                    self.assertEqual(set(raw[key]['party'][0]['backup_weapon_policy']),{'weapon','preferred_hand'})

    def test_json_malformed_policy_carry_and_pistol_preconditions_fail_before_rng(self):
        mutations = (
            lambda member: member.update(backup_weapon_policy={}),
            lambda member: member['backup_weapon_policy'].update(weapon='pistol'),
            lambda member: member['backup_weapon_policy'].update(weapon='pickaxe'),
            lambda member: member['backup_weapon_policy'].update(preferred_hand='both'),
            lambda member: member['backup_weapon_policy'].update(trigger='after_first_shot'),
            lambda member: member['pc'].update(strength=1),
            lambda member: member['pc'].update(strength=True),
            lambda member: member.update(initial_weapon_hand='both'),
            lambda member: member['pc']['ranged'].update(has_blackpowder_kit=False),
            lambda member: member['pc']['ranged'].update(has_blackpowder_lore=False),
            lambda member: member['pc']['ranged'].update(initially_loaded=False),
        )
        for balance in (False,True):
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error = PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                for mutate in mutations:
                    raw = request_document(balance=balance)
                    mutate(raw[key]['party'][0])
                    with self.subTest(balance=balance,member=raw[key]['party'][0]),self.assertRaises(error):
                        parse(json.dumps(raw))
                raw = request_document(balance=balance)
                del raw[key]['party'][0]['backup_weapon_policy']
                with self.assertRaises(error):
                    parse(json.dumps(raw))
                rng.assert_not_called()

    def test_codec_without_schema_preserves_complete_closed_policy(self):
        for policy in ({},{'weapon':'sword'},
                {'weapon':'sword','preferred_hand':'right','trigger':'always'}):
            raw = request_document()['scenario']
            raw['party'][0]['backup_weapon_policy'] = policy
            with self.subTest(policy=policy),self.assertRaises(PcMeleeSimulationInputError):
                parse_scenario(raw,path_prefix='/scenario',error_type=PcMeleeSimulationInputError)

    def test_native_nested_policy_and_carry_forgery_are_rejected_before_rng(self):
        class Alias(str,Enum):
            SWORD = 'sword'
        request = PcMeleeSimulationRequest(backup_source(shield=True),42,1)
        for kind in ('carry','policy','lore'):
            forged = deepcopy(request)
            member = forged.scenario.party[0]
            if kind=='carry':
                object.__setattr__(member.pc,'strength',1)
            elif kind=='policy':
                object.__setattr__(member.backup_weapon_policy,'weapon',Alias.SWORD)
            else:
                object.__setattr__(member.pc.ranged,'has_blackpowder_lore',False)
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                with self.subTest(kind=kind),self.assertRaises((TypeError,ValueError)):
                    run_pc_melee_trial(forged,0,rng_factory=rng)
                rng.assert_not_called()

    def test_candidates_keep_full_party_backup_shield_and_pistol_source(self):
        raw = request_document(balance=True)
        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
        for count in (1,2):
            candidate = project_pc_melee_candidate(command.request,(count,)).scenario
            member,original = candidate.party[0],command.request.template.party[0]
            self.assertEqual((member.pc,member.backup_weapon_policy,member.shield,member.initial_weapon_hand),
                (original.pc,original.backup_weapon_policy,original.shield,original.initial_weapon_hand))
            echoed = scenario_document(candidate)['party'][0]
            for name in ('pc','backup_weapon_policy','shield','initial_weapon_hand'):
                self.assertEqual(echoed[name],raw['template']['party'][0][name])
        self.assertEqual(scenario_document(command.request.template),raw['template'])

    def test_actual_services_preserve_full_root_and_candidate_equipment_echoes(self):
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
