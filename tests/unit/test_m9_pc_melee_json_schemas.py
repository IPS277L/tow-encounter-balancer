"""Seven bundled PC schemas: offline closure and strict public shapes."""
from copy import deepcopy
from importlib.resources import files
import json
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from tests.unit.test_m9_pc_melee_json import aggregate, balance_result, document
from towr.adapters import pc_melee_json as wire
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError, PcMeleeSimulationInputError
from towr.adapters import pc_melee_json_schema as schema
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code


def samples():
    simulation=document()
    balance=document(balance=True)
    simulation_command=wire.parse_pc_melee_simulation_request(json.dumps(simulation))
    balance_command=wire.parse_pc_melee_balance_request(json.dumps(balance))
    return (
        (schema.validate_pc_melee_simulation_document,'request',simulation),
        (schema.validate_pc_melee_balance_document,'request',balance),
        (schema.validate_pc_melee_simulation_document,'result',json.loads(
            wire.encode_pc_melee_simulation_result(simulation_command,aggregate(simulation_command.request)))),
        (schema.validate_pc_melee_balance_document,'result',json.loads(
            wire.encode_pc_melee_balance_result(balance_command,balance_result(balance_command)))),
        (schema.validate_pc_melee_simulation_document,'error',json.loads(
            wire.encode_pc_melee_simulation_error(PcMeleeSimulationInputError(Code.INVALID_JSON,'bad')))),
        (schema.validate_pc_melee_balance_document,'error',json.loads(
            wire.encode_pc_melee_balance_error(PcMeleeBalanceInputError(Code.INVALID_INPUT,'bad',path='/generation')))),
    )


class PcMeleeJsonSchemaTests(unittest.TestCase):
    def test_all_seven_current_documents_and_their_refs_resolve_offline(self):
        names=['pc-melee-common.schema.json', *[
            f'pc-melee-{family}-{kind}-v1.schema.json'
            for family in ('simulation','balance') for kind in ('request','result','error')]]
        resources=files('towr.adapters.schemas')
        documents=[json.loads(resources.joinpath(name).read_text(encoding='utf-8')) for name in names]
        self.assertEqual(len({document['$id'] for document in documents}),7)
        registry=Registry().with_resources((doc['$id'],Resource.from_contents(doc)) for doc in documents)
        refs=[]
        def collect(value,base):
            if isinstance(value,dict):
                if '$ref' in value:
                    refs.append((base,value['$ref']))
                for child in value.values():
                    collect(child,base)
            elif isinstance(value,list):
                for child in value:
                    collect(child,base)
        with patch('socket.create_connection',side_effect=AssertionError('schemas must be offline')):
            for doc in documents:
                Draft202012Validator.check_schema(doc)
                collect(doc,doc['$id'])
            self.assertGreater(len(refs),0)
            for base,reference in refs:
                registry.resolver(base_uri=base).lookup(reference)
            for validator,kind,value in samples():
                validator(value,kind)

    def test_six_public_shapes_require_every_field_and_reject_unknown_fields(self):
        for validator,kind,value in samples():
            for name in value:
                changed=deepcopy(value)
                del changed[name]
                with self.subTest(kind=kind,field=name),self.assertRaises(ValidationError):
                    validator(changed,kind)
            changed=dict(value,not_in_contract=True)
            with self.subTest(kind=kind),self.assertRaises(ValidationError):
                validator(changed,kind)

    def test_nested_result_and_error_fields_are_closed(self):
        for validator,kind,value in samples():
            if kind=='request':
                continue
            changed=deepcopy(value)
            inner=changed['error'] if kind=='error' else changed['runtime']
            inner['private_cause']='forbidden'
            with self.subTest(kind=kind),self.assertRaises(ValidationError):
                validator(changed,kind)
        balance=samples()[3][2]
        for path in (('candidates',0,'summary'),('candidates',0,'summary','pc_defeat_counts',0),
                     ('candidates',0,'assessment'),('request','evaluation')):
            changed=deepcopy(balance)
            target=changed
            for name in path:
                target=target[name]
            target['extra']=True
            with self.subTest(path=path),self.assertRaises(ValidationError):
                schema.validate_pc_melee_balance_document(changed,'result')

    def test_party_members_and_loss_counts_require_complete_closed_shapes(self):
        raw=document(party_size=2)
        for field in raw['scenario']['party'][1]:
            changed=deepcopy(raw)
            del changed['scenario']['party'][1][field]
            with self.subTest(field=field),self.assertRaises(ValidationError):
                schema.validate_pc_melee_simulation_document(changed)
        changed=deepcopy(raw)
        changed['scenario']['party'][1]['invented_state']={}
        with self.assertRaises(ValidationError):
            schema.validate_pc_melee_simulation_document(changed)
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        result=json.loads(wire.encode_pc_melee_simulation_result(command,aggregate(command.request)))
        for field in ('any_pc_defeated_count','pc_defeat_counts'):
            changed=deepcopy(result)
            del changed['summary'][field]
            with self.subTest(field=field),self.assertRaises(ValidationError):
                schema.validate_pc_melee_simulation_document(changed,'result')

    def test_execution_modes_refuse_bool_or_missing_or_irrelevant_process_options(self):
        for execution in ({'mode':'sequential','workers':None}, {'mode':'process'},
                          {'mode':'process','workers':True,'batch_size':1},
                          {'mode':'process','workers':62,'batch_size':1},
                          {'mode':'process','workers':1,'batch_size':0}):
            raw=document()
            raw['execution']=execution
            with self.subTest(execution=execution),self.assertRaises(ValidationError):
                schema.validate_pc_melee_simulation_document(raw)
        raw=document()
        raw['execution']={'mode':'process','workers':61,'batch_size':1}
        schema.validate_pc_melee_simulation_document(raw)

    def test_fate_and_enemy_derived_scope_cannot_be_overridden_in_wire(self):
        for update in (lambda raw:raw['scenario']['party'][0]['fate'].update(has_lucky=True),
                       lambda raw:raw['scenario']['party'][0]['fate'].update(spends=[{}]),
                       lambda raw:raw['scenario']['enemies'][0]['definition']['attack']['test_profile'].update(pool_cap=4),
                       lambda raw:raw['scenario']['enemies'][0]['definition']['attack']['damage'].update(success_multiplier=2),
                       lambda raw:raw['scenario']['party'][0]['defeat_decisions'][0].update(gm_approved=False),
                       lambda raw:raw['scenario']['party'][0]['pc'].update(armour_bonus=False)):
            raw=document()
            update(raw)
            with self.subTest(update=update),self.assertRaises(ValidationError):
                schema.validate_pc_melee_simulation_document(raw)

    def test_current_family_versions_and_kinds_have_no_legacy_shapes(self):
        raw=document()
        for version in ('0','2','6',1,True):
            with self.subTest(version=version),self.assertRaises(ValidationError):
                schema.validate_pc_melee_simulation_document(dict(raw,schema_version=version))
        with self.assertRaises(ValidationError):
            schema.validate_pc_melee_balance_document(raw)
        for kind in ('other',None):
            with self.assertRaises(ValueError):
                schema._validator(kind)
        with self.assertRaises(ValueError):
            schema._validator('request','other')

    def test_validator_cache_is_bounded_to_the_six_current_shapes(self):
        schema._validator.cache_clear()
        for family in ('simulation','balance'):
            for kind in ('request','result','error'):
                self.assertIs(schema._validator(kind,family),schema._validator(kind,family))
        info=schema._validator.cache_info()
        self.assertEqual((info.maxsize,info.currsize,info.misses),(6,6,6))


if __name__=='__main__':
    unittest.main()
