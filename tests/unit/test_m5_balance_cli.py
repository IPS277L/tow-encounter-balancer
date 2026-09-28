import io
import json
import unittest
from unittest.mock import patch

from tests.unit.test_m5_ranged_balance_json import document, make_result
from towr import cli
from towr.adapters.ranged_balance_json import parse_ranged_balance_request
from towr.application.ranged_balance_errors import RangedBalanceGenerationError, RangedBalanceExecutionError


class M5BalanceCliTests(unittest.TestCase):
    def setUp(self):
        self.command = parse_ranged_balance_request(json.dumps(document()))
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
            with patch.object(cli,'execute_ranged_balance',return_value=result) as service:
                self.assertEqual(cli.main(['balance','-']),0)
            service.assert_called_once_with(self.command)
            actual=json.loads(self.stdout.buffer.getvalue())
            self.assertEqual(actual['status'],result.evaluation_result.status.value)
            self.assertEqual(self.stderr.buffer.getvalue(),b'')

    def test_generation_and_execution_errors_have_phase_context_without_partial_output(self):
        for error,code in ((RangedBalanceGenerationError('req','candidate',(1,0)),'generation_failed'),
                           (RangedBalanceExecutionError('req',1,'candidate'),'execution_failed')):
            self.stdin.buffer.seek(0); self.stdout.buffer.seek(0); self.stdout.buffer.truncate()
            error.__cause__=RuntimeError('private cause')
            with patch.object(cli,'execute_ranged_balance',side_effect=error) as service:
                self.assertEqual(cli.main(['balance','-']),3)
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
                    patch.object(cli,'parse_ranged_balance_request') as parse, \
                    patch.object(cli,'execute_ranged_balance') as execute:
                self.assertEqual(cli.main(['balance','file.json' if name=='read_bytes' else '-']),4)
            parse.assert_not_called(); execute.assert_not_called()
            self.assertEqual(self.stdout.buffer.getvalue(),b'')

    def test_input_failure_never_reaches_service(self):
        self.stdin.buffer.seek(0); self.stdin.buffer.truncate(); self.stdin.buffer.write(b'{'); self.stdin.buffer.seek(0)
        with patch.object(cli,'execute_ranged_balance') as execute:
            self.assertEqual(cli.main(['balance','-']),2)
        execute.assert_not_called()
        self.assertEqual(json.loads(self.stdout.buffer.getvalue())['error']['code'],'invalid_json')

    def test_encoder_exceptions_including_typed_failures_propagate_before_stdout(self):
        for error in (ValueError('bug'),RangedBalanceExecutionError('request')):
            self.stdin.buffer.seek(0)
            with patch.object(cli,'execute_ranged_balance',return_value=self.result), \
                    patch.object(cli,'encode_ranged_balance_result',side_effect=error):
                with self.assertRaises(type(error)) as caught: cli.main(['balance','-'])
            self.assertIs(caught.exception,error)
        self.assertEqual(self.stdout.buffer.getvalue(),b''); self.assertEqual(self.stderr.buffer.getvalue(),b'')

    def test_write_flush_failure_is_io_without_second_json_or_shutdown_flush(self):
        for method in ('write','flush'):
            self.stdin.buffer.seek(0)
            with patch.object(cli,'execute_ranged_balance',return_value=self.result), \
                    patch.object(self.stdout.buffer,method,side_effect=BrokenPipeError('closed')) as fail, \
                    patch.object(cli,'_silence_failed_stream') as silence:
                self.assertEqual(cli.main(['balance','-']),4)
                fail.assert_called_once(); silence.assert_called_once_with(self.stdout)

    def test_diagnostic_failure_retains_io_status(self):
        with patch.object(cli,'execute_ranged_balance',side_effect=RangedBalanceGenerationError('req')), \
                patch.object(self.stderr.buffer,'write',side_effect=OSError('closed')):
            self.assertEqual(cli.main(['balance','-']),4)
        self.assertEqual(json.loads(self.stdout.buffer.getvalue())['error']['code'],'generation_failed')

    def test_interrupts_are_not_encoded(self):
        for kind in (KeyboardInterrupt,SystemExit):
            self.stdin.buffer.seek(0)
            with patch.object(cli,'execute_ranged_balance',side_effect=kind()):
                with self.assertRaises(kind): cli.main(['balance','-'])
        self.assertEqual(self.stdout.buffer.getvalue(),b'')
