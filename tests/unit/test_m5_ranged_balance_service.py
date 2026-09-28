from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from tests.unit.test_m5_ranged_balance_json import document, make_result, EXAMPLES
from towr.adapters.ranged_balance_json import parse_ranged_balance_request as parse, encode_ranged_balance_error as encode
from towr.adapters.ranged_balance_json_errors import RangedBalanceInputError
from towr.adapters.ranged_json_errors import RangedInputErrorCode, RangedSimulationInputError
from towr.adapters.ranged_json_schema import validate_ranged_balance_document
from towr.application import ranged_balance_service as service
from towr.application.ranged_balance_errors import RangedBalanceGenerationError, RangedBalanceExecutionError
from towr.application.ranged_candidate_generation_errors import RangedCandidateGenerationError
from towr.application.ranged_staged_evaluation_errors import RangedStagedEvaluationError


class M5BalanceServiceTests(unittest.TestCase):
    def test_dispatch_passes_exact_sources_and_execution_options(self):
        for execution in ({'mode':'sequential'}, {'mode':'process','workers':2,'batch_size':4}):
            command = parse(json.dumps(dict(document(), execution=execution)))
            expected = make_result(command)
            with patch.object(service, 'generate_ranged_candidates', return_value=expected.generation_result) as generate, \
                    patch.object(service, 'evaluate_ranged_candidates_staged', return_value=expected.evaluation_result) as evaluate:
                self.assertEqual(service.execute_ranged_balance(command), expected)
            generate.assert_called_once_with(command.generation_request)
            evaluate.assert_called_once_with(expected.generation_result.evaluation_request, command.execution)

    def test_complete_and_early_unsupported_are_successful_results(self):
        command = parse(json.dumps(document()))
        for counts in (lambda i,p,n: (n//2,n-n//2,0,0), lambda i,p,n: (0,0,0,n),
                       lambda i,p,n: (0,0,0,n) if i else (n,0,0,0), lambda i,p,n: (0,0,n,0)):
            expected = make_result(command, counts)
            with patch.object(service, 'generate_ranged_candidates', return_value=expected.generation_result), \
                    patch.object(service, 'evaluate_ranged_candidates_staged', return_value=expected.evaluation_result):
                self.assertEqual(service.execute_ranged_balance(command), expected)

    def test_invalid_command_is_rejected_before_any_dispatch(self):
        with patch.object(service, 'generate_ranged_candidates') as generate, \
                patch.object(service, 'evaluate_ranged_candidates_staged') as evaluate:
            with self.assertRaises(TypeError): service.execute_ranged_balance(None)
        generate.assert_not_called(); evaluate.assert_not_called()

    def test_typed_generation_error_preserves_context_and_cause_chain_without_evaluation(self):
        command = parse(json.dumps(document()))
        original = ValueError('private admission details'); original.add_note('private note')
        cause = RangedCandidateGenerationError('example:counts:1,0', (1,0)); cause.__cause__ = original
        with patch.object(service, 'generate_ranged_candidates', side_effect=cause) as generate, \
                patch.object(service, 'evaluate_ranged_candidates_staged') as evaluate:
            with self.assertRaises(RangedBalanceGenerationError) as caught:
                service.execute_ranged_balance(command)
        generate.assert_called_once(); evaluate.assert_not_called()
        error = caught.exception
        self.assertEqual((error.request_id,error.candidate_id,error.counts), (command.request_id,cause.candidate_id,(1,0)))
        self.assertIs(error.__cause__, cause)
        self.assertIs(error.__cause__.__cause__, original)
        self.assertEqual(original.__notes__, ['private note'])
        self.assertNotIn('private', encode(error))

    def test_untyped_generation_failure_has_unknown_context(self):
        command = parse(json.dumps(document())); cause = OSError('private')
        with patch.object(service, 'generate_ranged_candidates', side_effect=cause) as generate, \
                patch.object(service, 'evaluate_ranged_candidates_staged') as evaluate:
            with self.assertRaises(RangedBalanceGenerationError) as caught: service.execute_ranged_balance(command)
        generate.assert_called_once(); evaluate.assert_not_called()
        self.assertIs(caught.exception.__cause__, cause)
        self.assertIsNone(caught.exception.candidate_id); self.assertIsNone(caught.exception.counts)

    def test_invalid_or_foreign_generated_result_stops_before_evaluation(self):
        command = parse(json.dumps(document()))
        foreign = make_result(replace(command, generation_request=replace(command.generation_request,master_seed=43)))
        for result in (None, foreign.generation_result):
            with patch.object(service, 'generate_ranged_candidates', return_value=result), \
                    patch.object(service, 'evaluate_ranged_candidates_staged') as evaluate:
                with self.assertRaises(RangedBalanceGenerationError) as caught: service.execute_ranged_balance(command)
            evaluate.assert_not_called()
            self.assertIsInstance(caught.exception.__cause__, (ValueError, TypeError))
            self.assertIsNone(caught.exception.candidate_id)

    def test_typed_evaluation_error_preserves_stage_candidate_and_cause(self):
        command = parse(json.dumps(document())); generated = make_result(command).generation_result
        cause = RangedStagedEvaluationError(1, 'example:counts:1,0'); cause.add_note('private note')
        with patch.object(service, 'generate_ranged_candidates', return_value=generated), \
                patch.object(service, 'evaluate_ranged_candidates_staged', side_effect=cause) as evaluate:
            with self.assertRaises(RangedBalanceExecutionError) as caught: service.execute_ranged_balance(command)
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
            with patch.object(service, 'generate_ranged_candidates', return_value=expected.generation_result), \
                    patch.object(service, 'evaluate_ranged_candidates_staged', **options) as evaluate:
                with self.assertRaises(RangedBalanceExecutionError) as caught: service.execute_ranged_balance(command)
            evaluate.assert_called_once()
            self.assertIsNone(caught.exception.stage_index); self.assertIsNone(caught.exception.candidate_id)
            self.assertIsNotNone(caught.exception.__cause__)

    def test_interrupts_propagate_from_both_phases(self):
        command = parse(json.dumps(document())); generated = make_result(command).generation_result
        for interruption in (KeyboardInterrupt, SystemExit):
            for phase in ('generate', 'evaluate'):
                with patch.object(service, 'generate_ranged_candidates', return_value=generated,
                                  side_effect=interruption() if phase=='generate' else None), \
                        patch.object(service, 'evaluate_ranged_candidates_staged', side_effect=interruption()) as evaluate:
                    with self.assertRaises(interruption): service.execute_ranged_balance(command)
                    if phase=='generate': evaluate.assert_not_called()

    def test_error_encoder_covers_all_categories_and_unknown_context(self):
        for code in RangedInputErrorCode:
            error = RangedBalanceInputError(code, 'message', request_id='request', path='/a~1b/~0')
            actual = json.loads(encode(error)); validate_ranged_balance_document(actual, 'error')
            self.assertEqual(actual['error']['code'], code.value)
            self.assertEqual(actual['error']['path'], '/a~1b/~0')
            self.assertEqual([actual['error'][k] for k in ('candidate_id','counts','stage_index')], [None]*3)
        for error, code in ((RangedBalanceGenerationError('request'),'generation_failed'),
                            (RangedBalanceExecutionError('request'),'execution_failed')):
            actual = json.loads(encode(error))
            self.assertEqual(actual['error']['code'],code)
            self.assertEqual([actual['error'][k] for k in ('path','candidate_id','counts','stage_index')],[None]*4)

    def test_three_error_examples_are_reproduced_by_real_encoder(self):
        errors = (
            ('input', RangedBalanceInputError(RangedInputErrorCode.INVALID_INPUT,
                'denominator must be a positive integer', path='/evaluation/window/minimum/denominator', request_id='example:balance')),
            ('generation', RangedBalanceGenerationError('example:balance','example:counts:1,0',(1,0))),
            ('execution', RangedBalanceExecutionError('example:balance',1,'example:counts:1,1')),
        )
        for name,error in errors:
            expected=json.loads((EXAMPLES/f'balance-v1.{name}-error.json').read_text(encoding='utf-8'))
            self.assertEqual(json.loads(encode(error)),expected)

    def test_encoder_rejects_unknown_errors_escapes_bad_unicode_and_has_no_execution(self):
        for error in (ValueError('raw'), RangedCandidateGenerationError('candidate',(1,)),
                      RangedSimulationInputError(RangedInputErrorCode.INVALID_INPUT,'other command')):
            with self.assertRaises(TypeError): encode(error)
        error=RangedBalanceInputError(RangedInputErrorCode.INVALID_JSON,'bad '+chr(0xD800))
        with patch.object(service,'execute_ranged_balance',side_effect=AssertionError('executed')):
            text=encode(error)
        text.encode('utf-8')
        self.assertTrue(text.endswith('\n'))
        self.assertIsNone(json.loads(text)['request_id'])
        self.assertEqual(set(json.loads(text)),{'schema_version','kind','request_id','error'})
