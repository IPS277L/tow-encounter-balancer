"""ADR-0054 transports the independent native permission without widening play."""
from copy import deepcopy
from dataclasses import replace
import json
import pickle
import random
import unittest
from unittest.mock import patch

from tests.unit.test_m8_magic_json import summary
from tests.unit.test_m8_magic_balance_json import make_result
from tests.unit.test_m8_magic_json_v3 import document as simulation_v3
from tests.unit.test_m8_magic_balance_json_v3 import document as balance_v3
from towr.adapters import magic_simulation_json as sim, magic_balance_json as bal
from towr.adapters.magic_json_errors import MagicSimulationInputError, MagicBalanceInputError
from towr.adapters.magic_json_schema import validate_magic_simulation_document, validate_magic_balance_document
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.application.magic_simulation_errors import MagicSimulationExecutionError
from towr.application.magic_balance_errors import MagicBalanceGenerationError, MagicBalanceExecutionError
from towr.domain.npc_magic_scenario_models import NpcMagicRepeatedLegSpasmPolicy as Policy

FIELD = 'repeated_leg_spasm_continuation'
POLICY = Policy.STAND_ONCE_WITH_JOURNAL_WITNESSES
FAMILIES = (
    (False, sim.parse_magic_simulation_request, sim.encode_magic_simulation_result,
     sim.encode_magic_simulation_error, MagicSimulationInputError, validate_magic_simulation_document),
    (True, bal.parse_magic_balance_request, bal.encode_magic_balance_result,
     bal.encode_magic_balance_error, MagicBalanceInputError, validate_magic_balance_document),
)


def document(*, balance=False, stationary=True, miscast=False, repeated=True):
    data = (balance_v3 if balance else simulation_v3)(stationary=stationary, miscast=miscast)
    data['schema_version'] = '4'
    scenario = data['reserve']['scenario'] if balance else data['scenario']
    scenario[FIELD] = POLICY.value if repeated else None
    if balance:
        data['generation'][FIELD] = scenario[FIELD]
    return data


