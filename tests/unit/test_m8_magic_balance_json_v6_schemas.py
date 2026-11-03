"""ADR-0062 balance6 keeps both complete nullable profile assertions."""
from copy import deepcopy
from importlib.resources import files
from itertools import product
import json
import unittest

from jsonschema import ValidationError

from pathlib import Path
from tests.unit.test_m8_magic_json_v6_schemas import FIELD, PERMISSIONS, references
from towr.adapters import magic_json_schema as production


def document(profile=None):
    data = json.loads((Path(__file__).resolve().parents[2] /
        'docs/examples/m8/json/magic-balance-v6.request.json').read_text(encoding='utf-8'))
    data['schema_version'] = '6'
    value = None if profile is None else {'endurance_profile': profile, 'prone_policy': None}
    data['reserve']['scenario'][FIELD] = deepcopy(value)
    data['generation'][FIELD] = deepcopy(value)
    return data


class MagicBalanceJsonV6SchemaTests(unittest.TestCase):
    def test_both_assertions_are_required_but_matching_remains_typed_semantics(self):
        for reserve, family in product((None, {'endurance_profile': {'dice': 2, 'threshold': 5}, 'prone_policy': None},
                                       {'endurance_profile': {'dice': 2, 'threshold': 4}, 'prone_policy': None}), repeat=2):
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
        invalid_values = (True, False, '2d/5', {}, {'endurance_profile': {}, 'prone_policy': None},
            {'endurance_profile': {'dice': 2, 'threshold': 0}, 'prone_policy': None},
            {'endurance_profile': {'dice': 2, 'threshold': 11}, 'prone_policy': None},
            {'endurance_profile': {'dice': False, 'threshold': 5}, 'prone_policy': None},
            {'endurance_profile': {'dice': 2, 'threshold': 5, 'pool_cap': 4}, 'prone_policy': None},
            {'endurance_profile': {'dice': 2, 'threshold': 5}, 'facts': {}, 'prone_policy': None})
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
        self.assertEqual(production._validator.cache_info().maxsize, 6)

    def test_phase_errors_keep_closed_context_and_current_metadata(self):
        for code, path, candidate, counts, stage in (
            ('invalid_input', '/generation', None, None, None),
            ('generation_failed', '/generation', 'family:1', [1, 0], None),
            ('evaluation_failed', '/evaluation', 'family:1', None, 1),
        ):
            raw = dict(schema_version='6', kind='magic_balance_error', request_id='input',
                       error=dict(code=code, path=path, message='invalid',
                                  candidate_id=candidate, counts=counts, stage_index=stage))
            production.validate_magic_balance_document(raw, 'error')
            for changes in ({'schema_version': '5'}, {'kind': 'magic_simulation_error'}, {'unknown': None}):
                with self.subTest(code=code, changes=changes), self.assertRaises(ValidationError):
                    production.validate_magic_balance_document(dict(raw, **changes), 'error')
            invalid = deepcopy(raw)
            invalid['error']['counts'] = [1] if counts is None else None
            if code == 'generation_failed':
                invalid['error']['stage_index'] = 1
            with self.subTest(code=code, wrong_phase=True), self.assertRaises(ValidationError):
                production.validate_magic_balance_document(invalid, 'error')

    def test_reserve_generation_and_root_are_closed(self):
        for location in ('root', 'reserve', 'scenario', 'generation'):
            raw = document()
            node = raw if location == 'root' else raw['reserve']['scenario'] if location == 'scenario' else raw[location]
            node['unknown'] = None
            with self.subTest(location=location), self.assertRaises(ValidationError):
                production.validate_magic_balance_document(raw)


if __name__ == '__main__':
    unittest.main()
