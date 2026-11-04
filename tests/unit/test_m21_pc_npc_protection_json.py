"""Authored NPC numeric Protection keeps its explicit Skill in PC JSON1."""
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
from towr.domain.test_models import Skill


def protection_document(*,balance=False):
    raw=document(balance=balance,party_size=2,mixed=True)
    key='template' if balance else 'scenario'
    for enemy,skill,dice,threshold in zip(raw[key]['enemies'],('defence','athletics'),(1,4),(7,2)):
        enemy['definition']['protection']={'source_rule_id':f'authored:protection:{skill}',
            'skill':skill,'test_profile':{'dice':dice,'threshold':threshold,'pool_cap':None}}
    return raw


class PcNpcProtectionJsonTests(unittest.TestCase):
    def test_current_skill_enum_is_exact_and_defence_is_explicit(self):
        common=json.loads(files('towr.adapters.schemas').joinpath('pc-melee-common.schema.json')
            .read_text(encoding='utf-8'))
        self.assertEqual(common['$defs']['protection']['properties']['skill'],
            {'enum':['defence','athletics']})
        raw=document()
        self.assertEqual(raw['scenario']['enemies'][0]['definition']['protection']['skill'],'defence')
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        self.assertIs(command.request.scenario.enemies[0].definition.protection[0].skill,Skill.DEFENCE)
        self.assertEqual(scenario_document(command.request.scenario),raw['scenario'])

    def test_numeric_defence_and_athletics_preserve_complete_root_and_candidate_sources(self):
        for balance in (False,True):
            raw=protection_document(balance=balance)
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertEqual(tuple(enemy.definition.protection[0].skill for enemy in source.enemies),
                (Skill.DEFENCE,Skill.ATHLETICS))
            self.assertEqual(scenario_document(source),raw[key])
            report=balance_result(command) if balance else aggregate(command.request)
            encode=wire.encode_pc_melee_balance_result if balance else wire.encode_pc_melee_simulation_result
            result=json.loads(encode(command,report))
            self.assertEqual(result['request'],raw)
            validate=schema.validate_pc_melee_balance_document if balance else schema.validate_pc_melee_simulation_document
            validate(result,'result')
            if balance:
                original={enemy['actor_id']:enemy['definition'] for enemy in raw[key]['enemies']}
                for candidate,typed in zip(result['candidates'],report.candidates):
                    actual=candidate['request']['scenario']
                    self.assertEqual(actual,scenario_document(typed.source_request.scenario))
                    for enemy in actual['enemies']:
                        self.assertEqual(enemy['definition'],original[enemy['actor_id']])

    def test_request_skill_is_required_and_rejects_other_skills_aliases_and_types(self):
        for balance in (False,True):
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            validate=schema.validate_pc_melee_balance_document if balance else schema.validate_pc_melee_simulation_document
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for index in (0,1):
                for skill in ('melee','shooting','endurance','Athletics','DEFENCE','dodge','',True,1,None,[],{}):
                    raw=protection_document(balance=balance)
                    raw[key]['enemies'][index]['definition']['protection']['skill']=skill
                    with self.subTest(balance=balance,index=index,skill=skill):
                        with self.assertRaises(ValidationError):
                            validate(raw)
                        with self.assertRaises(error):
                            parse(json.dumps(raw))
                raw=protection_document(balance=balance)
                del raw[key]['enemies'][index]['definition']['protection']['skill']
                with self.subTest(balance=balance,index=index,omitted=True),self.assertRaises(error):
                    parse(json.dumps(raw))

    def test_result_schema_requires_valid_skill_in_root_and_every_candidate_source(self):
        for balance in (False,True):
            raw=protection_document(balance=balance)
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
                for enemy in source['enemies']:
                    protection=enemy['definition']['protection']
                    saved=protection.pop('skill')
                    with self.subTest(balance=balance,source=index,enemy=enemy['actor_id'],omitted=True),self.assertRaises(ValidationError):
                        validate(result,'result')
                    for skill in ('melee','Athletics',False,None):
                        protection['skill']=skill
                        with self.subTest(balance=balance,source=index,skill=skill),self.assertRaises(ValidationError):
                            validate(result,'result')
                    protection['skill']=saved

    def test_skill_difference_is_part_of_complete_summary_source_identity(self):
        raw=protection_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        raw['scenario']['enemies'][1]['definition']['protection']['skill']='defence'
        different=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        with self.assertRaises(ValueError):
            wire.encode_pc_melee_simulation_result(command,aggregate(different.request))

    def test_encoders_readmit_cached_raw_and_foreign_skill_types(self):
        class ForeignSkill(str,Enum):
            ATHLETICS='athletics'

        for balance in (False,True):
            raw=protection_document(balance=balance)
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            report=balance_result(command) if balance else aggregate(command.request)
            encode=wire.encode_pc_melee_balance_result if balance else wire.encode_pc_melee_simulation_result
            for skill in ('athletics',ForeignSkill.ATHLETICS):
                forged=deepcopy(command)
                source=forged.request.template if balance else forged.request.scenario
                object.__setattr__(source.enemies[1].definition.protection[0],'skill',skill)
                self.assertEqual(forged,command)
                with self.subTest(balance=balance,skill=skill),self.assertRaises(TypeError):
                    encode(forged,report)
                if balance:
                    forged_report=deepcopy(report)
                    enemy=forged_report.candidates[0].source_request.scenario.enemies[0]
                    self.assertIs(enemy.definition.protection[0].skill,Skill.ATHLETICS)
                    object.__setattr__(enemy.definition.protection[0],'skill',skill)
                    self.assertEqual(forged_report,report)
                    with self.assertRaises(TypeError):
                        encode(command,forged_report)


if __name__=='__main__':
    unittest.main()
