"""Two-handed firearm admission and end-to-end current PC JSON1 contracts."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import json
import unittest
from unittest.mock import patch

from tests.support.pc_handgun_scenarios import make_pc_handgun_scenario
from tests.support.pc_shield_scenarios import shield_loadout
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError, PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document, validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_balance_models import project_pc_melee_candidate
from towr.application.pc_melee_service import execute_pc_melee_balance, execute_pc_melee_simulation
from towr.domain.pc_melee_models import (
    PC_HANDGUN_WEAPONS, PC_RANGED_WEAPONS, PC_TWO_HANDED_RANGED_WEAPONS,
    PcMeleeWeapon, PcRepeaterBonusPolicy, PcTwoHandedGrip, PcWeaponHand,
)
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


CASES = ((PcMeleeWeapon.HANDGUN, None),
    (PcMeleeWeapon.REPEATER_HANDGUN, PcRepeaterBonusPolicy.WHEN_AVAILABLE),
    (PcMeleeWeapon.REPEATER_HANDGUN, PcRepeaterBonusPolicy.NEVER))


def request_document(*, balance=False, weapon=PcMeleeWeapon.HANDGUN, mode=None):
    scene = make_pc_handgun_scenario(weapon=weapon, repeater_bonus_policy=mode,
        enemy_count=2, max_rounds=3, npc_toughness=3, npc_armour_bonus=2,
        npc_armoured=True)
    raw = document(balance=balance)
    raw['template' if balance else 'scenario'] = scenario_document(scene)
    if balance:
        raw['generation']['facts'] = deepcopy(raw['template']['facts'])
        raw['evaluation'].update(trials_per_candidate=1, max_total_trials=2)
    else:
        raw['simulation']['trials'] = 2
    return raw


class PcHandgunJsonTests(unittest.TestCase):
    def test_both_handguns_and_repeater_choices_roundtrip_complete_firearm_sources(self):
        self.assertEqual(tuple(weapon.value for weapon in PC_HANDGUN_WEAPONS),
            ('handgun', 'repeater_handgun'))
        self.assertEqual(len(PC_TWO_HANDED_RANGED_WEAPONS), 9)
        self.assertEqual(len(PC_RANGED_WEAPONS), 13)
        for weapon, mode in CASES:
            for balance in (False, True):
                raw = request_document(balance=balance, weapon=weapon, mode=mode)
                key = 'template' if balance else 'scenario'
                parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
                command = parse(json.dumps(raw))
                scene = command.request.template if balance else command.request.scenario
                with self.subTest(weapon=weapon, mode=mode, balance=balance):
                    self.assertEqual(scenario_document(scene), raw[key])
                    self.assertIs(scene.party[0].initial_weapon_hand, PcTwoHandedGrip.BOTH)
                    expected = {'ballistic_skill':3, 'shooting':4, 'initiative':3,
                        'dexterity':4, 'has_blackpowder_lore':True, 'has_blackpowder_kit':True,
                        'ammunition_supply_confirmed':True, 'initially_loaded':True,
                        'reload_hand_policy':'two_available_hands'}
                    if mode is not None:
                        expected['repeater_bonus_policy'] = mode.value
                    self.assertEqual(raw[key]['party'][0]['pc']['ranged'], expected)

    def test_missing_null_false_partial_and_unrelated_firearm_fields_are_rejected(self):
        for weapon, mode in CASES:
            for balance in (False, True):
                base = request_document(balance=balance, weapon=weapon, mode=mode)
                key = 'template' if balance else 'scenario'
                parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
                error = PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
                profile = base[key]['party'][0]['pc']['ranged']
                changes = [lambda pc:pc.update(ranged=None), lambda pc:pc.update(ranged={}),
                    lambda pc:pc['ranged'].update(extra=True),
                    lambda pc:pc['ranged'].update(ballistic_skill=True),
                    lambda pc:pc['ranged'].update(reload_hand_policy='weapon_hand_only'),
                    lambda pc:pc['ranged'].update(has_engineering_kit=True)]
                changes += [lambda pc, field=field:pc['ranged'].pop(field) for field in profile]
                changes += [lambda pc, field=field:pc['ranged'].update({field:None}) for field in profile]
                for field in ('has_blackpowder_lore', 'has_blackpowder_kit',
                        'ammunition_supply_confirmed', 'initially_loaded'):
                    changes += [lambda pc, field=field, value=value:
                        pc['ranged'].update({field:value}) for value in (False, 1)]
                if mode is None:
                    changes.append(lambda pc:pc['ranged'].update(repeater_bonus_policy='never'))
                else:
                    changes.append(lambda pc:pc['ranged'].update(repeater_bonus_policy='always'))
                for index, change in enumerate(changes):
                    raw = deepcopy(base)
                    change(raw[key]['party'][0]['pc'])
                    with self.subTest(weapon=weapon, mode=mode, balance=balance,
                            index=index), self.assertRaises(error):
                        parse(json.dumps(raw))

    def test_grip_shield_close_opening_and_carry_requirements_cross_native_and_wire(self):
        class Alias(str, Enum):
            HANDGUN = 'handgun'
        for weapon, mode in CASES:
            scene = make_pc_handgun_scenario(weapon=weapon, repeater_bonus_policy=mode)
            member = scene.party[0]
            for field, value in (('has_blackpowder_lore',None), ('has_blackpowder_kit',None),
                    ('shooting',True), ('reload_hand_policy','two_available_hands')):
                with self.subTest(weapon=weapon, field=field), self.assertRaises((TypeError, ValueError)):
                    replace(member.pc, ranged=replace(member.pc.ranged, **{field:value}))
            with self.assertRaises(ValueError):
                replace(member, shield=shield_loadout())
            with self.assertRaises(TypeError):
                replace(member, initial_weapon_hand=PcWeaponHand.RIGHT)
            with self.assertRaises(ValueError):
                replace(member, pc=replace(member.pc, strength=1))
            with self.assertRaises(ValueError):
                replace(scene, short_range_opening=None,
                    facts=replace(scene.facts, all_opponents_close=True))
            base = request_document(weapon=weapon, mode=mode)
            changes = [lambda raw:raw['scenario']['party'][0].update(initial_weapon_hand='right'),
                lambda raw:raw['scenario']['party'][0]['pc'].update(strength=1),
                lambda raw:raw['scenario']['party'][0].update(shield={
                    'initial_hand':'left', 'hand_conflict_policy':'weapon_first',
                    'recovery_policy':'restore_before_attack'}),
                lambda raw:raw['scenario'].pop('short_range_opening')]
            for index, change in enumerate(changes):
                raw = deepcopy(base)
                change(raw)
                with self.subTest(weapon=weapon, index=index), self.assertRaises(PcMeleeSimulationInputError):
                    wire.parse_pc_melee_simulation_request(json.dumps(raw))
        with self.assertRaises(TypeError):
            member = make_pc_handgun_scenario().party[0]
            replace(member.pc, weapon=Alias.HANDGUN)

    def test_cached_firearm_and_bonus_forgeries_fail_before_rng(self):
        for weapon, mode in CASES:
            request = PcMeleeSimulationRequest(make_pc_handgun_scenario(
                weapon=weapon, repeater_bonus_policy=mode), 42, 1)
            for field, value in (('has_blackpowder_lore',None), ('has_blackpowder_kit',False),
                    ('ballistic_skill',True), ('initially_loaded',False),
                    ('repeater_bonus_policy',PcRepeaterBonusPolicy.NEVER if mode is None else None)):
                forged = deepcopy(request)
                object.__setattr__(forged.scenario.party[0].pc.ranged, field, value)
                with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                    with self.subTest(weapon=weapon, field=field), self.assertRaises((TypeError, ValueError)):
                        run_pc_melee_trial(forged, 0, rng_factory=rng)
                    rng.assert_not_called()

    def test_services_count_search_schemas_and_full_source_candidate_echoes(self):
        for weapon, mode in CASES:
            for balance in (False, True):
                raw = request_document(balance=balance, weapon=weapon, mode=mode)
                with self.subTest(weapon=weapon, mode=mode, balance=balance):
                    if balance:
                        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
                        for count in (1, 2):
                            candidate = project_pc_melee_candidate(command.request, (count,)).scenario
                            for member, original in zip(candidate.party,
                                    command.request.template.party, strict=True):
                                # The fixture's declared group priority is minion2,minion1.
                                # PC target priority keeps its own order among retained NPCs.
                                self.assertEqual(member, replace(original,
                                    target_priority=('minion2',) if count == 1 else ('minion1','minion2'),
                                    defeat_decisions=original.defeat_decisions[1:] if count == 1
                                        else original.defeat_decisions))
                            self.assertEqual(candidate.short_range_opening,
                                command.request.template.short_range_opening)
                            self.assertTrue(all(enemy.definition.resilience.armoured is True
                                for enemy in candidate.enemies))
                        result = execute_pc_melee_balance(command)
                        output = json.loads(wire.encode_pc_melee_balance_result(command, result))
                        validate_pc_melee_balance_document(output, 'result')
                        for row, candidate in zip(output['candidates'], result.candidates, strict=True):
                            self.assertEqual(row['request']['scenario'],
                                scenario_document(candidate.source_request.scenario))
                    else:
                        command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
                        result = execute_pc_melee_simulation(command)
                        output = json.loads(wire.encode_pc_melee_simulation_result(command, result))
                        validate_pc_melee_simulation_document(output, 'result')
                    self.assertEqual(output['request'], raw)


if __name__ == '__main__':
    unittest.main()
