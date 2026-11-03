"""ADR-0058 simulation5 preserves the complete fresh Crushed Rib source."""
from copy import deepcopy
from dataclasses import replace
import json
import pickle
import random
import unittest
from unittest.mock import patch

from jsonschema import ValidationError

from tests.unit.test_m8_magic_json import summary
from tests.unit.test_m8_magic_json_v4 import document as v4_document
from towr.adapters import magic_simulation_json as sim
from towr.adapters.magic_json_errors import MagicSimulationInputError
from towr.adapters.magic_json_schema import validate_magic_simulation_document
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.application.magic_simulation_errors import MagicSimulationExecutionError
from towr.domain.npc_magic_scenario_models import NpcMagicCrushedRibPolicy as CrushedRib


FIELD = 'crushed_rib_continuation'
POLICY = CrushedRib.NEXT_TEST_WITH_JOURNAL_WITNESSES


def document(*, opted=True):
    data = v4_document(balance=False, stationary=False, repeated=False)
    data['schema_version'] = '5'
    data['scenario'][FIELD] = POLICY.value if opted else None
    return data


class M8MagicJsonV5Tests(unittest.TestCase):
    def test_required_nullable_field_roundtrips_full_typed_source_without_execution(self):
        rng = random.getstate()
        with patch('random.Random', side_effect=AssertionError('wire must not create RNG')), \
                patch('towr.simulation.npc_magic_simulation.run_npc_magic_simulation',
                      side_effect=AssertionError('wire must not execute simulation')), \
                patch('towr.simulation.npc_magic_parallel.ProcessPoolExecutor',
                      side_effect=AssertionError('wire must not create a pool')):
            for opted in (False, True):
                raw = document(opted=opted)
                command = sim.parse_magic_simulation_request(json.dumps(raw).encode('utf-8'))
                before = deepcopy(command)
                self.assertEqual(command.schema_version, '5')
                self.assertIs(command.request.scenario.crushed_rib_continuation, POLICY if opted else None)
                self.assertEqual(pickle.loads(pickle.dumps(command)), command)
                output = json.loads(sim.encode_magic_simulation_result(command, summary(command)))
                validate_magic_simulation_document(output, 'result', schema_version='5')
                self.assertEqual(output['request'], raw)
                self.assertEqual(sim.parse_magic_simulation_request(json.dumps(output['request'])), command)
                self.assertEqual(command, before)
        self.assertEqual(random.getstate(), rng)

    def test_policy_spelling_and_required_key_errors_retain_decoded_v5_metadata(self):
        for mutation, path in (
                (lambda data: data['scenario'].pop(FIELD), '/scenario'),
                (lambda data: data['scenario'].__setitem__(FIELD, 'NEXT_TEST_WITH_JOURNAL_WITNESSES'),
                 '/scenario/' + FIELD),
                (lambda data: data['scenario'].__setitem__(FIELD, None) or data['scenario'].__setitem__(
                    'unknown_future_field', None), '/scenario')):
            raw = document()
            mutation(raw)
            with self.subTest(path=path), self.assertRaises(MagicSimulationInputError) as caught:
                sim.parse_magic_simulation_request(json.dumps(raw))
            self.assertEqual(caught.exception.schema_version, '5')
            self.assertEqual(caught.exception.request_id, raw['request_id'])
            self.assertEqual(caught.exception.code, Code.INVALID_INPUT)
            self.assertEqual(caught.exception.path, path)
            error = json.loads(sim.encode_magic_simulation_error(caught.exception))
            validate_magic_simulation_document(error, 'error', schema_version='5')
            self.assertEqual((error['schema_version'], error['request_id']), ('5', raw['request_id']))

    def test_only_simulation5_opens_crushed_rib_and_old_versions_remain_lossless(self):
        parsed = sim.parse_magic_simulation_request(json.dumps(document()))
        result = summary(parsed)
        for version in ('1', '2', '3', '4'):
            old = replace(parsed, schema_version=version)
            with self.subTest(version=version), self.assertRaisesRegex(
                    ValueError, 'Crushed Rib continuation.*losslessly'):
                sim.encode_magic_simulation_result(old, result)
        legacy = sim.parse_magic_simulation_request(json.dumps(document(opted=False)))
        output = json.loads(sim.encode_magic_simulation_result(replace(legacy, schema_version='4'), summary(legacy)))
        self.assertNotIn(FIELD, output['request']['scenario'])
        with self.assertRaises(MagicSimulationInputError) as caught:
            sim.parse_magic_simulation_request(json.dumps(dict(document(), schema_version='7')))
        self.assertEqual((caught.exception.code, caught.exception.path,
                          caught.exception.schema_version, caught.exception.request_id),
                         (Code.UNSUPPORTED_VERSION, '/schema_version', '1', document()['request_id']))

    def test_lexical_fallback_and_runtime_errors_keep_their_own_version_privately(self):
        raw = '{"schema_version":"5","request_id":"decoded-but-untrusted",'
        for malformed in (raw, raw + '"x":NaN}', raw + '"x":1.0}',
                          raw + '"request_id":"duplicate"}', raw + '"x":"\\ud800"}',
                          raw + '"x":0} {}'):
            with self.subTest(malformed=malformed), self.assertRaises(MagicSimulationInputError) as caught:
                sim.parse_magic_simulation_request(malformed)
            self.assertEqual((caught.exception.schema_version, caught.exception.request_id), ('1', None))
        error = MagicSimulationExecutionError('command-v5', schema_version='5')
        error.__cause__ = RuntimeError('private-source')
        error.add_note('private-note')
        encoded = sim.encode_magic_simulation_error(error)
        output = json.loads(encoded)
        validate_magic_simulation_document(output, 'error', schema_version='5')
        self.assertEqual((output['schema_version'], output['request_id'], output['error']['code']),
                         ('5', 'command-v5', 'simulation_failed'))
        self.assertNotIn('private', encoded)


if __name__ == '__main__':
    unittest.main()
