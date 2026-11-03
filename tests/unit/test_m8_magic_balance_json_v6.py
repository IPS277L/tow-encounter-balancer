"""Current Magic JSON contract: deterministic admission and source guards."""
from copy import deepcopy
from dataclasses import replace
from itertools import product
import json
import pickle
import unittest

from tests.unit.test_m8_magic_balance_json import make_result
from tests.unit.test_m8_magic_balance_json_v5 import document as v5_document
from towr.adapters import magic_balance_json as bal
from towr.adapters.magic_json_errors import MagicBalanceInputError
from towr.adapters.magic_json_schema import validate_magic_balance_document
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.application.magic_balance_errors import MagicBalanceGenerationError, MagicBalanceExecutionError
from towr.domain.npc_magic_scenario_models import NpcMagicBatteredLegPolicy
from towr.domain.test_models import InlineProfile


FIELD = 'battered_leg_continuation'


def document(*, miscast=False, stationary=False, repeated=False, crushed=False, battered=True,
             dice=2, threshold=5):
    data = v5_document(miscast=miscast, stationary=stationary, repeated=repeated, crushed=crushed)
    data['schema_version'] = '6'
    profile = {'endurance_profile': {'dice': dice, 'threshold': threshold}, 'prone_policy': None} if battered else None
    data['reserve']['scenario'][FIELD] = deepcopy(profile)
    data['generation'][FIELD] = deepcopy(profile)
    return data


