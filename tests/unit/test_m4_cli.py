import io
import json
import unittest
from unittest.mock import patch

from tests.unit.test_m4_ranged_json import EXAMPLES
from towr import cli
from towr.application.ranged_simulation_errors import RangedSimulationExecutionError


class M4CliTests(unittest.TestCase):
    def setUp(self):
        self.stdin = io.TextIOWrapper(io.BytesIO((EXAMPLES / "ranged-v1.request.json").read_bytes()))
        self.stdout = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
        self.stderr = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
        for name in ("stdin", "stdout", "stderr"):
            stream = getattr(self, name)
            self.addCleanup(stream.close)
            self.enterContext(patch.object(cli.sys, name, stream))

    def test_execution_error_has_its_own_status_envelope_and_diagnostic(self):
        error = RangedSimulationExecutionError("request")
        error.__cause__ = RuntimeError("private cause")
        with patch.object(cli, "execute_ranged_simulation", side_effect=error) as service:
            self.assertEqual(cli.main(["simulate", "-"]), 3)
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
                patch.object(cli, "parse_ranged_simulation_request") as parse, \
                patch.object(cli, "execute_ranged_simulation") as service:
            self.assertEqual(cli.main(["simulate", "file.json"]), 4)
            parse.assert_not_called()
            service.assert_not_called()
        self.assertEqual(self.stdout.buffer.getvalue(), b"")
        self.assertIn(b"input I/O error", self.stderr.buffer.getvalue())

    def test_stdin_io_failure_is_not_invalid_json(self):
        with patch.object(self.stdin.buffer, "read", side_effect=OSError("read failed")), \
                patch.object(cli, "parse_ranged_simulation_request") as parse:
            self.assertEqual(cli.main(["simulate", "-"]), 4)
            parse.assert_not_called()
        self.assertEqual(self.stdout.buffer.getvalue(), b"")

    def test_unexpected_encoder_error_propagates_before_output(self):
        with patch.object(cli, "encode_ranged_simulation_result", side_effect=ValueError("broken encoder")):
            with self.assertRaisesRegex(ValueError, "broken encoder"):
                cli.main(["simulate", "-"])
        self.assertEqual(self.stdout.buffer.getvalue(), b"")
        self.assertEqual(self.stderr.buffer.getvalue(), b"")

    def test_write_or_flush_failure_returns_io_status_without_retry(self):
        for method in ("write", "flush"):
            with self.subTest(method=method), \
                    patch.object(self.stdout.buffer, method, side_effect=BrokenPipeError("closed")) as failed, \
                    patch.object(cli, "_silence_failed_stream") as silence:
                self.stdin.buffer.seek(0)
                self.assertEqual(cli.main(["simulate", "-"]), 4)
                failed.assert_called_once()
                silence.assert_called_once_with(self.stdout)
        self.assertIn(b"output I/O error", self.stderr.buffer.getvalue())

    def test_failed_diagnostic_returns_io_status(self):
        self.stdin.buffer.seek(0)
        self.stdin.buffer.truncate(0)
        with patch.object(self.stderr.buffer, "write", side_effect=OSError("stderr closed")):
            self.assertEqual(cli.main(["simulate", "-"]), 4)
        self.assertEqual(json.loads(self.stdout.buffer.getvalue())["error"]["code"], "invalid_json")

    def test_interrupt_is_not_reclassified_or_written_as_json(self):
        with patch.object(cli, "execute_ranged_simulation", side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                cli.main(["simulate", "-"])
        self.assertEqual(self.stdout.buffer.getvalue(), b"")

