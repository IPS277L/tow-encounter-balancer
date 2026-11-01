"""ADR-0054 requires matching generation permission; JSON1/2/3 remain closed."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import json
import pickle
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_magic_json import document as simulation_v1, summary
from tests.unit.test_m8_magic_json_v2 import document as simulation_v2
from tests.unit.test_m8_magic_json_v3 import document as simulation_v3
from tests.unit.test_m8_magic_balance_json import document as balance_v1, make_result
from tests.unit.test_m8_magic_balance_json_v2 import document as balance_v2
from tests.unit.test_m8_magic_balance_json_v3 import document as balance_v3
from tests.unit.test_m8_stationary_wound_generation import family, Unreadable
from towr.adapters._magic_scenario_json import scenario_document
from towr.adapters import magic_balance_json as balance_wire, magic_simulation_json as simulation_wire
from towr.adapters.magic_json_errors import MagicBalanceInputError, MagicSimulationInputError
from towr.application import magic_candidate_generation as generation
from towr.application.magic_candidate_generation_models import MagicCandidateGenerationResult
from towr.domain.npc_magic_scenario_models import (
    NpcMagicRepeatedLegSpasmPolicy as Policy, NpcMagicStationaryWoundPolicy as Stationary,
)


FIELD = 'repeated_leg_spasm_continuation'
POLICY = Policy.STAND_ONCE_WITH_JOURNAL_WITNESSES


def documents(family_name):
    if family_name == 'simulation':
        return simulation_v1(), simulation_v2(opted=False), simulation_v3(stationary=True, miscast=True)
    return balance_v1(), balance_v2(opted=False), balance_v3(stationary=True, miscast=True)


def opted(source):
    return replace(source, stationary_wound_continuation=Stationary.LEG_SPASM_STAND_AND_CONTINUE,
                   repeated_leg_spasm_continuation=POLICY)


class RepeatedLegSpasmRefusalTests(unittest.TestCase):
    def test_generation_constructor_refuses_before_materializing_collections(self):
        source = family()
        before = deepcopy(source)
        rng = getstate()
        with patch('random.Random', side_effect=AssertionError('no RNG')):
            with self.assertRaisesRegex(ValueError, 'repeated Leg Spasm.*explicit family'):
                replace(source, template_scenario=opted(source.template_scenario),
                    groups=Unreadable(source.groups), scene_frames=Unreadable(source.scene_frames),
                    stages=Unreadable(source.stages))
        self.assertEqual(source, before)
        self.assertEqual(getstate(), rng)

    def test_factory_and_result_reject_unpickled_opted_source_before_enumeration(self):
        source = family()
        generated = generation.generate_magic_candidates(source)
        corrupted = deepcopy(source)
        object.__setattr__(corrupted, 'template_scenario', opted(corrupted.template_scenario))
        corrupted = pickle.loads(pickle.dumps(corrupted))
        before = deepcopy(corrupted)
        with (patch.object(generation, '_count_vectors', side_effect=AssertionError('no enumeration')) as counts,
              patch.object(generation, '_project_candidate', side_effect=AssertionError('no projection')) as project):
            for operation in (lambda: generation.generate_magic_candidates(corrupted),
                              lambda: MagicCandidateGenerationResult(corrupted, generated.evaluation_request)):
                with self.assertRaisesRegex(ValueError, 'repeated Leg Spasm.*explicit family'):
                    operation()
            counts.assert_not_called()
            project.assert_not_called()
        self.assertEqual(corrupted, before)
        self.assertIsNone(source.template_scenario.repeated_leg_spasm_continuation)

    def test_every_transported_candidate_is_refused_before_any_vector_or_projection(self):
        generated = generation.generate_magic_candidates(family())
        for index in (0, len(generated.evaluation_request.candidates) - 1):
            wrong = deepcopy(generated)
            child = wrong.evaluation_request.candidates[index]
            object.__setattr__(child, 'scenario', opted(child.scenario))
            before = deepcopy(wrong)
            with (patch.object(generation, '_count_vectors', side_effect=AssertionError('no enumeration')) as counts,
                  patch.object(generation, '_project_candidate', side_effect=AssertionError('no projection')) as project):
                with self.subTest(index=index), self.assertRaisesRegex(ValueError, 'repeated Leg Spasm.*explicit family'):
                    replace(wrong)
                counts.assert_not_called()
                project.assert_not_called()
            self.assertEqual(wrong, before)

    def test_detached_policy_aliases_are_type_errors_before_equality(self):
        source = family()
        selected = opted(source.template_scenario)
        for value in (POLICY.value, True, False, 0, 1, {}, Stationary.LEG_SPASM_STAND_AND_CONTINUE):
            scenario = deepcopy(selected)
            object.__setattr__(scenario, FIELD, value)
            if value == POLICY.value:
                self.assertEqual(scenario, selected)
            wrong = deepcopy(source)
            object.__setattr__(wrong, 'template_scenario', scenario)
            with (patch.object(generation, '_count_vectors', side_effect=AssertionError('no enumeration')) as counts,
                  patch.object(generation, '_project_candidate', side_effect=AssertionError('no projection')) as project):
                with self.subTest(value=value), self.assertRaises(TypeError):
                    generation.generate_magic_candidates(wrong)
                counts.assert_not_called()
                project.assert_not_called()
            for version in ('1', '2', '3'):
                with self.subTest(value=value, version=version), self.assertRaises(TypeError):
                    scenario_document(scenario, ('missing',), schema_version=version)

    def test_same_value_raw_candidate_permission_cannot_hide_in_result_equality(self):
        generated = generation.generate_magic_candidates(family())
        wrong = deepcopy(generated)
        child = wrong.evaluation_request.candidates[-1]
        selected = opted(child.scenario)
        corrupt = deepcopy(selected)
        object.__setattr__(corrupt, FIELD, POLICY.value)
        self.assertEqual(corrupt, selected)
        object.__setattr__(child, 'scenario', corrupt)
        with (patch.object(generation, '_count_vectors', side_effect=AssertionError('no enumeration')) as counts,
              patch.object(generation, '_project_candidate', side_effect=AssertionError('no projection')) as project):
            with self.assertRaises(TypeError):
                replace(wrong)
            counts.assert_not_called()
            project.assert_not_called()
        self.assertIs(type(child.scenario.repeated_leg_spasm_continuation), str)

    def test_direct_mapper_refuses_all_versions_before_definition_projection(self):
        source = opted(family().template_scenario)
        before = deepcopy(source)
        for version in ('1', '2', '3'):
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, 'repeated Leg Spasm.*losslessly'):
                scenario_document(source, ('missing',), schema_version=version)
        self.assertEqual(source, before)

    def test_simulation_request_result_and_detached_summary_refuse_without_codec_reconstruction(self):
        for document in documents('simulation'):
            base = simulation_wire.parse_magic_simulation_request(json.dumps(document))
            command = replace(base, request=replace(base.request, scenario=opted(base.request.scenario)))
            before = deepcopy(command)
            with (patch.object(simulation_wire, 'parse_magic_simulation_request', side_effect=AssertionError('no reconstruct')),
                  patch('random.Random', side_effect=AssertionError('no RNG'))):
                for operation in (lambda: simulation_wire._request_document(command),
                                  lambda: simulation_wire.encode_magic_simulation_result(command, summary(command))):
                    with self.subTest(version=command.schema_version), self.assertRaisesRegex(ValueError, 'repeated Leg Spasm.*losslessly'):
                        operation()
            foreign = deepcopy(summary(command))
            object.__setattr__(foreign.source_request.scenario, FIELD, POLICY.value)
            self.assertEqual(foreign.source_request, command.request)
            # Both sources must be admitted before equality can hide a raw Enum.
            clean_command = replace(command, request=replace(command.request,
                scenario=replace(command.request.scenario, repeated_leg_spasm_continuation=None)))
            with self.assertRaises(TypeError):
                simulation_wire.encode_magic_simulation_result(clean_command, foreign)
            self.assertEqual(command, before)

    def test_balance_request_and_generation_report_chain_refuse_without_enumeration(self):
        for document in documents('balance'):
            base = balance_wire.parse_magic_balance_request(json.dumps(document))
            selected_source = replace(base.generation_request,
                template_scenario=opted(base.generation_request.template_scenario),
                stationary_wound_continuation=Stationary.LEG_SPASM_STAND_AND_CONTINUE,
                repeated_leg_spasm_continuation=POLICY)
            command = replace(base, generation_request=selected_source)
            result = make_result(command)
            with (patch.object(generation, '_count_vectors', side_effect=AssertionError('no enumeration')) as counts,
                  patch.object(generation, '_project_candidate', side_effect=AssertionError('no projection')) as project):
                for operation in (lambda: balance_wire._request_document(command),
                                  lambda: balance_wire.encode_magic_balance_result(command, result)):
                    with self.subTest(version=base.schema_version), self.assertRaisesRegex(ValueError, 'repeated Leg Spasm.*losslessly'):
                        operation()
                counts.assert_not_called()
                project.assert_not_called()
        base = balance_wire.parse_magic_balance_request(json.dumps(balance_v3(stationary=True)))
        result = deepcopy(make_result(base))
        child = result.generation_result.evaluation_request.candidates[-1]
        object.__setattr__(child, 'scenario', opted(child.scenario))
        with patch.object(generation, '_count_vectors', side_effect=AssertionError('no enumeration')) as counts:
            with self.assertRaisesRegex(ValueError, 'repeated Leg Spasm.*explicit family'):
                balance_wire.encode_magic_balance_result(base, result)
            counts.assert_not_called()

    def test_all_closed_versions_refuse_even_null_unknown_permission(self):
        for family_name, parser, error_type in (
            ('simulation', simulation_wire.parse_magic_simulation_request, MagicSimulationInputError),
            ('balance', balance_wire.parse_magic_balance_request, MagicBalanceInputError),
        ):
            for original in documents(family_name):
                locations = ('scenario',) if family_name == 'simulation' else ('reserve', 'generation')
                for location in locations:
                    for value in (None, POLICY.value):
                        document = deepcopy(original)
                        target = document['scenario'] if family_name == 'simulation' else (
                            document['reserve']['scenario'] if location == 'reserve' else document['generation'])
                        target[FIELD] = value
                        with self.subTest(family=family_name, version=original['schema_version'], location=location, value=value):
                            with self.assertRaises(error_type) as caught:
                                parser(json.dumps(document))
                            self.assertEqual(caught.exception.schema_version, original['schema_version'])

    def test_none_roundtrip_preserves_full_existing_documents_and_exact_encoder_bytes(self):
        rng = getstate()
        with ExitStack() as stack:
            stack.enter_context(patch('random.Random', side_effect=AssertionError('no RNG')))
            for family_name, parser, encoder, result_factory in (
                ('simulation', simulation_wire.parse_magic_simulation_request, simulation_wire.encode_magic_simulation_result, summary),
                ('balance', balance_wire.parse_magic_balance_request, balance_wire.encode_magic_balance_result, make_result),
            ):
                for original in documents(family_name):
                    command = parser(json.dumps(original))
                    result = result_factory(command)
                    encoded = encoder(command, result)
                    restored = parser(json.dumps(json.loads(encoded)['request']))
                    self.assertEqual(restored, command)
                    self.assertEqual(json.loads(encoded)['request'], original)
                    self.assertNotIn(FIELD, encoded)
                    self.assertEqual(encoder(restored, result_factory(restored)), encoded)
        self.assertEqual(getstate(), rng)


if __name__ == '__main__':
    unittest.main()
