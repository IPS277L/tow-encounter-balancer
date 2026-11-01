"""ADR-0051 simulation3 shape/registry closure; balance3 stays unsupported here."""
from copy import deepcopy
from importlib.resources import files
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator, ValidationError

from tests.unit.test_m8_magic_json import document as v1_document
from tests.unit.test_m8_magic_json_v2 import document as v2_document
from towr.adapters import magic_json_schema as schemas


FIELD = 'stationary_wound_continuation'
VALUE = 'leg_spasm_stand_and_continue'


def document(*, miscast=False, stationary=None):
    source = v2_document(opted=miscast)
    source['schema_version'] = '3'
    source['scenario'][FIELD] = stationary
    return source


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


class MagicSimulationSchemaV3Tests(unittest.TestCase):
    def test_three_packaged_v3_schemas_have_exact_ids_and_local_reference_closure(self):
        for kind in ('request', 'result', 'error'):
            schema = json.loads(files('towr.adapters.schemas').joinpath(
                f'magic-simulation-{kind}-v3.schema.json').read_text(encoding='utf-8'))
            self.assertEqual(schema['$id'], f'urn:towr:magic-simulation:{kind}:3')
            Draft202012Validator.check_schema(schema)
            validator = schemas._validator(kind, 'simulation', '3')
            self.assertEqual(validator.schema, schema)
            for ref in references(schema):
                # Resolve against the real production registry, not a separate
                # test registry which might accidentally provide missing refs.
                with self.subTest(kind=kind, ref=ref):
                    validator._registry.resolver(schema['$id']).lookup(ref)

    def test_all_four_policy_combinations_and_explicit_null_are_valid(self):
        for miscast in (False, True):
            for stationary in (None, VALUE):
                data = document(miscast=miscast, stationary=stationary)
                original = deepcopy(data)
                with self.subTest(miscast=miscast, stationary=stationary):
                    schemas.validate_magic_simulation_document(data, schema_version='3')
                self.assertEqual(data, original)

    def test_stationary_permission_is_only_null_or_the_exact_string(self):
        for value in (False, True, 0, 1, {}, [], '', 'LEG_SPASM_STAND_AND_CONTINUE',
                      'self_stand_when_safe', {'choice': VALUE}):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                schemas.validate_magic_simulation_document(document(stationary=value), schema_version='3')

    def test_scenario_requires_both_permissions_and_remains_closed(self):
        for key in ('miscast_continuation', FIELD):
            data = document()
            del data['scenario'][key]
            with self.subTest(missing=key), self.assertRaises(ValidationError):
                schemas.validate_magic_simulation_document(data, schema_version='3')
        for node in ('root', 'scenario', 'miscast'):
            data = document(miscast=True)
            target = data if node == 'root' else data['scenario'] if node == 'scenario' else data['scenario']['miscast_continuation']
            target['unknown'] = None
            with self.subTest(unknown=node), self.assertRaises(ValidationError):
                schemas.validate_magic_simulation_document(data, schema_version='3')
        data = document(miscast=True)
        data['scenario']['miscast_continuation']['facts']['no_effect_immunities'] = False
        with self.assertRaises(ValidationError):
            schemas.validate_magic_simulation_document(data, schema_version='3')

    def test_result_echo_and_error_envelopes_require_their_own_version3(self):
        root = Path(__file__).resolve().parents[2]
        result = json.loads((root / 'docs/examples/m8/json/magic-simulation-v2.result.json').read_text(encoding='utf-8'))
        result['schema_version'] = result['request']['schema_version'] = '3'
        result['request']['scenario'][FIELD] = None
        schemas.validate_magic_simulation_document(result, 'result', schema_version='3')
        for location in ('outer', 'request'):
            wrong = deepcopy(result)
            (wrong if location == 'outer' else wrong['request'])['schema_version'] = '2'
            with self.subTest(version=location), self.assertRaises(ValidationError):
                schemas.validate_magic_simulation_document(wrong, 'result', schema_version='3')
        missing = deepcopy(result)
        del missing['request']['scenario'][FIELD]
        with self.assertRaises(ValidationError):
            schemas.validate_magic_simulation_document(missing, 'result', schema_version='3')
        error = dict(schema_version='3', kind='magic_simulation_error', request_id=None,
                     error=dict(code='invalid_input', path='/scenario/' + FIELD, message='bad value'))
        schemas.validate_magic_simulation_document(error, 'error', schema_version='3')
        for changes in ({'schema_version': '2'}, {'kind': 'magic_balance_error'}, {'unknown': None}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                schemas.validate_magic_simulation_document(dict(error, **changes), 'error', schema_version='3')

    def test_default_v1_and_old_versions_do_not_accept_the_new_field_even_null(self):
        schemas.validate_magic_simulation_document(v1_document())
        with self.assertRaises(ValidationError): schemas.validate_magic_simulation_document(document())
        for version, source in (('1', v1_document()), ('2', v2_document(opted=False))):
            for value in (None, VALUE):
                data = deepcopy(source)
                data['scenario'][FIELD] = value
                with self.subTest(version=version, value=value), self.assertRaises(ValidationError):
                    schemas.validate_magic_simulation_document(data, schema_version=version)

    def test_balance3_rejects_before_loading_any_schema_file(self):
        schemas._validator.cache_clear()
        with patch.object(schemas, 'files', side_effect=AssertionError('no file lookup for unsupported balance3')) as lookup:
            with self.assertRaisesRegex(ValueError, 'unsupported magic balance schema version'):
                schemas.validate_magic_balance_document({}, schema_version='3')
            with self.assertRaisesRegex(ValueError, 'unsupported magic balance schema version'):
                schemas._validator('request', 'balance', '3')
            lookup.assert_not_called()

    def test_registry_caches_all_fifteen_current_magic_family_kind_versions(self):
        schemas._validator.cache_clear()
        for family, versions in (('simulation', ('1', '2', '3')), ('balance', ('1', '2'))):
            for version in versions:
                for kind in ('request', 'result', 'error'):
                    validator = schemas._validator(kind, family, version)
                    self.assertEqual(validator.schema['$id'], f'urn:towr:magic-{family}:{kind}:{version}')
        self.assertEqual(schemas._validator.cache_info().currsize, 15)
        self.assertEqual(schemas._validator.cache_info().maxsize, 15)
        names = tuple(p.name for p in files('towr.adapters.schemas').iterdir() if p.name.endswith('.schema.json'))
        self.assertEqual(len(names), 33)
        self.assertEqual(sum(name.startswith('magic-') for name in names), 15)
        for version in (None, 3, True, '03', '4'):
            with self.subTest(version=version), self.assertRaises(ValueError):
                schemas.validate_magic_simulation_document({}, schema_version=version)


if __name__ == '__main__':
    unittest.main()
