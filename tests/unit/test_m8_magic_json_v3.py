"""ADR-0051 simulation3 carries independent typed permissions without loss."""
from copy import deepcopy
from dataclasses import replace
import json
import pickle
import random
import unittest
from unittest.mock import patch

from jsonschema import ValidationError

from tests.unit.test_m8_magic_json import document as legacy_document, summary
from tests.unit.test_m8_magic_json_v2 import document as v2_document
from tests.unit.test_m8_magic_balance_json import document as balance_document
from tests.unit.test_m8_magic_simulation_service import result_for
from tests.unit.test_m8_miscast_continuation_policy import continuation_policy
from towr.adapters.magic_balance_json import parse_magic_balance_request
from towr.adapters.magic_json_errors import MagicBalanceInputError, MagicSimulationInputError
from towr.adapters.magic_json_schema import validate_magic_simulation_document as validate
from towr.adapters.magic_simulation_json import (
    parse_magic_simulation_request as parse, encode_magic_simulation_result as encode,
    encode_magic_simulation_error as encode_error,
)
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.application import magic_simulation_service as service
from towr.application.magic_balance_errors import MagicBalanceGenerationError, MagicBalanceExecutionError
from towr.application.magic_simulation_errors import MagicSimulationExecutionError
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.domain.npc_magic_scenario_models import NpcMagicStationaryWoundPolicy as Policy


FIELD = 'stationary_wound_continuation'
POLICY = Policy.LEG_SPASM_STAND_AND_CONTINUE


def document(*, stationary=True, miscast=False):
    data = v2_document(opted=miscast)
    data['schema_version'] = '3'
    data['scenario'][FIELD] = POLICY.value if stationary else None
    return data


