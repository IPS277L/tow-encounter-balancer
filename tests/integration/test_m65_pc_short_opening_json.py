"""Strict Short-opening/bow sources cross current JSON, trials and count search."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import json
import unittest
from unittest.mock import patch

from tests.support.pc_bow_scenarios import bow_profile, make_pc_bow_scenario
from tests.support.pc_melee_fixtures import make_pc_melee_scenario, with_pc_melee_brute
from tests.support.pc_ranged_scenarios import make_pc_ranged_scenario
from tests.support.pc_shield_scenarios import shield_loadout
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import parse_scenario, scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError, PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import validate_pc_melee_balance_document, validate_pc_melee_simulation_document
from towr.application.pc_melee_balance_models import project_pc_melee_candidate
from towr.application.pc_melee_service import execute_pc_melee_balance, execute_pc_melee_simulation
from towr.domain.pc_melee_models import (
    PC_BOW_WEAPONS, PcBackupWeaponPolicy, PcMeleeWeapon, PcShortRangeOpening,
    PcTwoHandedGrip, PcWeaponHand,
)
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc
from towr.domain.pc_npc_close_shooting_models import PcNpcCloseShootingProtectionPolicy
from towr.domain.test_models import Skill
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


def request_document(*, balance=False, weapon=PcMeleeWeapon.SHORTBOW):
    source = make_pc_bow_scenario(weapon=weapon, enemy_count=2, max_rounds=3)
    raw = document(balance=balance)
    raw['template' if balance else 'scenario'] = scenario_document(source)
    if balance:
        raw['generation']['facts'] = deepcopy(raw['template']['facts'])
        raw['evaluation'].update(trials_per_candidate=1, max_total_trials=2)
    else:
        raw['simulation']['trials'] = 2
    return raw


class PcShortOpeningJsonTests(unittest.TestCase):
    def test_three_bow_sources_have_only_actual_shooting_facts_and_roundtrip_both_families(self):
        for weapon in PC_BOW_WEAPONS:
            for balance in (False, True):
                with self.subTest(weapon=weapon, balance=balance):
                    raw = request_document(balance=balance, weapon=weapon)
                    key = 'template' if balance else 'scenario'
                    parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
                    command = parse(json.dumps(raw))
                    source = command.request.template if balance else command.request.scenario
                    self.assertEqual(scenario_document(source), raw[key])
                    member = source.party[0]
                    self.assertIs(member.initial_weapon_hand, PcTwoHandedGrip.BOTH)
                    self.assertIsNone(member.pc.ranged.initiative)
                    self.assertIsNone(member.pc.ranged.dexterity)
                    self.assertEqual(raw[key]['party'][0]['pc']['ranged'], {
                        'ballistic_skill':3, 'shooting':4, 'ammunition_supply_confirmed':True})
                    self.assertEqual(raw[key]['short_range_opening'], {
                        'party_clustered_confirmed':True, 'npc_approach_clear_confirmed':True})

    def test_bows_forbid_reload_firearm_and_bonus_facts_with_strict_scalar_types(self):
        class Number(int):
            pass
        class Alias(str, Enum):
            SHORTBOW = 'shortbow'
        member = make_pc_bow_scenario().party[0]
        for weapon in PC_BOW_WEAPONS:
            for field, value in (('has_blackpowder_lore',True), ('has_blackpowder_kit',True),
                    ('initiative',3), ('dexterity',4), ('initially_loaded',True),
                    ('reload_hand_policy','two_available_hands'), ('repeater_bonus_policy','never'),
                    ('ballistic_skill',True), ('shooting',True), ('ammunition_supply_confirmed',1)):
                raw = request_document(weapon=weapon)
                raw['scenario']['party'][0]['pc']['ranged'][field] = value
                with self.subTest(weapon=weapon,field=field), self.assertRaises((TypeError, ValueError)):
                    changed = replace(member.pc.ranged, **{field:value})
                    replace(member.pc, ranged=changed)
                with self.assertRaises(PcMeleeSimulationInputError):
                    wire.parse_pc_melee_simulation_request(json.dumps(raw))
        for weapon in ('shortbow', Alias.SHORTBOW):
            with self.assertRaises(TypeError):
                replace(member.pc, weapon=weapon)
        with self.assertRaises(TypeError):
            replace(member.pc.ranged,shooting=Number(4))
        self.assertEqual(bow_profile().shooting_profile.characteristic, 3)

    def test_closed_source_profiles_missing_and_unknown_fields_fail_before_execution(self):
        for balance in (False, True):
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error = PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            base = request_document(balance=balance)
            mutations = [lambda pc:pc.update(ranged=None), lambda pc:pc.update(ranged={}),
                lambda pc:pc.update(pistol=pc.pop('ranged')),
                lambda pc:pc['ranged'].update(extra=True)]
            mutations += [lambda pc,field=field:pc['ranged'].pop(field)
                for field in ('ballistic_skill','shooting','ammunition_supply_confirmed')]
            mutations += [lambda pc,field=field:pc['ranged'].update({field:None})
                for field in ('initiative','dexterity','initially_loaded','has_blackpowder_lore',
                    'has_blackpowder_kit','reload_hand_policy','repeater_bonus_policy')]
            for index, mutate in enumerate(mutations):
                raw = deepcopy(base)
                mutate(raw[key]['party'][0]['pc'])
                with self.subTest(balance=balance,index=index), self.assertRaises(error):
                    parse(json.dumps(raw))

    def test_opening_requires_exact_closed_confirmations_and_consistent_facts(self):
        source = make_pc_bow_scenario()
        for field in ('party_clustered_confirmed','npc_approach_clear_confirmed'):
            for invalid in (False,None,1,'true'):
                with self.subTest(field=field,invalid=invalid), self.assertRaises((TypeError,ValueError)):
                    replace(source.short_range_opening, **{field:invalid})
        for raw_opening in (None,False,{}, {'party_clustered_confirmed':True},
                {'party_clustered_confirmed':True,'npc_approach_clear_confirmed':True,'extra':True}):
            raw = request_document()
            raw['scenario']['short_range_opening'] = raw_opening
            with self.subTest(opening=raw_opening), self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))
            with self.assertRaises(PcMeleeSimulationInputError):
                parse_scenario(raw['scenario'], path_prefix='/scenario', error_type=PcMeleeSimulationInputError)
        for changes in ({'short_range_opening':None},
                {'facts':replace(source.facts,all_opponents_close=True)},
                {'facts':replace(source.facts,can_leave_zone=True)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(source, **changes)
        with self.assertRaises(ValueError):
            replace(source,short_range_opening=None,facts=replace(source.facts,all_opponents_close=True))
        ordinary = make_pc_melee_scenario()
        with self.assertRaises(ValueError):
            replace(ordinary,facts=replace(ordinary.facts,all_opponents_close=False))

    def test_short_scope_rejects_unsupported_npc_roles_shields_and_protection_override(self):
        source = make_pc_bow_scenario()
        with self.assertRaises(ValueError):
            with_pc_melee_brute(source,'minion1',wound_limit=3)
        book = create_pc_book_npc(PcBookNpcProfile.HORSE,'minion1')
        with self.assertRaises(ValueError):
            replace(source,enemies=(book,))
        with self.assertRaises(ValueError):
            replace(source,npc_close_shooting_protection_policies=(
                PcNpcCloseShootingProtectionPolicy('minion1',Skill.ATHLETICS),))
        member = source.party[0]
        with self.assertRaises(ValueError):
            replace(member,shield=shield_loadout())
        with self.assertRaises(TypeError):
            replace(member,initial_weapon_hand=PcWeaponHand.RIGHT)
        with self.assertRaises(ValueError):
            replace(member,pc=replace(member.pc,strength=1))
        no_backup = replace(member,backup_weapon_policy=None)
        self.assertEqual(replace(source,party=(no_backup,)).party[0].backup_weapon_policy,None)
        for raw_change in (lambda s:s['party'][0]['pc'].update(weapon='staff'),
                lambda s:s['enemies'][0].update(holds_shield=True),
                lambda s:s['enemies'][0]['definition'].update(injury_policy='brute',wound_limit=3),
                lambda s:s['enemies'][0]['definition']['attack'].update(range_max='short'),
                lambda s:s['enemies'][0]['definition']['protection'].update(skill='defence'),
                lambda s:s.update(npc_close_shooting_protection_policies=[{'actor_id':'minion1','skill':'athletics'}])):
            raw = request_document()
            raw_change(raw['scenario'])
            with self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_current_gun_sources_remain_identical_in_short_opening_and_in_close(self):
        for weapon in (PcMeleeWeapon.PISTOL,PcMeleeWeapon.REPEATER_HANDBOW,PcMeleeWeapon.REPEATER_PISTOL):
            kwargs = {'repeater_bonus_policy':None} if weapon is PcMeleeWeapon.PISTOL else {}
            old = make_pc_ranged_scenario(weapon=weapon,**kwargs)
            old_wire = scenario_document(old)
            short = replace(old, facts=replace(old.facts,all_opponents_close=False,can_leave_zone=False),
                short_range_opening=PcShortRangeOpening(True,True))
            raw = document()
            raw['scenario'] = scenario_document(short)
            decoded = wire.parse_pc_melee_simulation_request(json.dumps(raw)).request.scenario
            self.assertEqual(decoded,short)
            self.assertEqual(raw['scenario']['party'],old_wire['party'])
            self.assertNotIn('short_range_opening',old_wire)
            self.assertTrue(old_wire['facts']['all_opponents_close'])

    def test_cached_opening_weapon_and_profile_forgeries_fail_before_rng(self):
        request = PcMeleeSimulationRequest(make_pc_bow_scenario(),42,1)
        for mutate in (
                lambda s:object.__setattr__(s.short_range_opening,'party_clustered_confirmed',1),
                lambda s:object.__setattr__(s.facts,'all_opponents_close',True),
                lambda s:object.__setattr__(s.party[0].pc.ranged,'initially_loaded',True),
                lambda s:object.__setattr__(s.party[0].pc.ranged,'shooting',True),
                lambda s:object.__setattr__(s,'short_range_opening',None)):
            forged = deepcopy(request)
            mutate(forged.scenario)
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                with self.assertRaises((TypeError,ValueError)):
                    run_pc_melee_trial(forged,0,rng_factory=rng)
                rng.assert_not_called()

    def test_three_bows_cross_actual_services_count_search_and_full_current_echoes(self):
        for weapon in PC_BOW_WEAPONS:
            for balance in (False,True):
                raw = request_document(balance=balance,weapon=weapon)
                with self.subTest(weapon=weapon,balance=balance):
                    if balance:
                        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
                        for count in (1,2):
                            projected = project_pc_melee_candidate(command.request,(count,)).scenario
                            self.assertEqual(projected.short_range_opening,command.request.template.short_range_opening)
                            self.assertEqual(projected.party[0].pc.ranged,command.request.template.party[0].pc.ranged)
                        result = execute_pc_melee_balance(command)
                        output = json.loads(wire.encode_pc_melee_balance_result(command,result))
                        validate_pc_melee_balance_document(output,'result')
                        for row,candidate in zip(output['candidates'],result.candidates,strict=True):
                            self.assertEqual(row['request']['scenario'],scenario_document(candidate.source_request.scenario))
                    else:
                        command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
                        result = execute_pc_melee_simulation(command)
                        output = json.loads(wire.encode_pc_melee_simulation_result(command,result))
                        validate_pc_melee_simulation_document(output,'result')
                    self.assertEqual(output['request'],raw)


if __name__=='__main__':
    unittest.main()
