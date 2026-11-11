"""Sling source, shield and current PC JSON1 services preserve full facts."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import json
import unittest
from unittest.mock import patch

from jsonschema import ValidationError

from tests.support.pc_sling_scenarios import make_pc_sling_scenario
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
    PC_BOW_WEAPONS, PC_FREE_RELOAD_WEAPONS, PC_RANGED_WEAPONS, PC_TWO_HANDED_RANGED_WEAPONS,
    PcMeleeWeapon, PcRangedReloadHandPolicy, PcRepeaterBonusPolicy, PcTwoHandedGrip, PcWeaponHand,
)
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


def request_document(*, balance=False, shield=False, backup_hand=PcWeaponHand.RIGHT):
    source = make_pc_sling_scenario(enemy_count=2, max_rounds=3, shield=shield,
        backup_hand=backup_hand, npc_toughness=3, npc_armour_bonus=2, npc_armoured=True)
    raw = document(balance=balance)
    raw['template' if balance else 'scenario'] = scenario_document(source)
    if balance:
        raw['generation']['facts'] = deepcopy(raw['template']['facts'])
        raw['evaluation'].update(trials_per_candidate=1, max_total_trials=2)
    else:
        raw['simulation']['trials'] = 2
    return raw


class PcSlingJsonTests(unittest.TestCase):
    def test_exact_free_source_optional_shield_and_both_initial_hands_roundtrip(self):
        self.assertEqual(len(PC_BOW_WEAPONS), 3)
        self.assertEqual(PC_FREE_RELOAD_WEAPONS, (*PC_BOW_WEAPONS, PcMeleeWeapon.SLING))
        self.assertEqual(len(PC_TWO_HANDED_RANGED_WEAPONS), 9)
        self.assertEqual(len(PC_RANGED_WEAPONS), 13)
        for shield in (False, True):
            for hand in (PcWeaponHand.LEFT, PcWeaponHand.RIGHT):
                source = make_pc_sling_scenario(shield=shield, initial_hand=hand)
                for balance in (False, True):
                    raw = request_document(balance=balance)
                    key = 'template' if balance else 'scenario'
                    raw[key] = scenario_document(source)
                    if balance:
                        # The generation group must name the current source enemy.
                        raw['generation']['groups'][0]['actor_ids'] = ['minion1']
                        raw['generation']['groups'][0]['minimum_count'] = 1
                        raw['generation']['groups'][0]['maximum_count'] = 1
                        raw['generation']['facts'] = raw[key]['facts']
                    parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
                    command = parse(json.dumps(raw))
                    actual = command.request.template if balance else command.request.scenario
                    with self.subTest(shield=shield, hand=hand, balance=balance):
                        self.assertEqual(scenario_document(actual), raw[key])
                        self.assertEqual(raw[key]['party'][0]['pc']['ranged'], {
                            'ballistic_skill':3, 'shooting':4, 'ammunition_supply_confirmed':True})
                        self.assertIs(actual.party[0].initial_weapon_hand, hand)
                        self.assertEqual(actual.party[0].shield, source.party[0].shield)

    def test_exact_three_fields_reject_partial_exacting_firearm_repeater_and_false_facts(self):
        for balance in (False, True):
            base = request_document(balance=balance)
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            validate = validate_pc_melee_balance_document if balance else validate_pc_melee_simulation_document
            error = PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            changes = [lambda pc:pc.pop('ranged'), lambda pc:pc.update(ranged=None),
                lambda pc:pc.update(ranged={}), lambda pc:pc['ranged'].update(extra=True),
                lambda pc:pc['ranged'].update(ballistic_skill=True),
                lambda pc:pc['ranged'].update(shooting=0)]
            for field in ('ballistic_skill','shooting','ammunition_supply_confirmed'):
                changes += [lambda pc, field=field:pc['ranged'].pop(field),
                    lambda pc, field=field:pc['ranged'].update({field:None})]
            for field, value in (('initiative',3), ('dexterity',4), ('initially_loaded',True),
                    ('reload_hand_policy','two_available_hands'), ('has_blackpowder_lore',True),
                    ('has_blackpowder_kit',True), ('repeater_bonus_policy','never')):
                changes += [lambda pc, field=field, value=value:pc['ranged'].update({field:value})]
            for value in (False,1):
                changes += [lambda pc, value=value:pc['ranged'].update(ammunition_supply_confirmed=value)]
            for index, change in enumerate(changes):
                raw = deepcopy(base)
                change(raw[key]['party'][0]['pc'])
                with self.subTest(balance=balance, index=index):
                    with self.assertRaises(ValidationError):
                        validate(raw)
                    with self.assertRaises(error):
                        parse(json.dumps(raw))

    def test_native_and_wire_grip_close_shield_and_carry_guards(self):
        source = make_pc_sling_scenario(shield=True)
        member = source.party[0]
        with self.assertRaises(TypeError):
            replace(member, initial_weapon_hand=PcTwoHandedGrip.BOTH)
        with self.assertRaises(ValueError):
            replace(member, shield=replace(member.shield, initial_hand=member.initial_weapon_hand))
        with self.assertRaises(ValueError):
            replace(member, pc=replace(member.pc, strength=1))
        one = make_pc_sling_scenario(strength=1, backup=False, shield=True)
        self.assertEqual(one.party[0].pc.strength, 1)
        self.assertIsNone(one.party[0].backup_weapon_policy)
        raw_one = request_document()
        raw_one['scenario'] = scenario_document(one)
        self.assertEqual(wire.parse_pc_melee_simulation_request(json.dumps(raw_one)).request.scenario, one)
        with self.assertRaises(ValueError):
            replace(source, short_range_opening=None,
                facts=replace(source.facts, all_opponents_close=True))
        for changes in ({'initiative':3,'dexterity':4,'initially_loaded':True,
                    'reload_hand_policy':PcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS}, {'initially_loaded':True},
                {'reload_hand_policy':PcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS},
                {'repeater_bonus_policy':PcRepeaterBonusPolicy.NEVER},
                {'has_blackpowder_lore':True}, {'has_blackpowder_kit':True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(member.pc, ranged=replace(member.pc.ranged, **changes))
        base = request_document(shield=True)
        changes = [lambda raw:raw['scenario']['party'][0].update(initial_weapon_hand='both'),
            lambda raw:raw['scenario']['party'][0]['shield'].update(initial_hand='right'),
            lambda raw:raw['scenario']['party'][0]['pc'].update(strength=1),
            lambda raw:raw['scenario'].pop('short_range_opening')]
        for index, change in enumerate(changes):
            raw = deepcopy(base)
            change(raw)
            with self.subTest(index=index), self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_cached_foreign_partial_source_is_readmitted_before_rng(self):
        class ForeignWeapon(str, Enum):
            SLING = 'sling'
        request = PcMeleeSimulationRequest(make_pc_sling_scenario(),42,1)
        cases = (('ranged','ammunition_supply_confirmed',False),
            ('ranged','ballistic_skill',True), ('ranged','initiative',3),
            ('ranged','has_blackpowder_lore',True), ('ranged','repeater_bonus_policy',PcRepeaterBonusPolicy.NEVER),
            ('pc','weapon',ForeignWeapon.SLING), ('member','initial_weapon_hand',PcTwoHandedGrip.BOTH))
        for owner, field, value in cases:
            forged = deepcopy(request)
            member = forged.scenario.party[0]
            target = member.pc.ranged if owner == 'ranged' else member.pc if owner == 'pc' else member
            object.__setattr__(target,field,value)
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                with self.subTest(owner=owner, field=field), self.assertRaises((TypeError,ValueError)):
                    run_pc_melee_trial(forged,0,rng_factory=rng)
                rng.assert_not_called()

    def test_services_count_search_and_full_echo_with_and_without_shield_conflict(self):
        for shield in (False, True):
            for balance in (False, True):
                # A left preferred backup deliberately conflicts with the initial shield.
                raw = request_document(balance=balance, shield=shield, backup_hand=PcWeaponHand.LEFT)
                with self.subTest(shield=shield,balance=balance):
                    if balance:
                        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
                        for count in (1,2):
                            candidate = project_pc_melee_candidate(command.request,(count,)).scenario
                            for member, original in zip(candidate.party,command.request.template.party,strict=True):
                                self.assertEqual(member,replace(original,
                                    target_priority=('minion2',) if count==1 else ('minion1','minion2'),
                                    defeat_decisions=original.defeat_decisions[1:] if count==1 else original.defeat_decisions))
                            self.assertEqual(candidate.short_range_opening,command.request.template.short_range_opening)
                        result = execute_pc_melee_balance(command)
                        output = json.loads(wire.encode_pc_melee_balance_result(command,result))
                        validate_pc_melee_balance_document(output,'result')
                        for row, candidate in zip(output['candidates'],result.candidates,strict=True):
                            self.assertEqual(row['request']['scenario'],scenario_document(candidate.source_request.scenario))
                    else:
                        command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
                        result = execute_pc_melee_simulation(command)
                        output = json.loads(wire.encode_pc_melee_simulation_result(command,result))
                        validate_pc_melee_simulation_document(output,'result')
                    self.assertEqual(output['request'],raw)


if __name__ == '__main__':
    unittest.main()
