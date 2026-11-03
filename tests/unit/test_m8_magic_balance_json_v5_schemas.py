"""ADR-0058 balance5 schemas define the independent full-source assertions."""
from copy import deepcopy
from importlib.resources import files
import json
import unittest

from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from tests.unit.test_m8_magic_balance_json_v5 import FIELD, document
from towr.adapters import magic_json_schema as production
from towr.adapters.magic_json_schema import validate_magic_balance_document


class M8MagicBalanceJsonV5SchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = {
            schema['$id']: schema
            for path in files('towr.adapters.schemas').iterdir() if path.name.endswith('.schema.json')
            for schema in (json.loads(path.read_text(encoding='utf-8')),)
        }
        cls.registry = Registry().with_resources(
            (uri, Resource.from_contents(schema)) for uri, schema in cls.documents.items())

    def test_final_registry_and_every_reference_are_bundled(self):
        self.assertEqual(len(self.documents), 54)
        self.assertEqual(sum(uri.startswith('urn:towr:magic-') for uri in self.documents), 36)
        for uri, schema in self.documents.items():
            Draft202012Validator.check_schema(schema)
            for ref in self._refs(schema):
                with self.subTest(uri=uri, ref=ref):
                    self.registry.resolver(uri).lookup(ref)
        for kind in ('request', 'result', 'error'):
            validator = production._validator(kind, 'balance', '5')
            for uri, resource in validator._registry.items():
                for ref in self._refs(resource.contents):
                    with self.subTest(kind=kind, uri=uri, ref=ref):
                        validator._registry.resolver(uri).lookup(ref)
        self.assertEqual(production._validator.cache_info().maxsize, 36)

    def test_required_reserve_and_family_fields_remain_independent(self):
        for miscast in (False, True):
            for stationary in (False, True):
                for repeated in (False, True):
                    for crushed in (False, True):
                        raw = document(miscast=miscast, stationary=stationary,
                                       repeated=repeated, crushed=crushed)
                        validate_magic_balance_document(raw, schema_version='5')
        raw = document(crushed=True)
        raw['reserve']['scenario'][FIELD] = None
        validate_magic_balance_document(raw, schema_version='5')
        for location in ('reserve', 'generation'):
            for value in (None, 'next_test_with_journal_witnesses'):
                invalid = deepcopy(document(crushed=True))
                node = invalid['reserve']['scenario'] if location == 'reserve' else invalid['generation']
                del node[FIELD]
                with self.subTest(location=location, value=value), self.assertRaises(ValidationError):
                    validate_magic_balance_document(invalid, schema_version='5')
                node[FIELD] = value
                validate_magic_balance_document(invalid, schema_version='5')

    def test_exact_nullable_enum_closed_objects_and_full_v5_echo(self):
        raw = document(crushed=True)
        for location in ('reserve', 'generation'):
            for value in (False, True, 0, 1, {}, [], '', 'NEXT_TEST_WITH_JOURNAL_WITNESSES', 'unknown'):
                invalid = deepcopy(raw)
                node = invalid['reserve']['scenario'] if location == 'reserve' else invalid['generation']
                node[FIELD] = value
                with self.subTest(location=location, value=value), self.assertRaises(ValidationError):
                    validate_magic_balance_document(invalid, schema_version='5')
        output = json.loads(files('towr.adapters.schemas').joinpath(
            'magic-balance-result-v5.schema.json').read_text(encoding='utf-8'))
        self.assertEqual(output['properties']['request']['$ref'], 'urn:towr:magic-balance:request:5')
        self.assertEqual(self.documents['urn:towr:magic-balance:request:5']['properties']['reserve']['properties']
                         ['scenario']['$ref'], 'urn:towr:magic-simulation:request:5#/$defs/scenario')
        for version in ('1', '2', '3', '4'):
            old = deepcopy(raw)
            old['schema_version'] = version
            with self.subTest(version=version), self.assertRaises(ValidationError):
                validate_magic_balance_document(old, schema_version=version)

    @staticmethod
    def _refs(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == '$ref':
                    yield child
                else:
                    yield from M8MagicBalanceJsonV5SchemaTests._refs(child)
        elif isinstance(value, list):
            for child in value:
                yield from M8MagicBalanceJsonV5SchemaTests._refs(child)


if __name__ == '__main__':
    unittest.main()
