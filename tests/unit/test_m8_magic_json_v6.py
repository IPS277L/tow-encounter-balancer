"""Simulation6 preserves the authored Endurance profile and source identity."""
from copy import deepcopy
from dataclasses import replace
from itertools import product
import json
import pickle
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_magic_json import summary
from tests.unit.test_m8_magic_json_v4 import document as v4_document
from towr.adapters import magic_simulation_json as sim
from towr.adapters.magic_json_errors import MagicSimulationInputError
from towr.adapters.magic_json_schema import validate_magic_simulation_document
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.application.magic_simulation_errors import MagicSimulationExecutionError
from towr.domain.npc_magic_scenario_models import NpcMagicBatteredLegPolicy, NpcMagicCrushedRibPolicy
from towr.domain.test_models import InlineProfile


FIELD = 'battered_leg_continuation'


def document(*, miscast=False, stationary=False, repeated=False, crushed=False, battered=True,
             dice=2, threshold=5):
    data = v4_document(balance=False, miscast=miscast, stationary=stationary, repeated=repeated)
    data['schema_version'] = '6'
    data['scenario']['crushed_rib_continuation'] = (
        NpcMagicCrushedRibPolicy.NEXT_TEST_WITH_JOURNAL_WITNESSES.value if crushed else None)
    data['scenario'][FIELD] = {'endurance_profile': {'dice': dice, 'threshold': threshold}} if battered else None
    return data


