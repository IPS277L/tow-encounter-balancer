"""ADR-0054 structural v4 contracts and bundled-only reference closure."""
from copy import deepcopy
from importlib.resources import files
from itertools import product
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from towr.adapters import magic_json_schema as production


FIELD = 'repeated_leg_spasm_continuation'
VALUE = 'stand_once_with_journal_witnesses'
BASE = 'stationary_wound_continuation'
BASE_VALUE = 'leg_spasm_stand_and_continue'
PERMISSIONS = ('miscast_continuation', BASE, FIELD)
EXAMPLES = Path(__file__).resolve().parents[2] / 'docs/examples/m8/json'


def read_example(family, version='3', kind='request'):
    return json.loads((EXAMPLES / f'magic-{family}-v{version}.{kind}.json').read_text(encoding='utf-8'))


def nodes(document, family):
    return (document['scenario'],) if family == 'simulation' else (document['reserve']['scenario'], document['generation'])


def request(family, *, miscast=False, stationary=False, repeated=False):
    document = read_example(family)
    document['schema_version'] = '4'
    for node in nodes(document, family):
        if not miscast:
            node['miscast_continuation'] = None
        node[BASE] = BASE_VALUE if stationary else None
        node[FIELD] = VALUE if repeated else None
    return document


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


class MagicJsonV4SchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = {
            document['$id']: document
            for path in files('towr.adapters.schemas').iterdir() if path.name.endswith('.schema.json')
            for document in (json.loads(path.read_text(encoding='utf-8')),)
        }
        cls.registry = Registry().with_resources(
            (uri, Resource.from_contents(document)) for uri, document in cls.documents.items())

    def validator(self, family, kind='request', version='4'):
        return Draft202012Validator(self.documents[f'urn:towr:magic-{family}:{kind}:{version}'], registry=self.registry)

    def test_six_new_schema_ids_and_transitive_offline_bundle_closure(self):
        self.assertEqual(len(self.documents), 54)
        self.assertEqual(sum(uri.startswith('urn:towr:magic-') for uri in self.documents), 36)
        for uri, document in self.documents.items():
            Draft202012Validator.check_schema(document)
            for ref in references(document):
                with self.subTest(uri=uri, ref=ref):
                    self.registry.resolver(uri).lookup(ref)
        for family, kind in product(('simulation', 'balance'), ('request', 'result', 'error')):
            uri = f'urn:towr:magic-{family}:{kind}:4'
            self.assertEqual(self.validator(family, kind).schema['$id'], uri)
            self.assertEqual(self.documents[uri]['properties']['schema_version'], {'type': 'string', 'const': '4'})

    def test_six_valid_and_two_semantically_invalid_combinations_remain_structural(self):
        # Dependency/equality are typed admission, preserving semantic pointers;
        # structural schemas must not add a different if/then error priority.
        for family in ('simulation', 'balance'):
            validator = self.validator(family)
            for miscast, stationary, repeated in product((False, True), repeat=3):
                document = request(family, miscast=miscast, stationary=stationary, repeated=repeated)
                before = deepcopy(document)
                with self.subTest(family=family, policies=(miscast, stationary, repeated)):
                    validator.validate(document)
                self.assertEqual(document, before)
            if family == 'balance':
                document = request(family, stationary=True, repeated=True)
                document['generation'][FIELD] = None
                validator.validate(document)

    def test_repeat_fields_are_only_null_or_the_exact_string(self):
        for family in ('simulation', 'balance'):
            for index in range(1 if family == 'simulation' else 2):
                for value in (False, True, 0, 1, {}, [], '', 'STAND_ONCE_WITH_JOURNAL_WITNESSES',
                              'self_stand_when_safe', {'choice': VALUE}):
                    document = request(family, stationary=True)
                    nodes(document, family)[index][FIELD] = value
                    with self.subTest(family=family, node=index, value=value), self.assertRaises(ValidationError):
                        self.validator(family).validate(document)

    def test_all_three_permissions_are_required_at_each_location(self):
        for family in ('simulation', 'balance'):
            for index in range(1 if family == 'simulation' else 2):
                for field in PERMISSIONS:
                    document = request(family)
                    del nodes(document, family)[index][field]
                    with self.subTest(family=family, node=index, missing=field), self.assertRaises(ValidationError):
                        self.validator(family).validate(document)

    def test_scenario_and_generation_are_own_closed_objects_with_old_fragments(self):
        scenario = self.documents['urn:towr:magic-simulation:request:4']['$defs']['scenario']
        generation = self.documents['urn:towr:magic-balance:request:4']['properties']['generation']
        self.assertNotIn('allOf', scenario)
        self.assertNotIn('allOf', generation)
        for family in ('simulation', 'balance'):
            document = request(family, miscast=True, stationary=True, repeated=True)
            targets = [('root', document), *[(f'policy:{i}', node) for i, node in enumerate(nodes(document, family))]]
            if family == 'balance':
                targets.append(('reserve', document['reserve']))
            for label, target in targets:
                target['unknown'] = None
                with self.subTest(family=family, unknown=label), self.assertRaises(ValidationError):
                    self.validator(family).validate(document)
                del target['unknown']
            for index, node in enumerate(nodes(document, family)):
                node['miscast_continuation']['facts']['no_effect_immunities'] = False
                with self.subTest(family=family, invalid_miscast=index), self.assertRaises(ValidationError):
                    self.validator(family).validate(document)
                node['miscast_continuation']['facts']['no_effect_immunities'] = True

    def test_result4_requires_own_version_and_complete_request4_echo(self):
        for family in ('simulation', 'balance'):
            output = read_example(family, kind='result')
            output['schema_version'] = '4'
            output['request'] = request(family, stationary=True, repeated=True)
            validator = self.validator(family, 'result')
            validator.validate(output)
            for target in ('outer', 'request'):
                wrong = deepcopy(output)
                (wrong if target == 'outer' else wrong['request'])['schema_version'] = '3'
                with self.subTest(family=family, wrong_version=target), self.assertRaises(ValidationError):
                    validator.validate(wrong)
            for index in range(len(nodes(output['request'], family))):
                wrong = deepcopy(output)
                del nodes(wrong['request'], family)[index][FIELD]
                with self.subTest(family=family, missing_echo=index), self.assertRaises(ValidationError):
                    validator.validate(wrong)
            wrong = dict(output, repeated_leg_spasm_continuation=VALUE)
            with self.assertRaises(ValidationError):
                validator.validate(wrong)

    def test_error4_keeps_old_input_runtime_and_balance_phase_shapes(self):
        for family in ('simulation', 'balance'):
            validator = self.validator(family, 'error')
            cases = (('invalid_input', '/scenario', None, None, None),)
            if family == 'simulation':
                cases += (('simulation_failed', None, None, None, None),)
            else:
                cases += (('generation_failed', '/generation', 'candidate', [1, 0], None),
                          ('evaluation_failed', '/evaluation', 'candidate', None, 1))
            for code, path, candidate, counts, stage in cases:
                error = dict(schema_version='4', kind=f'magic_{family}_error', request_id='input',
                             error=dict(code=code, path=path, message='failure'))
                if family == 'balance':
                    error['error'].update(candidate_id=candidate, counts=counts, stage_index=stage)
                with self.subTest(family=family, code=code):
                    validator.validate(error)
                with self.assertRaises(ValidationError):
                    validator.validate(dict(error, schema_version='3'))
                with self.assertRaises(ValidationError):
                    validator.validate(dict(error, unknown=None))

    def test_old_versions_are_closed_to_the_new_field_even_null_and_default_stays1(self):
        for family in ('simulation', 'balance'):
            public_validator = (production.validate_magic_simulation_document if family == 'simulation'
                                else production.validate_magic_balance_document)
            public_validator(read_example(family, '1'))
            with self.assertRaises(ValidationError):
                public_validator(request(family))
            for version in ('1', '2', '3'):
                original = read_example(family, version)
                self.validator(family, version=version).validate(original)
                for index in range(1 if family == 'simulation' else 2):
                    for value in (None, VALUE):
                        wrong = deepcopy(original)
                        nodes(wrong, family)[index][FIELD] = value
                        with self.subTest(family=family, version=version, node=index, value=value), self.assertRaises(ValidationError):
                            self.validator(family, version=version).validate(wrong)

    def test_production_registry_resolves_each_new_family_kind_without_retrieval(self):
        # Run after the main agent's registry integration. This checks the real
        # registry rather than merely the independent offline bundle above.
        for family, kind in product(('simulation', 'balance'), ('request', 'result', 'error')):
            validator = production._validator(kind, family, '4')
            self.assertEqual(validator.schema, self.validator(family, kind).schema)
            for uri, resource in validator._registry.items():
                for ref in references(resource.contents):
                    with self.subTest(family=family, kind=kind, uri=uri, ref=ref):
                        validator._registry.resolver(uri).lookup(ref)
        self.assertEqual(production._validator.cache_info().maxsize, 36)


if __name__ == '__main__':
    unittest.main()
