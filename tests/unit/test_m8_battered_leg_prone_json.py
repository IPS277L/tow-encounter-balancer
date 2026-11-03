"""Explicit Battered Leg self-stand permission in the sole current wire contract."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from tests.unit.test_m8_magic_json import summary
from tests.unit.test_m8_magic_json_v6 import document as simulation_document
from tests.unit.test_m8_magic_balance_json import make_result
from tests.unit.test_m8_magic_balance_json_v6 import document as balance_document
from towr.adapters import magic_balance_json as balance, magic_simulation_json as simulation
from towr.adapters._magic_scenario_json import battered_leg_continuation_document
from towr.adapters.magic_json_errors import MagicBalanceInputError, MagicSimulationInputError
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.domain.npc_magic_scenario_models import NpcMagicPronePolicy


FIELD = 'battered_leg_continuation'
SELECTED = NpcMagicPronePolicy.SELF_STAND_WHEN_SAFE
BOUNDARIES = (
    (False, simulation_document, simulation.parse_magic_simulation_request, MagicSimulationInputError),
    (True, balance_document, balance.parse_magic_balance_request, MagicBalanceInputError),
)


def nodes(document, balanced):
    return ((document['reserve']['scenario'], document['generation']) if balanced
            else (document['scenario'],))


class BatteredLegProneJsonTests(unittest.TestCase):
    def test_explicit_null_and_selected_permission_preserve_full_echo_without_execution(self):
        for balanced, build, parse, _ in BOUNDARIES:
            for permission in (None, SELECTED):
                raw = build()
                for node in nodes(raw, balanced):
                    node[FIELD]['prone_policy'] = None if permission is None else permission.value
                with self.subTest(balance=balanced, permission=permission), patch(
                        'random.Random', side_effect=AssertionError('wire creates no RNG')):
                    command = parse(json.dumps(raw))
                    if balanced:
                        source = command.generation_request
                        self.assertIs(source.battered_leg_continuation.prone_policy, permission)
                        result = make_result(command)
                        for candidate in result.generation_result.evaluation_request.candidates:
                            self.assertEqual(candidate.scenario.battered_leg_continuation,
                                             source.battered_leg_continuation)
                        encoded = balance.encode_magic_balance_result(command, result)
                    else:
                        self.assertIs(command.request.scenario.battered_leg_continuation.prone_policy,
                                      permission)
                        encoded = simulation.encode_magic_simulation_result(command, summary(command))
                    echoed = json.loads(encoded)['request']
                    self.assertEqual(echoed, raw)
                    self.assertEqual(parse(json.dumps(echoed)), command)

    def test_missing_unknown_and_nonnullable_values_keep_current_error_identity(self):
        for balanced, build, parse, error_type in BOUNDARIES:
            for location in range(2 if balanced else 1):
                for invalid in ('missing', 'recover', '', True, False, 1, {}, []):
                    raw = build()
                    policy = nodes(raw, balanced)[location][FIELD]
                    if invalid == 'missing':
                        del policy['prone_policy']
                    else:
                        policy['prone_policy'] = invalid
                    with self.subTest(balance=balanced, location=location, invalid=invalid):
                        with self.assertRaises(error_type) as caught:
                            parse(json.dumps(raw))
                        self.assertEqual((caught.exception.code, caught.exception.schema_version,
                                          caught.exception.request_id),
                                         (Code.INVALID_INPUT, '6', raw['request_id']))

    def test_family_matching_includes_the_independent_prone_permission(self):
        for reserve, family in ((None, SELECTED.value), (SELECTED.value, None)):
            raw = balance_document()
            raw['reserve']['scenario'][FIELD]['prone_policy'] = reserve
            raw['generation'][FIELD]['prone_policy'] = family
            with self.subTest(reserve=reserve, family=family), self.assertRaises(
                    MagicBalanceInputError) as caught:
                balance.parse_magic_balance_request(json.dumps(raw))
            self.assertEqual(caught.exception.path, '/generation/' + FIELD)

    def test_original_raw_enum_alias_is_rejected_before_profile_projection(self):
        raw = simulation_document()
        raw['scenario'][FIELD]['prone_policy'] = SELECTED.value
        command = simulation.parse_magic_simulation_request(json.dumps(raw))
        policy = command.request.scenario.battered_leg_continuation
        forged = deepcopy(policy)
        object.__setattr__(forged, 'prone_policy', SELECTED.value)
        self.assertEqual(forged, policy)
        with patch('towr.adapters._magic_scenario_json._profile_document',
                   side_effect=AssertionError('no projection before original admission')):
            with self.assertRaises(TypeError):
                battered_leg_continuation_document(forged)


if __name__ == '__main__':
    unittest.main()
