"""Balance3 permissions, exact family provenance and trusted phase failures."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import json
import random
import unittest
from unittest.mock import patch

from jsonschema import ValidationError

from tests.unit.test_m4_ranged_json import at
from tests.unit.test_m8_magic_balance_json import document as legacy_document, make_result
from tests.unit.test_m8_magic_balance_json_v2 import document as v2_document
from tests.unit.test_m8_magic_json_v2 import policy_document
from tests.unit.test_m8_miscast_continuation_policy import continuation_policy
from towr.adapters.magic_balance_json import (
    parse_magic_balance_request as parse, encode_magic_balance_result as encode,
    encode_magic_balance_error as encode_error,
)
from towr.adapters.magic_json_errors import MagicBalanceInputError
from towr.adapters.magic_json_schema import validate_magic_balance_document as validate
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.application import magic_balance_service as service
from towr.application.magic_balance_errors import MagicBalanceGenerationError, MagicBalanceExecutionError
from towr.application.magic_candidate_generation_errors import MagicCandidateGenerationError
from towr.application.magic_staged_evaluation_errors import MagicStagedEvaluationError
from towr.domain.npc_magic_scenario_models import NpcMagicStationaryWoundPolicy as Policy


FIELD = 'stationary_wound_continuation'
POLICY = Policy.LEG_SPASM_STAND_AND_CONTINUE


def document(*, stationary=True, miscast=False, source=None):
    data = v2_document(opted=miscast, source=source)
    data['schema_version'] = '3'
    data['reserve']['scenario'][FIELD] = POLICY.value if stationary else None
    data['generation'][FIELD] = POLICY.value if stationary else None
    return data


class M8MagicBalanceJsonV3Tests(unittest.TestCase):
    def invalid(self, data, *, version='3', path=None, code=Code.INVALID_INPUT):
        with self.assertRaises(MagicBalanceInputError) as caught:
            parse(json.dumps(data))
        error = caught.exception
        self.assertEqual((error.schema_version, error.code), (version, code))
        if path is not None:
            self.assertEqual(error.path, path)
        output = json.loads(encode_error(error))
        validate(output, 'error', schema_version=version)
        self.assertEqual(output['schema_version'], version)
        return error

    def test_four_combinations_roundtrip_full_ordered_catalog_stages_seeds_and_family_sources(self):
        baseline = parse(json.dumps(legacy_document()))
        old = make_result(baseline)
        for stationary in (False, True):
            for miscast in (False, True):
                data = document(stationary=stationary, miscast=miscast)
                with patch('towr.application.magic_candidate_generation._count_vectors',
                           side_effect=AssertionError('parse must not enumerate')):
                    command = parse(json.dumps(data).encode('utf-8'))
                before = deepcopy(command)
                request = command.generation_request
                self.assertIs(request.stationary_wound_continuation, POLICY if stationary else None)
                self.assertIs(request.template_scenario.stationary_wound_continuation, request.stationary_wound_continuation)
                self.assertEqual(request.miscast_continuation, continuation_policy() if miscast else None)
                self.assertEqual(request.miscast_continuation, request.template_scenario.miscast_continuation)
                result = make_result(command)
                for candidate, old_candidate in zip(result.generation_result.evaluation_request.candidates,
                        old.generation_result.evaluation_request.candidates, strict=True):
                    self.assertEqual(candidate.candidate_id, old_candidate.candidate_id)
                    self.assertEqual(candidate.scenario, replace(old_candidate.scenario,
                        stationary_wound_continuation=request.stationary_wound_continuation,
                        miscast_continuation=request.miscast_continuation))
                for report in result.evaluation_result.stage_reports:
                    for row, simulation in zip(report.candidates, report.source_request.simulation_requests, strict=True):
                        self.assertEqual(row.assessment.source_request, simulation)
                        self.assertEqual(row.assessment.summary.source_request, simulation)
                        self.assertIs(simulation.scenario.stationary_wound_continuation, request.stationary_wound_continuation)
                        self.assertEqual(simulation.scenario.miscast_continuation, request.miscast_continuation)
                output = json.loads(encode(command, result))
                validate(output, 'result', schema_version='3')
                self.assertEqual(output['request'], data)
                self.assertEqual(parse(json.dumps(output['request'])), command)
                self.assertEqual([c['counts'] for c in output['candidates']], [[1, 0], [1, 1], [2, 0], [2, 1]])
                self.assertEqual((output['candidate_count'], output['planned_trials'], output['total_trials']), (4, 16, 16))
                self.assertEqual(command, before)

    def test_both_locations_require_both_nullable_fields_and_stationary_values_are_strict(self):
        for parent in (('reserve', 'scenario'), ('generation',)):
            for field in (FIELD, 'miscast_continuation'):
                data = document()
                del at(data, parent)[field]
                self.invalid(data, path='/' + '/'.join(parent))
            for value in (False, True, 0, 1, {}, [], '', 'stand', 'LEG_SPASM_STAND_AND_CONTINUE'):
                data = document()
                at(data, parent)[FIELD] = value
                self.invalid(data, path='/' + '/'.join((*parent, FIELD)))
            data = document(miscast=True)
            at(data, parent)['miscast_continuation']['facts']['no_external_short_range_creatures'] = 1
            self.invalid(data, path='/' + '/'.join((*parent, 'miscast_continuation', 'facts', 'no_external_short_range_creatures')))
            data = document()
            at(data, parent)['additional_stationary_facts'] = {}
            self.invalid(data, path='/' + '/'.join(parent))

    def test_independent_mismatch_both_directions_stops_before_family_preflight_or_materialization(self):
        for stationary in (False, True):
            for miscast in (False, True):
                for field in (FIELD, 'miscast_continuation'):
                    data = document(stationary=stationary, miscast=miscast)
                    data['generation'][field] = ((None if stationary else POLICY.value) if field == FIELD
                        else (None if miscast else policy_document()))
                    with patch('towr.adapters.magic_balance_json.MagicCandidateGenerationRequest',
                               side_effect=AssertionError('family preflight ran before mismatch')), \
                            patch('towr.application.magic_candidate_generation._count_vectors',
                                  side_effect=AssertionError('enumerated')):
                        error = self.invalid(data, path='/generation/' + field)
                    self.assertEqual(error.request_id, data['request_id'])

    def test_v1_v2_reject_each_stationary_field_even_null_and_never_encode_opted_family(self):
        for version, base in (('1', legacy_document()), ('2', v2_document(opted=False))):
            for parent in (('reserve', 'scenario'), ('generation',)):
                for value in (None, POLICY.value):
                    data = deepcopy(base)
                    at(data, parent)[FIELD] = value
                    self.invalid(data, version=version, path='/' + '/'.join(parent))
            command = replace(parse(json.dumps(document())), schema_version=version)
            with self.assertRaises(ValueError):
                encode(command, make_result(command))

    def test_lexical_decode_failure_never_trusts_v3_metadata(self):
        prefix = '{"schema_version":"3","request_id":"seen",'
        cases = ((b'\xff' + prefix.encode(), Code.INVALID_JSON), (prefix, Code.INVALID_JSON),
            (prefix + '"schema_version":"3"}', Code.INVALID_JSON),
            (prefix + '"nested":{"a":1,"a":2}}', Code.INVALID_JSON),
            (prefix + '"x":"\\ud800"}', Code.INVALID_JSON),
            (prefix + '"x":NaN}', Code.INVALID_JSON),
            (prefix + '"x":Infinity}', Code.INVALID_JSON),
            (prefix + '"x":1.0}', Code.INVALID_INPUT),
            (prefix + '"x":1e999}', Code.INVALID_INPUT))
        for raw, code in cases:
            with self.subTest(raw=raw), self.assertRaises(MagicBalanceInputError) as caught:
                parse(raw)
            self.assertEqual((caught.exception.schema_version, caught.exception.request_id, caught.exception.code),
                             ('1', None, code))
            validate(json.loads(encode_error(caught.exception)), 'error', schema_version='1')

    def test_decoded_v3_semantics_and_unknown_version_keep_exact_metadata(self):
        for path, mutate in (
            ('/evaluation/master_seed', lambda d: d['evaluation'].update(master_seed=str(2**64))),
            ('/reserve/scenario/actors/0/definition_id', lambda d: d['reserve']['scenario']['actors'][0].update(definition_id='missing')),
            ('/generation/' + FIELD, lambda d: d['generation'].update({FIELD: None}))):
            data = document()
            mutate(data)
            self.assertEqual(self.invalid(data, path=path).request_id, data['request_id'])
        missing = document()
        del missing['schema_version']
        self.assertEqual(self.invalid(missing, version='1').request_id, missing['request_id'])
        self.invalid(dict(document(), schema_version='6'), version='1', path='/schema_version', code=Code.UNSUPPORTED_VERSION)
        self.assertIsNone(self.invalid(dict(document(), request_id=' '), path='/request_id').request_id)

    def test_encode_rejects_same_id_policy_substitution_at_generation_and_report_boundaries(self):
        on, off = (parse(json.dumps(document(stationary=value, miscast=True))) for value in (True, False))
        for command, foreign in ((on, off), (off, on)):
            result, wrong = make_result(command), make_result(foreign)
            self.assertEqual(command.generation_request.template_scenario.id, foreign.generation_request.template_scenario.id)
            with self.assertRaises(ValueError):
                encode(command, wrong)
            with self.assertRaises(ValueError):
                replace(result, evaluation_result=wrong.evaluation_result)
            with patch.object(service, 'generate_magic_candidates', return_value=wrong.generation_result), \
                    patch.object(service, 'evaluate_magic_candidates_staged') as evaluate:
                with self.assertRaises(MagicBalanceGenerationError) as caught:
                    service.execute_magic_balance(command)
                self.assertEqual(caught.exception.schema_version, '3')
                evaluate.assert_not_called()
            with patch.object(service, 'generate_magic_candidates', return_value=result.generation_result), \
                    patch.object(service, 'evaluate_magic_candidates_staged', return_value=wrong.evaluation_result):
                with self.assertRaises(MagicBalanceExecutionError) as caught:
                    service.execute_magic_balance(command)
                self.assertEqual(caught.exception.schema_version, '3')

    def test_encoder_rejects_equal_integer_facts_and_string_enum_in_transported_chain(self):
        command = parse(json.dumps(document(miscast=True)))
        original = make_result(command)
        before = deepcopy((command, original))
        for kind in ('generation-facts', 'summary-facts', 'candidate-policy'):
            wrong = deepcopy(original)
            if kind == 'generation-facts':
                object.__setattr__(wrong.generation_result.source_request.facts, 'no_external_condition_sources', 1)
            elif kind == 'summary-facts':
                assessment = wrong.evaluation_result.stage_reports[0].candidates[0].assessment
                detached = deepcopy(assessment.summary)
                object.__setattr__(detached.source_request.scenario.facts, 'no_external_condition_sources', 1)
                object.__setattr__(assessment, 'summary', detached)
                self.assertIs(wrong.generation_result.source_request.facts.no_external_condition_sources, True)
                self.assertIs(assessment.source_request.scenario.facts.no_external_condition_sources, True)
            else:
                object.__setattr__(wrong.generation_result.evaluation_request.candidates[0].scenario, FIELD, POLICY.value)
            self.assertEqual(wrong, original)  # Equality alone would launder corruption.
            with self.subTest(kind=kind), self.assertRaises(TypeError):
                encode(command, wrong)
        self.assertEqual((command, original), before)
        self.assertIs(command.generation_request.facts.no_external_condition_sources, True)

    def test_service_revalidates_equal_corrupted_source_at_each_phase_before_equality(self):
        command = parse(json.dumps(document()))
        original = make_result(command)
        bad_command = deepcopy(command)
        object.__setattr__(bad_command.generation_request.facts, 'no_external_condition_sources', 1)
        bad_result = deepcopy(original)
        object.__setattr__(bad_result.generation_result.source_request.facts, 'no_external_condition_sources', 1)
        for phase in ('command', 'generation', 'evaluation'):
            if phase == 'evaluation':
                bad_evaluation = deepcopy(original.evaluation_result)
                assessment = bad_evaluation.stage_reports[0].candidates[0].assessment
                detached = deepcopy(assessment.summary)
                object.__setattr__(detached.source_request.scenario.facts, 'no_external_condition_sources', 1)
                object.__setattr__(assessment, 'summary', detached)
                self.assertIs(assessment.source_request.scenario.facts.no_external_condition_sources, True)
            else:
                bad_evaluation = original.evaluation_result
            with patch('random.Random', side_effect=AssertionError('preflight must not draw RNG')), \
                    patch.object(service, 'generate_magic_candidates', return_value=
                        bad_result.generation_result if phase == 'generation' else original.generation_result) as generate, \
                    patch.object(service, 'evaluate_magic_candidates_staged', return_value=bad_evaluation) as evaluate:
                expected = MagicBalanceExecutionError if phase == 'evaluation' else MagicBalanceGenerationError
                with self.assertRaises(expected) as caught:
                    service.execute_magic_balance(bad_command if phase == 'command' else command)
                self.assertEqual((caught.exception.schema_version, caught.exception.request_id), ('3', command.request_id))
                self.assertIsInstance(caught.exception.__cause__, TypeError)
                if phase == 'command':
                    generate.assert_not_called()
                if phase != 'evaluation':
                    evaluate.assert_not_called()
        self.assertIs(command.generation_request.facts.no_external_condition_sources, True)

    def test_transported_simulation_request_cache_cannot_be_normalized_during_publication(self):
        command = parse(json.dumps(document(miscast=True)))
        original = make_result(command)
        wrong = deepcopy(original)
        report = wrong.evaluation_result.stage_reports[0]
        cached = report.source_request.simulation_requests
        foreign = replace(cached[0], scenario=replace(cached[0].scenario, stationary_wound_continuation=None))
        corrupted = (foreign, *cached[1:])
        object.__setattr__(report.source_request, 'simulation_requests', corrupted)
        self.assertEqual(wrong, original)  # The derived cache is compare=False.
        self.assertIs(report.source_request.candidates[0].scenario.stationary_wound_continuation, POLICY)
        self.assertIs(report.candidates[0].assessment.summary.source_request.scenario.stationary_wound_continuation, POLICY)
        before = deepcopy((command, original, wrong))
        with patch('random.Random', side_effect=AssertionError('validation cannot sample')):
            with self.assertRaises(ValueError):
                encode(command, wrong)
            with patch.object(service, 'generate_magic_candidates', return_value=original.generation_result), \
                    patch.object(service, 'evaluate_magic_candidates_staged', return_value=wrong.evaluation_result):
                with self.assertRaises(MagicBalanceExecutionError) as caught:
                    service.execute_magic_balance(command)
            self.assertEqual((caught.exception.schema_version, caught.exception.request_id), ('3', command.request_id))
            self.assertIsInstance(caught.exception.__cause__, ValueError)
        self.assertEqual((command, original, wrong), before)
        self.assertIs(report.source_request.simulation_requests, corrupted)
        self.assertIsNone(report.source_request.simulation_requests[0].scenario.stationary_wound_continuation)
        self.assertIs(original.evaluation_result.stage_reports[0].source_request.simulation_requests[0].scenario.stationary_wound_continuation, POLICY)

    def test_phase_errors_use_command_v3_and_retain_known_counts_stage_without_private_cause(self):
        command = parse(json.dumps(document()))
        result = make_result(command)
        cases = ((MagicCandidateGenerationError('candidate', (1, 0)), 'generation'),
            (MagicStagedEvaluationError(1, 'candidate'), 'evaluation'),
            (MagicBalanceExecutionError('private-foreign', schema_version='2'), 'generation'),
            (MagicBalanceGenerationError('private-foreign', schema_version='1'), 'evaluation'))
        for cause, phase in cases:
            cause.add_note('private-note')
            with patch.object(service, 'generate_magic_candidates', return_value=result.generation_result,
                    side_effect=cause if phase == 'generation' else None), \
                    patch.object(service, 'evaluate_magic_candidates_staged', side_effect=cause):
                expected = MagicBalanceGenerationError if phase == 'generation' else MagicBalanceExecutionError
                with self.assertRaises(expected) as caught:
                    service.execute_magic_balance(command)
            error = caught.exception
            self.assertIs(error.__cause__, cause)
            self.assertEqual((error.schema_version, error.request_id), ('3', command.request_id))
            output = json.loads(encode_error(error))
            validate(output, 'error', schema_version='3')
            known = isinstance(cause, (MagicCandidateGenerationError, MagicStagedEvaluationError))
            self.assertEqual(output['error']['candidate_id'], 'candidate' if known else None)
            self.assertEqual(output['error']['counts'], [1, 0] if isinstance(cause, MagicCandidateGenerationError) else None)
            self.assertEqual(output['error']['stage_index'], 1 if isinstance(cause, MagicStagedEvaluationError) else None)
            self.assertNotIn('private', json.dumps(output))

    def test_wire_boundaries_are_pure_and_reconstruction_keeps_version_definition_order(self):
        commands = [parse(json.dumps(document(stationary=s, miscast=m))) for s in (False, True) for m in (False, True)]
        pairs = [(c, make_result(c)) for c in commands]
        rng_before = random.getstate()
        with ExitStack() as stack:
            for target in ('random.Random', 'concurrent.futures.ProcessPoolExecutor',
                'towr.application.magic_candidate_generation.generate_magic_candidates',
                'towr.application.magic_staged_evaluation_service.evaluate_magic_candidates_staged',
                'towr.application.magic_evaluation_service.run_npc_magic_simulation',
                'towr.adapters.magic_simulation_json.parse_magic_simulation_request'):
                stack.enter_context(patch(target, side_effect=AssertionError(target)))
            for command, result in pairs:
                output = json.loads(encode(command, result))
                self.assertEqual(parse(json.dumps(output['request'])), command)
        self.assertEqual(random.getstate(), rng_before)
        command, result = pairs[0]
        for foreign in (replace(command, schema_version='2'),
                        replace(command, definition_order=tuple(reversed(command.definition_order)))):
            with patch('towr.adapters.magic_balance_json.parse_magic_balance_request', return_value=foreign), \
                    self.assertRaises(ValueError):
                encode(command, result)

    def test_null_result_remains_v3_and_result_error_shapes_are_version_bound(self):
        command = parse(json.dumps(document(stationary=False, miscast=False)))
        output = json.loads(encode(command, make_result(command)))
        self.assertEqual(output['schema_version'], '3')
        self.assertIsNone(output['request']['generation'][FIELD])
        for changed in (dict(output, schema_version='2'), dict(output, request=v2_document(opted=False)),
                        dict(output, extra=True)):
            with self.assertRaises(ValidationError):
                validate(changed, 'result', schema_version='3')
        for error in (MagicBalanceInputError(Code.INVALID_INPUT, 'bad', schema_version='3'),
                      MagicBalanceGenerationError('request', schema_version='3'),
                      MagicBalanceExecutionError('request', schema_version='3')):
            error_doc = json.loads(encode_error(error))
            validate(error_doc, 'error', schema_version='3')
            with self.assertRaises(ValidationError):
                validate(dict(error_doc, schema_version='2'), 'error', schema_version='3')


if __name__ == '__main__':
    unittest.main()
