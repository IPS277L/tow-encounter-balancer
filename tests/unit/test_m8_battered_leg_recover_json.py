"""Recover permission is explicit and confined to Battered Leg in current JSON6."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from tests.unit.test_m8_battered_leg_prone_json import BOUNDARIES, FIELD, nodes
from tests.unit.test_m8_magic_json import summary
from tests.unit.test_m8_magic_balance_json import make_result
from towr.adapters import magic_balance_json as balance, magic_simulation_json as simulation
from towr.adapters._magic_scenario_json import battered_leg_continuation_document
from towr.adapters.magic_json_errors import MagicBalanceInputError
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.domain.npc_magic_scenario_models import NpcMagicPronePolicy


RECOVER = 'recover_self'


class BatteredLegRecoverJsonTests(unittest.TestCase):
    def test_recover_permission_preserves_full_command_generation_and_result_echo(self):
        permission = NpcMagicPronePolicy(RECOVER)
        for balanced, build, parse, _ in BOUNDARIES:
            raw = build()
            for node in nodes(raw, balanced):
                node[FIELD]['prone_policy'] = RECOVER
            with self.subTest(balance=balanced), patch(
                    'random.Random', side_effect=AssertionError('wire creates no RNG')):
                command = parse(json.dumps(raw))
                before = deepcopy(command)
                if balanced:
                    policy = command.generation_request.battered_leg_continuation
                    self.assertIs(policy.prone_policy, permission)
                    result = make_result(command)
                    self.assertTrue(all(candidate.scenario.battered_leg_continuation == policy
                        for candidate in result.generation_result.evaluation_request.candidates))
                    encoded = balance.encode_magic_balance_result(command, result)
                else:
                    self.assertIs(command.request.scenario.battered_leg_continuation.prone_policy, permission)
                    encoded = simulation.encode_magic_simulation_result(command, summary(command))
                echoed = json.loads(encoded)
                self.assertEqual(echoed['schema_version'], '6')
                self.assertEqual(echoed['request'], raw)
                self.assertEqual(parse(json.dumps(echoed['request'])), command)
                self.assertEqual(command, before)

    def test_family_matching_distinguishes_recover_from_self_stand_and_null(self):
        _, build, parse, _ = BOUNDARIES[1]
        for other in (None, NpcMagicPronePolicy.SELF_STAND_WHEN_SAFE.value):
            for reserve, family in ((RECOVER, other), (other, RECOVER)):
                raw = build()
                raw['reserve']['scenario'][FIELD]['prone_policy'] = reserve
                raw['generation'][FIELD]['prone_policy'] = family
                with self.subTest(reserve=reserve, family=family), self.assertRaises(
                        MagicBalanceInputError) as caught:
                    parse(json.dumps(raw))
                self.assertEqual(caught.exception.path, '/generation/' + FIELD)

    def test_miscast_permission_does_not_gain_recover_mode(self):
        permission = NpcMagicPronePolicy(RECOVER)
        for balanced, build, parse, error_type in BOUNDARIES:
            raw = build(miscast=True)
            command = parse(json.dumps(raw))
            source = command.generation_request.template_scenario if balanced else command.request.scenario
            with self.subTest(balance=balanced), self.assertRaises(ValueError):
                replace(source.miscast_continuation, prone_policy=permission)
            for node in nodes(raw, balanced):
                node['miscast_continuation']['prone_policy'] = RECOVER
            with self.subTest(balance=balanced), self.assertRaises(error_type) as caught:
                parse(json.dumps(raw))
            self.assertEqual((caught.exception.code, caught.exception.schema_version), (Code.INVALID_INPUT, '6'))

    def test_unknown_or_mistyped_modes_remain_invalid(self):
        for balanced, build, parse, error_type in BOUNDARIES:
            for invalid in ('recover', 'RECOVER_SELF', 'recover_ally', False, 0, {}, []):
                raw = build()
                for node in nodes(raw, balanced):
                    node[FIELD]['prone_policy'] = invalid
                with self.subTest(balance=balanced, invalid=invalid), self.assertRaises(error_type) as caught:
                    parse(json.dumps(raw))
                self.assertEqual((caught.exception.code, caught.exception.schema_version), (Code.INVALID_INPUT, '6'))

    def test_original_raw_recover_enum_alias_is_rejected_before_projection(self):
        _, build, parse, _ = BOUNDARIES[0]
        raw = build()
        raw['scenario'][FIELD]['prone_policy'] = RECOVER
        policy = parse(json.dumps(raw)).request.scenario.battered_leg_continuation
        forged = deepcopy(policy)
        object.__setattr__(forged, 'prone_policy', RECOVER)
        self.assertEqual(forged, policy)
        with patch('towr.adapters._magic_scenario_json._profile_document',
                   side_effect=AssertionError('no projection before original admission')):
            with self.assertRaises(TypeError):
                battered_leg_continuation_document(forged)

    def test_other_prone_permission_summary_is_a_different_full_source(self):
        _, build, parse, _ = BOUNDARIES[0]
        raw = build()
        raw['scenario'][FIELD]['prone_policy'] = RECOVER
        command = parse(json.dumps(raw))
        different_policy = replace(command.request.scenario.battered_leg_continuation,
                                   prone_policy=NpcMagicPronePolicy.SELF_STAND_WHEN_SAFE)
        foreign = replace(command, request=replace(command.request,
            scenario=replace(command.request.scenario, battered_leg_continuation=different_policy)))
        with self.assertRaises(ValueError):
            simulation.encode_magic_simulation_result(command, summary(foreign))


if __name__ == '__main__':
    unittest.main()
