"""Magic balance CLI phase boundaries over the existing byte I/O contract."""
from contextlib import ExitStack
import io
import json
import unittest
from unittest.mock import patch

from tests.unit.test_m8_magic_balance_json import document, make_result
from towr import cli
from towr.adapters.magic_balance_json import parse_magic_balance_request
from towr.application.magic_balance_errors import MagicBalanceGenerationError, MagicBalanceExecutionError


class M8MagicBalanceCliTests(unittest.TestCase):
    def setUp(self):
        self.command = parse_magic_balance_request(json.dumps(document()))
        self.result = make_result(self.command)
        self.stdin = io.TextIOWrapper(io.BytesIO(json.dumps(document()).encode()))
        self.stdout = io.TextIOWrapper(io.BytesIO(), encoding='ascii')
        self.stderr = io.TextIOWrapper(io.BytesIO(), encoding='ascii')
        for name in ('stdin','stdout','stderr'):
            stream = getattr(self,name)
            self.addCleanup(stream.close)
            self.enterContext(patch.object(cli.sys,name,stream))

    def test_complete_early_stop_and_final_unsupported_all_exit_zero(self):
        for counts in (None,lambda i,p,n:(0,0,0,n),lambda i,p,n:(0,0,0,n) if i else (n,0,0,0)):
            self.stdin.buffer.seek(0); self.stdout.buffer.seek(0); self.stdout.buffer.truncate()
            result = make_result(self.command, counts)
            with patch.object(cli,'execute_magic_balance',return_value=result) as service:
                self.assertEqual(cli.main(['balance-magic','-']),0)
            service.assert_called_once_with(self.command)
            actual=json.loads(self.stdout.buffer.getvalue())
            self.assertEqual(actual['status'],result.evaluation_result.status.value)
            self.assertEqual(self.stderr.buffer.getvalue(),b'')

    def test_generation_and_execution_errors_have_phase_context_without_partial_output(self):
        for error,code in ((MagicBalanceGenerationError('req','candidate',(1,0)),'generation_failed'),
                           (MagicBalanceExecutionError('req',1,'candidate'),'evaluation_failed')):
            self.stdin.buffer.seek(0); self.stdout.buffer.seek(0); self.stdout.buffer.truncate()
            error.__cause__=RuntimeError('private cause')
            with patch.object(cli,'execute_magic_balance',side_effect=error) as service:
                self.assertEqual(cli.main(['balance-magic','-']),3)
            service.assert_called_once()
            actual=json.loads(self.stdout.buffer.getvalue())
            self.assertEqual(actual['error']['code'],code)
            self.assertEqual(actual['request_id'],'req')
            self.assertEqual(set(actual),{'schema_version','kind','request_id','error'})
            self.assertIn(code.encode(),self.stderr.buffer.getvalue())
            self.assertNotIn(b'private',self.stderr.buffer.getvalue())

    def test_read_failures_do_not_parse_or_execute(self):
        for target,name in ((cli.Path,'read_bytes'),(self.stdin.buffer,'read')):
            with patch.object(target,name,side_effect=OSError('denied')), \
                    patch.object(cli,'parse_magic_balance_request') as parse, \
                    patch.object(cli,'execute_magic_balance') as execute:
                self.assertEqual(cli.main(['balance-magic','file.json' if name=='read_bytes' else '-']),4)
            parse.assert_not_called(); execute.assert_not_called()
            self.assertEqual(self.stdout.buffer.getvalue(),b'')

    def test_input_failure_never_reaches_service(self):
        self.stdin.buffer.seek(0); self.stdin.buffer.truncate(); self.stdin.buffer.write(b'{'); self.stdin.buffer.seek(0)
        with patch.object(cli,'execute_magic_balance') as execute:
            self.assertEqual(cli.main(['balance-magic','-']),2)
        execute.assert_not_called()
        self.assertEqual(json.loads(self.stdout.buffer.getvalue())['error']['code'],'invalid_json')

    def test_encoder_exceptions_including_typed_failures_propagate_before_stdout(self):
        from towr.adapters.magic_json_errors import MagicBalanceInputError
        from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
        for error in (ValueError('bug'),MagicBalanceInputError(Code.INVALID_INPUT, 'typed encoder'),
                      MagicBalanceGenerationError('request'),MagicBalanceExecutionError('request')):
            self.stdin.buffer.seek(0)
            with patch.object(cli,'execute_magic_balance',return_value=self.result), \
                    patch.object(cli,'encode_magic_balance_result',side_effect=error):
                with self.assertRaises(type(error)) as caught: cli.main(['balance-magic','-'])
            self.assertIs(caught.exception,error)
        self.assertEqual(self.stdout.buffer.getvalue(),b''); self.assertEqual(self.stderr.buffer.getvalue(),b'')

    def test_write_flush_failure_is_io_without_second_json_or_shutdown_flush(self):
        for method in ('write','flush'):
            self.stdin.buffer.seek(0)
            with patch.object(cli,'execute_magic_balance',return_value=self.result), \
                    patch.object(self.stdout.buffer,method,side_effect=BrokenPipeError('closed')) as fail, \
                    patch.object(cli,'_silence_failed_stream') as silence:
                self.assertEqual(cli.main(['balance-magic','-']),4)
                fail.assert_called_once(); silence.assert_called_once_with(self.stdout)

    def test_diagnostic_failure_retains_io_status(self):
        with patch.object(cli,'execute_magic_balance',side_effect=MagicBalanceGenerationError('req')), \
                patch.object(self.stderr.buffer,'write',side_effect=OSError('closed')):
            self.assertEqual(cli.main(['balance-magic','-']),4)
        self.assertEqual(json.loads(self.stdout.buffer.getvalue())['error']['code'],'generation_failed')

    def test_interrupts_are_not_encoded(self):
        for kind in (KeyboardInterrupt,SystemExit):
            self.stdin.buffer.seek(0)
            with patch.object(cli,'execute_magic_balance',side_effect=kind()):
                with self.assertRaises(kind): cli.main(['balance-magic','-'])
        self.assertEqual(self.stdout.buffer.getvalue(),b'')

    def test_error_encoder_failure_propagates_without_output(self):
        with patch.object(cli, 'execute_magic_balance', side_effect=MagicBalanceGenerationError('request')), \
                patch.object(cli, 'encode_magic_balance_error', side_effect=ValueError('encoder failed')):
            with self.assertRaisesRegex(ValueError, 'encoder failed'):
                cli.main(['balance-magic', '-'])
        self.assertEqual(self.stdout.buffer.getvalue(), b'')
        self.assertEqual(self.stderr.buffer.getvalue(), b'')

    def test_closed_python_streams_return_io_status(self):
        for name in ('stdin', 'stdout', 'stderr'):
            with self.subTest(stream=name):
                closed = io.TextIOWrapper(io.BytesIO()); closed.close()
                self.stdin.buffer.seek(0)
                with patch.object(cli.sys, name, closed), \
                        patch.object(cli, 'execute_magic_balance', side_effect=MagicBalanceGenerationError('request')):
                    self.assertEqual(cli.main(['balance-magic', '-']), 4)

    def test_failed_diagnostic_flush_returns_io_status(self):
        with patch.object(cli, 'execute_magic_balance', side_effect=MagicBalanceExecutionError('request')), \
                patch.object(self.stderr.buffer, 'flush', side_effect=OSError('flush failed')) as failed:
            self.assertEqual(cli.main(['balance-magic', '-']), 4)
        failed.assert_called_once()
        self.assertEqual(json.loads(self.stdout.buffer.getvalue())['kind'], 'magic_balance_error')

    def test_no_other_command_service_is_called(self):
        with ExitStack() as stack:
            others = [stack.enter_context(patch.object(cli, name)) for name in (
                'execute_ranged_balance', 'execute_ranged_simulation',
                'execute_melee_balance', 'execute_melee_simulation', 'execute_mixed_balance',
                'execute_mixed_simulation', 'execute_magic_simulation')]
            execute = stack.enter_context(patch.object(cli, 'execute_magic_balance', return_value=self.result))
            self.assertEqual(cli.main(['balance-magic', '-']), 0)
        execute.assert_called_once_with(self.command)
        for other in others:
            other.assert_not_called()