class M8MagicJsonV4Tests(unittest.TestCase):
    def test_six_valid_combinations_full_source_echo_pickle_and_pure_mapping(self):
        rng = random.getstate()
        with patch('random.Random', side_effect=AssertionError('no wire RNG')), \
                patch('towr.simulation.npc_magic_parallel.ProcessPoolExecutor', side_effect=AssertionError('no pool')):
            for balance, parse, encode, _, _, validate in FAMILIES:
                for stationary, repeated in ((False, False), (True, False), (True, True)):
                    for miscast in (False, True):
                        with self.subTest(balance=balance, stationary=stationary, repeated=repeated, miscast=miscast):
                            data = document(balance=balance, stationary=stationary, repeated=repeated, miscast=miscast)
                            command = parse(json.dumps(data))
                            before = deepcopy(command)
                            result = make_result(command) if balance else summary(command)
                            output = json.loads(encode(command, result))
                            validate(output, 'result', schema_version='4')
                            self.assertEqual(output['request'], data)
                            self.assertEqual(parse(json.dumps(output['request'])), command)
                            self.assertEqual(pickle.loads(pickle.dumps(command)), command)
                            source = command.generation_request.template_scenario if balance else command.request.scenario
                            self.assertIs(source.repeated_leg_spasm_continuation, POLICY if repeated else None)
                            if balance:
                                self.assertIs(command.generation_request.repeated_leg_spasm_continuation,
                                              POLICY if repeated else None)
                            self.assertEqual(command, before)
        self.assertEqual(random.getstate(), rng)

    def test_required_fields_and_exact_dependency_and_matching_paths(self):
        for balance, parse, _, encode_error, error_type, validate in FAMILIES:
            base = document(balance=balance)
            paths = [('reserve/scenario' if balance else 'scenario', base['reserve']['scenario'] if balance else base['scenario'])]
            if balance:
                paths.append(('generation', base['generation']))
            for location, _ in paths:
                for field in (FIELD, 'stationary_wound_continuation', 'miscast_continuation'):
                    data = deepcopy(base)
                    target = data['reserve']['scenario'] if location == 'reserve/scenario' else data[location]
                    del target[field]
                    with self.subTest(balance=balance, missing=location + '/' + field), self.assertRaises(error_type) as caught:
                        parse(json.dumps(data))
                    self.assertEqual(caught.exception.schema_version, '4')
                    self.assertEqual(caught.exception.path, '/' + location)
            for miscast in (False, True):
                data = document(balance=balance, stationary=False, miscast=miscast)
                with self.assertRaises(error_type) as caught:
                    parse(json.dumps(data))
                self.assertEqual(caught.exception.path, '/reserve/scenario/' + FIELD if balance else '/scenario/' + FIELD)
                output = json.loads(encode_error(caught.exception))
                validate(output, 'error', schema_version='4')
                self.assertEqual(output['request_id'], data['request_id'])
            if balance:
                for template, family in ((None, POLICY.value), (POLICY.value, None)):
                    data = document(balance=True)
                    data['reserve']['scenario'][FIELD] = template
                    data['generation'][FIELD] = family
                    with self.assertRaises(error_type) as caught:
                        parse(json.dumps(data))
                    self.assertEqual(caught.exception.path, '/generation/' + FIELD)
            for bad in (True, False, 0, 1, {}, [], '', 'STAND_ONCE_WITH_JOURNAL_WITNESSES', 'unknown'):
                data = document(balance=balance)
                target = data['reserve']['scenario'] if balance else data['scenario']
                target[FIELD] = bad
                with self.subTest(balance=balance, bad=bad), self.assertRaises(error_type) as caught:
                    parse(json.dumps(data))
                self.assertEqual(caught.exception.schema_version, '4')
                self.assertEqual(caught.exception.path, '/reserve/scenario/' + FIELD if balance else '/scenario/' + FIELD)

    def test_legacy_none_bytes_and_non_none_refusal_are_versioned(self):
        for balance, parse, encode, _, _, _ in FAMILIES:
            for version in ('1', '2', '3'):
                command4 = parse(json.dumps(document(balance=balance, stationary=False, repeated=False)))
                command = replace(command4, schema_version=version)
                result = make_result(command) if balance else summary(command)
                encoded = encode(command, result)
                echoed = json.loads(encoded)['request']
                self.assertNotIn(FIELD, echoed['reserve']['scenario'] if balance else echoed['scenario'])
                reparsed = parse(json.dumps(echoed))
                self.assertEqual(encode(reparsed, make_result(reparsed) if balance else summary(reparsed)), encoded)
                opted = replace(parse(json.dumps(document(balance=balance))), schema_version=version)
                with self.assertRaisesRegex(ValueError, 'repeated Leg Spasm.*losslessly'):
                    encode(opted, make_result(opted) if balance else summary(opted))

    def test_lexical_fallback_decoded_unknown_six_and_trusted_four(self):
        for balance, parse, _, encode_error, error_type, _ in FAMILIES:
            prefix = '{"schema_version":"4","request_id":"untrusted",'
            for raw in (prefix, prefix + '"x":NaN}', prefix + '"x":1.0}',
                        prefix + '"x":1e0}', prefix + '"request_id":"again"}',
                        prefix + '"x":"\\ud800"}', prefix + '"x":0} {}', b'\xff'):
                with self.assertRaises(error_type) as caught:
                    parse(raw)
                self.assertEqual((caught.exception.schema_version, caught.exception.request_id), ('1', None))
                self.assertEqual(json.loads(encode_error(caught.exception))['schema_version'], '1')
            data = document(balance=balance)
            data['kind'] = 'wrong'
            with self.assertRaises(error_type) as caught:
                parse(json.dumps(data))
            self.assertEqual((caught.exception.schema_version, caught.exception.request_id), ('4', data['request_id']))
            next_version = '7'
            for version in (next_version, None, False, 4):
                wrong = dict(data, schema_version=version)
                with self.assertRaises(error_type) as caught:
                    parse(json.dumps(wrong))
                self.assertEqual((caught.exception.schema_version, caught.exception.request_id), ('1', data['request_id']))
                if version == next_version:
                    self.assertEqual((caught.exception.code, caught.exception.path), (Code.UNSUPPORTED_VERSION, '/schema_version'))

    def test_phase_errors_own_version_and_privacy(self):
        for constructor, args, encode, validate in (
                (MagicSimulationExecutionError, ('own',), sim.encode_magic_simulation_error, validate_magic_simulation_document),
                (MagicBalanceGenerationError, ('own', 'candidate', (1, 0)), bal.encode_magic_balance_error, validate_magic_balance_document),
                (MagicBalanceExecutionError, ('own', 1, 'candidate'), bal.encode_magic_balance_error, validate_magic_balance_document)):
            error = constructor(*args, schema_version='4')
            error.__cause__ = RuntimeError('private-source-secret')
            error.add_note('private-note')
            text = encode(error)
            output = json.loads(text)
            validate(output, 'error', schema_version='4')
            self.assertEqual((output['schema_version'], output['request_id']), ('4', 'own'))
            self.assertNotIn('private', text)


if __name__ == '__main__':
    unittest.main()
