"""ADR-0062 structural profile contract and offline JSON6 schema closure."""
from copy import deepcopy
from importlib.resources import files
import json
import unittest

from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from pathlib import Path
from unittest.mock import patch
from towr.adapters import magic_json_schema as production


FIELD = 'battered_leg_continuation'
PERMISSIONS = ('miscast_continuation', 'stationary_wound_continuation',
               'repeated_leg_spasm_continuation', 'crushed_rib_continuation', FIELD)


def document(profile=None):
    data = json.loads((Path(__file__).resolve().parents[2] /
        'docs/examples/m8/json/magic-simulation-v6.request.json').read_text(encoding='utf-8'))
    data['schema_version'] = '6'
    data['scenario'][FIELD] = None if profile is None else {'endurance_profile': profile, 'prone_policy': None}
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
        self.assertEqual(len(self.documents), 32)
        self.assertEqual(sum(uri.startswith('urn:towr:magic-') for uri in self.documents), 6)
        for uri, schema in self.documents.items():
            Draft202012Validator.check_schema(schema)
            for ref in references(schema):
                with self.subTest(uri=uri, ref=ref):
                    self.registry.resolver(uri).lookup(ref)
        for family in ('simulation', 'balance'):
            for kind in ('request', 'result', 'error'):
                schema = self.documents[f'urn:towr:magic-{family}:{kind}:6']
                self.assertEqual(schema['properties']['schema_version'], {'type': 'string', 'const': '6'})
        self.assertEqual(production._validator.cache_info().maxsize, 6)

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
        invalid_values = (False, True, 0, 1, [], '', {}, {'endurance_profile': None, 'prone_policy': None},
            {'endurance_profile': {'dice': 2}, 'prone_policy': None}, {'endurance_profile': {'threshold': 5}, 'prone_policy': None},
            {'endurance_profile': {'dice': 0, 'threshold': 5}, 'prone_policy': None},
            {'endurance_profile': {'dice': -1, 'threshold': 5}, 'prone_policy': None},
            {'endurance_profile': {'dice': True, 'threshold': 5}, 'prone_policy': None},
            {'endurance_profile': {'dice': 2.5, 'threshold': 5}, 'prone_policy': None},
            {'endurance_profile': {'dice': '2', 'threshold': 5}, 'prone_policy': None},
            {'endurance_profile': {'dice': 2, 'threshold': False}, 'prone_policy': None},
            {'endurance_profile': {'dice': 2, 'threshold': 0}, 'prone_policy': None},
            {'endurance_profile': {'dice': 2, 'threshold': 11}, 'prone_policy': None},
            {'endurance_profile': {'dice': 2, 'threshold': 5, 'pool_cap': 4}, 'prone_policy': None},
            {'endurance_profile': {'dice': 2, 'threshold': 5}, 'actor_id': 'wizard', 'prone_policy': None})
        for value in invalid_values:
            invalid = document()
            invalid['scenario'][FIELD] = value
            with self.subTest(value=value), self.assertRaises(ValidationError):
                production.validate_magic_simulation_document(invalid, schema_version='6')

    def test_noncurrent_versions_are_rejected_before_loading_resources(self):
        production._validator.cache_clear()
        with patch.object(production, 'files', side_effect=AssertionError('no legacy lookup')) as lookup:
            for family in ('simulation', 'balance'):
                for version in (None, True, 6, '1', '2', '3', '4', '5', '7', '06'):
                    with self.subTest(family=family, version=version), self.assertRaises(ValueError):
                        production._validator('request', family, version)
            lookup.assert_not_called()

    def test_registry_is_only_six_current_roots_and_shared_definitions(self):
        production._validator.cache_clear()
        for family in ('simulation', 'balance'):
            for kind in ('request', 'result', 'error'):
                validator = production._validator(kind, family)
                self.assertEqual(validator.schema['$id'], f'urn:towr:magic-{family}:{kind}:6')
                self.assertEqual(len(validator._registry), 7)
                for uri, resource in validator._registry.items():
                    for ref in references(resource.contents):
                        validator._registry.resolver(uri).lookup(ref)
        self.assertEqual(production._validator.cache_info().currsize, 6)
        self.assertIn('urn:towr:magic:common', validator._registry)
        production.validate_magic_simulation_document(document())

    def test_enum_permissions_and_miscast_facts_remain_strict(self):
        values = {'stationary_wound_continuation': 'leg_spasm_stand_and_continue',
                  'repeated_leg_spasm_continuation': 'stand_once_with_journal_witnesses',
                  'crushed_rib_continuation': 'next_test_with_journal_witnesses'}
        for field, value in values.items():
            raw = document()
            raw['scenario'][field] = value
            production.validate_magic_simulation_document(raw)
            for invalid in (True, False, 0, 1, {}, [], '', value.upper()):
                raw['scenario'][field] = invalid
                with self.subTest(field=field, invalid=invalid), self.assertRaises(ValidationError):
                    production.validate_magic_simulation_document(raw)
        raw = document()
        raw['scenario']['miscast_continuation'] = {
            'choice': 'decline_cast_before_miscast', 'prone_policy': 'self_stand_when_safe',
            'facts': dict.fromkeys(('all_combatants_in_roster', 'no_external_short_range_creatures',
                'unmounted_combatants_only', 'no_effect_immunities', 'no_cross_zone_close'), True)}
        production.validate_magic_simulation_document(raw)
        for key in tuple(raw['scenario']['miscast_continuation']['facts']):
            raw['scenario']['miscast_continuation']['facts'][key] = False
            with self.subTest(fact=key), self.assertRaises(ValidationError):
                production.validate_magic_simulation_document(raw)
            raw['scenario']['miscast_continuation']['facts'][key] = True

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
