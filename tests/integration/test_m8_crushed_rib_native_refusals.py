"""Native ADR-0057 permission must never disappear through generation/wire."""
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
from tests.unit.test_m8_magic_json_v4 import document as version4
from tests.unit.test_m8_stationary_wound_generation import family, Unreadable
from towr.adapters import magic_balance_json as balance, magic_simulation_json as simulation
from towr.adapters._magic_scenario_json import scenario_document
from towr.adapters.magic_json_errors import MagicBalanceInputError, MagicSimulationInputError
from towr.application import magic_candidate_generation as generation
from towr.application.magic_candidate_generation_models import MagicCandidateGenerationResult
from towr.domain.npc_magic_scenario_models import NpcMagicCrushedRibPolicy as Policy


FIELD = 'crushed_rib_continuation'
POLICY = Policy.NEXT_TEST_WITH_JOURNAL_WITNESSES


def opted(scenario):
    return replace(scenario, crushed_rib_continuation=POLICY)


def documents(*, balance_family=False):
    return ((balance_v1(), balance_v2(opted=False), balance_v3(stationary=False, miscast=False),
             version4(balance=True, stationary=False, repeated=False)) if balance_family else
            (simulation_v1(), simulation_v2(opted=False), simulation_v3(stationary=False, miscast=False),
             version4(stationary=False, repeated=False)))


