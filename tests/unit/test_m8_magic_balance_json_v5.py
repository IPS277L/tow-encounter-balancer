"""Current Magic JSON contract: deterministic admission and source guards."""
from copy import deepcopy
from dataclasses import replace
import json
import pickle
import random
import unittest
from unittest.mock import patch

from tests.unit.test_m8_magic_balance_json import make_result
from tests.unit.test_m8_magic_json_v4 import document as v4_document
from tests.unit.test_m8_magic_json_v5 import POLICY
from towr.adapters import magic_balance_json as bal
from towr.adapters.magic_json_errors import MagicBalanceInputError
from towr.adapters.magic_json_schema import validate_magic_balance_document
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.application.magic_balance_errors import MagicBalanceGenerationError, MagicBalanceExecutionError
from towr.domain.npc_magic_scenario_models import NpcMagicCrushedRibPolicy as CrushedRib


FIELD = 'crushed_rib_continuation'


def document(*, miscast=False, stationary=False, repeated=False, crushed=False):
    data = v4_document(balance=True, stationary=stationary, miscast=miscast, repeated=repeated)
    data['schema_version'] = '6'
    value = CrushedRib.NEXT_TEST_WITH_JOURNAL_WITNESSES.value if crushed else None
    data['reserve']['scenario'][FIELD] = value
    data['generation'][FIELD] = value
    return data


class M8MagicBalanceJsonV5Tests(unittest.TestCase):
    def test_all_twelve_valid_permission_combinations_echo_full_source_and_result(self):
        rng = random.getstate()
        for mask in range(16):
            miscast, stationary, repeated, crushed = (bool(mask & (1 << bit)) for bit in range(4))
            if repeated and not stationary:
                continue
            raw = document(miscast=miscast, stationary=stationary, repeated=repeated, crushed=crushed)
            command = bal.parse_magic_balance_request(json.dumps(raw).encode('utf-8'))
            before = deepcopy(command)
            source = command.generation_request
            scenario = source.template_scenario
            self.assertEqual(scenario.crushed_rib_continuation,
                             CrushedRib.NEXT_TEST_WITH_JOURNAL_WITNESSES if crushed else None)
            self.assertIs(source.crushed_rib_continuation,
                          CrushedRib.NEXT_TEST_WITH_JOURNAL_WITNESSES if crushed else None)
            result = make_result(command)
            output = json.loads(bal.encode_magic_balance_result(command, result))
            validate_magic_balance_document(output, 'result', schema_version='6')
            self.assertEqual(output['request'], raw)
            self.assertEqual(bal.parse_magic_balance_request(json.dumps(output['request'])), command)
            self.assertEqual(pickle.loads(pickle.dumps(command)), command)
            self.assertEqual(command, before)
        self.assertEqual(random.getstate(), rng)

    def test_crushed_reserve_family_mismatch_has_its_own_path_and_v5_error(self):
        for reserve_value, family_value in ((None, POLICY.value), (POLICY.value, None)):
            raw = document(crushed=True)
            raw['reserve']['scenario'][FIELD] = reserve_value
            raw['generation'][FIELD] = family_value
            with self.subTest(reserve=reserve_value, family=family_value),\
                    self.assertRaises(MagicBalanceInputError) as caught:
                bal.parse_magic_balance_request(json.dumps(raw))
            self.assertEqual((caught.exception.schema_version, caught.exception.request_id,
                              caught.exception.path, caught.exception.code),
                             ('6', raw['request_id'], '/generation/' + FIELD, Code.INVALID_INPUT))
            output = json.loads(bal.encode_magic_balance_error(caught.exception))
            validate_magic_balance_document(output, 'error', schema_version='6')
            self.assertEqual((output['schema_version'], output['request_id']), ('6', raw['request_id']))

    def test_required_exact_types_and_version_fallbacks(self):
        for location in ('reserve', 'generation'):
            for value in (False, True, 0, 1, {}, [], '', 'NEXT_TEST_WITH_JOURNAL_WITNESSES', 'unknown'):
                raw = document(crushed=True)
                node = raw['reserve']['scenario'] if location == 'reserve' else raw['generation']
                node[FIELD] = value
                with self.subTest(location=location, value=value), self.assertRaises(MagicBalanceInputError) as caught:
                    bal.parse_magic_balance_request(json.dumps(raw))
                self.assertEqual((caught.exception.schema_version, caught.exception.request_id),
                                 ('6', raw['request_id']))
            raw = document(crushed=True)
            node = raw['reserve']['scenario'] if location == 'reserve' else raw['generation']
            del node[FIELD]
            with self.assertRaises(MagicBalanceInputError) as caught:
                bal.parse_magic_balance_request(json.dumps(raw))
            self.assertEqual(caught.exception.schema_version, '6')
        with self.assertRaises(MagicBalanceInputError) as caught:
            bal.parse_magic_balance_request(json.dumps(dict(document(crushed=True), schema_version='7')))
        self.assertEqual((caught.exception.schema_version, caught.exception.request_id, caught.exception.code,
                          caught.exception.path), ('6', document()['request_id'], Code.UNSUPPORTED_VERSION,
                                                    '/schema_version'))
        for malformed in ('{"schema_version":"6","request_id":"x","request_id":"y"}',
                          '{"schema_version":"6","request_id":"x","n":NaN}'):
            with self.assertRaises(MagicBalanceInputError) as caught:
                bal.parse_magic_balance_request(malformed)
            self.assertEqual((caught.exception.schema_version, caught.exception.request_id), ('6', None))



if __name__ == '__main__':
    unittest.main()
