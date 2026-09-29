from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from tests.unit.test_m7_mixed_balance_json import document, make_result
from towr.adapters.mixed_balance_json import parse_mixed_balance_request as parse, encode_mixed_balance_error as encode
from towr.adapters.mixed_json_errors import MixedBalanceInputError
from towr.adapters.ranged_json_errors import RangedInputErrorCode
from towr.adapters.mixed_json_errors import MixedSimulationInputError
from towr.adapters.mixed_json_schema import validate_mixed_balance_document
from towr.application import mixed_balance_service as service
from towr.application.mixed_balance_errors import MixedBalanceGenerationError, MixedBalanceExecutionError
from towr.application.mixed_candidate_generation_errors import MixedCandidateGenerationError
from towr.application.mixed_staged_evaluation_errors import MixedStagedEvaluationError


class M7MixedBalanceServiceTests(unittest.TestCase):
    def test_ranged_command_is_rejected_before_either_phase(self):
        from tests.unit.test_m5_ranged_balance_json import document as ranged_document
        from towr.adapters.ranged_balance_json import parse_ranged_balance_request
        from tests.unit.test_m6_melee_balance_json import document as melee_document
        from towr.adapters.melee_balance_json import parse_melee_balance_request
        ranged = parse_ranged_balance_request(json.dumps(ranged_document()))
        melee = parse_melee_balance_request(json.dumps(melee_document()))
        with patch.object(service, 'generate_mixed_candidates') as generate, \
                patch.object(service, 'evaluate_mixed_candidates_staged') as evaluate:
            for command in (ranged, melee):
                with self.assertRaises(TypeError): service.execute_mixed_balance(command)
            generate.assert_not_called(); evaluate.assert_not_called()

    def test_failure_category_follows_the_active_phase(self):
        command = parse(json.dumps(document()))
        generated = make_result(command).generation_result
        cause = MixedStagedEvaluationError(9, 'unrelated')
        with patch.object(service, 'generate_mixed_candidates', side_effect=cause), \
                patch.object(service, 'evaluate_mixed_candidates_staged') as evaluate:
            with self.assertRaises(MixedBalanceGenerationError) as caught:
                service.execute_mixed_balance(command)
            evaluate.assert_not_called()
        self.assertIs(caught.exception.__cause__, cause)
        self.assertIsNone(caught.exception.candidate_id)
        self.assertIsNone(caught.exception.counts)
        cause = MixedCandidateGenerationError('unrelated', (9,))
        with patch.object(service, 'generate_mixed_candidates', return_value=generated), \
                patch.object(service, 'evaluate_mixed_candidates_staged', side_effect=cause):
            with self.assertRaises(MixedBalanceExecutionError) as caught:
                service.execute_mixed_balance(command)
        self.assertIs(caught.exception.__cause__, cause)
        self.assertIsNone(caught.exception.stage_index)
        self.assertIsNone(caught.exception.candidate_id)

    def test_error_counts_are_copied_and_execution_messages_are_generic(self):
        counts = [1, 0]
        generation = MixedBalanceGenerationError('outer', 'candidate', counts)
        counts.clear()
        self.assertEqual(generation.counts, (1, 0))
        for error in (generation, MixedBalanceExecutionError('outer', 1, 'candidate')):
            error.args = ('private worker details',)
            error.add_note('private note')
            actual = encode(error)
            self.assertNotIn('private', actual)
            self.assertEqual(json.loads(actual)['request_id'], 'outer')

    def test_error_encoder_rejects_other_command_families(self):
        from towr.adapters.ranged_balance_json_errors import RangedBalanceInputError
        from towr.application.ranged_balance_errors import RangedBalanceExecutionError, RangedBalanceGenerationError
        from towr.application.mixed_simulation_errors import MixedSimulationExecutionError
        from towr.adapters.melee_json_errors import MeleeBalanceInputError
        from towr.application.melee_balance_errors import MeleeBalanceExecutionError, MeleeBalanceGenerationError
        for error in (MeleeBalanceInputError(RangedInputErrorCode.INVALID_INPUT, 'other'),
                      MeleeBalanceGenerationError('other'), MeleeBalanceExecutionError('other'),
                      RangedBalanceInputError(RangedInputErrorCode.INVALID_INPUT, 'other'),
                      RangedBalanceGenerationError('other'), RangedBalanceExecutionError('other'),
                      MixedSimulationExecutionError('other'), KeyboardInterrupt(), None):
            with self.assertRaises(TypeError): encode(error)

    def test_dispatch_passes_exact_sources_and_execution_options(self):
        for execution in ({'mode':'sequential'}, {'mode':'process','workers':2,'batch_size':4}):
            command = parse(json.dumps(dict(document(), execution=execution)))
            expected = make_result(command)
            with patch.object(service, 'generate_mixed_candidates', return_value=expected.generation_result) as generate, \
                    patch.object(service, 'evaluate_mixed_candidates_staged', return_value=expected.evaluation_result) as evaluate:
                self.assertEqual(service.execute_mixed_balance(command), expected)
            generate.assert_called_once_with(command.generation_request)
            evaluate.assert_called_once_with(expected.generation_result.evaluation_request, command.execution)

    def test_complete_and_early_unsupported_are_successful_results(self):
        command = parse(json.dumps(document()))
        for counts in (lambda i,p,n: (n//2,n-n//2,0,0), lambda i,p,n: (0,0,0,n),
                       lambda i,p,n: (0,0,0,n) if i else (n,0,0,0), lambda i,p,n: (0,0,n,0)):
            expected = make_result(command, counts)
            with patch.object(service, 'generate_mixed_candidates', return_value=expected.generation_result), \
                    patch.object(service, 'evaluate_mixed_candidates_staged', return_value=expected.evaluation_result):
                self.assertEqual(service.execute_mixed_balance(command), expected)

    def test_invalid_command_is_rejected_before_any_dispatch(self):
        with patch.object(service, 'generate_mixed_candidates') as generate, \
                patch.object(service, 'evaluate_mixed_candidates_staged') as evaluate:
            with self.assertRaises(TypeError): service.execute_mixed_balance(None)
        generate.assert_not_called(); evaluate.assert_not_called()

    def test_typed_generation_error_preserves_context_and_cause_chain_without_evaluation(self):
        command = parse(json.dumps(document()))
        original = ValueError('private admission details'); original.add_note('private note')
        cause = MixedCandidateGenerationError('mixed:counts:1,0', (1,0)); cause.__cause__ = original
        with patch.object(service, 'generate_mixed_candidates', side_effect=cause) as generate, \
                patch.object(service, 'evaluate_mixed_candidates_staged') as evaluate:
            with self.assertRaises(MixedBalanceGenerationError) as caught:
                service.execute_mixed_balance(command)
        generate.assert_called_once(); evaluate.assert_not_called()
        error = caught.exception
        self.assertEqual((error.request_id,error.candidate_id,error.counts), (command.request_id,cause.candidate_id,(1,0)))
        self.assertIs(error.__cause__, cause)
        self.assertIs(error.__cause__.__cause__, original)
        self.assertEqual(original.__notes__, ['private note'])
        self.assertNotIn('private', encode(error))

    def test_untyped_generation_failure_has_unknown_context(self):
        command = parse(json.dumps(document())); cause = OSError('private')
        with patch.object(service, 'generate_mixed_candidates', side_effect=cause) as generate, \
                patch.object(service, 'evaluate_mixed_candidates_staged') as evaluate:
            with self.assertRaises(MixedBalanceGenerationError) as caught: service.execute_mixed_balance(command)
        generate.assert_called_once(); evaluate.assert_not_called()
        self.assertIs(caught.exception.__cause__, cause)
        self.assertIsNone(caught.exception.candidate_id); self.assertIsNone(caught.exception.counts)

    def test_invalid_or_foreign_generated_result_stops_before_evaluation(self):
        command = parse(json.dumps(document()))
        foreign = make_result(replace(command, generation_request=replace(command.generation_request,master_seed=43)))
        for result in (None, foreign.generation_result):
            with patch.object(service, 'generate_mixed_candidates', return_value=result), \
                    patch.object(service, 'evaluate_mixed_candidates_staged') as evaluate:
                with self.assertRaises(MixedBalanceGenerationError) as caught: service.execute_mixed_balance(command)
            evaluate.assert_not_called()
            self.assertIsInstance(caught.exception.__cause__, (ValueError, TypeError))
            self.assertIsNone(caught.exception.candidate_id)

    def test_typed_evaluation_error_preserves_stage_candidate_and_cause(self):
        command = parse(json.dumps(document())); generated = make_result(command).generation_result
        cause = MixedStagedEvaluationError(1, 'mixed:counts:1,0'); cause.add_note('private note')
        with patch.object(service, 'generate_mixed_candidates', return_value=generated), \
                patch.object(service, 'evaluate_mixed_candidates_staged', side_effect=cause) as evaluate:
            with self.assertRaises(MixedBalanceExecutionError) as caught: service.execute_mixed_balance(command)
        evaluate.assert_called_once_with(generated.evaluation_request, command.execution)
        error = caught.exception
        self.assertEqual((error.request_id,error.stage_index,error.candidate_id), (command.request_id,1,cause.candidate_id))
        self.assertIs(error.__cause__, cause)
        self.assertEqual(error.__cause__.__notes__, ['private note'])
        self.assertNotIn('private', encode(error))

    def test_untyped_evaluation_failure_and_wrong_result_have_unknown_context(self):
        command = parse(json.dumps(document())); expected = make_result(command)
        foreign = make_result(replace(command, generation_request=replace(command.generation_request,master_seed=43)))
        cause = RuntimeError('private failure')
        for options in ({'side_effect':cause}, {'return_value':None}, {'return_value':foreign.evaluation_result}):
            with patch.object(service, 'generate_mixed_candidates', return_value=expected.generation_result), \
                    patch.object(service, 'evaluate_mixed_candidates_staged', **options) as evaluate:
                with self.assertRaises(MixedBalanceExecutionError) as caught: service.execute_mixed_balance(command)
            evaluate.assert_called_once()
            self.assertIsNone(caught.exception.stage_index); self.assertIsNone(caught.exception.candidate_id)
            self.assertIsNotNone(caught.exception.__cause__)

    def test_interrupts_propagate_from_both_phases(self):
        command = parse(json.dumps(document())); generated = make_result(command).generation_result
        for interruption in (KeyboardInterrupt, SystemExit):
            for phase in ('generate', 'evaluate'):
                with patch.object(service, 'generate_mixed_candidates', return_value=generated,
                                  side_effect=interruption() if phase=='generate' else None), \
                        patch.object(service, 'evaluate_mixed_candidates_staged', side_effect=interruption()) as evaluate:
                    with self.assertRaises(interruption): service.execute_mixed_balance(command)
                    if phase=='generate': evaluate.assert_not_called()

    def test_error_encoder_covers_all_categories_and_unknown_context(self):
        for code in RangedInputErrorCode:
            error = MixedBalanceInputError(code, 'message', request_id='request', path='/a~1b/~0')
            actual = json.loads(encode(error)); validate_mixed_balance_document(actual, 'error')
            self.assertEqual(actual['error']['code'], code.value)
            self.assertEqual(actual['error']['path'], '/a~1b/~0')
            self.assertEqual([actual['error'][k] for k in ('candidate_id','counts','stage_index')], [None]*3)
        for error, code in ((MixedBalanceGenerationError('request'),'generation_failed'),
                            (MixedBalanceExecutionError('request'),'execution_failed')):
            actual = json.loads(encode(error))
            self.assertEqual(actual['error']['code'],code)
            self.assertEqual([actual['error'][k] for k in ('path','candidate_id','counts','stage_index')],[None]*4)

    def test_known_error_contexts_have_complete_envelopes(self):
        cases = (
            (MixedBalanceInputError(RangedInputErrorCode.INVALID_INPUT, 'invalid window',
                path='/evaluation/window', request_id='outer'),
             dict(code='invalid_input', path='/evaluation/window', message='invalid window',
                  candidate_id=None, counts=None, stage_index=None)),
            (MixedBalanceGenerationError('outer','mixed:counts:1,0',(1,0)),
             dict(code='generation_failed', path=None, message='Balance candidate generation failed',
                  candidate_id='mixed:counts:1,0', counts=[1,0], stage_index=None)),
            (MixedBalanceExecutionError('outer',1,'mixed:counts:1,1'),
             dict(code='execution_failed', path=None, message='Balance evaluation failed',
                  candidate_id='mixed:counts:1,1', counts=None, stage_index=1)),
        )
        for error, expected in cases:
            self.assertEqual(json.loads(encode(error)), dict(schema_version='1',kind='mixed_balance_error',
                request_id='outer',error=expected))

    def test_encoder_rejects_unknown_errors_escapes_bad_unicode_and_has_no_execution(self):
        for error in (ValueError('raw'), MixedCandidateGenerationError('candidate',(1,)),
                      MixedSimulationInputError(RangedInputErrorCode.INVALID_INPUT,'other command')):
            with self.assertRaises(TypeError): encode(error)
        error=MixedBalanceInputError(RangedInputErrorCode.INVALID_JSON,'bad '+chr(0xD800))
        with patch.object(service,'execute_mixed_balance',side_effect=AssertionError('executed')):
            text=encode(error)
        text.encode('utf-8')
        self.assertTrue(text.endswith('\n'))
        self.assertIsNone(json.loads(text)['request_id'])
        self.assertEqual(set(json.loads(text)),{'schema_version','kind','request_id','error'})

    def test_pair_order_and_actor_escape_flags_are_part_of_both_phase_sources(self):
        command = parse(json.dumps(document()))
        expected = make_result(command)
        for change in ('pairs', 'escape'):
            data = document()
            if change == 'pairs':
                data['reserve']['scenario']['pair_ranges'].reverse()
                data['generation']['pair_ranges'].reverse()
            else:
                data['reserve']['scenario']['actor_policies'][2]['can_leave_zone'] = False
            foreign = make_result(parse(json.dumps(data)))
            self.assertNotEqual(expected.generation_result, foreign.generation_result)
            with patch.object(service, 'generate_mixed_candidates', return_value=foreign.generation_result), \
                    patch.object(service, 'evaluate_mixed_candidates_staged') as evaluate:
                with self.assertRaises(MixedBalanceGenerationError):
                    service.execute_mixed_balance(command)
            evaluate.assert_not_called()
            with patch.object(service, 'generate_mixed_candidates', return_value=expected.generation_result), \
                    patch.object(service, 'evaluate_mixed_candidates_staged', return_value=foreign.evaluation_result):
                with self.assertRaises(MixedBalanceExecutionError) as caught:
                    service.execute_mixed_balance(command)
            self.assertIsInstance(caught.exception.__cause__, ValueError)
            self.assertIsNone(caught.exception.stage_index)
