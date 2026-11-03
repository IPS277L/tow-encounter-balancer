"""ADR-0062 structural profile contract and offline JSON6 schema closure."""
from copy import deepcopy
from importlib.resources import files
import json
import unittest

from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from tests.unit.test_m8_magic_json_v5 import document as version5
from towr.adapters import magic_json_schema as production


FIELD = 'battered_leg_continuation'
PERMISSIONS = ('miscast_continuation', 'stationary_wound_continuation',
               'repeated_leg_spasm_continuation', 'crushed_rib_continuation', FIELD)


def document(profile=None):
    data = version5(opted=False)
    data['schema_version'] = '6'
    data['scenario'][FIELD] = None if profile is None else {'endurance_profile': profile}
    return data


def references(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == '$ref':
                yield child
            else:
                yield from references(child)
    elif isinstance(value, list):
        for child in value:
            yield from references(child)


class MagicJsonV6SchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = {schema['$id']: schema
            for path in files('towr.adapters.schemas').iterdir() if path.name.endswith('.schema.json')
            for schema in (json.loads(path.read_text(encoding='utf-8')),)}
        cls.registry = Registry().with_resources(
            (uri, Resource.from_contents(schema)) for uri, schema in cls.documents.items())

    def test_six_new_ids_and_every_reference_resolve_from_complete_local_bundle(self):
        self.assertEqual(len(self.documents), 54)
        self.assertEqual(sum(uri.startswith('urn:towr:magic-') for uri in self.documents), 36)
        for uri, schema in self.documents.items():
            Draft202012Validator.check_schema(schema)
            for ref in references(schema):
                with self.subTest(uri=uri, ref=ref):
                    self.registry.resolver(uri).lookup(ref)
        for family in ('simulation', 'balance'):
            for kind in ('request', 'result', 'error'):
                schema = self.documents[f'urn:towr:magic-{family}:{kind}:6']
                self.assertEqual(schema['properties']['schema_version'], {'type': 'string', 'const': '6'})
        self.assertEqual(production._validator.cache_info().maxsize, 36)

    def test_normal_profile_is_explicit_and_has_no_prototype_dice_maximum(self):
        for profile in (None, {'dice': 1, 'threshold': 5}, {'dice': 11, 'threshold': 5},
                        {'dice': 2, 'threshold': 1}, {'dice': 2, 'threshold': 10}):
            with self.subTest(profile=profile):
                production.validate_magic_simulation_document(document(profile), schema_version='6')

    def test_nullable_is_required_for_all_five_permissions_and_scenario_is_closed(self):
        valid = document()
        production.validate_magic_simulation_document(valid, schema_version='6')
        for name in PERMISSIONS:
            missing = deepcopy(valid)
            del missing['scenario'][name]
            with self.subTest(missing=name), self.assertRaises(ValidationError):
                production.validate_magic_simulation_document(missing, schema_version='6')
        invalid = deepcopy(valid)
        invalid['scenario']['pending'] = None
        with self.assertRaises(ValidationError):
            production.validate_magic_simulation_document(invalid, schema_version='6')
        schema = self.documents['urn:towr:magic-simulation:request:6']['$defs']['scenario']
        self.assertNotIn('allOf', schema)
        self.assertIs(schema['additionalProperties'], False)

    def test_policy_and_nested_profile_are_closed_and_strictly_bounded(self):
        invalid_values = (False, True, 0, 1, [], '', {}, {'endurance_profile': None},
            {'endurance_profile': {'dice': 2}}, {'endurance_profile': {'threshold': 5}},
            {'endurance_profile': {'dice': 0, 'threshold': 5}},
            {'endurance_profile': {'dice': -1, 'threshold': 5}},
            {'endurance_profile': {'dice': True, 'threshold': 5}},
            {'endurance_profile': {'dice': 2.5, 'threshold': 5}},
            {'endurance_profile': {'dice': '2', 'threshold': 5}},
            {'endurance_profile': {'dice': 2, 'threshold': False}},
            {'endurance_profile': {'dice': 2, 'threshold': 0}},
            {'endurance_profile': {'dice': 2, 'threshold': 11}},
            {'endurance_profile': {'dice': 2, 'threshold': 5, 'pool_cap': 4}},
            {'endurance_profile': {'dice': 2, 'threshold': 5}, 'actor_id': 'wizard'})
        for value in invalid_values:
            invalid = document()
            invalid['scenario'][FIELD] = value
            with self.subTest(value=value), self.assertRaises(ValidationError):
                production.validate_magic_simulation_document(invalid, schema_version='6')

    def test_older_closed_scenarios_refuse_new_field_even_null(self):
        for version in range(1, 6):
            old = version5(opted=False)
            old['schema_version'] = str(version)
            for introduced, name in enumerate(PERMISSIONS[:-1], start=2):
                if introduced > version:
                    del old['scenario'][name]
            production.validate_magic_simulation_document(old, schema_version=str(version))
            old['scenario'][FIELD] = None
            with self.subTest(version=version), self.assertRaises(ValidationError):
                production.validate_magic_simulation_document(old, schema_version=str(version))

    def test_result_echo_and_errors_have_their_own_six_metadata(self):
        result = self.documents['urn:towr:magic-simulation:result:6']
        self.assertEqual(result['properties']['request']['$ref'], 'urn:towr:magic-simulation:request:6')
        error = {'schema_version': '6', 'kind': 'magic_simulation_error', 'request_id': 'schema6',
                 'error': {'code': 'invalid_input', 'path': '/scenario/' + FIELD, 'message': 'invalid profile'}}
        production.validate_magic_simulation_document(error, 'error', schema_version='6')
        error['schema_version'] = '5'
        with self.assertRaises(ValidationError):
            production.validate_magic_simulation_document(error, 'error', schema_version='6')


if __name__ == '__main__':
    unittest.main()