class M8MagicJsonV3Tests(unittest.TestCase):
    def assert_invalid(self, data, *, version='3', path=None, code=Code.INVALID_INPUT):
        with self.assertRaises(MagicSimulationInputError) as caught:
            parse(json.dumps(data))
        error = caught.exception
        self.assertEqual(error.schema_version, version)
        self.assertEqual(error.code, code)
        if path is not None:
            self.assertEqual(error.path, path)
        output = json.loads(encode_error(error))
        validate(output, 'error', schema_version=version)
        self.assertEqual(output['schema_version'], version)
        return error

    def test_all_four_permissions_roundtrip_full_source_order_and_seed_without_rng(self):
        rng_before = random.getstate()
        with patch('random.Random', side_effect=AssertionError('wire must not create RNG')), \
                patch('towr.simulation.npc_magic_simulation.run_npc_magic_simulation', side_effect=AssertionError('runner')), \
                patch('towr.simulation.npc_magic_parallel.ProcessPoolExecutor', side_effect=AssertionError('pool')):
            for stationary in (False, True):
                for miscast in (False, True):
                    data = document(stationary=stationary, miscast=miscast)
                    command = parse(json.dumps(data).encode('utf-8'))
                    before = deepcopy(command)
                    self.assertEqual(command.schema_version, '3')
                    self.assertIs(command.request.scenario.stationary_wound_continuation, POLICY if stationary else None)
                    self.assertEqual(command.request.scenario.miscast_continuation, continuation_policy() if miscast else None)
                    output = json.loads(encode(command, summary(command)))
                    validate(output, 'result', schema_version='3')
                    self.assertEqual(output['request'], data)
                    self.assertEqual(parse(json.dumps(output['request'])), command)
                    baseline = parse(json.dumps(v2_document(opted=miscast)))
                    self.assertEqual(command.request, replace(baseline.request, scenario=replace(
                        baseline.request.scenario, stationary_wound_continuation=POLICY if stationary else None)))
                    self.assertEqual(command.definition_order, baseline.definition_order)
                    self.assertEqual(tuple(command.request.seed_for(i) for i in range(2)),
                                     tuple(baseline.request.seed_for(i) for i in range(2)))
                    self.assertEqual(pickle.loads(pickle.dumps(command)), command)
                    self.assertEqual(command, before)
        self.assertEqual(random.getstate(), rng_before)

    def test_both_permissions_are_required_nullable_and_new_enum_has_exact_path(self):
        for field in (FIELD, 'miscast_continuation'):
            missing = document()
            del missing['scenario'][field]
            self.assert_invalid(missing, path='/scenario')
        for value in (False, True, 0, 1, {}, [], '', 'LEG_SPASM_STAND_AND_CONTINUE', 'unknown'):
            with self.subTest(value=value):
                data = document()
                data['scenario'][FIELD] = value
                self.assert_invalid(data, path='/scenario/' + FIELD)
        extra = document()
        extra['scenario']['stationary_wound_facts'] = {}
        self.assert_invalid(extra, path='/scenario')
        bad_miscast = document(stationary=False, miscast=True)
        bad_miscast['scenario']['miscast_continuation']['facts']['no_cross_zone_close'] = False
        self.assert_invalid(bad_miscast, path='/scenario/miscast_continuation/facts/no_cross_zone_close')

    def test_old_versions_reject_stationary_field_even_null_and_full_opted_encoding(self):
        for version, original in (('1', legacy_document()), ('2', v2_document(opted=False))):
            for value in (None, POLICY.value):
                data = deepcopy(original)
                data['scenario'][FIELD] = value
                self.assert_invalid(data, version=version, path='/scenario')
            command = replace(parse(json.dumps(document())), schema_version=version)
            with self.assertRaises(ValueError):
                encode(command, summary(command))

    def test_lexical_failure_never_trusts_early_v3_or_request_id(self):
        prefix = '{"schema_version":"3","request_id":"seen",'
        cases = ((b'\xff' + prefix.encode(), Code.INVALID_JSON), (prefix, Code.INVALID_JSON),
            (prefix + '"schema_version":"3"}', Code.INVALID_JSON),
            (prefix + '"nested":{"a":1,"a":2}}', Code.INVALID_JSON),
            (prefix + '"x":"\\ud800"}', Code.INVALID_JSON),
            (prefix + '"\\ud800":1}', Code.INVALID_JSON),
            (prefix + '"x":NaN}', Code.INVALID_JSON),
            (prefix + '"x":Infinity}', Code.INVALID_JSON),
            (prefix + '"x":-Infinity}', Code.INVALID_JSON),
            (prefix + '"x":1.0}', Code.INVALID_INPUT),
            (prefix + '"x":1e0}', Code.INVALID_INPUT),
            (prefix + '"x":1e999}', Code.INVALID_INPUT),
            (prefix + '"x":0} {}', Code.INVALID_JSON))
        for raw, code in cases:
            with self.subTest(raw=raw), self.assertRaises(MagicSimulationInputError) as caught:
                parse(raw)
            error = caught.exception
            self.assertEqual((error.schema_version, error.request_id, error.code), ('1', None, code))
            output = json.loads(encode_error(error))
            self.assertEqual((output['schema_version'], output['request_id']), ('1', None))
            validate(output, 'error', schema_version='1')

    def test_decoded_v3_shape_semantics_and_missing_unknown_version_preserve_trust_rules(self):
        for path, change in (
            ('/scenario/' + FIELD, lambda d: d['scenario'].update({FIELD: 'wrong'})),
            ('/simulation/master_seed', lambda d: d['simulation'].update(master_seed=str(2**64))),
            ('/scenario/actors/0/definition_id', lambda d: d['scenario']['actors'][0].update(definition_id='missing')),
            ('/kind', lambda d: d.update(kind='npc_magic_balance'))):
            data = document()
            change(data)
            self.assertEqual(self.assert_invalid(data, path=path).request_id, data['request_id'])
        for version in (None, False, 3, '', '6'):
            data = dict(document(), schema_version=version)
            error = self.assert_invalid(data, version='1', path='/schema_version',
                code=Code.UNSUPPORTED_VERSION if isinstance(version, str) else Code.INVALID_INPUT)
            self.assertEqual(error.request_id, data['request_id'])
        data = document()
        del data['schema_version']
        # Missing version selects fallback v1 validation, whose first shape
        # error may be the now-unknown scenario permissions rather than root.
        self.assertEqual(self.assert_invalid(data, version='1').request_id, data['request_id'])
        for invalid_id in ('', ' \t', None, 7):
            self.assertIsNone(self.assert_invalid(dict(document(), request_id=invalid_id), path='/request_id').request_id)

    def test_both_magic_families_accept_v3_metadata_and_unknown_version_precedes_schema_loading(self):
        balance = parse_magic_balance_request(json.dumps(balance_document()))
        self.assertEqual(replace(balance, schema_version='3').schema_version, '3')
        for constructor, args in ((MagicSimulationInputError, (Code.INVALID_INPUT, 'bad')),
                                  (MagicSimulationExecutionError, ('request',))):
            error = constructor(*args, schema_version='3')
            self.assertEqual(json.loads(encode_error(error))['schema_version'], '3')
            self.assertEqual(constructor(*args).schema_version, '1')
        for constructor, args in ((MagicBalanceInputError, (Code.INVALID_INPUT, 'bad')),
                                  (MagicBalanceGenerationError, ('request',)),
                                  (MagicBalanceExecutionError, ('request',))):
            self.assertEqual(constructor(*args, schema_version='3').schema_version, '3')
            self.assertEqual(constructor(*args, schema_version='5').schema_version, '5')
        with patch('towr.adapters.magic_balance_json.validate_magic_balance_document',
                   side_effect=AssertionError('unsupported version must precede schema lookup')):
            with self.assertRaises(MagicBalanceInputError) as caught:
                parse_magic_balance_request(json.dumps({'schema_version': '6', 'request_id': 'balance6'}))
        self.assertEqual((caught.exception.schema_version, caught.exception.request_id, caught.exception.code),
                         ('1', 'balance6', Code.UNSUPPORTED_VERSION))

    def test_same_id_policy_source_substitution_rejected_by_encoder_and_both_service_phases(self):
        on = parse(json.dumps(document()))
        off = parse(json.dumps(document(stationary=False)))
        for source, foreign in ((on, off), (off, on)):
            self.assertEqual(source.request.scenario.id, foreign.request.scenario.id)
            with self.assertRaises(ValueError):
                encode(source, summary(foreign))
            with patch.object(service, 'run_npc_magic_simulation', return_value=result_for(foreign.request)), \
                    patch.object(service, 'summarize_npc_magic_simulation') as summarize:
                with self.assertRaises(MagicSimulationExecutionError) as caught:
                    service.execute_magic_simulation(source)
                self.assertEqual(caught.exception.schema_version, '3')
                self.assertIsInstance(caught.exception.__cause__, ValueError)
                summarize.assert_not_called()
            with patch.object(service, 'run_npc_magic_simulation', return_value=result_for(source.request)), \
                    patch.object(service, 'summarize_npc_magic_simulation', return_value=summary(foreign)):
                with self.assertRaises(MagicSimulationExecutionError) as caught:
                    service.execute_magic_simulation(source)
                self.assertEqual(caught.exception.schema_version, '3')

    def test_raw_native_string_permission_cannot_be_laundered_by_v3_encoder(self):
        command = deepcopy(parse(json.dumps(document())))
        object.__setattr__(command.request.scenario, FIELD, POLICY.value)
        with self.assertRaises(TypeError):
            encode(command, summary(command))

    def test_equal_foreign_summary_integer_fact_cannot_be_laundered_by_encoder(self):
        command = parse(json.dumps(document(miscast=True)))
        before = deepcopy(command)
        foreign = deepcopy(command)
        object.__setattr__(foreign.request.scenario.facts, 'no_external_condition_sources', 1)
        bad_summary = summary(foreign)
        # Python equality alone cannot distinguish this transported corruption.
        self.assertEqual(bad_summary.source_request, command.request)
        self.assertIs(type(bad_summary.source_request.scenario.facts.no_external_condition_sources), int)
        with patch('random.Random', side_effect=AssertionError('encoder must not use RNG')), \
                self.assertRaises(TypeError):
            encode(command, bad_summary)
        self.assertEqual(command, before)
        self.assertIs(command.request.scenario.facts.no_external_condition_sources, True)
        self.assertIs(type(foreign.request.scenario.facts.no_external_condition_sources), int)

    def test_service_rejects_integer_scope_fact_before_command_runner_and_summary_equality(self):
        base = parse(json.dumps(document(miscast=True)))
        for mode in Mode:
            command = replace(base, execution=Options(mode, 1, 1) if mode is Mode.PROCESS else Options(mode))
            before = deepcopy(command)
            foreign = deepcopy(command)
            object.__setattr__(foreign.request.scenario.facts, 'no_external_condition_sources', 1)
            self.assertEqual(foreign.request, command.request)
            target = 'run_npc_magic_simulation_parallel' if mode is Mode.PROCESS else 'run_npc_magic_simulation'
            other = 'run_npc_magic_simulation' if mode is Mode.PROCESS else 'run_npc_magic_simulation_parallel'
            for phase in ('command', 'runner', 'summary'):
                supplied = foreign if phase == 'command' else command
                returned = deepcopy(result_for(command.request))
                if phase == 'runner':
                    # Emulate an unpickled/foreign result AFTER valid model
                    # construction; the record constructor now rejects it too.
                    object.__setattr__(returned.source_request.scenario.facts,
                                       'no_external_condition_sources', 1)
                aggregated = summary(foreign if phase == 'summary' else command)
                with self.subTest(mode=mode, phase=phase), \
                        patch('random.Random', side_effect=AssertionError('validation must not create RNG')), \
                        patch.object(service, target, return_value=returned) as runner, \
                        patch.object(service, other) as unused, \
                        patch.object(service, 'summarize_npc_magic_simulation', return_value=aggregated) as summarizer:
                    with self.assertRaises(MagicSimulationExecutionError) as caught:
                        service.execute_magic_simulation(supplied)
                    self.assertEqual((caught.exception.schema_version, caught.exception.request_id),
                                     ('3', command.request_id))
                    self.assertIsInstance(caught.exception.__cause__, TypeError)
                    unused.assert_not_called()
                    if phase == 'command':
                        runner.assert_not_called()
                    else:
                        self.assertEqual(runner.call_count, 1)
                    if phase != 'summary':
                        summarizer.assert_not_called()
                    else:
                        summarizer.assert_called_once_with(returned)
                self.assertEqual(command, before)
                self.assertIs(command.request.scenario.facts.no_external_condition_sources, True)
                self.assertIs(type(foreign.request.scenario.facts.no_external_condition_sources), int)

    def test_service_owns_v3_error_version_in_both_backends_and_summary_phase(self):
        base = parse(json.dumps(document()))
        for mode in Mode:
            command = replace(base, execution=Options(mode, 1, 1) if mode is Mode.PROCESS else Options(mode))
            target = 'run_npc_magic_simulation_parallel' if mode is Mode.PROCESS else 'run_npc_magic_simulation'
            for phase in ('runner', 'summary'):
                cause = MagicSimulationExecutionError('foreign-private-id', schema_version='2')
                cause.add_note('private note')
                with patch.object(service, target, return_value=result_for(command.request),
                        side_effect=cause if phase == 'runner' else None), \
                        patch.object(service, 'summarize_npc_magic_simulation', side_effect=cause):
                    with self.assertRaises(MagicSimulationExecutionError) as caught:
                        service.execute_magic_simulation(command)
                error = caught.exception
                self.assertIs(error.__cause__, cause)
                self.assertEqual((error.schema_version, error.request_id), ('3', command.request_id))
                encoded = encode_error(error)
                self.assertNotIn('foreign-private-id', encoded)
                self.assertNotIn('private note', encoded)

    def test_encoder_reconstruction_checks_version_and_definition_order(self):
        command = parse(json.dumps(document(stationary=False)))
        for foreign in (replace(command, schema_version='2'),
                        replace(command, definition_order=tuple(reversed(command.definition_order)))):
            with patch('towr.adapters.magic_simulation_json.parse_magic_simulation_request', return_value=foreign), \
                    self.assertRaises(ValueError):
                encode(command, summary(command))

    def test_result_and_error_versions_are_closed_and_null_does_not_downgrade(self):
        command = parse(json.dumps(document(stationary=False, miscast=False)))
        output = json.loads(encode(command, summary(command)))
        self.assertEqual(output['schema_version'], '3')
        self.assertIsNone(output['request']['scenario'][FIELD])
        for changed in (dict(output, schema_version='2'), dict(output, extra=True),
                        dict(output, request=v2_document(opted=False))):
            with self.assertRaises(ValidationError):
                validate(changed, 'result', schema_version='3')
        error = json.loads(encode_error(MagicSimulationInputError(Code.INVALID_INPUT, 'bad', schema_version='3')))
        validate(error, 'error', schema_version='3')
        with self.assertRaises(ValidationError):
            validate(dict(error, schema_version='2'), 'error', schema_version='3')


if __name__ == '__main__':
    unittest.main()
