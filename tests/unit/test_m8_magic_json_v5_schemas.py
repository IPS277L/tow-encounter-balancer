"""ADR-0058 simulation5 schemas are closed and resolve from bundled refs."""
from copy import deepcopy
from importlib.resources import files
import json
import unittest

from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from tests.unit.test_m8_magic_json_v5 import FIELD, POLICY, document
from towr.adapters import magic_json_schema as production
from towr.adapters.magic_json_schema import validate_magic_simulation_document


class M8MagicJsonV5SchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = {
            schema['$id']: schema
            for path in files('towr.adapters.schemas').iterdir() if path.name.endswith('.schema.json')
            for schema in (json.loads(path.read_text(encoding='utf-8')),)
        }
        cls.registry = Registry().with_resources(
            (uri, Resource.from_contents(schema)) for uri, schema in cls.documents.items())

    def test_three_new_schemas_and_all_transitive_refs_are_bundled(self):
        self.assertEqual(len(self.documents), 54)
        self.assertEqual(sum(uri.startswith('urn:towr:magic-') for uri in self.documents), 36)
        for uri, schema in self.documents.items():
            Draft202012Validator.check_schema(schema)
            for ref in self._refs(schema):
                with self.subTest(uri=uri, ref=ref):
                    self.registry.resolver(uri).lookup(ref)
        for kind in ('request', 'result', 'error'):
            uri = f'urn:towr:magic-simulation:{kind}:5'
            self.assertEqual(self.documents[uri]['properties']['schema_version'], {'type': 'string', 'const': '5'})

    def test_request_requires_exact_nullable_policy_and_keeps_scenario_closed(self):
        valid = document()
        validate_magic_simulation_document(valid, schema_version='5')
        valid['scenario'][FIELD] = None
        validate_magic_simulation_document(valid, schema_version='5')
        for value in (False, True, 0, 1, {}, [], '', 'NEXT_TEST_WITH_JOURNAL_WITNESSES',
                      'unknown', {'policy': POLICY.value}):
            invalid = deepcopy(valid)
            invalid['scenario'][FIELD] = value
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validate_magic_simulation_document(invalid, schema_version='5')
        for field in ('miscast_continuation', 'stationary_wound_continuation',
                      'repeated_leg_spasm_continuation', FIELD):
            invalid = deepcopy(valid)
            del invalid['scenario'][field]
            with self.subTest(missing=field), self.assertRaises(ValidationError):
                validate_magic_simulation_document(invalid, schema_version='5')
        for version in ('1', '2', '3', '4'):
            invalid = deepcopy(valid)
            invalid['schema_version'] = version
            with self.subTest(version=version), self.assertRaises(ValidationError):
                validate_magic_simulation_document(invalid, schema_version=version)

    def test_result_echo_and_error_v5_have_own_strict_versions(self):
        result = json.loads(files('towr.adapters.schemas').joinpath(
            'magic-simulation-result-v5.schema.json').read_text(encoding='utf-8'))
        request = document()
        example = json.loads(files('towr.adapters.schemas').joinpath(
            'magic-simulation-error-v5.schema.json').read_text(encoding='utf-8'))
        self.assertEqual(result['properties']['request']['$ref'], 'urn:towr:magic-simulation:request:5')
        self.assertEqual(example['properties']['schema_version']['const'], '5')
        self.assertEqual(production._validator.cache_info().maxsize, 36)
        for kind in ('request', 'result', 'error'):
            validator = production._validator(kind, 'simulation', '5')
            for uri, resource in validator._registry.items():
                for ref in self._refs(resource.contents):
                    with self.subTest(kind=kind, uri=uri, ref=ref):
                        validator._registry.resolver(uri).lookup(ref)
        request['scenario'][FIELD] = POLICY.value

    @staticmethod
    def _refs(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == '$ref':
                    yield child
                else:
                    yield from M8MagicJsonV5SchemaTests._refs(child)
        elif isinstance(value, list):
            for child in value:
                yield from M8MagicJsonV5SchemaTests._refs(child)


if __name__ == '__main__':
    unittest.main()
