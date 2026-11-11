"""Blunderbuss sources, explicit initial cluster and projected JSON1 echoes."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import json
import unittest
from unittest.mock import patch

from jsonschema import ValidationError

from tests.support.pc_blunderbuss_scenarios import make_pc_blunderbuss_scenario
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
    PC_FREE_RELOAD_WEAPONS, PC_RANGED_WEAPONS, PC_TWO_HANDED_RANGED_WEAPONS,
    PcBlunderbussNearby, PcMeleeWeapon, PcRepeaterBonusPolicy, PcTwoHandedGrip, PcWeaponHand,
)
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


ORDER = ('minion2','minion3','minion1')


def request_document(*, balance=False):
    source = make_pc_blunderbuss_scenario(pc_count=2,enemy_count=3,max_rounds=3,
        npc_toughness=3,npc_armour_bonus=2,npc_armoured=True,target_priority=ORDER)
    raw = document(balance=balance)
    raw['template' if balance else 'scenario'] = scenario_document(source)
    if balance:
        raw['generation']['groups'] = [{'group_id':'cluster',
            'actor_ids':['minion3','minion1','minion2'],'minimum_count':1,'maximum_count':3}]
        raw['generation']['facts'] = deepcopy(raw['template']['facts'])
        raw['generation']['max_candidates'] = 3
        raw['evaluation'].update(trials_per_candidate=1,max_total_trials=3)
    else:
        raw['simulation']['trials'] = 2
    return raw


class PcBlunderbussJsonTests(unittest.TestCase):
    def test_exact_firearm_and_cluster_sources_roundtrip_in_both_families(self):
        self.assertEqual((len(PC_RANGED_WEAPONS),len(PC_TWO_HANDED_RANGED_WEAPONS),
            len(PC_FREE_RELOAD_WEAPONS)),(13,9,4))
        for balance in (False,True):
            raw = request_document(balance=balance)
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command = parse(json.dumps(raw))
            source = command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw[key])
            self.assertEqual(raw[key]['blunderbuss_nearby'],{
                'initial_npc_clustered_confirmed':True,'target_priority':list(ORDER)})
            self.assertEqual(raw[key]['party'][0]['pc']['ranged'],{
                'ballistic_skill':3,'shooting':4,'initiative':3,'dexterity':4,
                'has_blackpowder_lore':True,'has_blackpowder_kit':True,
                'ammunition_supply_confirmed':True,'initially_loaded':True,
                'reload_hand_policy':'two_available_hands'})
            self.assertIs(source.party[0].initial_weapon_hand,PcTwoHandedGrip.BOTH)
            changed = replace(source,blunderbuss_nearby=PcBlunderbussNearby(True,tuple(reversed(ORDER))))
            self.assertEqual(changed.blunderbuss_nearby.target_priority,tuple(reversed(ORDER)))

    def test_cluster_requires_exact_true_complete_shape_and_full_distinct_npc_membership(self):
        for balance in (False,True):
            base = request_document(balance=balance)
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            validate = validate_pc_melee_balance_document if balance else validate_pc_melee_simulation_document
            error = PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            shapes = (None,False,{},[],{'initial_npc_clustered_confirmed':True},
                {'target_priority':list(ORDER)},
                {'initial_npc_clustered_confirmed':False,'target_priority':list(ORDER)},
                {'initial_npc_clustered_confirmed':1,'target_priority':list(ORDER)},
                {'initial_npc_clustered_confirmed':True,'target_priority':None},
                {'initial_npc_clustered_confirmed':True,'target_priority':list(ORDER),'extra':True})
            for value in shapes:
                raw = deepcopy(base);raw[key]['blunderbuss_nearby'] = value
                with self.subTest(balance=balance,value=value):
                    with self.assertRaises(ValidationError):validate(raw)
                    with self.assertRaises(error):parse(json.dumps(raw))
            raw = deepcopy(base);raw[key].pop('blunderbuss_nearby')
            with self.assertRaises(ValidationError):validate(raw)
            with self.assertRaises(error):parse(json.dumps(raw))
            for order in ([],['minion1'],['minion1','minion1','minion3'],
                    ['minion1','minion2','pc1'],['minion1','minion2','unknown'],
                    ['minion1','minion2',True]):
                raw = deepcopy(base);raw[key]['blunderbuss_nearby']['target_priority'] = order
                with self.subTest(balance=balance,order=order),self.assertRaises(error):
                    parse(json.dumps(raw))
            raw = deepcopy(base)
            for member in raw[key]['party']:member['pc']['weapon'] = 'handgun'
            with self.assertRaises(ValidationError):validate(raw)
            with self.assertRaises(error):parse(json.dumps(raw))

    def test_firearm_grip_and_short_requirements_reject_partial_or_foreign_source(self):
        source = make_pc_blunderbuss_scenario()
        member = source.party[0]
        with self.assertRaises(TypeError):replace(source,blunderbuss_nearby=None)
        with self.assertRaises(ValueError):replace(make_pc_handgun_scenario(),
            blunderbuss_nearby=source.blunderbuss_nearby)
        with self.assertRaises(TypeError):replace(member,initial_weapon_hand=PcWeaponHand.RIGHT)
        with self.assertRaises(ValueError):replace(member,shield=shield_loadout())
        with self.assertRaises(ValueError):replace(source,short_range_opening=None,
            facts=replace(source.facts,all_opponents_close=True))
        for balance in (False,True):
            base = request_document(balance=balance)
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error = PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            profile = base[key]['party'][0]['pc']['ranged']
            changes = [lambda scene:scene['party'][0].update(initial_weapon_hand='right'),
                lambda scene:scene.pop('short_range_opening'),
                lambda scene:scene['party'][0]['pc']['ranged'].update(repeater_bonus_policy='never'),
                lambda scene:scene['party'][0]['pc']['ranged'].update(ballistic_skill=True)]
            changes += [lambda scene,field=field:scene['party'][0]['pc']['ranged'].pop(field)
                for field in profile]
            changes += [lambda scene,field=field:scene['party'][0]['pc']['ranged'].update({field:None})
                for field in profile]
            changes += [lambda scene,field=field:scene['party'][0]['pc']['ranged'].update({field:False})
                for field in ('has_blackpowder_lore','has_blackpowder_kit','ammunition_supply_confirmed','initially_loaded')]
            for index,change in enumerate(changes):
                raw = deepcopy(base);change(raw[key])
                with self.subTest(balance=balance,index=index),self.assertRaises(error):
                    parse(json.dumps(raw))

    def test_cached_cluster_profile_and_enum_forgeries_fail_before_rng(self):
        class ForeignWeapon(str,Enum):
            BLUNDERBUSS = 'blunderbuss'
        request = PcMeleeSimulationRequest(make_pc_blunderbuss_scenario(enemy_count=3),42,1)
        cases = (('nearby','initial_npc_clustered_confirmed',1),
            ('nearby','target_priority',['minion1','minion2','minion3']),
            ('nearby','target_priority',('minion1','minion1','minion3')),
            ('nearby','target_priority',('minion1','minion2','pc1')),
            ('ranged','has_blackpowder_lore',None),('ranged','initially_loaded',False),
            ('ranged','repeater_bonus_policy',PcRepeaterBonusPolicy.NEVER),
            ('pc','weapon',ForeignWeapon.BLUNDERBUSS))
        for owner,field,value in cases:
            forged = deepcopy(request)
            target = (forged.scenario.blunderbuss_nearby if owner=='nearby' else
                forged.scenario.party[0].pc.ranged if owner=='ranged' else forged.scenario.party[0].pc)
            object.__setattr__(target,field,value)
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                with self.subTest(owner=owner,field=field),self.assertRaises((TypeError,ValueError)):
                    run_pc_melee_trial(forged,0,rng_factory=rng)
                rng.assert_not_called()

    def test_generation_services_and_full_candidate_echo_preserve_filtered_cluster_order(self):
        raw = request_document(balance=True)
        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
        expected_orders = {1:('minion3',),2:('minion3','minion1'),3:ORDER}
        for count,order in expected_orders.items():
            source = project_pc_melee_candidate(command.request,(count,)).scenario
            self.assertEqual(source.blunderbuss_nearby,PcBlunderbussNearby(True,order))
            keep = set(order)
            for member,original in zip(source.party,command.request.template.party,strict=True):
                self.assertEqual(member,replace(original,
                    target_priority=tuple(actor for actor in original.target_priority if actor in keep),
                    defeat_decisions=tuple(d for d in original.defeat_decisions if d.target_id in keep)))
        result = execute_pc_melee_balance(command)
        output = json.loads(wire.encode_pc_melee_balance_result(command,result))
        validate_pc_melee_balance_document(output,'result')
        self.assertEqual(output['request'],raw)
        self.assertEqual(result.total_trials,3)
        for row,candidate in zip(output['candidates'],result.candidates,strict=True):
            self.assertEqual(row['request']['scenario'],scenario_document(candidate.source_request.scenario))
        raw = request_document()
        command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
        result = execute_pc_melee_simulation(command)
        output = json.loads(wire.encode_pc_melee_simulation_result(command,result))
        validate_pc_melee_simulation_document(output,'result')
        self.assertEqual(output['request'],raw)


if __name__ == '__main__':
    unittest.main()
