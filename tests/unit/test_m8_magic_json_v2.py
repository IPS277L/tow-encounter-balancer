"""ADR-0047 simulation v2 is explicit, lossless and isolated from v1 families."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from importlib.resources import files
import json
import pickle
import random
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator, ValidationError

from tests.unit.test_m4_ranged_json import at, object_paths
from tests.unit.test_m8_magic_json import document as legacy_document, summary
from tests.unit.test_m8_magic_simulation_service import result_for
from tests.unit.test_m8_miscast_continuation_policy import continuation_policy
from towr.adapters.magic_json_errors import MagicBalanceInputError, MagicSimulationInputError
from towr.adapters.magic_balance_json import encode_magic_balance_error
from towr.adapters.magic_json_schema import validate_magic_simulation_document as validate
from towr.adapters.magic_simulation_json import (
    encode_magic_simulation_error as encode_error,
    encode_magic_simulation_result as encode,
    parse_magic_simulation_request as parse,
)
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.application import magic_simulation_service as service
from towr.application.magic_simulation_errors import MagicSimulationExecutionError
from towr.application.magic_simulation_models import MagicSimulationCommand
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options


def policy_document():
    return {
        'choice': 'decline_cast_before_miscast',
        'facts': {
            'all_combatants_in_roster': True,
            'no_external_short_range_creatures': True,
            'unmounted_combatants_only': True,
            'no_effect_immunities': True,
            'no_cross_zone_close': True,
        },
        'prone_policy': 'self_stand_when_safe',
    }


def document(*, opted=True):
    data = legacy_document()
    data['schema_version'] = '2'
    data['scenario']['miscast_continuation'] = policy_document() if opted else None
    return data


class M8MagicJsonV2Tests(unittest.TestCase):
    def assert_invalid(self, data, *, version='2', path=None, code=Code.INVALID_INPUT):
        with self.assertRaises(MagicSimulationInputError) as caught:
            parse(json.dumps(data))
        error = caught.exception
        self.assertEqual(error.code, code)
        self.assertEqual(error.schema_version, version)
        if path is not None:
            self.assertEqual(error.path, path)
        output = json.loads(encode_error(error))
        self.assertEqual(output['schema_version'], version)
        validate(output, 'error', schema_version=version)
        return error

    def test_null_and_full_policy_roundtrip_without_version_downgrade(self):
        for opted in (False, True):
            with self.subTest(opted=opted):
                data = document(opted=opted)
                command = parse(json.dumps(data).encode('utf-8'))
                original = deepcopy(command)
                self.assertEqual(command.schema_version, '2')
                self.assertEqual(command.request.scenario.miscast_continuation,
                                 continuation_policy() if opted else None)
                encoded = encode(command, summary(command))
                self.assertTrue(encoded.endswith('\n'))
                output = json.loads(encoded)
                validate(output, 'result', schema_version='2')
                self.assertEqual(output['schema_version'], '2')
                self.assertEqual(output['request'], data)
                self.assertEqual(parse(json.dumps(output['request'])), command)
                self.assertEqual(command, original)

    def test_null_v2_preserves_full_native_request_seed_and_summary(self):
        legacy = parse(json.dumps(legacy_document()))
        current = parse(json.dumps(document(opted=False)))
        self.assertEqual(legacy.request, current.request)
        self.assertEqual(legacy.execution, current.execution)
        self.assertEqual(legacy.definition_order, current.definition_order)
        self.assertEqual(legacy, replace(current, schema_version='1'))
        old = json.loads(encode(legacy, summary(legacy)))
        new = json.loads(encode(current, summary(current)))
        self.assertEqual(old['summary'], new['summary'])
        self.assertEqual(old['seed_scheme'], new['seed_scheme'])
        self.assertEqual(old['runtime'], new['runtime'])
        self.assertNotIn('miscast_continuation', old['request']['scenario'])
        self.assertIn('miscast_continuation', new['request']['scenario'])

    def test_v1_still_forbids_null_or_policy_and_refuses_opted_native_source(self):
        for value in (None, policy_document()):
            data = legacy_document()
            data['scenario']['miscast_continuation'] = value
            self.assert_invalid(data, version='1', path='/scenario')
        opted = parse(json.dumps(document()))
        legacy = replace(opted, schema_version='1')
        with self.assertRaisesRegex(ValueError, 'losslessly'):
            encode(legacy, summary(legacy))

    def test_every_v2_request_object_is_closed_and_fields_are_required(self):
        original = document()
        for path in object_paths(original):
            for key in (None, *at(original, path)):
                data = deepcopy(original)
                if key is None:
                    at(data, path)['extra_rule'] = True
                else:
                    del at(data, path)[key]
                with self.subTest(path=path, key=key):
                    self.assert_invalid(data, version='1' if not path and key == 'schema_version' else '2')

    def test_policy_fields_facts_and_enums_have_exact_error_paths(self):
        base = ('scenario', 'miscast_continuation')
        cases = [
            (base, (False, 0, 1, '', [])),
            ((*base, 'choice'), (None, True, 'cast', 'decline')),
            ((*base, 'prone_policy'), (None, False, 'stand', '')),
            ((*base, 'facts'), (None, True, [], 'facts')),
        ]
        cases.extend(((*base, 'facts', key), (False, 0, 1, 'true', None, [], {}))
                     for key in policy_document()['facts'])
        for path, values in cases:
            for value in values:
                with self.subTest(path=path, value=value):
                    data = document()
                    at(data, path[:-1])[path[-1]] = value
                    self.assert_invalid(data, path='/' + '/'.join(path))

    def test_semantic_admission_and_helper_errors_keep_trusted_version(self):
        cases = [
            ('/simulation/master_seed', lambda d: d['simulation'].update(master_seed=str(2**64))),
            ('/scenario/definitions/2/id', lambda d: d['scenario']['definitions'].append(
                deepcopy(d['scenario']['definitions'][0]))),
            ('/scenario/actors/0/definition_id', lambda d: d['scenario']['actors'][0].update(definition_id='missing')),
        ]
        for path, change in cases:
            data = document()
            change(data)
            with self.subTest(path=path):
                error = self.assert_invalid(data, path=path)
                self.assertEqual(error.request_id, data['request_id'])

    def test_cross_zone_close_is_rejected_with_policy_before_execution(self):
        data = document()
        # Existing geometry admission must still run after the complete typed
        # policy has been assembled; explicit assertions cannot override it.
        frame = data['scenario']['scene_frames'][1]
        zones = {p['entity_id']: p['zone_id'] for p in frame['key']['placements']}
        pair = next(p for p in frame['pair_ranges']
                    if zones[p['first_actor_id']] != zones[p['second_actor_id']])
        pair['target_range'] = 'close'
        error = self.assert_invalid(data)
        self.assertTrue(error.path.startswith('/scenario'))
        self.assertIsNotNone(error.__cause__)
        data = document()
        for pair in data['scenario']['scene_frames'][3]['pair_ranges']:
            pair['target_range'] = 'close'
        self.assertEqual(parse(json.dumps(data)).request.scenario.miscast_continuation,
                         continuation_policy())

    def test_lexical_failures_never_trust_earlier_version_or_request_id(self):
        prefix = '{"schema_version":"2","request_id":"seen",'
        cases = [
            (b'\xff' + prefix.encode(), Code.INVALID_JSON),
            (prefix, Code.INVALID_JSON),
            (prefix + '"schema_version":"2"}', Code.INVALID_JSON),
            (prefix + '"nested":{"a":1,"a":2}}', Code.INVALID_JSON),
            (prefix + '"x":NaN}', Code.INVALID_JSON),
            (prefix + '"x":Infinity}', Code.INVALID_JSON),
            (prefix + '"x":-Infinity}', Code.INVALID_JSON),
            (prefix + '"x":1.0}', Code.INVALID_INPUT),
            (prefix + '"x":1e0}', Code.INVALID_INPUT),
            (prefix + '"x":1e999}', Code.INVALID_INPUT),
            (prefix + '"x":"\\ud800"}', Code.INVALID_JSON),
            (prefix + '"\\ud800":"value"}', Code.INVALID_JSON),
            (prefix + '"x":0} {}', Code.INVALID_JSON),
            ('\ufeff' + json.dumps(document()), Code.INVALID_JSON),
        ]
        for raw, code in cases:
            with self.subTest(raw=raw), self.assertRaises(MagicSimulationInputError) as caught:
                parse(raw)
            error = caught.exception
            self.assertEqual(error.schema_version, '1')
            self.assertEqual(error.code, code)
            self.assertIsNone(error.request_id)
            output = json.loads(encode_error(error))
            validate(output, 'error')
            self.assertEqual(output['schema_version'], '1')
            self.assertIsNone(output['request_id'])

    def test_decoded_version_boundary_and_request_id_trust(self):
        for version in (None, False, 2, [], {}, '', '3'):
            data = dict(document(), schema_version=version)
            with self.subTest(version=version):
                error = self.assert_invalid(data, version='1', path='/schema_version',
                    code=Code.UNSUPPORTED_VERSION if isinstance(version, str) else Code.INVALID_INPUT)
                self.assertEqual(error.request_id, data['request_id'])
        for value in ('', ' \t', None, 7):
            data = dict(document(), request_id=value)
            self.assertIsNone(self.assert_invalid(data, path='/request_id').request_id)
        for root in (None, [], 2, '2'):
            self.assertIsNone(self.assert_invalid(root, version='1').request_id)
        # A complete v2 root is trusted even if its family/kind is wrong.
        self.assert_invalid(dict(document(), kind='npc_magic_balance'), path='/kind')

    def test_schemas_are_packaged_versioned_and_public_default_remains_v1(self):
        command = parse(json.dumps(document()))
        documents = {
            'request': document(),
            'result': json.loads(encode(command, summary(command))),
            'error': json.loads(encode_error(MagicSimulationInputError(
                Code.INVALID_INPUT, 'invalid', schema_version='2'))),
        }
        for kind, data in documents.items():
            schema = json.loads(files('towr.adapters.schemas').joinpath(
                f'magic-simulation-{kind}-v2.schema.json').read_text(encoding='utf-8'))
            Draft202012Validator.check_schema(schema)
            self.assertEqual(schema['$id'], f'urn:towr:magic-simulation:{kind}:2')
            validate(data, kind, schema_version='2')
            with self.assertRaises(ValidationError):
                validate(data, kind)
        for version in (None, False, 2, '', '3', [], {}):
            with self.subTest(version=version), self.assertRaises(ValueError):
                validate({}, schema_version=version)
        with self.assertRaises(ValueError):
            validate({}, 'other', schema_version='2')

    def test_result_echo_and_error_shapes_are_closed_and_version_bound(self):
        command = parse(json.dumps(document()))
        originals = {
            'result': json.loads(encode(command, summary(command))),
            'error': json.loads(encode_error(MagicSimulationInputError(
                Code.INVALID_INPUT, 'invalid', schema_version='2'))),
        }
        for kind, original in originals.items():
            for path in object_paths(original):
                for key in (None, *at(original, path)):
                    data = deepcopy(original)
                    if key is None:
                        at(data, path)['extra'] = True
                    else:
                        del at(data, path)[key]
                    with self.subTest(kind=kind, path=path, key=key), self.assertRaises(ValidationError):
                        validate(data, kind, schema_version='2')
        changed = deepcopy(originals['result'])
        changed['request'] = legacy_document()
        with self.assertRaises(ValidationError):
            validate(changed, 'result', schema_version='2')

    def test_command_metadata_is_appended_typed_frozen_and_pickle_safe(self):
        legacy = parse(json.dumps(legacy_document()))
        self.assertEqual(fields(MagicSimulationCommand)[-1].name, 'schema_version')
        self.assertEqual(MagicSimulationCommand(legacy.request_id, legacy.request,
            legacy.execution, legacy.definition_order), legacy)
        command = parse(json.dumps(document()))
        self.assertEqual(pickle.loads(pickle.dumps(command)), command)
        with self.assertRaises(FrozenInstanceError):
            command.schema_version = '1'
        for value in (None, 1, 2, True, '', '3', [], {}):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                replace(command, schema_version=value)

    def test_error_metadata_is_explicit_closed_and_old_calls_default_v1(self):
        for version in ('1', '2'):
            for error in (
                MagicSimulationInputError(Code.INVALID_INPUT, 'bad', schema_version=version),
                MagicSimulationExecutionError('request', schema_version=version),
            ):
                self.assertEqual(error.schema_version, version)
                self.assertEqual(json.loads(encode_error(error))['schema_version'], version)
        self.assertEqual(MagicSimulationInputError(Code.INVALID_INPUT, 'bad').schema_version, '1')
        self.assertEqual(MagicSimulationExecutionError('request').schema_version, '1')
        for value in (None, 2, True, '', '3', [], {}):
            for constructor, args in ((MagicSimulationInputError, (Code.INVALID_INPUT, 'bad')),
                                      (MagicSimulationExecutionError, ('request',))):
                with self.subTest(value=value, constructor=constructor), self.assertRaises((TypeError, ValueError)):
                    constructor(*args, schema_version=value)

    def test_balance_error_cannot_silently_downgrade_shared_v2_metadata(self):
        legacy = MagicBalanceInputError(Code.INVALID_INPUT, 'bad')
        self.assertEqual(json.loads(encode_magic_balance_error(legacy))['schema_version'], '1')
        future = MagicBalanceInputError(Code.INVALID_INPUT, 'bad', schema_version='2')
        with self.assertRaises(ValueError):
            encode_magic_balance_error(future)

    def test_same_id_policy_substitution_is_rejected_by_encoder_and_service(self):
        opted, legacy = (parse(json.dumps(document(opted=value))) for value in (True, False))
        for source, foreign in ((opted, legacy), (legacy, opted)):
            self.assertEqual(source.request.scenario.id, foreign.request.scenario.id)
            with self.assertRaises(ValueError):
                encode(source, summary(foreign))
            with patch.object(service, 'run_npc_magic_simulation', return_value=result_for(foreign.request)), \
                    patch.object(service, 'summarize_npc_magic_simulation') as summarize:
                with self.assertRaises(MagicSimulationExecutionError) as caught:
                    service.execute_magic_simulation(source)
                self.assertEqual(caught.exception.schema_version, '2')
                self.assertIsInstance(caught.exception.__cause__, ValueError)
                summarize.assert_not_called()
            with patch.object(service, 'run_npc_magic_simulation', return_value=result_for(source.request)), \
                    patch.object(service, 'summarize_npc_magic_simulation', return_value=summary(foreign)):
                with self.assertRaises(MagicSimulationExecutionError) as caught:
                    service.execute_magic_simulation(source)
                self.assertEqual(caught.exception.schema_version, '2')
                self.assertIsInstance(caught.exception.__cause__, ValueError)

    def test_reconstruction_guard_compares_version_and_definition_order(self):
        command = parse(json.dumps(document()))
        for changed in (replace(command, schema_version='1'),
                        replace(command, definition_order=tuple(reversed(command.definition_order)))):
            with patch('towr.adapters.magic_simulation_json.parse_magic_simulation_request', return_value=changed), \
                    self.assertRaisesRegex(ValueError, 'losslessly'):
                encode(command, summary(command))

    def test_service_owns_version_in_both_backends_and_both_failure_phases(self):
        for version in ('1', '2'):
            base = parse(json.dumps(legacy_document() if version == '1' else document()))
            for mode in Mode:
                command = replace(base, execution=Options(mode, 2, 1) if mode is Mode.PROCESS else Options(mode))
                target = 'run_npc_magic_simulation_parallel' if mode is Mode.PROCESS else 'run_npc_magic_simulation'
                other = 'run_npc_magic_simulation' if mode is Mode.PROCESS else 'run_npc_magic_simulation_parallel'
                for phase in ('runner', 'summary'):
                    cause = MagicSimulationExecutionError('foreign', schema_version='2' if version == '1' else '1')
                    cause.add_note('private failure note')
                    with self.subTest(version=version, mode=mode, phase=phase), \
                            patch.object(service, target, return_value=result_for(command.request),
                                side_effect=cause if phase == 'runner' else None), \
                            patch.object(service, other) as unused, \
                            patch.object(service, 'summarize_npc_magic_simulation', side_effect=cause):
                        with self.assertRaises(MagicSimulationExecutionError) as caught:
                            service.execute_magic_simulation(command)
                        error = caught.exception
                        self.assertIs(error.__cause__, cause)
                        self.assertEqual(error.schema_version, version)
                        self.assertEqual(error.request_id, command.request_id)
                        encoded = encode_error(error)
                        self.assertNotIn('foreign', encoded)
                        self.assertNotIn('private', encoded)
                        self.assertEqual(json.loads(encoded)['schema_version'], version)
                        unused.assert_not_called()

    def test_parser_and_encoder_are_pure_for_both_policies_and_invalid_input(self):
        state = random.getstate()
        with patch('random.Random', side_effect=AssertionError('RNG created')), \
                patch('towr.simulation.npc_magic_simulation.run_npc_magic_simulation', side_effect=AssertionError('runner')), \
                patch('towr.simulation.npc_magic_parallel.ProcessPoolExecutor', side_effect=AssertionError('pool')):
            for opted in (False, True):
                command = parse(json.dumps(document(opted=opted)))
                output = json.loads(encode(command, summary(command)))
                self.assertEqual(parse(json.dumps(output['request'])), command)
            data = document()
            data['scenario']['miscast_continuation']['facts']['no_effect_immunities'] = False
            self.assert_invalid(data)
        self.assertEqual(random.getstate(), state)
