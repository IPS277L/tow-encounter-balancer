import io
import json
import unittest
from unittest.mock import patch

from tests.unit.test_m6_melee_json import EXAMPLES
from towr import cli
from towr.application.melee_simulation_errors import MeleeSimulationExecutionError


class M6MeleeCliTests(unittest.TestCase):
    def setUp(self):
        self.stdin = io.TextIOWrapper(io.BytesIO((EXAMPLES / "melee-simulation-v1.request.json").read_bytes()))
        self.stdout = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
        self.stderr = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
        for name in ("stdin", "stdout", "stderr"):
            stream = getattr(self, name)
            self.addCleanup(stream.close)
            self.enterContext(patch.object(cli.sys, name, stream))

    def test_execution_error_has_its_own_status_envelope_and_diagnostic(self):
        error = MeleeSimulationExecutionError("request")
        error.__cause__ = RuntimeError("private cause")
        with patch.object(cli, "execute_melee_simulation", side_effect=error) as service:
            self.assertEqual(cli.main(["simulate-melee", "-"]), 3)
        service.assert_called_once()
        actual = json.loads(self.stdout.buffer.getvalue())
        self.assertEqual(actual["error"]["code"], "execution_failed")
        self.assertEqual(actual["request_id"], "request")
        self.assertNotIn("trials", actual)
        self.assertNotIn("summary", actual)
        self.assertIn(b"execution_failed", self.stderr.buffer.getvalue())
        self.assertNotIn(b"private cause", self.stderr.buffer.getvalue())

    def test_input_io_failure_does_not_parse_or_execute(self):
        with patch.object(cli.Path, "read_bytes", side_effect=PermissionError("denied")), \
                patch.object(cli, "parse_melee_simulation_request") as parse, \
                patch.object(cli, "execute_melee_simulation") as service:
            self.assertEqual(cli.main(["simulate-melee", "file.json"]), 4)
            parse.assert_not_called()
            service.assert_not_called()
        self.assertEqual(self.stdout.buffer.getvalue(), b"")
        self.assertIn(b"input I/O error", self.stderr.buffer.getvalue())

    def test_stdin_io_failure_is_not_invalid_json(self):
        with patch.object(self.stdin.buffer, "read", side_effect=OSError("read failed")), \
                patch.object(cli, "parse_melee_simulation_request") as parse:
            self.assertEqual(cli.main(["simulate-melee", "-"]), 4)
            parse.assert_not_called()
        self.assertEqual(self.stdout.buffer.getvalue(), b"")

    def test_unexpected_encoder_error_propagates_before_output(self):
        with patch.object(cli, "encode_melee_simulation_result", side_effect=ValueError("broken encoder")):
            with self.assertRaisesRegex(ValueError, "broken encoder"):
                cli.main(["simulate-melee", "-"])
        self.assertEqual(self.stdout.buffer.getvalue(), b"")
        self.assertEqual(self.stderr.buffer.getvalue(), b"")

    def test_write_or_flush_failure_returns_io_status_without_retry(self):
        for method in ("write", "flush"):
            with self.subTest(method=method), \
                    patch.object(self.stdout.buffer, method, side_effect=BrokenPipeError("closed")) as failed, \
                    patch.object(cli, "_silence_failed_stream") as silence:
                self.stdin.buffer.seek(0)
                self.assertEqual(cli.main(["simulate-melee", "-"]), 4)
                failed.assert_called_once()
                silence.assert_called_once_with(self.stdout)
        self.assertIn(b"output I/O error", self.stderr.buffer.getvalue())

    def test_failed_diagnostic_returns_io_status(self):
        self.stdin.buffer.seek(0)
        self.stdin.buffer.truncate(0)
        with patch.object(self.stderr.buffer, "write", side_effect=OSError("stderr closed")):
            self.assertEqual(cli.main(["simulate-melee", "-"]), 4)
        self.assertEqual(json.loads(self.stdout.buffer.getvalue())["error"]["code"], "invalid_json")

    def test_interrupt_is_not_reclassified_or_written_as_json(self):
        with patch.object(cli, "execute_melee_simulation", side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                cli.main(["simulate-melee", "-"])
        self.assertEqual(self.stdout.buffer.getvalue(), b"")

    def test_typed_encoder_error_is_not_reclassified_as_execution_failure(self):
        error = MeleeSimulationExecutionError("request")
        with patch.object(cli, "encode_melee_simulation_result", side_effect=error):
            with self.assertRaises(MeleeSimulationExecutionError) as caught:
                cli.main(["simulate-melee", "-"])
        self.assertIs(caught.exception, error)
        self.assertEqual(self.stdout.buffer.getvalue(), b"")
        self.assertEqual(self.stderr.buffer.getvalue(), b"")

    def test_error_encoder_failure_propagates_without_partial_output(self):
        self.stdin.buffer.seek(0)
        self.stdin.buffer.truncate(0)
        with patch.object(cli, "encode_melee_simulation_error", side_effect=ValueError("encoder failed")):
            with self.assertRaisesRegex(ValueError, "encoder failed"):
                cli.main(["simulate-melee", "-"])
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
                    self.assertEqual(cli.main(["simulate-melee", "-"]), 4)

    def test_failed_diagnostic_flush_returns_io_status(self):
        self.stdin.buffer.seek(0)
        self.stdin.buffer.truncate(0)
        with patch.object(self.stderr.buffer, "flush", side_effect=OSError("flush failed")) as failed:
            self.assertEqual(cli.main(["simulate-melee", "-"]), 4)
        failed.assert_called_once()
        self.assertEqual(json.loads(self.stdout.buffer.getvalue())["kind"], "melee_simulation_error")

    def test_input_error_does_not_execute_any_backend(self):
        self.stdin.buffer.seek(0)
        self.stdin.buffer.truncate(0)
        with patch.object(cli, "execute_melee_simulation") as melee, \
                patch.object(cli, "execute_ranged_simulation") as ranged, \
                patch.object(cli, "execute_ranged_balance") as balance:
            self.assertEqual(cli.main(["simulate-melee", "-"]), 2)
            melee.assert_not_called()
            ranged.assert_not_called()
            balance.assert_not_called()

