"""Strict Hochland Awareness and explicit Second Action source contracts."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import json
import unittest
from unittest.mock import patch

from jsonschema import ValidationError

from tests.support.pc_hochland_scenarios import make_pc_hochland_scenario
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
from towr.domain.pc_melee_models import (
    PC_FREE_RELOAD_WEAPONS, PC_RANGED_WEAPONS, PC_TWO_HANDED_RANGED_WEAPONS,
    PcAimSecondActionPolicy, PcFatePolicy, PcGloriousPolicy, PcMeleeWeapon,
    PcTwoHandedGrip, PcWeaponHand,
)
from towr.domain.test_models import Skill, TestProfile
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


def request_document(*, balance=False, use_second_action=True):
    source = make_pc_hochland_scenario(enemy_count=2, use_second_action=use_second_action)
    raw = document(balance=balance)
    key = 'template' if balance else 'scenario'
    raw[key] = scenario_document(source)
    if balance:
        raw['generation']['facts'] = deepcopy(raw[key]['facts'])
    return raw


class PcHochlandSourceTests(unittest.TestCase):
    def test_ten_explicit_fields_policy_and_decline_roundtrip_in_both_families(self):
        self.assertEqual((len(PC_RANGED_WEAPONS), len(PC_TWO_HANDED_RANGED_WEAPONS),
            len(PC_FREE_RELOAD_WEAPONS)), (13,9,4))
        for balance in (False,True):
            for use_policy in (False,True):
                raw = request_document(balance=balance,use_second_action=use_policy)
                key = 'template' if balance else 'scenario'
                parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
                command = parse(json.dumps(raw))
                scene = command.request.template if balance else command.request.scenario
                member = scene.party[0]
                with self.subTest(balance=balance,use_policy=use_policy):
                    self.assertEqual(scenario_document(scene),raw[key])
                    self.assertEqual(member.pc.ranged.awareness_profile,TestProfile(3,4))
                    self.assertIs(member.initial_weapon_hand,PcTwoHandedGrip.BOTH)
                    self.assertEqual(len(raw[key]['party'][0]['pc']['ranged']),10)
                    self.assertEqual(raw[key]['party'][0]['pc']['ranged']['awareness'],4)
                    self.assertEqual(member.aim_second_action_policy,PcAimSecondActionPolicy(0) if use_policy else None)
                    self.assertIs(member.fate_policy,PcFatePolicy.CONFIGURED if use_policy else PcFatePolicy.DECLINE_OPTIONAL_FATE)
                    self.assertEqual('aim_second_action_policy' in raw[key]['party'][0],use_policy)

    def test_wire_rejects_missing_partial_false_or_unrelated_profile_and_policy_fields(self):
        for balance in (False,True):
            base = request_document(balance=balance)
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            validate = validate_pc_melee_balance_document if balance else validate_pc_melee_simulation_document
            error = PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            fields = base[key]['party'][0]['pc']['ranged']
            changes = [lambda m:m['pc'].update(ranged=None), lambda m:m['pc']['ranged'].update(extra=True),
                lambda m:m['pc']['ranged'].update(repeater_bonus_policy='never'),
                lambda m:m['pc']['ranged'].update(awareness=True), lambda m:m['pc']['ranged'].update(awareness=0),
                lambda m:m['pc']['ranged'].update(awareness=11),
                lambda m:m.update(aim_second_action_policy=None), lambda m:m.update(aim_second_action_policy={}),
                lambda m:m['aim_second_action_policy'].update(extra=True),
                lambda m:m['aim_second_action_policy'].update(minimum_remaining_session_spends=True),
                lambda m:m['aim_second_action_policy'].update(minimum_remaining_session_spends=-1),
                lambda m:m.update(fate_policy='decline_optional_fate'),
                lambda m:m.update(initial_weapon_hand='right'), lambda m:m.update(shield={
                    'initial_hand':'left','hand_conflict_policy':'weapon_first','recovery_policy':'restore_before_attack'})]
            changes += [lambda m,field=field:m['pc']['ranged'].pop(field) for field in fields]
            changes += [lambda m,field=field:m['pc']['ranged'].update({field:None}) for field in fields]
            for field in ('has_blackpowder_lore','has_blackpowder_kit','ammunition_supply_confirmed','initially_loaded'):
                changes += [lambda m,field=field:m['pc']['ranged'].update({field:False})]
            for index,change in enumerate(changes):
                raw = deepcopy(base);change(raw[key]['party'][0])
                with self.subTest(balance=balance,index=index):
                    with self.assertRaises(ValidationError):validate(raw)
                    with self.assertRaises(error):parse(json.dumps(raw))
            raw = deepcopy(base);raw[key].pop('short_range_opening')
            raw[key]['facts']['all_opponents_close'] = True
            with self.assertRaises(error):parse(json.dumps(raw))

    def test_native_readmission_and_other_weapons_keep_their_existing_shapes(self):
        source = make_pc_hochland_scenario()
        member = source.party[0]
        for value in (None,True,0,11):
            with self.subTest(awareness=value),self.assertRaises((TypeError,ValueError)):
                replace(member.pc,ranged=replace(member.pc.ranged,awareness=value))
        for value in (True,-1,'0'):
            with self.assertRaises((TypeError,ValueError)):PcAimSecondActionPolicy(value)
        with self.assertRaises(TypeError):replace(member,aim_second_action_policy={'minimum_remaining_session_spends':0})
        with self.assertRaises(ValueError):replace(member,shield=shield_loadout())
        with self.assertRaises(TypeError):replace(member,initial_weapon_hand=PcWeaponHand.RIGHT)
        with self.assertRaises(ValueError):replace(source,short_range_opening=None,
            facts=replace(source.facts,all_opponents_close=True))
        with self.assertRaises(ValueError):PcGloriousPolicy((Skill.AWARENESS,),0,0)
        old = make_pc_handgun_scenario()
        with self.assertRaises(ValueError):replace(old.party[0].pc,
            ranged=replace(old.party[0].pc.ranged,awareness=4))
        with self.assertRaises(ValueError):replace(old.party[0],
            aim_second_action_policy=PcAimSecondActionPolicy(0),fate_policy=PcFatePolicy.CONFIGURED)
        raw = request_document()
        raw['scenario'] = scenario_document(old)
        self.assertEqual(len(raw['scenario']['party'][0]['pc']['ranged']),9)
        wire.parse_pc_melee_simulation_request(json.dumps(raw))
        for field,value in (('awareness',4),):
            malformed = deepcopy(raw);malformed['scenario']['party'][0]['pc']['ranged'][field] = value
            with self.assertRaises(PcMeleeSimulationInputError):wire.parse_pc_melee_simulation_request(json.dumps(malformed))
        malformed = deepcopy(raw);malformed['scenario']['party'][0]['aim_second_action_policy'] = {'minimum_remaining_session_spends':0}
        malformed['scenario']['party'][0]['fate_policy'] = 'configured'
        with self.assertRaises(PcMeleeSimulationInputError):wire.parse_pc_melee_simulation_request(json.dumps(malformed))

    def test_lucky_is_an_explicit_hoc_only_fact_in_native_and_wire_sources(self):
        for enabled in (False,True):
            source = make_pc_hochland_scenario(fate_rating=0,has_lucky=enabled,reserve=0)
            self.assertIs(source.party[0].fate.has_lucky,enabled)
            for balance in (False,True):
                raw = request_document(balance=balance)
                key = 'template' if balance else 'scenario'
                raw[key] = scenario_document(source)
                if balance:
                    raw['generation']['groups'][0].update(actor_ids=['minion1'],minimum_count=1,maximum_count=1)
                    raw['generation']['facts'] = raw[key]['facts']
                parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
                command = parse(json.dumps(raw))
                actual = command.request.template if balance else command.request.scenario
                self.assertEqual(scenario_document(actual),raw[key])
        old = make_pc_handgun_scenario()
        with self.assertRaises(ValueError):replace(old.party[0],fate=replace(old.party[0].fate,has_lucky=True))
        raw = request_document();raw['scenario'] = scenario_document(old)
        raw['scenario']['party'][0]['fate']['has_lucky'] = True
        with self.assertRaises(ValidationError):validate_pc_melee_simulation_document(raw)
        with self.assertRaises(PcMeleeSimulationInputError):wire.parse_pc_melee_simulation_request(json.dumps(raw))
        for value in (None,1,'true'):
            raw = request_document();raw['scenario']['party'][0]['fate']['has_lucky'] = value
            with self.assertRaises(PcMeleeSimulationInputError):wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_cached_foreign_and_bool_source_fail_before_rng_creation(self):
        class ForeignWeapon(str,Enum):
            HOCHLAND = 'hochland_long_rifle'
        request = PcMeleeSimulationRequest(make_pc_hochland_scenario(),42,1)
        cases = (('ranged','awareness',True),('ranged','awareness',None),
            ('ranged','initiative',True),('ranged','has_blackpowder_lore',False),
            ('policy','minimum_remaining_session_spends',True),('policy','minimum_remaining_session_spends',-1),
            ('pc','weapon',ForeignWeapon.HOCHLAND),('fate','has_lucky',1))
        for owner,field,value in cases:
            forged = deepcopy(request)
            member = forged.scenario.party[0]
            target = member.pc.ranged if owner=='ranged' else member.aim_second_action_policy if owner=='policy' else member.fate if owner=='fate' else member.pc
            object.__setattr__(target,field,value)
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                with self.subTest(owner=owner,field=field),self.assertRaises((TypeError,ValueError)):
                    run_pc_melee_trial(forged,0,rng_factory=rng)
                rng.assert_not_called()

    def test_candidate_projection_preserves_resource_policy_awareness_and_complete_echoes(self):
        raw = request_document(balance=True)
        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
        for count,ids in ((1,('minion2',)),(2,('minion1','minion2'))):
            source = project_pc_melee_candidate(command.request,(count,)).scenario
            original = command.request.template.party[0]
            self.assertEqual(source.party[0],replace(original,
                target_priority=tuple(a for a in original.target_priority if a in ids),
                defeat_decisions=tuple(d for d in original.defeat_decisions if d.target_id in ids)))
            self.assertEqual(source.party[0].pc.ranged.awareness,4)
            self.assertEqual(source.party[0].aim_second_action_policy,PcAimSecondActionPolicy(0))
            self.assertEqual(source.party[0].fate,original.fate)
            echoed = scenario_document(source)
            self.assertEqual(echoed['party'][0]['aim_second_action_policy'],{'minimum_remaining_session_spends':0})


if __name__ == '__main__':
    unittest.main()