class M8MagicBalanceJsonV6Tests(unittest.TestCase):
    def test_only_current_version_is_admitted_and_old_versions_use_current_error_shape(self):
        original = bal.parse_magic_balance_request(json.dumps(document()))
        for version in ('1', '2', '3', '4', '5', '7'):
            with self.subTest(version=version):
                raw = dict(document(), schema_version=version)
                with self.assertRaises(MagicBalanceInputError) as caught:
                    bal.parse_magic_balance_request(json.dumps(raw))
                error = caught.exception
                self.assertEqual((error.code, error.path, error.request_id, error.schema_version),
                    (Code.UNSUPPORTED_VERSION, '/schema_version', raw['request_id'], '6'))
                output = json.loads(bal.encode_magic_balance_error(error))
                validate_magic_balance_document(output, 'error')
                self.assertEqual(output['schema_version'], '6')
                with self.assertRaises(ValueError):
                    replace(original, schema_version=version)
                with self.assertRaises(ValueError):
                    MagicBalanceInputError(Code.INVALID_INPUT, 'bad', schema_version=version)

    def test_all_24_valid_matching_profiles_roundtrip_full_generation_and_echo(self):
        valid = invalid = 0
        for flags in product((False, True), repeat=5):
            raw = document(**dict(zip(('miscast', 'stationary', 'repeated', 'crushed', 'battered'), flags)))
            if flags[2] and not flags[1]:
                with self.assertRaises(MagicBalanceInputError) as caught:
                    bal.parse_magic_balance_request(json.dumps(raw))
                self.assertEqual(caught.exception.schema_version, '6')
                invalid += 1
                continue
            command = bal.parse_magic_balance_request(json.dumps(raw))
            before = deepcopy(command)
            family = command.generation_request
            self.assertEqual(family.battered_leg_continuation, family.template_scenario.battered_leg_continuation)
            result = make_result(command)
            self.assertTrue(all(c.scenario.battered_leg_continuation == family.battered_leg_continuation
                for c in result.generation_result.evaluation_request.candidates))
            encoded = json.loads(bal.encode_magic_balance_result(command, result))
            validate_magic_balance_document(encoded, 'result', schema_version='6')
            self.assertEqual(encoded['request'], raw)
            self.assertEqual(bal.parse_magic_balance_request(json.dumps(encoded['request'])), command)
            self.assertEqual(pickle.loads(pickle.dumps(command)), command)
            self.assertEqual(command, before)
            valid += 1
        self.assertEqual((valid, invalid), (24, 8))

    def test_same_dice_different_threshold_and_other_matching_errors_have_own_path(self):
        for reserve_value, family_value in ((None, {'endurance_profile': {'dice': 2, 'threshold': 5}, 'prone_policy': None}),
                ({'endurance_profile': {'dice': 2, 'threshold': 5}, 'prone_policy': None}, None),
                ({'endurance_profile': {'dice': 2, 'threshold': 5}, 'prone_policy': None}, {'endurance_profile': {'dice': 2, 'threshold': 4}, 'prone_policy': None}),
                ({'endurance_profile': {'dice': 2, 'threshold': 5}, 'prone_policy': None}, {'endurance_profile': {'dice': 3, 'threshold': 5}, 'prone_policy': None})):
            raw = document()
            raw['reserve']['scenario'][FIELD] = reserve_value
            raw['generation'][FIELD] = family_value
            with self.subTest(reserve=reserve_value, family=family_value), self.assertRaises(MagicBalanceInputError) as caught:
                bal.parse_magic_balance_request(json.dumps(raw))
            self.assertEqual((caught.exception.schema_version, caught.exception.request_id, caught.exception.path,
                              caught.exception.code), ('6', raw['request_id'], '/generation/' + FIELD, Code.INVALID_INPUT))
            encoded = json.loads(bal.encode_magic_balance_error(caught.exception))
            validate_magic_balance_document(encoded, 'error', schema_version='6')

    def test_required_nullable_profile_objects_are_closed_on_both_sides(self):
        for location in ('reserve', 'generation'):
            for invalid in (True, 1, {}, {'endurance_profile': {'dice': 2, 'threshold': False}, 'prone_policy': None},
                    {'endurance_profile': {'dice': 2, 'threshold': 5, 'pool_cap': 4}, 'prone_policy': None},
                    {'endurance_profile': {'dice': 2, 'threshold': 5}, 'facts': {}, 'prone_policy': None}):
                raw = document()
                node = raw['reserve']['scenario'] if location == 'reserve' else raw['generation']
                node[FIELD] = invalid
                with self.subTest(location=location, invalid=invalid), self.assertRaises(MagicBalanceInputError) as caught:
                    bal.parse_magic_balance_request(json.dumps(raw))
                self.assertEqual((caught.exception.schema_version, caught.exception.request_id), ('6', raw['request_id']))
            raw = document(battered=False)
            node = raw['reserve']['scenario'] if location == 'reserve' else raw['generation']
            del node[FIELD]
            with self.assertRaises(MagicBalanceInputError):
                bal.parse_magic_balance_request(json.dumps(raw))
        for dice in (1, 11):
            raw = document(dice=dice)
            command = bal.parse_magic_balance_request(json.dumps(raw))
            self.assertEqual(command.generation_request.battered_leg_continuation.endurance_profile, InlineProfile(dice, 5))


    def test_original_profile_and_late_derived_cache_cannot_be_normalized_away(self):
        selected = bal.parse_magic_balance_request(json.dumps(document(dice=1)))
        raw = deepcopy(selected)
        object.__setattr__(raw.generation_request.battered_leg_continuation.endurance_profile, 'dice', True)
        self.assertEqual(raw, selected)
        with self.assertRaises(TypeError):
            bal.encode_magic_balance_result(raw, make_result(selected))
        result = make_result(selected)
        report_source = result.evaluation_result.stage_reports[-1].source_request
        requests = report_source.simulation_requests
        other = replace(requests[-1], scenario=replace(requests[-1].scenario,
            battered_leg_continuation=NpcMagicBatteredLegPolicy(InlineProfile(1, 4))))
        object.__setattr__(report_source, 'simulation_requests', (*requests[:-1], other))
        with self.assertRaises(ValueError):
            bal.encode_magic_balance_result(selected, result)

    def test_known_six_lexical_fallback_unknown_seven_and_phase_error_privacy(self):
        for malformed in ('{"schema_version":"6","request_id":"x","n":2.0}',
                          '{"schema_version":"6","request_id":"x","request_id":"y"}'):
            with self.assertRaises(MagicBalanceInputError) as caught:
                bal.parse_magic_balance_request(malformed)
            self.assertEqual((caught.exception.schema_version, caught.exception.request_id), ('6', None))
        raw = dict(document(), schema_version='7')
        with self.assertRaises(MagicBalanceInputError) as caught:
            bal.parse_magic_balance_request(json.dumps(raw))
        self.assertEqual((caught.exception.schema_version, caught.exception.request_id, caught.exception.code),
                         ('6', raw['request_id'], Code.UNSUPPORTED_VERSION))
        for error in (MagicBalanceGenerationError('request-six', schema_version='6'),
                      MagicBalanceExecutionError('request-six', schema_version='6')):
            error.__cause__ = RuntimeError('private cause')
            error.add_note('private note')
            encoded = bal.encode_magic_balance_error(error)
            output = json.loads(encoded)
            self.assertEqual((output['schema_version'], output['request_id']), ('6', 'request-six'))
            validate_magic_balance_document(output, 'error', schema_version='6')
            self.assertNotIn('private', encoded)


if __name__ == '__main__':
    unittest.main()
