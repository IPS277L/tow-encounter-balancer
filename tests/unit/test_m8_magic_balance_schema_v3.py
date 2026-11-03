"""ADR-0051 balance3 closed shapes, independent permissions and local closure."""
from copy import deepcopy
from importlib.resources import files
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator, ValidationError

from tests.unit.test_m8_magic_balance_json import document as v1_document
from tests.unit.test_m8_magic_balance_json_v2 import document as v2_document
from towr.adapters import magic_json_schema as schemas


FIELD = 'stationary_wound_continuation'
VALUE = 'leg_spasm_stand_and_continue'


def document(*, miscast=False, stationary=None):
    source = v2_document(opted=miscast)
    source['schema_version'] = '3'
    source['reserve']['scenario'][FIELD] = stationary
    source['generation'][FIELD] = stationary
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


class MagicBalanceSchemaV3Tests(unittest.TestCase):
    def test_three_packaged_schemas_and_every_transitive_reference_resolve_locally(self):
        for kind in ('request', 'result', 'error'):
            schema = json.loads(files('towr.adapters.schemas').joinpath(
                f'magic-balance-{kind}-v3.schema.json').read_text(encoding='utf-8'))
            self.assertEqual(schema['$id'], f'urn:towr:magic-balance:{kind}:3')
            Draft202012Validator.check_schema(schema)
            validator = schemas._validator(kind, 'balance', '3')
            self.assertEqual(validator.schema, schema)
            # The real production registry must supply all fragments, including
            # refs inside referenced v1/v2 documents, without retrieval.
            resources = tuple(validator._registry.items())
            self.assertEqual(len(resources), 19)
            for uri, resource in resources:
                for ref in references(resource.contents):
                    with self.subTest(kind=kind, uri=uri, ref=ref):
                        validator._registry.resolver(uri).lookup(ref)

    def test_four_combinations_keep_reserve_and_family_fields_independent(self):
        for miscast in (False, True):
            for stationary in (None, VALUE):
                source = document(miscast=miscast, stationary=stationary)
                before = deepcopy(source)
                with self.subTest(miscast=miscast, stationary=stationary):
                    schemas.validate_magic_balance_document(source, schema_version='3')
                self.assertEqual(source, before)
                # Schema admits each assertion independently; their exact
                # equality is the separate typed parser admission contract.
                source['generation'][FIELD] = VALUE if stationary is None else None
                schemas.validate_magic_balance_document(source, schema_version='3')

    def test_stationary_fields_reject_every_non_nullable_non_enum_shape(self):
        for location in ('reserve', 'generation'):
            for value in (False, True, 0, 1, {}, [], '', 'LEG_SPASM_STAND_AND_CONTINUE',
                          'self_stand_when_safe', {'choice': VALUE}):
                source = document()
                target = source['reserve']['scenario'] if location == 'reserve' else source['generation']
                target[FIELD] = value
                with self.subTest(location=location, value=value), self.assertRaises(ValidationError):
                    schemas.validate_magic_balance_document(source, schema_version='3')

    def test_both_permissions_are_required_and_all_existing_objects_stay_closed(self):
        for location in ('reserve', 'generation'):
            for field in (FIELD, 'miscast_continuation'):
                source = document()
                target = source['reserve']['scenario'] if location == 'reserve' else source['generation']
                del target[field]
                with self.subTest(location=location, missing=field), self.assertRaises(ValidationError):
                    schemas.validate_magic_balance_document(source, schema_version='3')
        for location in ('root', 'reserve', 'scenario', 'generation', 'family_miscast', 'family_facts'):
            source = document(miscast=True)
            target = {
                'root': source,
                'reserve': source['reserve'],
                'scenario': source['reserve']['scenario'],
                'generation': source['generation'],
                'family_miscast': source['generation']['miscast_continuation'],
                'family_facts': source['generation']['miscast_continuation']['facts'],
            }[location]
            target['unknown'] = None
            with self.subTest(unknown=location), self.assertRaises(ValidationError):
                schemas.validate_magic_balance_document(source, schema_version='3')
        for location in ('reserve', 'generation'):
            source = document(miscast=True)
            target = source['reserve']['scenario'] if location == 'reserve' else source['generation']
            target['miscast_continuation']['facts']['no_effect_immunities'] = False
            with self.subTest(invalid_fact=location), self.assertRaises(ValidationError):
                schemas.validate_magic_balance_document(source, schema_version='3')

    def test_result_requires_full_request3_echo_and_keeps_old_aggregate_shape(self):
        root = Path(__file__).resolve().parents[2]
        output = json.loads((root / 'docs/examples/m8/json/magic-balance-v2.result.json').read_text(encoding='utf-8'))
        output['schema_version'] = output['request']['schema_version'] = '3'
        output['request']['reserve']['scenario'][FIELD] = None
        output['request']['generation'][FIELD] = None
        schemas.validate_magic_balance_document(output, 'result', schema_version='3')
        for location in ('outer', 'request'):
            source = deepcopy(output)
            (source if location == 'outer' else source['request'])['schema_version'] = '2'
            with self.subTest(wrong_version=location), self.assertRaises(ValidationError):
                schemas.validate_magic_balance_document(source, 'result', schema_version='3')
        for location in ('reserve', 'generation'):
            source = deepcopy(output)
            target = source['request']['reserve']['scenario'] if location == 'reserve' else source['request']['generation']
            del target[FIELD]
            with self.subTest(missing_echo=location), self.assertRaises(ValidationError):
                schemas.validate_magic_balance_document(source, 'result', schema_version='3')
        source = deepcopy(output)
        source['stationary_wound_continuation'] = VALUE
        with self.assertRaises(ValidationError):
            schemas.validate_magic_balance_document(source, 'result', schema_version='3')

    def test_error3_preserves_input_generation_and_evaluation_context_shapes(self):
        for code, path, candidate, counts, stage in (
            ('invalid_input', '/generation/' + FIELD, None, None, None),
            ('generation_failed', '/generation', 'family:1', [1, 0], None),
            ('evaluation_failed', '/evaluation', 'family:1', None, 1),
        ):
            source = dict(schema_version='3', kind='magic_balance_error', request_id='input',
                          error=dict(code=code, path=path, message='bad input',
                                     candidate_id=candidate, counts=counts, stage_index=stage))
            with self.subTest(code=code):
                schemas.validate_magic_balance_document(source, 'error', schema_version='3')
            for changes in ({'schema_version': '2'}, {'kind': 'magic_simulation_error'}, {'unknown': None}):
                with self.subTest(code=code, changes=changes), self.assertRaises(ValidationError):
                    schemas.validate_magic_balance_document(dict(source, **changes), 'error', schema_version='3')
            wrong = deepcopy(source)
            wrong['error']['counts'] = [1] if counts is None else None
            if code == 'generation_failed':
                wrong['error']['stage_index'] = 1
            with self.subTest(wrong_phase=code), self.assertRaises(ValidationError):
                schemas.validate_magic_balance_document(wrong, 'error', schema_version='3')

    def test_default1_and_old1_2_reject_new_fields_even_when_null(self):
        schemas.validate_magic_balance_document(v1_document())
        with self.assertRaises(ValidationError):
            schemas.validate_magic_balance_document(document())
        for version, legacy in (('1', v1_document()), ('2', v2_document(opted=False))):
            schemas.validate_magic_balance_document(legacy, schema_version=version)
            for location in ('reserve', 'generation'):
                for value in (None, VALUE):
                    source = deepcopy(legacy)
                    target = source['reserve']['scenario'] if location == 'reserve' else source['generation']
                    target[FIELD] = value
                    with self.subTest(version=version, location=location, value=value), self.assertRaises(ValidationError):
                        schemas.validate_magic_balance_document(source, schema_version=version)

    def test_registry_contains_all_current_family_kind_versions_and_bundled_schemas(self):
        schemas._validator.cache_clear()
        for family in ('simulation', 'balance'):
            for version in ('1', '2', '3', '4', '5', '6'):
                for kind in ('request', 'result', 'error'):
                    validator = schemas._validator(kind, family, version)
                    self.assertEqual(validator.schema['$id'], f'urn:towr:magic-{family}:{kind}:{version}')
        self.assertEqual(schemas._validator.cache_info().currsize, 36)
        self.assertEqual(schemas._validator.cache_info().maxsize, 36)
        names = tuple(p.name for p in files('towr.adapters.schemas').iterdir() if p.name.endswith('.schema.json'))
        self.assertEqual(len(names), 54)
        self.assertEqual(sum(name.startswith('magic-') for name in names), 36)

    def test_unsupported_versions_reject_before_schema_files_are_loaded(self):
        schemas._validator.cache_clear()
        with patch.object(schemas, 'files', side_effect=AssertionError('unsupported version must not load files')) as lookup:
            for version in (None, 3, True, '03', '7'):
                with self.subTest(version=version), self.assertRaises(ValueError):
                    schemas.validate_magic_balance_document({}, schema_version=version)
            with self.assertRaisesRegex(ValueError, 'unsupported magic balance schema version'):
                schemas._validator('request', 'balance', '7')
            lookup.assert_not_called()


if __name__ == '__main__':
    unittest.main()
