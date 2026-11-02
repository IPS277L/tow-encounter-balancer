"""ADR-0047 balance v2: explicit family policy and lossless phase boundaries."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from importlib.resources import files
import json
import pickle
import random
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator, ValidationError

from tests.unit.test_m4_ranged_json import at, object_paths
from tests.unit.test_m8_magic_balance_json import (
    document as legacy_document, generation_failure_document, make_result,
)
from tests.unit.test_m8_magic_json_v2 import policy_document
from tests.unit.test_m8_miscast_continuation_policy import continuation_policy
from towr.adapters.magic_balance_json import (
    encode_magic_balance_error as encode_error,
    encode_magic_balance_result as encode,
    parse_magic_balance_request as parse,
)
from towr.adapters.magic_json_errors import MagicBalanceInputError
from towr.adapters.magic_json_schema import validate_magic_balance_document as validate
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.application import magic_balance_service as service
from towr.application.magic_balance_errors import MagicBalanceExecutionError, MagicBalanceGenerationError
from towr.application.magic_balance_models import MagicBalanceCommand
from towr.application.magic_candidate_generation_errors import MagicCandidateGenerationError
from towr.application.magic_staged_evaluation_errors import MagicStagedEvaluationError
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options


def document(*, opted=True, source=None):
    data = deepcopy(legacy_document() if source is None else source)
    data['schema_version'] = '2'
    data['reserve']['scenario']['miscast_continuation'] = policy_document() if opted else None
    data['generation']['miscast_continuation'] = policy_document() if opted else None
    return data


class M8MagicBalanceJsonV2Tests(unittest.TestCase):
    def invalid(self, data, *, version='2', path=None, code=Code.INVALID_INPUT):
        with self.assertRaises(MagicBalanceInputError) as caught:
            parse(json.dumps(data))
        error = caught.exception
        self.assertEqual(error.code, code)
        self.assertEqual(error.schema_version, version)
        if path is not None:
            self.assertEqual(error.path, path)
        output = json.loads(encode_error(error))
        validate(output, 'error', schema_version=version)
        self.assertEqual(output['schema_version'], version)
        return error

    def test_both_policies_roundtrip_separate_assertions_and_complete_sources(self):
        for opted in (False, True):
            with self.subTest(opted=opted):
                data = document(opted=opted)
                command = parse(json.dumps(data).encode())
                before = deepcopy(command)
                source = command.generation_request
                policy = continuation_policy() if opted else None
                self.assertEqual(source.miscast_continuation, policy)
                self.assertEqual(source.template_scenario.miscast_continuation, policy)
                if opted:
                    self.assertIsNot(source.miscast_continuation, source.template_scenario.miscast_continuation)
                result = make_result(command)
                for candidate in result.generation_result.evaluation_request.candidates:
                    self.assertEqual(candidate.scenario.miscast_continuation, policy)
                for report in result.evaluation_result.stage_reports:
                    for row in report.candidates:
                        self.assertEqual(row.assessment.summary.source_request.scenario.miscast_continuation, policy)
                output = json.loads(encode(command, result))
                validate(output, 'result', schema_version='2')
                self.assertEqual(output['schema_version'], '2')
                self.assertEqual(output['request'], data)
                self.assertEqual(parse(json.dumps(output['request'])), command)
                self.assertEqual([c['counts'] for c in output['candidates']], [[1, 0], [1, 1], [2, 0], [2, 1]])
                self.assertEqual((output['candidate_count'], output['planned_trials'], output['total_trials']), (4, 16, 16))
                self.assertEqual(command, before)

    def test_null_v2_has_exact_legacy_native_result_and_seed_but_distinct_wire(self):
        old = parse(json.dumps(legacy_document()))
        new = parse(json.dumps(document(opted=False)))
        self.assertEqual(old, replace(new, schema_version='1'))
        old_result, new_result = make_result(old), make_result(new)
        self.assertEqual(old_result, new_result)
        old_wire, new_wire = json.loads(encode(old, old_result)), json.loads(encode(new, new_result))
        for field in old_wire.keys() - {'schema_version', 'request'}:
            self.assertEqual(old_wire[field], new_wire[field])
        self.assertNotIn('miscast_continuation', old_wire['request']['generation'])
        self.assertIsNone(new_wire['request']['generation']['miscast_continuation'])

    def test_v1_rejects_both_new_fields_even_null_and_cannot_drop_native_policy(self):
        for path in (('generation',), ('reserve', 'scenario')):
            for value in (None, policy_document()):
                data = legacy_document()
                at(data, path)['miscast_continuation'] = value
                self.invalid(data, version='1', path='/' + '/'.join(path))
        opted = replace(parse(json.dumps(document())), schema_version='1')
        with self.assertRaisesRegex(ValueError, 'losslessly'):
            encode(opted, make_result(opted))

    def test_all_request_objects_close_and_all_fields_remain_required(self):
        original = document()
        for path in object_paths(original):
            for key in (None, *at(original, path)):
                data = deepcopy(original)
                if key is None:
                    at(data, path)['unexpected'] = True
                else:
                    del at(data, path)[key]
                with self.subTest(path=path, key=key):
                    self.invalid(data, version='1' if not path and key == 'schema_version' else '2')

    def test_both_policy_objects_enforce_five_strict_facts_types_enums_and_paths(self):
        for parent in (('reserve', 'scenario'), ('generation',)):
            base = (*parent, 'miscast_continuation')
            cases = [(base, (False, 0, 1, '', [])),
                     ((*base, 'choice'), (None, True, 'cast', 'decline')),
                     ((*base, 'prone_policy'), (None, False, 'stand', '')),
                     ((*base, 'facts'), (None, True, [], 'facts'))]
            cases.extend(((*base, 'facts', key), (False, 0, 1, 'true', None, [], {}))
                         for key in policy_document()['facts'])
            for path, values in cases:
                for value in values:
                    data = document()
                    at(data, path[:-1])[path[-1]] = value
                    with self.subTest(path=path, value=value):
                        self.invalid(data, path='/' + '/'.join(path))

    def test_separate_family_assertion_must_match_before_projection(self):
        with patch('towr.application.magic_candidate_generation._project_candidate', side_effect=AssertionError('projected')):
            for opted in (False, True):
                data = document(opted=opted)
                data['generation']['miscast_continuation'] = None if opted else policy_document()
                error = self.invalid(data, path='/generation/miscast_continuation')
                self.assertEqual(error.request_id, data['request_id'])

    def test_semantic_errors_keep_trusted_version_and_balance_paths(self):
        cases = [('/evaluation/master_seed', lambda d: d['evaluation'].update(master_seed=str(2**64))),
                 ('/reserve/scenario/actors/0/definition_id', lambda d: d['reserve']['scenario']['actors'][0].update(definition_id='missing'))]
        for path, change in cases:
            data = document()
            change(data)
            self.assertEqual(self.invalid(data, path=path).request_id, data['request_id'])
        data = document()
        frame = deepcopy(data['reserve']['scenario']['scene_frames'][0])
        frame['key']['placements'][0]['zone_id'] = 'boundary'
        frame['pair_ranges'][0]['target_range'] = 'close'
        data['reserve']['scenario']['scene_frames'].append(frame)
        data['generation']['scene_frames'] = deepcopy(data['reserve']['scenario']['scene_frames'])
        error = self.invalid(data)
        self.assertTrue(error.path.startswith('/reserve/scenario'))
        self.assertIn('Zone geometry', str(error.__cause__))

    def test_lexical_failures_use_v1_without_partial_version_or_request_id(self):
        prefix = '{"schema_version":"2","request_id":"seen",'
        cases = [(b'\xff' + prefix.encode(), Code.INVALID_JSON), (prefix, Code.INVALID_JSON),
                 (prefix + '"schema_version":"2"}', Code.INVALID_JSON),
                 (prefix + '"nested":{"a":1,"a":2}}', Code.INVALID_JSON),
                 (prefix + '"x":NaN}', Code.INVALID_JSON), (prefix + '"x":Infinity}', Code.INVALID_JSON),
                 (prefix + '"x":-Infinity}', Code.INVALID_JSON),
                 (prefix + '"x":1.0}', Code.INVALID_INPUT), (prefix + '"x":1e0}', Code.INVALID_INPUT),
                 (prefix + '"x":1e999}', Code.INVALID_INPUT),
                 (prefix + '"x":"\\ud800"}', Code.INVALID_JSON),
                 (prefix + '"\\ud800":"value"}', Code.INVALID_JSON),
                 (prefix + '"x":0} {}', Code.INVALID_JSON)]
        for raw, code in cases:
            with self.subTest(raw=raw), self.assertRaises(MagicBalanceInputError) as caught:
                parse(raw)
            error = caught.exception
            self.assertEqual((error.schema_version, error.request_id, error.code), ('1', None, code))
            output = json.loads(encode_error(error))
            validate(output, 'error')
            self.assertEqual(output['schema_version'], '1')

    def test_decoded_version_and_request_id_trust_boundary(self):
        for version in (None, False, 2, [], {}, '', '6'):
            error = self.invalid(dict(document(), schema_version=version), version='1', path='/schema_version',
                code=Code.UNSUPPORTED_VERSION if isinstance(version, str) else Code.INVALID_INPUT)
            self.assertEqual(error.request_id, document()['request_id'])
        for request_id in ('', ' \t', None, 7):
            self.assertIsNone(self.invalid(dict(document(), request_id=request_id), path='/request_id').request_id)
        for root in (None, [], 2, '2'):
            self.assertIsNone(self.invalid(root, version='1').request_id)
        self.invalid(dict(document(), kind='npc_magic_simulation'), path='/kind')

    def test_packaged_v2_schemas_and_explicit_validator_version(self):
        command = parse(json.dumps(document()))
        documents = {'request': document(), 'result': json.loads(encode(command, make_result(command))),
                     'error': json.loads(encode_error(MagicBalanceInputError(Code.INVALID_INPUT, 'bad', schema_version='2')))}
        for kind, data in documents.items():
            schema = json.loads(files('towr.adapters.schemas').joinpath(
                f'magic-balance-{kind}-v2.schema.json').read_text(encoding='utf-8'))
            Draft202012Validator.check_schema(schema)
            self.assertEqual(schema['$id'], f'urn:towr:magic-balance:{kind}:2')
            validate(data, kind, schema_version='2')
            with self.assertRaises(ValidationError):
                validate(data, kind)
        for version in (None, False, 2, '', '6', [], {}):
            with self.assertRaises(ValueError):
                validate({}, schema_version=version)
        with self.assertRaises(ValueError):
            validate({}, 'other', schema_version='2')

    def test_result_and_phase_error_shapes_close_and_echo_requires_v2(self):
        command = parse(json.dumps(document()))
        originals = [('result', json.loads(encode(command, make_result(command))))]
        originals.extend(('error', json.loads(encode_error(error))) for error in (
            MagicBalanceInputError(Code.INVALID_INPUT, 'bad', schema_version='2'),
            MagicBalanceGenerationError('outer', 'candidate', (1, 0), schema_version='2'),
            MagicBalanceExecutionError('outer', 1, 'candidate', schema_version='2')))
        for kind, original in originals:
            for path in object_paths(original):
                for key in (None, *at(original, path)):
                    data = deepcopy(original)
                    if key is None:
                        at(data, path)['extra'] = True
                    else:
                        del at(data, path)[key]
                    with self.subTest(kind=kind, path=path, key=key), self.assertRaises(ValidationError):
                        validate(data, kind, schema_version='2')
        changed = deepcopy(originals[0][1])
        changed['request'] = legacy_document()
        with self.assertRaises(ValidationError):
            validate(changed, 'result', schema_version='2')

    def test_command_and_errors_append_version_keep_defaults_and_reject_other_types(self):
        old = parse(json.dumps(legacy_document()))
        self.assertEqual(fields(MagicBalanceCommand)[-1].name, 'schema_version')
        self.assertEqual(MagicBalanceCommand(old.request_id, old.generation_request, old.execution, old.definition_order), old)
        command = parse(json.dumps(document()))
        self.assertEqual(pickle.loads(pickle.dumps(command)), command)
        with self.assertRaises(FrozenInstanceError):
            command.schema_version = '1'
        constructors = ((MagicBalanceInputError, (Code.INVALID_INPUT, 'bad')),
                        (MagicBalanceGenerationError, ('outer',)), (MagicBalanceExecutionError, ('outer',)))
        for constructor, args in constructors:
            self.assertEqual(constructor(*args).schema_version, '1')
            for version in ('1', '2'):
                error = constructor(*args, schema_version=version)
                self.assertEqual(json.loads(encode_error(error))['schema_version'], version)
        for version in (None, 1, 2, True, '', '6', [], {}):
            with self.assertRaises((TypeError, ValueError)):
                replace(command, schema_version=version)
            for constructor, args in constructors:
                with self.assertRaises((TypeError, ValueError)):
                    constructor(*args, schema_version=version)

    def test_full_policy_source_chain_rejects_same_ids_in_either_direction(self):
        opted, legacy = (parse(json.dumps(document(opted=value))) for value in (True, False))
        for command, foreign in ((opted, legacy), (legacy, opted)):
            result, wrong = make_result(command), make_result(foreign)
            self.assertEqual(command.generation_request.template_scenario.id, foreign.generation_request.template_scenario.id)
            with self.assertRaises(ValueError):
                encode(command, wrong)
            with self.assertRaises(ValueError):
                replace(result, evaluation_result=wrong.evaluation_result)
            evaluation = result.generation_result.evaluation_request
            for index, alternate in enumerate(wrong.generation_result.evaluation_request.candidates):
                candidates = list(evaluation.candidates)
                self.assertEqual(candidates[index].candidate_id, alternate.candidate_id)
                candidates[index] = alternate
                with self.assertRaises(ValueError):
                    replace(result.generation_result, evaluation_request=replace(evaluation, candidates=tuple(candidates)))
            with patch.object(service, 'generate_magic_candidates', return_value=wrong.generation_result), \
                    patch.object(service, 'evaluate_magic_candidates_staged') as evaluate:
                with self.assertRaises(MagicBalanceGenerationError) as caught:
                    service.execute_magic_balance(command)
                self.assertEqual(caught.exception.schema_version, '2')
                evaluate.assert_not_called()
            with patch.object(service, 'generate_magic_candidates', return_value=result.generation_result), \
                    patch.object(service, 'evaluate_magic_candidates_staged', return_value=wrong.evaluation_result):
                with self.assertRaises(MagicBalanceExecutionError) as caught:
                    service.execute_magic_balance(command)
                self.assertEqual(caught.exception.schema_version, '2')

    def test_reconstruction_checks_version_and_definition_order(self):
        command = parse(json.dumps(document()))
        for changed in (replace(command, schema_version='1'),
                        replace(command, definition_order=tuple(reversed(command.definition_order)))):
            with patch('towr.adapters.magic_balance_json.parse_magic_balance_request', return_value=changed), \
                    self.assertRaisesRegex(ValueError, 'losslessly'):
                encode(command, make_result(command))

    def test_phase_wrapping_uses_command_version_not_foreign_cause_metadata(self):
        for version in ('1', '2'):
            base = parse(json.dumps(legacy_document() if version == '1' else document()))
            result = make_result(base)
            for mode in Mode:
                command = replace(base, execution=Options(mode, 2, 1) if mode is Mode.PROCESS else Options(mode))
                for phase in ('generation', 'evaluation', 'result'):
                    cause = MagicBalanceExecutionError('private foreign', schema_version='2' if version == '1' else '1')
                    cause.add_note('private note')
                    error_type = MagicBalanceGenerationError if phase == 'generation' else MagicBalanceExecutionError
                    with self.subTest(version=version, mode=mode, phase=phase), \
                            patch.object(service, 'generate_magic_candidates', return_value=result.generation_result,
                                         side_effect=cause if phase == 'generation' else None), \
                            patch.object(service, 'evaluate_magic_candidates_staged', return_value=result.evaluation_result,
                                         side_effect=cause if phase == 'evaluation' else None), \
                            patch.object(service, 'MagicBalanceResult', side_effect=cause), \
                            self.assertRaises(error_type) as caught:
                        service.execute_magic_balance(command)
                    error = caught.exception
                    self.assertIs(error.__cause__, cause)
                    self.assertEqual((error.schema_version, error.request_id), (version, command.request_id))
                    wire = encode_error(error)
                    self.assertNotIn('private', wire)
                    self.assertEqual(json.loads(wire)['schema_version'], version)

    def test_known_candidate_counts_and_stage_contexts_survive_wrapping(self):
        command = parse(json.dumps(document()))
        result = make_result(command)
        for cause, phase in ((MagicCandidateGenerationError('candidate', (1, 0)), 'generation'),
                             (MagicStagedEvaluationError(1, 'candidate'), 'evaluation')):
            cause.add_note('private note')
            error_type = MagicBalanceGenerationError if phase == 'generation' else MagicBalanceExecutionError
            with patch.object(service, 'generate_magic_candidates', return_value=result.generation_result,
                              side_effect=cause if phase == 'generation' else None), \
                    patch.object(service, 'evaluate_magic_candidates_staged', side_effect=cause), \
                    self.assertRaises(error_type) as caught:
                service.execute_magic_balance(command)
            error = caught.exception
            self.assertIs(error.__cause__, cause)
            output = json.loads(encode_error(error))
            validate(output, 'error', schema_version='2')
            self.assertEqual(output['schema_version'], '2')
            self.assertEqual(output['error']['candidate_id'], 'candidate')
            self.assertEqual(output['error']['counts'], [1, 0] if phase == 'generation' else None)
            self.assertEqual(output['error']['stage_index'], None if phase == 'generation' else 1)
            self.assertNotIn('private', json.dumps(output))

    def test_valid_preflight_can_fail_real_subset_without_evaluation_or_partial_result(self):
        data = document(source=generation_failure_document())
        with patch('towr.application.magic_candidate_generation._project_candidate', side_effect=AssertionError('projected')):
            command = parse(json.dumps(data))
        before, state = deepcopy(command), random.getstate()
        with patch.object(service, 'evaluate_magic_candidates_staged') as evaluate, \
                self.assertRaises(MagicBalanceGenerationError) as caught:
            service.execute_magic_balance(command)
        evaluate.assert_not_called()
        error = caught.exception
        self.assertEqual((error.schema_version, error.counts), ('2', (1, 0)))
        self.assertIsInstance(error.__cause__, MagicCandidateGenerationError)
        self.assertIsNotNone(error.__cause__.__cause__)
        output = json.loads(encode_error(error))
        self.assertEqual(output['error']['counts'], [1, 0])
        self.assertNotIn('candidates', output)
        self.assertEqual(command, before)
        self.assertEqual(random.getstate(), state)

    def test_parse_encode_never_generate_sample_spawn_or_fake_simulation_envelope(self):
        pairs = []
        for opted in (False, True):
            command = parse(json.dumps(document(opted=opted)))
            pairs.append((command, make_result(command)))
        state = random.getstate()
        with ExitStack() as stack:
            for target in ('random.Random', 'concurrent.futures.ProcessPoolExecutor',
                           'towr.application.magic_candidate_generation.generate_magic_candidates',
                           'towr.application.magic_staged_evaluation_service.evaluate_magic_candidates_staged',
                           'towr.application.magic_evaluation_service.run_npc_magic_simulation',
                           'towr.application.magic_evaluation_service.run_npc_magic_simulation_parallel',
                           'towr.adapters.magic_simulation_json.parse_magic_simulation_request'):
                stack.enter_context(patch(target, side_effect=AssertionError(target)))
            for command, result in pairs:
                output = json.loads(encode(command, result))
                self.assertEqual(parse(json.dumps(output['request'])), command)
            data = document()
            data['generation']['miscast_continuation'] = None
            self.invalid(data, path='/generation/miscast_continuation')
        self.assertEqual(random.getstate(), state)
