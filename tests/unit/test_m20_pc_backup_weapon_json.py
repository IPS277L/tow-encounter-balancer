"""Current PC JSON1 admits an explicit nullable, source-preserving backup."""
from copy import deepcopy
from enum import Enum
import json
import unittest

from jsonschema import ValidationError

from tests.unit.test_m9_pc_melee_json import aggregate, balance_result, document
from towr.adapters import pc_melee_json as wire
from towr.adapters import pc_melee_json_schema as schema
from towr.adapters._pc_melee_scenario_json import parse_scenario, scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError, PcMeleeSimulationInputError
from towr.domain.pc_melee_models import PcBackupWeaponPolicy, PcMeleeWeapon, PcWeaponHand


BACKUPS=('staff','sword','dagger','axe','warhammer','morning_star')
PRIMARIES=('pickaxe','flail','billhook','halberd','glaive','greataxe')


def configured_document(*,balance=False):
    raw=document(balance=balance,party_size=8,mixed=True)
    key='template' if balance else 'scenario'
    for index,(member,primary,backup) in enumerate(zip(raw[key]['party'],PRIMARIES,BACKUPS)):
        member['pc'].update(weapon=primary,strength=2)
        member['initial_weapon_hand']='both'
        member['backup_weapon_policy']={'weapon':backup,'preferred_hand':'left' if index%2 else 'right'}
    member=raw[key]['party'][-1]
    member['pc'].update(weapon='greathammer',strength=1)
    member['initial_weapon_hand']='both'
    return raw


