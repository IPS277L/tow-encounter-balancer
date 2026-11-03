"""Repeated Leg Spasm retains matching-family and original-source admission guards."""
from copy import deepcopy
from dataclasses import replace
import json
import pickle
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_magic_json import document as simulation_document, summary
from tests.unit.test_m8_magic_balance_json import document as balance_document, make_result
from tests.unit.test_m8_stationary_wound_generation import family, Unreadable
from towr.adapters._magic_scenario_json import scenario_document
from towr.adapters import magic_balance_json as balance_wire, magic_simulation_json as simulation_wire
from towr.application import magic_candidate_generation as generation
from towr.application.magic_candidate_generation_models import MagicCandidateGenerationResult
from towr.domain.npc_magic_scenario_models import (
    NpcMagicRepeatedLegSpasmPolicy as Policy, NpcMagicStationaryWoundPolicy as Stationary,
)


FIELD = 'repeated_leg_spasm_continuation'
POLICY = Policy.STAND_ONCE_WITH_JOURNAL_WITNESSES




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
            with self.subTest(value=value, boundary='current mapper'), self.assertRaises(TypeError):
                scenario_document(scenario, ('missing',), schema_version='6')

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






    def test_same_value_raw_summary_permission_is_admitted_before_equality(self):
        base = simulation_wire.parse_magic_simulation_request(json.dumps(simulation_document()))
        command = replace(base, request=replace(base.request, scenario=opted(base.request.scenario)))
        foreign = deepcopy(summary(command))
        object.__setattr__(foreign.source_request.scenario, FIELD, POLICY.value)
        self.assertEqual(foreign.source_request, command.request)
        with patch.object(simulation_wire, 'parse_magic_simulation_request',
                          side_effect=AssertionError('no reconstruction before source admission')):
            with self.assertRaises(TypeError):
                simulation_wire.encode_magic_simulation_result(command, foreign)

    def test_balance_report_candidate_policy_is_checked_before_enumeration(self):
        data = balance_document()
        data['reserve']['scenario']['stationary_wound_continuation'] = Stationary.LEG_SPASM_STAND_AND_CONTINUE.value
        data['generation']['stationary_wound_continuation'] = Stationary.LEG_SPASM_STAND_AND_CONTINUE.value
        base = balance_wire.parse_magic_balance_request(json.dumps(data))
        result = deepcopy(make_result(base))
        child = result.generation_result.evaluation_request.candidates[-1]
        object.__setattr__(child, 'scenario', opted(child.scenario))
        with patch.object(generation, '_count_vectors', side_effect=AssertionError('no enumeration')) as counts:
            with self.assertRaisesRegex(ValueError, 'repeated Leg Spasm.*explicit family'):
                balance_wire.encode_magic_balance_result(base, result)
            counts.assert_not_called()


if __name__ == '__main__':
    unittest.main()
