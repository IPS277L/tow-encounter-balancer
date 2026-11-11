"""One weapon-specific ranged source crosses current JSON, trials and search."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import json
import unittest
from unittest.mock import patch

from tests.support.pc_ranged_scenarios import make_pc_ranged_scenario, ranged_profile
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
    PC_RANGED_WEAPONS, PcBackupWeaponPolicy, PcHelpPolicy, PcHelpTarget, PcMeleePolicy,
    PcMeleeWeapon, PcRangedProfile, PcRangedReloadHandPolicy, PcRepeaterBonusPolicy,
    PcWeaponHand,
)
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc
from towr.domain.pc_npc_pistol_source_models import PcNpcPistolPolicy, PcNpcPistolReloadHandPolicy
from towr.domain.pc_npc_close_shooting_models import PcNpcCloseShootingProtectionPolicy
from towr.domain.test_models import Skill
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


MODES = (PcRepeaterBonusPolicy.WHEN_AVAILABLE, PcRepeaterBonusPolicy.NEVER)


def source(*, weapon=PcMeleeWeapon.REPEATER_HANDBOW,
        mode=PcRepeaterBonusPolicy.WHEN_AVAILABLE, shield=False, backup=False,
        hand=PcWeaponHand.RIGHT, enemies=1):
    scene = make_pc_ranged_scenario(weapon=weapon, repeater_bonus_policy=mode,
        enemy_count=enemies, max_rounds=4)
    member = replace(scene.party[0], initial_weapon_hand=hand,
        shield=shield_loadout(PcWeaponHand.LEFT if hand is PcWeaponHand.RIGHT else PcWeaponHand.RIGHT)
            if shield else None,
        backup_weapon_policy=PcBackupWeaponPolicy(PcMeleeWeapon.SWORD, hand) if backup else None,
        close_shooting_protection_skill=Skill.MELEE)
    return replace(scene, party=(member,))


def request_document(*, balance=False, weapon=PcMeleeWeapon.REPEATER_HANDBOW,
        mode=PcRepeaterBonusPolicy.WHEN_AVAILABLE):
    raw = document(balance=balance)
    raw['template' if balance else 'scenario'] = scenario_document(source(weapon=weapon,
        mode=mode, shield=True, backup=True, enemies=2 if balance else 1))
    if balance:
        raw['evaluation'].update(trials_per_candidate=1, max_total_trials=2)
        raw['generation']['facts'] = deepcopy(raw['template']['facts'])
    else:
        raw['simulation']['trials'] = 2
    return raw


class PcRangedJsonTests(unittest.TestCase):
    def test_three_weapons_modes_shield_backup_and_both_hands_roundtrip(self):
        for weapon in (PcMeleeWeapon.PISTOL,PcMeleeWeapon.REPEATER_HANDBOW,PcMeleeWeapon.REPEATER_PISTOL):
            for mode in (None,) if weapon is PcMeleeWeapon.PISTOL else MODES:
                for shield in (False, True):
                    for backup in (False, True):
                        for hand in (PcWeaponHand.LEFT, PcWeaponHand.RIGHT):
                            with self.subTest(weapon=weapon, mode=mode, shield=shield, backup=backup, hand=hand):
                                scene = source(weapon=weapon, mode=mode, shield=shield, backup=backup, hand=hand)
                                raw = document()
                                raw['scenario'] = scenario_document(scene)
                                command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
                                self.assertEqual(command.request.scenario, scene)
                                self.assertEqual(scenario_document(command.request.scenario), raw['scenario'])
                                pc = raw['scenario']['party'][0]['pc']
                                self.assertNotIn('pistol', pc)
                                self.assertEqual('has_blackpowder_lore' in pc['ranged'],
                                    weapon is not PcMeleeWeapon.REPEATER_HANDBOW)
                                self.assertEqual('repeater_bonus_policy' in pc['ranged'],
                                    weapon is not PcMeleeWeapon.PISTOL)

    def test_generic_native_profile_keeps_explicit_facts_and_final_weapon_validation(self):
        class Alias(str, Enum):
            NEVER = 'never'
        profile = ranged_profile()
        self.assertIsNone(profile.has_blackpowder_lore)
        self.assertIsNone(profile.has_blackpowder_kit)
        with self.assertRaises(ValueError):
            PcRangedProfile(3,4,3,4)
        for changes in ({'repeater_bonus_policy':'never'}, {'repeater_bonus_policy':Alias.NEVER},
                {'reload_hand_policy':'two_available_hands'}, {'shooting':True},
                {'ammunition_supply_confirmed':False}, {'initially_loaded':False}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(profile, **changes)
        pc = source().party[0].pc
        for weapon, changed in ((PcMeleeWeapon.REPEATER_HANDBOW, replace(profile, has_blackpowder_lore=True)),
                (PcMeleeWeapon.REPEATER_HANDBOW, replace(profile, has_blackpowder_kit=True)),
                (PcMeleeWeapon.REPEATER_HANDBOW, replace(profile, repeater_bonus_policy=None)),
                (PcMeleeWeapon.REPEATER_PISTOL, profile), (PcMeleeWeapon.PISTOL, profile),
                (PcMeleeWeapon.SWORD, profile)):
            with self.subTest(weapon=weapon, changed=changed), self.assertRaises((TypeError, ValueError)):
                replace(pc, weapon=weapon, ranged=changed)
        pistol = ranged_profile(weapon=PcMeleeWeapon.PISTOL, repeater_bonus_policy=None)
        with self.assertRaises(ValueError):
            replace(pc, weapon=PcMeleeWeapon.PISTOL,
                ranged=replace(pistol, repeater_bonus_policy=PcRepeaterBonusPolicy.NEVER))
        self.assertIs(PcRangedProfile(3,4,3,4,True,True,True,True,
            PcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS).reload_hand_policy,
            PcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS)

    def test_conditional_json_fields_and_retired_pc_key_fail_before_rng(self):
        mutations = (
            lambda pc: pc.update(pistol=deepcopy(pc['ranged'])),
            lambda pc: pc.pop('ranged'),
            lambda pc: pc['ranged'].pop('repeater_bonus_policy'),
            lambda pc: pc['ranged'].update(repeater_bonus_policy=None),
            lambda pc: pc['ranged'].update(repeater_bonus_policy='automatic'),
            lambda pc: pc['ranged'].update(has_blackpowder_lore=True),
            lambda pc: pc['ranged'].update(has_blackpowder_kit=None),
            lambda pc: pc['ranged'].update(has_engineering_lore=True),
            lambda pc: pc['ranged'].update(ammunition_supply_confirmed=False),
            lambda pc: pc['ranged'].update(initially_loaded=1),
            lambda pc: pc['ranged'].update(dexterity=True),
            lambda pc: pc['ranged'].update(reload_hand_policy='one_hand'),
            lambda pc: pc.update(weapon='sword'),
        )
        for balance in (False, True):
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error = PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                for mutate in mutations:
                    raw = request_document(balance=balance)
                    mutate(raw[key]['party'][0]['pc'])
                    with self.subTest(balance=balance, mutate=mutate), self.assertRaises(error):
                        parse(json.dumps(raw))
                for weapon in (PcMeleeWeapon.PISTOL, PcMeleeWeapon.REPEATER_PISTOL):
                    raw = request_document(balance=balance, weapon=weapon,
                        mode=None if weapon is PcMeleeWeapon.PISTOL else PcRepeaterBonusPolicy.NEVER)
                    del raw[key]['party'][0]['pc']['ranged']['has_blackpowder_kit']
                    with self.subTest(balance=balance, weapon=weapon), self.assertRaises(error):
                        parse(json.dumps(raw))
                rng.assert_not_called()
        raw = request_document()['scenario']
        pc = raw['party'][0]['pc']
        pc['pistol'] = pc.pop('ranged')
        with self.assertRaises(PcMeleeSimulationInputError):
            parse_scenario(raw, path_prefix='/scenario', error_type=PcMeleeSimulationInputError)
        for name, value in (('has_blackpowder_lore', None), ('repeater_bonus_policy', None)):
            raw = request_document()['scenario']
            raw['party'][0]['pc']['ranged'][name] = value
            with self.subTest(name=name), self.assertRaises(PcMeleeSimulationInputError):
                parse_scenario(raw, path_prefix='/scenario', error_type=PcMeleeSimulationInputError)

    def test_roles_carry_backup_and_opposite_hand_guards_apply_to_both_repeaters(self):
        for weapon in (PcMeleeWeapon.REPEATER_HANDBOW, PcMeleeWeapon.REPEATER_PISTOL):
            member = source(weapon=weapon, shield=True, backup=True).party[0]
            for changes in ({'pc':replace(member.pc, strength=1)},
                    {'initial_weapon_hand':member.shield.initial_hand},
                    {'policy':PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
                        'help_policy':PcHelpPolicy('ally', PcHelpTarget.MELEE_ATTACK, None)}):
                with self.subTest(weapon=weapon, changes=changes), self.assertRaises(ValueError):
                    replace(member, **changes)
            with self.assertRaises(ValueError):
                PcBackupWeaponPolicy(weapon, PcWeaponHand.RIGHT)

    def test_cached_bonus_and_weapon_fact_forgeries_fail_before_trial_rng(self):
        class Alias(str, Enum):
            NEVER = 'never'
        request = PcMeleeSimulationRequest(source(), 42, 1)
        for name, value in (('repeater_bonus_policy', 'never'), ('repeater_bonus_policy', Alias.NEVER),
                ('has_blackpowder_lore', True), ('ammunition_supply_confirmed', 1)):
            forged = deepcopy(request)
            object.__setattr__(forged.scenario.party[0].pc.ranged, name, value)
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                with self.subTest(name=name, value=value), self.assertRaises((TypeError, ValueError)):
                    run_pc_melee_trial(forged, 0, rng_factory=rng)
                rng.assert_not_called()

    def test_npc_pistol_source_is_preserved_beside_the_new_pc_ranged_key(self):
        scene = source()
        enemy = create_pc_book_npc(PcBookNpcProfile.IMPERIAL_OGRE_PISTOL, 'minion1')
        scene = replace(scene, enemies=(enemy,), npc_pistol_policies=(PcNpcPistolPolicy('minion1',
            True,True,True,True,PcNpcPistolReloadHandPolicy.TWO_AVAILABLE_HANDS),))
        raw = document()
        raw['scenario'] = scenario_document(scene)
        command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
        encoded = scenario_document(command.request.scenario)
        self.assertEqual(encoded, raw['scenario'])
        self.assertIn('ranged', encoded['party'][0]['pc'])
        self.assertIn('pistol', encoded['enemies'][0])
        self.assertNotIn('ranged', encoded['enemies'][0])

    def test_both_repeaters_keep_lawful_roster_stealth_and_explicit_protection_guards(self):
        for weapon in (PcMeleeWeapon.REPEATER_HANDBOW, PcMeleeWeapon.REPEATER_PISTOL):
            scene = source(weapon=weapon)
            trooper = create_pc_book_npc(PcBookNpcProfile.EMPIRE_STATE_TROOPER_HALBERD, 'minion1')
            with self.subTest(weapon=weapon), self.assertRaises(ValueError):
                replace(scene, enemies=(trooper,))
            for choice in (Skill.MELEE, Skill.ATHLETICS):
                selected = replace(scene, enemies=(trooper,), npc_close_shooting_protection_policies=(
                    PcNpcCloseShootingProtectionPolicy('minion1', choice),))
                raw = document()
                raw['scenario'] = scenario_document(selected)
                command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
                self.assertEqual(command.request.scenario, selected)
            thief = create_pc_book_npc(PcBookNpcProfile.HALFLING_THIEF_DAGGER, 'minion1')
            selected = replace(scene, enemies=(thief,))
            raw = document()
            raw['scenario'] = scenario_document(selected)
            command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
            self.assertEqual(command.request.scenario, selected)

    def test_both_repeater_modes_cross_actual_services_search_schemas_and_full_echoes(self):
        for weapon in (PcMeleeWeapon.REPEATER_HANDBOW, PcMeleeWeapon.REPEATER_PISTOL):
            for mode in MODES:
                for balance in (False, True):
                    with self.subTest(weapon=weapon, mode=mode, balance=balance):
                        raw = request_document(balance=balance, weapon=weapon, mode=mode)
                        if balance:
                            command = wire.parse_pc_melee_balance_request(json.dumps(raw))
                            for count in (1,2):
                                candidate = project_pc_melee_candidate(command.request, (count,)).scenario
                                self.assertEqual(candidate.party[0].pc.ranged, command.request.template.party[0].pc.ranged)
                            result = execute_pc_melee_balance(command)
                            output = json.loads(wire.encode_pc_melee_balance_result(command, result))
                            validate_pc_melee_balance_document(output, 'result')
                            for row, candidate in zip(output['candidates'], result.candidates, strict=True):
                                self.assertEqual(row['request']['scenario'], scenario_document(candidate.source_request.scenario))
                        else:
                            command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
                            result = execute_pc_melee_simulation(command)
                            output = json.loads(wire.encode_pc_melee_simulation_result(command, result))
                            validate_pc_melee_simulation_document(output, 'result')
                        self.assertEqual(output['request'], raw)


if __name__ == '__main__':
    unittest.main()