class CrushedRibGenerationFamilyTests(unittest.TestCase):
    def test_generation_requires_matching_family_before_collection_materialization_and_projects_opt_in(self):
        source = family(stationary=None)
        before, rng = pickle.dumps(source), getstate()
        selected = opted(source.template_scenario)
        with self.assertRaisesRegex(ValueError, 'Crushed Rib.*explicit family'):
            replace(source, template_scenario=opted(source.template_scenario),
                groups=Unreadable(source.groups), scene_frames=Unreadable(source.scene_frames),
                stages=Unreadable(source.stages))
        with self.assertRaisesRegex(ValueError, 'Crushed Rib.*explicit family'):
            replace(source, crushed_rib_continuation=POLICY,
                groups=Unreadable(source.groups), scene_frames=Unreadable(source.scene_frames),
                stages=Unreadable(source.stages))
        matching = replace(source, template_scenario=selected, crushed_rib_continuation=POLICY)
        generated = generation.generate_magic_candidates(matching)
        self.assertTrue(generated.evaluation_request.candidates)
        self.assertTrue(all(candidate.scenario.crushed_rib_continuation is POLICY
                            for candidate in generated.evaluation_request.candidates))
        self.assertEqual(pickle.dumps(source), before)
        self.assertEqual(getstate(), rng)

    def test_factory_and_result_refuse_transported_source_before_vectors_projection(self):
        source = family(stationary=None)
        generated = generation.generate_magic_candidates(source)
        wrong = deepcopy(source)
        object.__setattr__(wrong, 'template_scenario', opted(wrong.template_scenario))
        wrong = pickle.loads(pickle.dumps(wrong))
        before = pickle.dumps(wrong)
        with patch.object(generation, '_count_vectors', side_effect=AssertionError('no vectors')) as vectors, \
                patch.object(generation, '_project_candidate', side_effect=AssertionError('no projection')) as project:
            for operation in (lambda: generation.generate_magic_candidates(wrong),
                              lambda: MagicCandidateGenerationResult(wrong, generated.evaluation_request)):
                with self.assertRaisesRegex(ValueError, 'Crushed Rib.*explicit family'):
                    operation()
            vectors.assert_not_called()
            project.assert_not_called()
        self.assertEqual(pickle.dumps(wrong), before)

    def test_first_and_last_candidate_permissions_checked_before_projection(self):
        generated = generation.generate_magic_candidates(family(stationary=None))
        for index in (0, len(generated.evaluation_request.candidates) - 1):
            wrong = deepcopy(generated)
            candidate = wrong.evaluation_request.candidates[index]
            object.__setattr__(candidate, 'scenario', opted(candidate.scenario))
            with patch.object(generation, '_count_vectors', side_effect=AssertionError('no vectors')) as vectors, \
                    patch.object(generation, '_project_candidate', side_effect=AssertionError('no projection')) as project:
                with self.subTest(index=index), self.assertRaisesRegex(ValueError, 'Crushed Rib.*explicit family'):
                    replace(wrong)
                vectors.assert_not_called()
                project.assert_not_called()

    def test_raw_permission_aliases_are_type_errors_before_generation_or_mapping(self):
        source = family(stationary=None)
        selected = opted(source.template_scenario)
        for value in (POLICY.value, True, False, 0, 1, {}, []):
            scenario = deepcopy(selected)
            object.__setattr__(scenario, FIELD, value)
            wrong = deepcopy(source)
            object.__setattr__(wrong, 'template_scenario', scenario)
            with patch.object(generation, '_count_vectors', side_effect=AssertionError('no vectors')):
                with self.subTest(value=value), self.assertRaises(TypeError):
                    generation.generate_magic_candidates(wrong)
            for version in ('1', '2', '3', '4'):
                with self.subTest(value=value, version=version), self.assertRaises(TypeError):
                    scenario_document(scenario, ('missing:definition',), schema_version=version)

    def test_all_wire_versions_refuse_before_definition_projection(self):
        scenario = opted(family(stationary=None).template_scenario)
        before = pickle.dumps(scenario)
        for version in ('1', '2', '3', '4'):
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, 'Crushed Rib.*losslessly'):
                scenario_document(scenario, ('missing:definition',), schema_version=version)
        self.assertEqual(pickle.dumps(scenario), before)

    def test_matching_generation_family_still_refuses_lossy_balance_json_v1_to_v4(self):
        for data in documents(balance_family=True):
            base = balance.parse_magic_balance_request(json.dumps(data))
            source = base.generation_request
            matching = replace(source, template_scenario=opted(source.template_scenario),
                               crushed_rib_continuation=POLICY)
            command = replace(base, generation_request=matching)
            result = make_result(command)
            with self.subTest(version=base.schema_version), self.assertRaisesRegex(ValueError, 'Crushed Rib.*losslessly'):
                balance._request_document(command)
            with self.assertRaisesRegex(ValueError, 'Crushed Rib.*losslessly'):
                balance.encode_magic_balance_result(command, result)

    def test_simulation_request_result_and_same_value_raw_summary_cannot_drop_permission(self):
        for data in documents():
            base = simulation.parse_magic_simulation_request(json.dumps(data))
            command = replace(base, request=replace(base.request, scenario=opted(base.request.scenario)))
            result = summary(command)
            with patch.object(simulation, 'parse_magic_simulation_request', side_effect=AssertionError('no reconstruction')):
                for operation in (lambda: simulation._request_document(command),
                                  lambda: simulation.encode_magic_simulation_result(command, result)):
                    with self.subTest(version=base.schema_version), self.assertRaisesRegex(ValueError, 'Crushed Rib.*losslessly'):
                        operation()
            bad = deepcopy(result)
            object.__setattr__(bad.source_request.scenario, FIELD, POLICY.value)
            self.assertEqual(bad.source_request, command.request)
            with self.assertRaises(TypeError):
                simulation.encode_magic_simulation_result(command, bad)

    def test_transported_balance_command_and_result_refuse_before_enumeration_or_pool(self):
        for data in documents(balance_family=True):
            command = balance.parse_magic_balance_request(json.dumps(data))
            result = make_result(command)
            bad = deepcopy(command)
            object.__setattr__(bad.generation_request, 'template_scenario', opted(bad.generation_request.template_scenario))
            with patch.object(generation, '_count_vectors', side_effect=AssertionError('no vectors')) as vectors, \
                    patch.object(generation, '_project_candidate', side_effect=AssertionError('no projection')) as project, \
                    patch('towr.simulation.npc_magic_parallel.ProcessPoolExecutor', side_effect=AssertionError('no pool')) as pool:
                with self.subTest(version=command.schema_version), self.assertRaisesRegex(ValueError, 'Crushed Rib.*losslessly'):
                    balance._request_document(bad)
                with self.assertRaisesRegex(ValueError, 'Crushed Rib.*explicit family'):
                    balance.encode_magic_balance_result(bad, result)
                vectors.assert_not_called()
                project.assert_not_called()
                pool.assert_not_called()

    def test_closed_decoders_reject_new_field_even_null_and_none_wire_remains_identical(self):
        for balance_family in (False, True):
            wire = balance if balance_family else simulation
            parse = wire.parse_magic_balance_request if balance_family else wire.parse_magic_simulation_request
            encode = wire.encode_magic_balance_result if balance_family else wire.encode_magic_simulation_result
            error = MagicBalanceInputError if balance_family else MagicSimulationInputError
            for data in documents(balance_family=balance_family):
                command = parse(json.dumps(data))
                result = make_result(command) if balance_family else summary(command)
                before = encode(command, result)
                self.assertNotIn('"' + FIELD + '"', before)
                self.assertEqual(json.loads(before)['request'], data)
                self.assertEqual(encode(pickle.loads(pickle.dumps(command)), result), before)
                for value in (None, POLICY.value):
                    wrong = deepcopy(data)
                    location = wrong['reserve']['scenario'] if balance_family else wrong['scenario']
                    location[FIELD] = value
                    with self.subTest(balance=balance_family, version=command.schema_version, value=value), self.assertRaises(error):
                        parse(json.dumps(wrong))


if __name__ == '__main__':
    unittest.main()