class PcBackupWeaponJsonTests(unittest.TestCase):
    def test_default_none_is_encoded_as_required_null_for_every_member(self):
        for balance in (False,True):
            raw=document(balance=balance,party_size=3)
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            for member in raw[key]['party']:
                self.assertIn('backup_weapon_policy',member)
                self.assertIsNone(member['backup_weapon_policy'])
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertTrue(all(member.backup_weapon_policy is None for member in source.party))
            self.assertEqual(scenario_document(source),raw[key])

    def test_all_backups_and_null_policies_preserve_full_mixed_sources(self):
        for balance in (False,True):
            raw=configured_document(balance=balance)
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            for member,weapon in zip(source.party,BACKUPS):
                self.assertIs(type(member.backup_weapon_policy),PcBackupWeaponPolicy)
                self.assertIs(member.backup_weapon_policy.weapon,PcMeleeWeapon(weapon))
                self.assertIs(type(member.backup_weapon_policy.preferred_hand),PcWeaponHand)
            self.assertIsNone(source.party[-1].backup_weapon_policy)
            self.assertIsNone(source.party[-2].backup_weapon_policy)
            self.assertEqual(scenario_document(source),raw[key])
            report=balance_result(command) if balance else aggregate(command.request)
            encode=wire.encode_pc_melee_balance_result if balance else wire.encode_pc_melee_simulation_result
            result=json.loads(encode(command,report))
            validate=schema.validate_pc_melee_balance_document if balance else schema.validate_pc_melee_simulation_document
            validate(result,'result')
            self.assertEqual(result['request'],raw)
            if balance:
                for candidate,typed in zip(result['candidates'],report.candidates):
                    self.assertEqual(candidate['request']['scenario'],scenario_document(typed.source_request.scenario))
                    self.assertEqual([member['backup_weapon_policy'] for member in candidate['request']['scenario']['party']],
                        [member['backup_weapon_policy'] for member in raw[key]['party']])

    def test_backup_is_closed_typed_one_handed_and_requires_eligible_primary(self):
        invalid=(False,0,'sword',[],{},
            {'weapon':'sword'}, {'preferred_hand':'left'},
            {'weapon':'sword','preferred_hand':'left','extra':0},
            *({'weapon':value,'preferred_hand':'left'} for value in
                ('pickaxe','flail','billhook','halberd','glaive','greataxe','greathammer',
                 'unknown','SWORD','morning-star',False,None,1,[])),
            *({'weapon':'sword','preferred_hand':value} for value in
                ('both','LEFT','dominant','',False,None,1,[])))
        for balance in (False,True):
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            validate=schema.validate_pc_melee_balance_document if balance else schema.validate_pc_melee_simulation_document
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for policy in invalid:
                raw=configured_document(balance=balance)
                raw[key]['party'][0]['backup_weapon_policy']=policy
                with self.subTest(balance=balance,policy=policy):
                    with self.assertRaises(ValidationError):
                        validate(raw)
                    with self.assertRaises(error):
                        parse(json.dumps(raw))
            for primary,strength,hand in (('pickaxe',1,'both'),
                    *((weapon,2,'left') for weapon in BACKUPS)):
                raw=configured_document(balance=balance)
                raw[key]['party'][0]['pc'].update(weapon=primary,strength=strength)
                raw[key]['party'][0]['initial_weapon_hand']=hand
                with self.subTest(balance=balance,primary=primary,strength=strength):
                    with self.assertRaises(ValidationError):
                        validate(raw)
                    with self.assertRaises(error):
                        parse(json.dumps(raw))

    def test_omitted_field_is_refused_on_each_member_without_defaulting(self):
        for balance in (False,True):
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for index in (0,1):
                raw=document(balance=balance,party_size=2)
                del raw[key]['party'][index]['backup_weapon_policy']
                with self.subTest(balance=balance,index=index),self.assertRaises(error):
                    parse(json.dumps(raw))

    def test_scenario_codec_does_not_drop_extra_backup_source_fields(self):
        raw=configured_document()['scenario']
        raw['party'][0]['backup_weapon_policy']['extra']='unrepresentable source'
        with self.assertRaises(PcMeleeSimulationInputError):
            parse_scenario(raw,path_prefix='/scenario',error_type=PcMeleeSimulationInputError)

    def test_result_schema_applies_backup_shape_and_correlation_to_every_source(self):
        for balance in (False,True):
            raw=configured_document(balance=balance)
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
                member=source['party'][0]
                saved=member.pop('backup_weapon_policy')
                with self.subTest(balance=balance,source=index,missing=True),self.assertRaises(ValidationError):
                    validate(result,'result')
                for policy in ({'weapon':'sword','preferred_hand':'both'},
                        {'weapon':'greathammer','preferred_hand':'right'},False):
                    member['backup_weapon_policy']=policy
                    with self.subTest(balance=balance,source=index,policy=policy),self.assertRaises(ValidationError):
                        validate(result,'result')
                member['backup_weapon_policy']=saved
                member['pc']['strength']=1
                with self.subTest(balance=balance,source=index,strength=1),self.assertRaises(ValidationError):
                    validate(result,'result')
                member['pc']['strength']=2

    def test_encoding_readmits_nested_backup_types_in_cached_sources(self):
        class ForeignWeapon(str,Enum):
            STAFF='staff'

        class ForeignHand(str,Enum):
            RIGHT='right'

        for balance in (False,True):
            raw=configured_document(balance=balance)
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            report=balance_result(command) if balance else aggregate(command.request)
            encode=wire.encode_pc_melee_balance_result if balance else wire.encode_pc_melee_simulation_result
            for field,value in (('weapon',ForeignWeapon.STAFF),('weapon','staff'),
                    ('preferred_hand',ForeignHand.RIGHT),('preferred_hand','right')):
                forged=deepcopy(command)
                source=forged.request.template if balance else forged.request.scenario
                object.__setattr__(source.party[0].backup_weapon_policy,field,value)
                self.assertEqual(forged,command)
                with self.subTest(balance=balance,field=field,value=value),self.assertRaises(TypeError):
                    encode(forged,report)
                if balance:
                    forged_report=deepcopy(report)
                    policy=forged_report.candidates[0].source_request.scenario.party[0].backup_weapon_policy
                    object.__setattr__(policy,field,value)
                    self.assertEqual(forged_report,report)
                    with self.assertRaises(TypeError):
                        encode(command,forged_report)


if __name__=='__main__':
    unittest.main()
