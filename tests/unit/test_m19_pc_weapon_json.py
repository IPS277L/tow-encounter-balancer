"""PC JSON1 correlates two-handed weapons and grip throughout source echoes."""
from copy import deepcopy
from enum import Enum
from importlib.resources import files
import json
import unittest

from jsonschema import ValidationError

from tests.unit.test_m9_pc_melee_json import aggregate, balance_result, document
from towr.adapters import pc_melee_json as wire
from towr.adapters import pc_melee_json_schema as schema
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError, PcMeleeSimulationInputError
from towr.domain.pc_melee_models import PcMeleeWeapon, PcTwoHandedGrip, PcWeaponHand


ONE_HANDED=('staff','sword','dagger','axe','warhammer','morning_star')
TWO_HANDED=('pickaxe','flail','billhook','halberd','glaive','greataxe','greathammer')


def armed_document(*,balance=False):
    raw=document(balance=balance,party_size=len(ONE_HANDED+TWO_HANDED),mixed=True)
    key='template' if balance else 'scenario'
    for index,(member,weapon) in enumerate(zip(raw[key]['party'],ONE_HANDED+TWO_HANDED)):
        member['pc']['weapon']=weapon
        member['initial_weapon_hand']='both' if weapon in TWO_HANDED else ('left' if index%2 else 'right')
    return raw


class PcTwoHandedWeaponJsonTests(unittest.TestCase):
    def test_exact_catalog_and_grip_types_roundtrip_all_weapons(self):
        common=json.loads(files('towr.adapters.schemas').joinpath('pc-melee-common.schema.json')
            .read_text(encoding='utf-8'))
        self.assertEqual(common['$defs']['pc']['properties']['weapon'],
            {'enum':list(ONE_HANDED+TWO_HANDED+('pistol','repeater_handbow','repeater_pistol','shortbow','warbow','longbow','crossbow','repeater_crossbow','handgun','repeater_handgun','sling','blunderbuss','hochland_long_rifle'))})
        self.assertEqual(tuple(weapon.value for weapon in PcMeleeWeapon),ONE_HANDED+TWO_HANDED+('pistol','repeater_handbow','repeater_pistol','shortbow','warbow','longbow','crossbow','repeater_crossbow','handgun','repeater_handgun','sling','blunderbuss','hochland_long_rifle'))
        for balance in (False,True):
            raw=armed_document(balance=balance)
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw[key])
            for member in source.party:
                expected=PcTwoHandedGrip if member.pc.weapon.value in TWO_HANDED else PcWeaponHand
                self.assertIs(type(member.initial_weapon_hand),expected)

    def test_simulation_balance_and_candidate_sources_echo_every_weapon_and_grip(self):
        for balance in (False,True):
            raw=armed_document(balance=balance)
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            report=balance_result(command) if balance else aggregate(command.request)
            encode=wire.encode_pc_melee_balance_result if balance else wire.encode_pc_melee_simulation_result
            result=json.loads(encode(command,report))
            validate=schema.validate_pc_melee_balance_document if balance else schema.validate_pc_melee_simulation_document
            validate(result,'result')
            self.assertEqual(result['request'],raw)
            if balance:
                for candidate,typed in zip(result['candidates'],report.candidates):
                    actual=candidate['request']['scenario']
                    self.assertEqual(actual,scenario_document(typed.source_request.scenario))
                    self.assertEqual([(member['pc'],member['initial_weapon_hand']) for member in actual['party']],
                        [(member['pc'],member['initial_weapon_hand']) for member in raw[key]['party']])

    def test_requests_refuse_mismatched_grips_for_every_weapon(self):
        for balance in (False,True):
            key='template' if balance else 'scenario'
            validate=schema.validate_pc_melee_balance_document if balance else schema.validate_pc_melee_simulation_document
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for weapon in ONE_HANDED+TWO_HANDED:
                for grip in (('left','right') if weapon in TWO_HANDED else ('both',)):
                    raw=document(balance=balance)
                    raw[key]['party'][0]['pc']['weapon']=weapon
                    raw[key]['party'][0]['initial_weapon_hand']=grip
                    with self.subTest(balance=balance,weapon=weapon,grip=grip):
                        with self.assertRaises(ValidationError):
                            validate(raw)
                        with self.assertRaises(error):
                            parse(json.dumps(raw))

    def test_unknown_weapon_and_grip_spellings_types_and_missing_grip_are_refused(self):
        for balance in (False,True):
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for field,values in (
                    ('weapon',('greatsword','great_axe','great axe','GREATHAMMER','unknown_weapon',True,1,None,[],{})),
                    ('initial_weapon_hand',('BOTH','two_handed','both_hands','',True,1,None,[],{}))):
                for value in values:
                    raw=document(balance=balance)
                    member=raw[key]['party'][0]
                    member['pc']['weapon']='greathammer'
                    member['initial_weapon_hand']='both'
                    (member['pc'] if field=='weapon' else member)[field]=value
                    with self.subTest(balance=balance,field=field,value=value),self.assertRaises(error):
                        parse(json.dumps(raw))
            raw=document(balance=balance)
            raw[key]['party'][0]['pc']['weapon']='pickaxe'
            del raw[key]['party'][0]['initial_weapon_hand']
            with self.assertRaises(error):
                parse(json.dumps(raw))

    def test_result_schema_refuses_wrong_grip_in_root_and_every_candidate_source(self):
        for balance in (False,True):
            raw=armed_document(balance=balance)
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            result=json.loads(wire.encode_pc_melee_balance_result(command,balance_result(command)) if balance
                else wire.encode_pc_melee_simulation_result(command,aggregate(command.request)))
            validate=schema.validate_pc_melee_balance_document if balance else schema.validate_pc_melee_simulation_document
            sources=[result['request'][key]]
            if balance:
                sources.extend(candidate['request']['scenario'] for candidate in result['candidates'])
            for index,source in enumerate(sources):
                for member in source['party']:
                    saved=member['initial_weapon_hand']
                    member['initial_weapon_hand']='left' if saved=='both' else 'both'
                    with self.subTest(balance=balance,source=index,weapon=member['pc']['weapon']),self.assertRaises(ValidationError):
                        validate(result,'result')
                    member['initial_weapon_hand']=saved

    def test_encoding_readmits_foreign_both_enum_in_cached_sources(self):
        class ForeignGrip(str,Enum):
            BOTH='both'

        for balance in (False,True):
            raw=document(balance=balance)
            key='template' if balance else 'scenario'
            raw[key]['party'][0]['pc']['weapon']='pickaxe'
            raw[key]['party'][0]['initial_weapon_hand']='both'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            report=balance_result(command) if balance else aggregate(command.request)
            forged=deepcopy(command)
            source=forged.request.template if balance else forged.request.scenario
            object.__setattr__(source.party[0],'initial_weapon_hand',ForeignGrip.BOTH)
            self.assertEqual(forged,command)
            encode=wire.encode_pc_melee_balance_result if balance else wire.encode_pc_melee_simulation_result
            with self.subTest(balance=balance),self.assertRaises(TypeError):
                encode(forged,report)
            if balance:
                forged_report=deepcopy(report)
                object.__setattr__(forged_report.candidates[0].source_request.scenario.party[0],
                    'initial_weapon_hand',ForeignGrip.BOTH)
                self.assertEqual(forged_report,report)
                with self.assertRaises(TypeError):
                    encode(command,forged_report)


if __name__=='__main__':
    unittest.main()
