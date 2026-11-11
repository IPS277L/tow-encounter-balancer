"""Crossbow Exacting sources and explicit authored armour cross current PC JSON1."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tests.support.pc_crossbow_scenarios import make_pc_crossbow_scenario
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_shield_scenarios import shield_loadout
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError, PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import validate_pc_melee_balance_document, validate_pc_melee_simulation_document
from towr.application.pc_melee_balance_models import project_pc_melee_candidate
from towr.application.pc_melee_service import execute_pc_melee_balance, execute_pc_melee_simulation
from towr.domain.attack_models import ResilienceProfile
from towr.domain.pc_melee_models import (
    PC_CROSSBOW_WEAPONS, PC_TWO_HANDED_RANGED_WEAPONS, PcMeleeWeapon,
    PcRepeaterBonusPolicy, PcTwoHandedGrip, PcWeaponHand,
)
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


CASES = ((PcMeleeWeapon.CROSSBOW,None),
    (PcMeleeWeapon.REPEATER_CROSSBOW,PcRepeaterBonusPolicy.WHEN_AVAILABLE),
    (PcMeleeWeapon.REPEATER_CROSSBOW,PcRepeaterBonusPolicy.NEVER))


def request_document(*,balance=False,weapon=PcMeleeWeapon.CROSSBOW,mode=None,armoured=None):
    scene = make_pc_crossbow_scenario(weapon=weapon,repeater_bonus_policy=mode,
        enemy_count=2,max_rounds=3,npc_toughness=3,npc_armour_bonus=1,npc_armoured=armoured)
    raw = document(balance=balance)
    raw['template' if balance else 'scenario'] = scenario_document(scene)
    if balance:
        raw['generation']['facts'] = deepcopy(raw['template']['facts'])
        raw['evaluation'].update(trials_per_candidate=1,max_total_trials=2)
    else:
        raw['simulation']['trials'] = 2
    return raw


class PcCrossbowJsonTests(unittest.TestCase):
    def test_both_crossbows_roundtrip_full_reload_profiles_and_both_repeater_modes(self):
        self.assertEqual(tuple(weapon.value for weapon in PC_CROSSBOW_WEAPONS),
            ('crossbow','repeater_crossbow'))
        self.assertEqual(len(PC_TWO_HANDED_RANGED_WEAPONS),9)
        for weapon,mode in CASES:
            for balance in (False,True):
                with self.subTest(weapon=weapon,mode=mode,balance=balance):
                    raw = request_document(balance=balance,weapon=weapon,mode=mode)
                    parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
                    source_key = 'template' if balance else 'scenario'
                    command = parse(json.dumps(raw))
                    scene = command.request.template if balance else command.request.scenario
                    self.assertEqual(scenario_document(scene),raw[source_key])
                    member = scene.party[0]
                    self.assertIs(member.initial_weapon_hand,PcTwoHandedGrip.BOTH)
                    expected = {'ballistic_skill':3,'shooting':4,'initiative':3,'dexterity':4,
                        'ammunition_supply_confirmed':True,'initially_loaded':True,
                        'reload_hand_policy':'two_available_hands'}
                    if mode is not None:
                        expected['repeater_bonus_policy'] = mode.value
                    self.assertEqual(raw[source_key]['party'][0]['pc']['ranged'],expected)

    def test_crossbows_reject_partial_null_extra_firearm_and_wrong_bonus_fields(self):
        for weapon,mode in CASES:
            for balance in (False,True):
                base = request_document(balance=balance,weapon=weapon,mode=mode)
                key = 'template' if balance else 'scenario'
                parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
                error = PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
                profile = base[key]['party'][0]['pc']['ranged']
                changes = [lambda pc:pc.update(ranged=None),lambda pc:pc.update(ranged={}),
                    lambda pc:pc['ranged'].update(extra=True),
                    lambda pc:pc['ranged'].update(has_blackpowder_lore=True),
                    lambda pc:pc['ranged'].update(has_blackpowder_kit=False),
                    lambda pc:pc['ranged'].update(has_blackpowder_kit=None),
                    lambda pc:pc['ranged'].update(initially_loaded=False),
                    lambda pc:pc['ranged'].update(ballistic_skill=True),
                    lambda pc:pc['ranged'].update(reload_hand_policy='weapon_hand_only')]
                changes += [lambda pc,field=field:pc['ranged'].pop(field) for field in profile]
                changes += [lambda pc,field=field:pc['ranged'].update({field:None}) for field in profile]
                if weapon is PcMeleeWeapon.CROSSBOW:
                    changes.append(lambda pc:pc['ranged'].update(repeater_bonus_policy='never'))
                for index,change in enumerate(changes):
                    raw = deepcopy(base)
                    change(raw[key]['party'][0]['pc'])
                    with self.subTest(weapon=weapon,mode=mode,balance=balance,index=index),self.assertRaises(error):
                        parse(json.dumps(raw))

    def test_native_weapon_profile_grip_shield_close_and_carry_guards_are_exact(self):
        class Alias(str,Enum):
            CROSSBOW = 'crossbow'
        for weapon,mode in CASES:
            scene = make_pc_crossbow_scenario(weapon=weapon,repeater_bonus_policy=mode)
            member = scene.party[0]
            for changes in ({'has_blackpowder_lore':True},{'has_blackpowder_kit':True},
                    {'ammunition_supply_confirmed':1},{'shooting':True},
                    {'reload_hand_policy':'two_available_hands'}):
                with self.subTest(weapon=weapon,changes=changes),self.assertRaises((TypeError,ValueError)):
                    replace(member.pc,ranged=replace(member.pc.ranged,**changes))
            with self.assertRaises(ValueError):
                replace(member,shield=shield_loadout())
            with self.assertRaises(TypeError):
                replace(member,initial_weapon_hand=PcWeaponHand.RIGHT)
            with self.assertRaises(ValueError):
                replace(member,pc=replace(member.pc,strength=1))
            with self.assertRaises(ValueError):
                replace(scene,short_range_opening=None,facts=replace(scene.facts,all_opponents_close=True))
        with self.assertRaises(ValueError):
            member = make_pc_crossbow_scenario().party[0]
            replace(member.pc,ranged=replace(member.pc.ranged,repeater_bonus_policy=PcRepeaterBonusPolicy.NEVER))
        with self.assertRaises(TypeError):
            member = make_pc_crossbow_scenario().party[0]
            replace(member.pc,weapon=Alias.CROSSBOW)

    def test_authored_armour_true_false_and_absence_preserve_full_fresh_resilience(self):
        for armoured in (None,False,True):
            for balance in (False,True):
                raw = request_document(balance=balance,armoured=armoured)
                key = 'template' if balance else 'scenario'
                parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
                command = parse(json.dumps(raw))
                scene = command.request.template if balance else command.request.scenario
                self.assertEqual(scenario_document(scene),raw[key])
                for enemy in scene.enemies:
                    self.assertIs(enemy.definition.resilience.armoured,armoured)
                    self.assertEqual(enemy.state.current_resilience,enemy.definition.resilience)
                    encoded = next(item for item in raw[key]['enemies'] if item['actor_id']==enemy.state.actor_id)
                    actual = encoded['definition']['resilience']
                    if armoured is None:
                        self.assertNotIn('armoured',actual)
                    else:
                        self.assertIs(actual['armoured'],armoured)
                    self.assertIs(enemy.definition.resilience.is_armoured,True if armoured is None else armoured)
        # This remains an authored PC-family source fact outside Short scenes too.
        scene = make_pc_melee_scenario()
        enemy = scene.enemies[0]
        resilience = ResilienceProfile(3,2,armoured=False)
        enemy = replace(enemy,definition=replace(enemy.definition,resilience=resilience),
            state=replace(enemy.state,current_resilience=resilience))
        scene = replace(scene,enemies=(enemy,))
        raw = document()
        raw['scenario'] = scenario_document(scene)
        decoded = wire.parse_pc_melee_simulation_request(json.dumps(raw)).request.scenario
        self.assertIs(decoded.enemies[0].state.current_resilience.armoured,False)

    def test_authored_armour_strict_types_and_matching_snapshot_cannot_be_forged(self):
        for invalid in (None,0,1,'false',[],{}):
            raw = request_document()
            raw['scenario']['enemies'][0]['definition']['resilience']['armoured'] = invalid
            with self.subTest(armoured=invalid),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))
        scene = make_pc_crossbow_scenario(npc_armour_bonus=1,npc_armoured=False)
        enemy = scene.enemies[0]
        with self.assertRaises(ValueError):
            changed = replace(enemy,state=replace(enemy.state,
                current_resilience=replace(enemy.state.current_resilience,armoured=True)))
            replace(scene,enemies=(changed,))
        request = PcMeleeSimulationRequest(scene,42,1)
        forged = deepcopy(request)
        object.__setattr__(forged.scenario.enemies[0].definition.resilience,'armoured',1)
        with patch('towr.simulation.pc_melee_simulation.Random') as rng:
            with self.assertRaises((TypeError,ValueError)):
                run_pc_melee_trial(forged,0,rng_factory=rng)
            rng.assert_not_called()

    def test_canonical_npc_armour_metadata_restrictions_remain_unchanged(self):
        scene = make_pc_melee_scenario()
        actor = scene.enemies[0].state.actor_id
        enemy = create_pc_book_npc(PcBookNpcProfile.FOOTPAD,actor)
        armour = replace(enemy.definition.resilience,armoured=True)
        with self.assertRaises(ValueError):
            changed = replace(enemy,definition=replace(enemy.definition,resilience=armour),
                state=replace(enemy.state,current_resilience=armour))
            replace(scene,enemies=(changed,))
        path = Path(__file__).resolve().parents[2]/'docs/examples/m52/pc-melee-simulation.request.json'
        original = json.loads(path.read_bytes())
        wire.parse_pc_melee_simulation_request(json.dumps(original))
        net = next(enemy for enemy in original['scenario']['enemies']
            if enemy['definition']['id']=='pc-book-npc:night_goblin_net_spear')
        self.assertIs(net['definition']['resilience']['armoured'],True)
        net['definition']['resilience']['armoured'] = False
        with self.assertRaises(PcMeleeSimulationInputError):
            wire.parse_pc_melee_simulation_request(json.dumps(original))

    def test_cached_crossbow_profile_forgeries_fail_before_rng(self):
        for weapon,mode in CASES:
            request = PcMeleeSimulationRequest(make_pc_crossbow_scenario(
                weapon=weapon,repeater_bonus_policy=mode),42,1)
            for field,value in (('has_blackpowder_lore',True),('shooting',True),
                    ('initially_loaded',False),('repeater_bonus_policy',
                        PcRepeaterBonusPolicy.NEVER if mode is None else None)):
                forged = deepcopy(request)
                object.__setattr__(forged.scenario.party[0].pc.ranged,field,value)
                with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                    with self.subTest(weapon=weapon,field=field),self.assertRaises((TypeError,ValueError)):
                        run_pc_melee_trial(forged,0,rng_factory=rng)
                    rng.assert_not_called()

    def test_crossbows_actual_services_search_schemas_and_armoured_false_full_echoes(self):
        for weapon,mode in CASES:
            for balance in (False,True):
                raw = request_document(balance=balance,weapon=weapon,mode=mode,armoured=False)
                with self.subTest(weapon=weapon,mode=mode,balance=balance):
                    if balance:
                        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
                        for count in (1,2):
                            candidate = project_pc_melee_candidate(command.request,(count,)).scenario
                            for member,original in zip(candidate.party,command.request.template.party,strict=True):
                                self.assertEqual(member.pc,original.pc)
                                self.assertEqual(member.backup_weapon_policy,original.backup_weapon_policy)
                                self.assertIs(member.initial_weapon_hand,original.initial_weapon_hand)
                            self.assertEqual(candidate.short_range_opening,command.request.template.short_range_opening)
                            self.assertTrue(all(enemy.state.current_resilience.armoured is False
                                for enemy in candidate.enemies))
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