class M8MagicJsonV6Tests(unittest.TestCase):
    def test_all_24_valid_permissions_echo_complete_source_and_8_dependencies_fail(self):
        rng = getstate()
        valid = invalid = 0
        with patch('random.Random', side_effect=AssertionError('wire creates no RNG')):
            for flags in product((False, True), repeat=5):
                raw = document(**dict(zip(('miscast', 'stationary', 'repeated', 'crushed', 'battered'), flags)))
                if flags[2] and not flags[1]:
                    with self.assertRaises(MagicSimulationInputError) as caught:
                        sim.parse_magic_simulation_request(json.dumps(raw))
                    self.assertEqual(caught.exception.schema_version, '6')
                    invalid += 1
                    continue
                command = sim.parse_magic_simulation_request(json.dumps(raw).encode())
                before = deepcopy(command)
                expected = NpcMagicBatteredLegPolicy(InlineProfile(2, 5)) if flags[4] else None
                self.assertEqual(command.request.scenario.battered_leg_continuation, expected)
                output = json.loads(sim.encode_magic_simulation_result(command, summary(command)))
                self.assertEqual(output['schema_version'], '6')
                self.assertEqual(output['request'], raw)
                self.assertEqual(sim.parse_magic_simulation_request(json.dumps(output['request'])), command)
                self.assertEqual(pickle.loads(pickle.dumps(command)), command)
                self.assertEqual(command, before)
                valid += 1
        self.assertEqual((valid, invalid), (24, 8))
        self.assertEqual(getstate(), rng)

    def test_profile_range_and_explicit_null_do_not_infer_from_casting(self):
        for dice, threshold in ((1, 1), (1, 5), (11, 5), (20, 10)):
            raw = document(dice=dice, threshold=threshold)
            command = sim.parse_magic_simulation_request(json.dumps(raw))
            self.assertEqual(command.request.scenario.battered_leg_continuation.endurance_profile,
                             InlineProfile(dice, threshold))
            self.assertEqual(json.loads(sim.encode_magic_simulation_result(command, summary(command)))['request'], raw)
        none = sim.parse_magic_simulation_request(json.dumps(document(battered=False)))
        self.assertEqual(none.schema_version, '6')
        self.assertIsNone(none.request.scenario.battered_leg_continuation)

    def test_missing_nested_fields_caps_bool_and_closed_objects_keep_v6_identity(self):
        invalid = (True, 0, '2d/5', {}, {'endurance_profile': {}},
            {'endurance_profile': {'dice': True, 'threshold': 5}},
            {'endurance_profile': {'dice': 0, 'threshold': 5}},
            {'endurance_profile': {'dice': 2, 'threshold': 11}},
            {'endurance_profile': {'dice': 2, 'threshold': 5, 'pool_cap': 4}},
            {'endurance_profile': {'dice': 2, 'threshold': 5}, 'actor_id': 'wizard'})
        for value in invalid:
            raw = document()
            raw['scenario'][FIELD] = value
            with self.subTest(value=value), self.assertRaises(MagicSimulationInputError) as caught:
                sim.parse_magic_simulation_request(json.dumps(raw))
            self.assertEqual((caught.exception.schema_version, caught.exception.request_id), ('6', raw['request_id']))
            encoded = json.loads(sim.encode_magic_simulation_error(caught.exception))
            validate_magic_simulation_document(encoded, 'error', schema_version='6')
        raw = document(battered=False)
        del raw['scenario'][FIELD]
        with self.assertRaises(MagicSimulationInputError) as caught:
            sim.parse_magic_simulation_request(json.dumps(raw))
        self.assertEqual(caught.exception.path, '/scenario')

    def test_lexical_errors_are_untrusted_and_unknown_seven_retains_decoded_id(self):
        prefix = '{"schema_version":"6","request_id":"untrusted",'
        for malformed in (prefix, prefix + '"n":2.0}', prefix + '"n":NaN}',
                          prefix + '"request_id":"duplicate"}', prefix + '"n":"\\ud800"}'):
            with self.subTest(malformed=malformed), self.assertRaises(MagicSimulationInputError) as caught:
                sim.parse_magic_simulation_request(malformed)
            self.assertEqual((caught.exception.schema_version, caught.exception.request_id), ('1', None))
        raw = dict(document(), schema_version='7')
        with self.assertRaises(MagicSimulationInputError) as caught:
            sim.parse_magic_simulation_request(json.dumps(raw))
        self.assertEqual((caught.exception.code, caught.exception.path, caught.exception.schema_version,
                          caught.exception.request_id), (Code.UNSUPPORTED_VERSION, '/schema_version', '1', raw['request_id']))

    def test_old_versions_refuse_profile_while_none_does_not_add_field(self):
        command = sim.parse_magic_simulation_request(json.dumps(document()))
        for version in ('1', '2', '3', '4', '5'):
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, 'Battered Leg.*losslessly'):
                sim.encode_magic_simulation_result(replace(command, schema_version=version), summary(command))
        legacy = sim.parse_magic_simulation_request(json.dumps(document(battered=False)))
        output = json.loads(sim.encode_magic_simulation_result(replace(legacy, schema_version='5'), summary(legacy)))
        self.assertNotIn(FIELD, output['request']['scenario'])

    def test_encoder_reads_original_equal_value_profile_alias_before_projection(self):
        command = sim.parse_magic_simulation_request(json.dumps(document(dice=1)))
        forged = deepcopy(command)
        object.__setattr__(forged.request.scenario.battered_leg_continuation.endurance_profile, 'dice', True)
        self.assertEqual(forged, command)
        with self.assertRaises(TypeError):
            sim.encode_magic_simulation_result(forged, summary(forged))

    def test_equally_identified_other_profile_summary_is_not_foreign_source_fallback(self):
        command = sim.parse_magic_simulation_request(json.dumps(document()))
        other = replace(command, request=replace(command.request, scenario=replace(command.request.scenario,
            battered_leg_continuation=NpcMagicBatteredLegPolicy(InlineProfile(2, 4)))))
        self.assertEqual(other.request.scenario.id, command.request.scenario.id)
        with self.assertRaises(ValueError):
            sim.encode_magic_simulation_result(command, summary(other))

    def test_execution_error_uses_six_without_private_cause_or_notes(self):
        error = MagicSimulationExecutionError('request-six', schema_version='6')
        error.__cause__ = RuntimeError('private cause')
        error.add_note('private note')
        encoded = sim.encode_magic_simulation_error(error)
        result = json.loads(encoded)
        self.assertEqual((result['schema_version'], result['request_id'], result['error']['code']),
                         ('6', 'request-six', 'simulation_failed'))
        validate_magic_simulation_document(result, 'error', schema_version='6')
        self.assertNotIn('private', encoded)


if __name__ == '__main__':
    unittest.main()
