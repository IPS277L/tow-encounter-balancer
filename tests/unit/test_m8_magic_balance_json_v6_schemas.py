"""ADR-0062 balance6 keeps both complete nullable profile assertions."""
from copy import deepcopy
from importlib.resources import files
from itertools import product
import json
import unittest

from jsonschema import ValidationError

from tests.unit.test_m8_magic_balance_json_v5 import document as version5
from tests.unit.test_m8_magic_json_v6_schemas import FIELD, PERMISSIONS, references
from towr.adapters import magic_json_schema as production


def document(profile=None):
    data = version5()
    data['schema_version'] = '6'
    value = None if profile is None else {'endurance_profile': profile}
    data['reserve']['scenario'][FIELD] = deepcopy(value)
    data['generation'][FIELD] = deepcopy(value)
    return data


class MagicBalanceJsonV6SchemaTests(unittest.TestCase):
    def test_both_assertions_are_required_but_matching_remains_typed_semantics(self):
        for reserve, family in product((None, {'endurance_profile': {'dice': 2, 'threshold': 5}},
                                       {'endurance_profile': {'dice': 2, 'threshold': 4}}), repeat=2):
            raw = document()
            raw['reserve']['scenario'][FIELD], raw['generation'][FIELD] = reserve, family
            production.validate_magic_balance_document(raw, schema_version='6')
        for location in ('reserve', 'generation'):
            for field in PERMISSIONS:
                raw = document()
                node = raw['reserve']['scenario'] if location == 'reserve' else raw['generation']
                del node[field]
                with self.subTest(location=location, field=field), self.assertRaises(ValidationError):
                    production.validate_magic_balance_document(raw, schema_version='6')

    def test_each_nullable_profile_object_is_closed_and_rejects_invalid_shapes(self):
        invalid_values = (True, False, '2d/5', {}, {'endurance_profile': {}},
            {'endurance_profile': {'dice': 2, 'threshold': 0}},
            {'endurance_profile': {'dice': 2, 'threshold': 11}},
            {'endurance_profile': {'dice': False, 'threshold': 5}},
            {'endurance_profile': {'dice': 2, 'threshold': 5, 'pool_cap': 4}},
            {'endurance_profile': {'dice': 2, 'threshold': 5}, 'facts': {}})
        for location in ('reserve', 'generation'):
            for value in invalid_values:
                raw = document()
                node = raw['reserve']['scenario'] if location == 'reserve' else raw['generation']
                node[FIELD] = value
                with self.subTest(location=location, value=value), self.assertRaises(ValidationError):
                    production.validate_magic_balance_document(raw, schema_version='6')
            raw = document({'dice': 11, 'threshold': 5})
            production.validate_magic_balance_document(raw, schema_version='6')

    def test_reserve_scenario_and_result_echo_resolve_to_the_six_contract(self):
        for kind in ('request', 'result', 'error'):
            validator = production._validator(kind, 'balance', '6')
            for uri, resource in validator._registry.items():
                for ref in references(resource.contents):
                    with self.subTest(kind=kind, uri=uri, ref=ref):
                        validator._registry.resolver(uri).lookup(ref)
        request = json.loads(files('towr.adapters.schemas').joinpath('magic-balance-request-v6.schema.json').read_text(encoding='utf-8'))
        result = json.loads(files('towr.adapters.schemas').joinpath('magic-balance-result-v6.schema.json').read_text(encoding='utf-8'))
        self.assertEqual(request['properties']['reserve']['properties']['scenario']['$ref'],
                         'urn:towr:magic-simulation:request:6#/$defs/scenario')
        self.assertEqual(result['properties']['request']['$ref'], 'urn:towr:magic-balance:request:6')
        self.assertEqual(production._validator.cache_info().maxsize, 36)

    def test_old_versions_refuse_both_new_fields_even_when_null(self):
        for version in range(1, 6):
            old = version5()
            old['schema_version'] = str(version)
            for location in ('reserve', 'generation'):
                node = old['reserve']['scenario'] if location == 'reserve' else old['generation']
                for introduced, name in enumerate(PERMISSIONS[:-1], start=2):
                    if introduced > version:
                        del node[name]
            production.validate_magic_balance_document(old, schema_version=str(version))
            for location in ('reserve', 'generation'):
                invalid = deepcopy(old)
                node = invalid['reserve']['scenario'] if location == 'reserve' else invalid['generation']
                node[FIELD] = None
                with self.subTest(version=version, location=location), self.assertRaises(ValidationError):
                    production.validate_magic_balance_document(invalid, schema_version=str(version))


if __name__ == '__main__':
    unittest.main()