class MagicBalanceErrorEncoderTests(unittest.TestCase):
    def test_typed_errors_keep_exact_nullable_phase_context_and_generic_messages(self):
        from towr.adapters.magic_balance_json import encode_magic_balance_error
        from towr.adapters.magic_json_errors import MagicBalanceInputError
        from towr.adapters.magic_json_schema import validate_magic_balance_document
        from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
        cases = (
            (MagicBalanceInputError(Code.INVALID_INPUT, 'invalid window', path='/evaluation/window', request_id='outer'),
             dict(code='invalid_input', path='/evaluation/window', message='invalid window', candidate_id=None, counts=None, stage_index=None)),
            (MagicBalanceGenerationError('outer','candidate',(1,0)),
             dict(code='generation_failed', path='/generation', message='Magic balance candidate generation failed', candidate_id='candidate', counts=[1,0], stage_index=None)),
            (MagicBalanceExecutionError('outer',1,'candidate'),
             dict(code='evaluation_failed', path='/evaluation', message='Magic balance evaluation failed', candidate_id='candidate', counts=None, stage_index=1)),
            (MagicBalanceGenerationError('outer'),
             dict(code='generation_failed', path='/generation', message='Magic balance candidate generation failed', candidate_id=None, counts=None, stage_index=None)),
            (MagicBalanceExecutionError('outer'),
             dict(code='evaluation_failed', path='/evaluation', message='Magic balance evaluation failed', candidate_id=None, counts=None, stage_index=None)),
        )
        for error,expected in cases:
            with self.subTest(code=expected['code'], context=expected['candidate_id']):
                if not isinstance(error, MagicBalanceInputError):
                    error.args = ('private application details',)
                    error.__cause__ = OSError('private worker details')
                    error.__cause__.add_note('private worker note')
                    error.add_note('private application note')
                encoded = encode_magic_balance_error(error)
                actual = json.loads(encoded)
                validate_magic_balance_document(actual,'error')
                self.assertEqual(actual, dict(schema_version='1',kind='magic_balance_error',request_id='outer',error=expected))
                self.assertTrue(encoded.endswith('\n'))
                self.assertNotIn('private', encoded)

    def test_input_codes_escape_surrogates_and_preserve_nullable_request_identity(self):
        from towr.adapters.magic_balance_json import encode_magic_balance_error
        from towr.adapters.magic_json_errors import MagicBalanceInputError
        from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
        for code in Code:
            error = MagicBalanceInputError(code,'invalid '+chr(0xD800),path='/a~1b/~0')
            text=encode_magic_balance_error(error)
            text.encode('utf-8')
            actual=json.loads(text)
            self.assertIsNone(actual['request_id'])
            self.assertEqual(actual['error'],dict(code=code.value,path='/a~1b/~0',message=str(error),candidate_id=None,counts=None,stage_index=None))

    def test_encoder_refuses_foreign_families_without_execution(self):
        from towr.adapters.magic_balance_json import encode_magic_balance_error
        from towr.adapters.magic_json_errors import MagicSimulationInputError
        from towr.adapters.mixed_json_errors import MixedBalanceInputError
        from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
        from towr.application.magic_candidate_generation_errors import MagicCandidateGenerationError
        from towr.application.magic_staged_evaluation_errors import MagicStagedEvaluationError
        from towr.application.magic_simulation_errors import MagicSimulationExecutionError
        from towr.application.mixed_balance_errors import MixedBalanceGenerationError,MixedBalanceExecutionError
        errors=(None,ValueError('raw'),KeyboardInterrupt(),MagicSimulationInputError(Code.INVALID_INPUT,'other'),
                MagicSimulationExecutionError('other'),MixedBalanceInputError(Code.INVALID_INPUT,'other'),
                MixedBalanceGenerationError('other'),MixedBalanceExecutionError('other'),
                MagicCandidateGenerationError('candidate',(1,)),MagicStagedEvaluationError(1,'candidate'))
        for error in errors:
            with self.subTest(type=type(error)),self.assertRaises(TypeError):
                encode_magic_balance_error(error)
