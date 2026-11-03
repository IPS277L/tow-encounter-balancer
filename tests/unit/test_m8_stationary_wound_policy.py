"""ADR-0050 native policy is independent, typed and rejected by older transports."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import json
import pickle
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_magic_candidate_generation_models import request as generation_request
from tests.unit.test_m8_magic_json import document as v1_document, summary
from tests.unit.test_m8_magic_json_v2 import document as v2_document
from tests.unit.test_m8_miscast_continuation_policy import continuation_policy
from tests.unit.test_m8_npc_magic_scenario import scenario
from towr.adapters._magic_scenario_json import scenario_document
from towr.adapters.magic_json_errors import MagicSimulationInputError
from towr.adapters.magic_simulation_json import (
    _request_document, encode_magic_simulation_result, parse_magic_simulation_request,
)
from towr.application import magic_candidate_generation as generation
from towr.domain.npc_magic_scenario_models import NpcMagicScenario, NpcMagicStationaryWoundPolicy as Policy
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest, NpcMagicTrialRecord
from towr.simulation.npc_magic_parallel import _normalize_batch


POLICY = Policy.LEG_SPASM_STAND_AND_CONTINUE


class StationaryWoundPolicyTests(unittest.TestCase):
    def test_enum_and_all_four_policy_combinations_are_independent(self):
        self.assertEqual(tuple(Policy), (POLICY,))
        self.assertEqual(POLICY.value, 'leg_spasm_stand_and_continue')
        source = scenario()
        original, rng = deepcopy(source), getstate()
        with (patch.object(NpcMagicScenario, 'initial_runtime_state',
                           new=property(lambda _: self.fail('no bootstrap'))),
              patch('random.Random', side_effect=AssertionError('no RNG'))):
            for miscast in (None, continuation_policy()):
                for stationary in (None, POLICY):
                    with self.subTest(miscast=miscast is not None, stationary=stationary):
                        value = replace(source, miscast_continuation=miscast,
                                        stationary_wound_continuation=stationary)
                        self.assertIs(value.stationary_wound_continuation, stationary)
                        self.assertEqual(value.miscast_continuation, miscast)
                        self.assertEqual(replace(value, miscast_continuation=None,
                            stationary_wound_continuation=None), source)
        self.assertEqual(source, original)
        self.assertEqual(getstate(), rng)

    def test_required_enum_rejects_bool_string_dict_and_other_policy(self):
        source = scenario()
        for bad in (True, False, 0, 1, POLICY.value, {}, continuation_policy(),
                    continuation_policy().prone_policy):
            with self.subTest(bad=bad), self.assertRaises(TypeError):
                replace(source, stationary_wound_continuation=bad)

    def test_append_last_preserves_both_previous_positional_forms_and_explicit_none(self):
        source = scenario()
        names = tuple(f.name for f in fields(source))
        self.assertEqual(names[-5:], ('miscast_continuation', 'stationary_wound_continuation',
                                      'repeated_leg_spasm_continuation', 'crushed_rib_continuation',
                                      'battered_leg_continuation'))
        self.assertIsNone(fields(source)[-1].default)
        original_arguments = tuple(getattr(source, name) for name in names[:-5])
        self.assertEqual(NpcMagicScenario(*original_arguments), source)
        self.assertEqual(NpcMagicScenario(*original_arguments, None), source)
        self.assertEqual(NpcMagicScenario(*original_arguments, None, None), source)
        miscast = continuation_policy()
        self.assertEqual(NpcMagicScenario(*original_arguments, miscast),
                         replace(source, miscast_continuation=miscast))

    def test_full_source_frozen_slotted_deepcopy_and_pickle_preserve_enum(self):
        source = replace(scenario(), stationary_wound_continuation=POLICY)
        self.assertFalse(hasattr(source, '__dict__'))
        for value in (deepcopy(source), pickle.loads(pickle.dumps(source)), replace(source)):
            self.assertEqual(value, source)
            self.assertIs(value.stationary_wound_continuation, POLICY)
        with self.assertRaises(FrozenInstanceError):
            source.stationary_wound_continuation = None
        self.assertNotEqual(source, replace(source, stationary_wound_continuation=None))

    def test_generation_requires_separate_family_before_collection_reads_projection_or_rng(self):
        source = generation_request()

        class Unreadable(list):
            def __iter__(self):
                raise AssertionError('unsupported policy must be checked before collection materialization')

        with ExitStack() as stack:
            spies = [stack.enter_context(patch.object(generation, name,
                     side_effect=AssertionError('no projection'))) for name in
                     ('_count_vectors', '_project_candidate', '_project_frames')]
            stack.enter_context(patch('random.Random', side_effect=AssertionError('no RNG')))
            for miscast in (None, continuation_policy()):
                template = replace(source.template_scenario, miscast_continuation=miscast,
                                   stationary_wound_continuation=POLICY)
                with self.subTest(miscast=miscast is not None), self.assertRaisesRegex(ValueError, 'stationary Wound'):
                    replace(source, template_scenario=template, miscast_continuation=miscast,
                            groups=Unreadable(source.groups), scene_frames=Unreadable(source.scene_frames),
                            stages=Unreadable(source.stages))
            for spy in spies:
                spy.assert_not_called()

    def test_generation_none_projects_only_none_without_silent_policy_loss(self):
        source = generation_request()
        result = generation.generate_magic_candidates(source)
        self.assertTrue(result.evaluation_request.candidates)
        self.assertTrue(all(candidate.scenario.stationary_wound_continuation is None
                            for candidate in result.evaluation_request.candidates))

    def test_direct_scenario_mapper_rejects_both_versions_before_definition_mapping(self):
        for miscast in (None, continuation_policy()):
            source = replace(scenario(), miscast_continuation=miscast,
                             stationary_wound_continuation=POLICY)
            before = deepcopy(source)
            for version in ('1', '2'):
                with self.subTest(version=version, miscast=miscast is not None), self.assertRaisesRegex(
                        ValueError, 'stationary Wound.*losslessly'):
                    # Invalid definition order would fail if projection were attempted.
                    scenario_document(source, ('missing',), schema_version=version)
            self.assertEqual(source, before)

    def test_request_and_result_encoder_reject_native_policy_without_downgrade(self):
        for document in (v1_document(), v2_document(opted=False), v2_document(opted=True)):
            command = parse_magic_simulation_request(json.dumps(document))
            source = replace(command.request.scenario, stationary_wound_continuation=POLICY)
            command = replace(command, request=replace(command.request, scenario=source))
            before = deepcopy(command)
            with self.subTest(version=command.schema_version, miscast=source.miscast_continuation is not None):
                with self.assertRaisesRegex(ValueError, 'stationary Wound.*losslessly'):
                    _request_document(command)
                with self.assertRaisesRegex(ValueError, 'stationary Wound.*losslessly'):
                    encode_magic_simulation_result(command, summary(command))
            self.assertEqual(command, before)

    def test_existing_wire_versions_reject_new_key_even_when_null(self):
        for document in (v1_document(), v2_document(opted=False)):
            for value in (None, POLICY.value):
                data = deepcopy(document)
                data['scenario']['stationary_wound_continuation'] = value
                with self.subTest(version=data['schema_version'], value=value), self.assertRaises(MagicSimulationInputError):
                    parse_magic_simulation_request(json.dumps(data))

    def test_native_worker_rejects_same_id_source_policy_substitution(self):
        source = replace(scenario(), stationary_wound_continuation=POLICY)
        request = NpcMagicSimulationRequest(source, 42, 1)
        record = NpcMagicTrialRecord(source, 0, request.seed_for(0),
            NpcMagicScenarioOutcome.UNSUPPORTED_PATH, 0, 1, 0)
        canonical = _normalize_batch(request, range(1), (pickle.loads(pickle.dumps(record)),))
        self.assertIs(canonical[0].source_scenario, source)
        foreign = replace(record, source_scenario=replace(source, stationary_wound_continuation=None))
        with self.assertRaisesRegex(ValueError, 'different full scenario'):
            _normalize_batch(request, range(1), (foreign,))

    def test_native_worker_rejects_same_value_string_policy_before_source_normalization(self):
        source = replace(scenario(), stationary_wound_continuation=POLICY)
        request = NpcMagicSimulationRequest(source, 42, 1)
        record = NpcMagicTrialRecord(source, 0, request.seed_for(0),
            NpcMagicScenarioOutcome.UNSUPPORTED_PATH, 0, 1, 0)
        worker = deepcopy(record)
        # Unpickling does not run Scenario.__post_init__. A corrupt payload can
        # therefore contain a raw str which compares equal to the str Enum.
        object.__setattr__(worker.source_scenario, 'stationary_wound_continuation', POLICY.value)
        self.assertEqual(worker.source_scenario, source)
        self.assertIs(type(worker.source_scenario.stationary_wound_continuation), str)
        with self.assertRaises(TypeError):
            _normalize_batch(request, range(1), (worker,))
        self.assertIs(source.stationary_wound_continuation, POLICY)

    def test_generation_factory_rejects_tampered_policy_before_count_vector_materialization(self):
        original = generation_request()
        tampered = deepcopy(original)
        object.__setattr__(tampered, 'template_scenario', replace(
            tampered.template_scenario, stationary_wound_continuation=POLICY))
        with (patch.object(generation, '_count_vectors', side_effect=AssertionError('no count vectors')) as counts,
              patch.object(generation, '_project_candidate', side_effect=AssertionError('no candidate')) as project):
            with self.assertRaisesRegex(ValueError, 'stationary Wound'):
                generation.generate_magic_candidates(tampered)
            counts.assert_not_called()
            project.assert_not_called()
        self.assertIsNone(original.template_scenario.stationary_wound_continuation)


if __name__ == '__main__':
    unittest.main()
