"""Magic CLI boundaries share byte I/O while keeping their own error family."""
import io
import json
import unittest
from unittest.mock import patch

from tests.unit.test_m8_magic_json import EXAMPLES
from towr import cli
from towr.application.magic_simulation_errors import MagicSimulationExecutionError


class M8MagicCliTests(unittest.TestCase):
    def setUp(self):
        self.stdin = io.TextIOWrapper(io.BytesIO((EXAMPLES / "magic-simulation-v1.request.json").read_bytes()))
        self.stdout = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
        self.stderr = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
        for name in ("stdin", "stdout", "stderr"):
            stream = getattr(self, name)
            self.addCleanup(stream.close)
            self.enterContext(patch.object(cli.sys, name, stream))

    def test_all_complete_outcomes_are_success_without_reclassification(self):
        from tests.unit.test_m8_magic_json import document
        from towr.simulation.npc_magic_models import NpcMagicOutcomeCounts
        from towr.simulation.npc_magic_summary_models import NpcMagicSimulationSummary
        data = document()
        command = cli.parse_magic_simulation_request(json.dumps(data))
        trials = command.request.trials
        for index, outcome in enumerate(("objective_achieved", "perspective_defeated", "round_limit_reached", "unsupported_path")):
            counts = tuple(trials if n == index else 0 for n in range(4))
            rounds = trials * command.request.scenario.max_rounds if index == 2 else trials
            summary = NpcMagicSimulationSummary(command.request, NpcMagicOutcomeCounts(*counts),
                rounds if index == 2 else trials if index < 2 else 0, rounds, rounds if index == 2 else 0)
            self.stdin.buffer.seek(0)
            self.stdout.buffer.seek(0)
            self.stdout.buffer.truncate(0)
            with self.subTest(outcome=outcome), patch.object(cli, "execute_magic_simulation", return_value=summary):
                self.assertEqual(cli.main(["simulate-magic", "-"]), 0)
            result = json.loads(self.stdout.buffer.getvalue())
            self.assertEqual(result["kind"], "npc_magic_simulation_result")
            self.assertEqual(result["summary"]["outcome_counts"][outcome], trials)
            self.assertEqual(self.stderr.buffer.getvalue(), b"")

    def test_execution_error_has_its_own_status_envelope_and_diagnostic(self):
        error = MagicSimulationExecutionError("request")
        error.__cause__ = RuntimeError("private cause")
        with patch.object(cli, "execute_magic_simulation", side_effect=error) as service:
            self.assertEqual(cli.main(["simulate-magic", "-"]), 3)
        service.assert_called_once()
        actual = json.loads(self.stdout.buffer.getvalue())
        self.assertEqual(actual["error"]["code"], "simulation_failed")
        self.assertEqual(actual["request_id"], "request")
        self.assertNotIn("trials", actual)
        self.assertNotIn("summary", actual)
        self.assertIn(b"simulation_failed", self.stderr.buffer.getvalue())
        self.assertNotIn(b"private cause", self.stderr.buffer.getvalue())

    def test_input_io_failure_does_not_parse_or_execute(self):
        with patch.object(cli.Path, "read_bytes", side_effect=PermissionError("denied")), \
                patch.object(cli, "parse_magic_simulation_request") as parse, \
                patch.object(cli, "execute_magic_simulation") as service:
            self.assertEqual(cli.main(["simulate-magic", "file.json"]), 4)
            parse.assert_not_called()
            service.assert_not_called()
        self.assertEqual(self.stdout.buffer.getvalue(), b"")
        self.assertIn(b"input I/O error", self.stderr.buffer.getvalue())

    def test_stdin_io_failure_is_not_invalid_json(self):
        with patch.object(self.stdin.buffer, "read", side_effect=OSError("read failed")), \
                patch.object(cli, "parse_magic_simulation_request") as parse:
            self.assertEqual(cli.main(["simulate-magic", "-"]), 4)
            parse.assert_not_called()
        self.assertEqual(self.stdout.buffer.getvalue(), b"")

    def test_unexpected_encoder_error_propagates_before_output(self):
        with patch.object(cli, "encode_magic_simulation_result", side_effect=ValueError("broken encoder")):
            with self.assertRaisesRegex(ValueError, "broken encoder"):
                cli.main(["simulate-magic", "-"])
        self.assertEqual(self.stdout.buffer.getvalue(), b"")
        self.assertEqual(self.stderr.buffer.getvalue(), b"")

    def test_write_or_flush_failure_returns_io_status_without_retry(self):
        for method in ("write", "flush"):
            with self.subTest(method=method), \
                    patch.object(self.stdout.buffer, method, side_effect=BrokenPipeError("closed")) as failed, \
                    patch.object(cli, "_silence_failed_stream") as silence:
                self.stdin.buffer.seek(0)
                self.assertEqual(cli.main(["simulate-magic", "-"]), 4)
                failed.assert_called_once()
                silence.assert_called_once_with(self.stdout)
        self.assertIn(b"output I/O error", self.stderr.buffer.getvalue())

    def test_failed_diagnostic_returns_io_status(self):
        self.stdin.buffer.seek(0)
        self.stdin.buffer.truncate(0)
        with patch.object(self.stderr.buffer, "write", side_effect=OSError("stderr closed")):
            self.assertEqual(cli.main(["simulate-magic", "-"]), 4)
        self.assertEqual(json.loads(self.stdout.buffer.getvalue())["error"]["code"], "invalid_json")

    def test_interrupt_is_not_reclassified_or_written_as_json(self):
        with patch.object(cli, "execute_magic_simulation", side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                cli.main(["simulate-magic", "-"])
        self.assertEqual(self.stdout.buffer.getvalue(), b"")

    def test_typed_encoder_error_is_not_reclassified_as_execution_failure(self):
        from towr.adapters.magic_json_errors import MagicSimulationInputError
        from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
        errors = (MagicSimulationExecutionError("request"),
                  MagicSimulationInputError(Code.INVALID_INPUT, "encoder bug"))
        for error in errors:
            self.stdin.buffer.seek(0)
            with self.subTest(error=type(error)), patch.object(cli, "encode_magic_simulation_result", side_effect=error):
                with self.assertRaises(type(error)) as caught:
                    cli.main(["simulate-magic", "-"])
            self.assertIs(caught.exception, error)
            self.assertEqual(self.stdout.buffer.getvalue(), b"")
            self.assertEqual(self.stderr.buffer.getvalue(), b"")

    def test_error_encoder_failure_propagates_without_partial_output(self):
        self.stdin.buffer.seek(0)
        self.stdin.buffer.truncate(0)
        with patch.object(cli, "encode_magic_simulation_error", side_effect=ValueError("encoder failed")):
            with self.assertRaisesRegex(ValueError, "encoder failed"):
                cli.main(["simulate-magic", "-"])
        self.assertEqual(self.stdout.buffer.getvalue(), b"")
        self.assertEqual(self.stderr.buffer.getvalue(), b"")

    def test_closed_python_streams_return_io_status(self):
        for name in ("stdin", "stdout", "stderr"):
            with self.subTest(stream=name):
                closed = io.TextIOWrapper(io.BytesIO())
                closed.close()
                self.stdin.buffer.seek(0)
                if name == "stderr":
                    self.stdin.buffer.truncate(0)
                with patch.object(cli.sys, name, closed):
                    self.assertEqual(cli.main(["simulate-magic", "-"]), 4)

    def test_failed_diagnostic_flush_returns_io_status(self):
        self.stdin.buffer.seek(0)
        self.stdin.buffer.truncate(0)
        with patch.object(self.stderr.buffer, "flush", side_effect=OSError("flush failed")) as failed:
            self.assertEqual(cli.main(["simulate-magic", "-"]), 4)
        failed.assert_called_once()
        self.assertEqual(json.loads(self.stdout.buffer.getvalue())["kind"], "magic_simulation_error")

    def test_input_error_does_not_execute_any_backend(self):
        self.stdin.buffer.seek(0)
        self.stdin.buffer.truncate(0)
        with patch.object(cli, "execute_magic_simulation") as magic, \
                patch.object(cli, "execute_ranged_simulation") as ranged, \
                patch.object(cli, "execute_ranged_balance") as balance:
            self.assertEqual(cli.main(["simulate-magic", "-"]), 2)
            magic.assert_not_called()
            ranged.assert_not_called()
            balance.assert_not_called()


class MagicSimulationErrorEncoderTests(unittest.TestCase):
    def test_input_errors_preserve_code_path_external_id_and_escape_surrogates(self):
        from towr.adapters.magic_json_errors import MagicSimulationInputError
        from towr.adapters.magic_json_schema import validate_magic_simulation_document
        from towr.adapters.magic_simulation_json import encode_magic_simulation_error
        from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
        for code in Code:
            with self.subTest(code=code):
                error = MagicSimulationInputError(code, 'invalid ' + chr(0xD800),
                    path='/scenario/a~1b/~0', request_id='external request')
                encoded = encode_magic_simulation_error(error)
                encoded.encode('utf-8')
                self.assertTrue(encoded.endswith('\n'))
                result = json.loads(encoded)
                validate_magic_simulation_document(result, 'error')
                self.assertEqual(result['request_id'], 'external request')
                self.assertEqual(result['error'], {'code': code.value, 'path': '/scenario/a~1b/~0', 'message': str(error)})

    def test_execution_error_is_generic_and_drops_cause_and_notes(self):
        from towr.adapters.magic_json_schema import validate_magic_simulation_document
        from towr.adapters.magic_simulation_json import encode_magic_simulation_error
        error = MagicSimulationExecutionError('external request')
        error.__cause__ = OSError('private cause')
        error.__cause__.add_note('private worker note')
        error.add_note('private application note')
        encoded = encode_magic_simulation_error(error)
        result = json.loads(encoded)
        validate_magic_simulation_document(result, 'error')
        self.assertEqual(result, {'schema_version': '1', 'kind': 'magic_simulation_error',
            'request_id': 'external request', 'error': {'code': 'simulation_failed', 'path': None,
            'message': 'Magic simulation execution failed'}})
        self.assertNotIn('private', encoded)
        self.assertIsNotNone(error.__cause__)
        self.assertEqual(error.__cause__.__notes__, ['private worker note'])

    def test_error_encoder_rejects_other_families_and_untyped_errors(self):
        from towr.adapters.magic_simulation_json import encode_magic_simulation_error
        from towr.adapters.magic_json_errors import MagicBalanceInputError
        from towr.adapters.mixed_json_errors import MixedSimulationInputError
        from towr.adapters.ranged_json_errors import RangedSimulationInputError, RangedInputErrorCode as Code
        from towr.application.mixed_simulation_errors import MixedSimulationExecutionError
        for error in (ValueError('invalid'), MagicBalanceInputError(Code.INVALID_INPUT, 'balance'),
                      MixedSimulationInputError(Code.INVALID_INPUT, 'mixed'),
                      RangedSimulationInputError(Code.INVALID_INPUT, 'ranged'), MixedSimulationExecutionError('mixed')):
            with self.subTest(error=type(error)), self.assertRaises(TypeError):
                encode_magic_simulation_error(error)
