import io
import json
import unittest
from unittest.mock import patch

from tests.unit.test_m7_mixed_json import EXAMPLES
from towr import cli
from towr.application.mixed_simulation_errors import MixedSimulationExecutionError


class M7MixedCliTests(unittest.TestCase):
    def setUp(self):
        self.stdin = io.TextIOWrapper(io.BytesIO((EXAMPLES / "mixed-simulation-v1.request.json").read_bytes()))
        self.stdout = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
        self.stderr = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
        for name in ("stdin", "stdout", "stderr"):
            stream = getattr(self, name)
            self.addCleanup(stream.close)
            self.enterContext(patch.object(cli.sys, name, stream))

    def test_all_complete_outcomes_are_success_without_reclassification(self):
        from tests.unit.test_m7_mixed_json import document
        from towr.simulation.npc_mixed_models import NpcMixedOutcomeCounts
        from towr.simulation.npc_mixed_summary_models import NpcMixedSimulationSummary
        data = document()
        command = cli.parse_mixed_simulation_request(json.dumps(data))
        trials = command.request.trials
        for index, outcome in enumerate(("objective_achieved", "side_defeated", "round_limit", "unsupported_path")):
            counts = tuple(trials if n == index else 0 for n in range(4))
            summary = NpcMixedSimulationSummary(command.request, NpcMixedOutcomeCounts(*counts),
                trials if index < 2 else 0, trials * (command.request.scenario.initial.max_rounds if index == 2 else 1))
            self.stdin.buffer.seek(0)
            self.stdout.buffer.seek(0)
            self.stdout.buffer.truncate(0)
            with self.subTest(outcome=outcome), patch.object(cli, "execute_mixed_simulation", return_value=summary):
                self.assertEqual(cli.main(["simulate-mixed", "-"]), 0)
            result = json.loads(self.stdout.buffer.getvalue())
            self.assertEqual(result["kind"], "npc_mixed_simulation_result")
            self.assertEqual(result["summary"]["outcome_counts"][outcome], trials)
            self.assertEqual(self.stderr.buffer.getvalue(), b"")

    def test_execution_error_has_its_own_status_envelope_and_diagnostic(self):
        error = MixedSimulationExecutionError("request")
        error.__cause__ = RuntimeError("private cause")
        with patch.object(cli, "execute_mixed_simulation", side_effect=error) as service:
            self.assertEqual(cli.main(["simulate-mixed", "-"]), 3)
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
                patch.object(cli, "parse_mixed_simulation_request") as parse, \
                patch.object(cli, "execute_mixed_simulation") as service:
            self.assertEqual(cli.main(["simulate-mixed", "file.json"]), 4)
            parse.assert_not_called()
            service.assert_not_called()
        self.assertEqual(self.stdout.buffer.getvalue(), b"")
        self.assertIn(b"input I/O error", self.stderr.buffer.getvalue())

    def test_stdin_io_failure_is_not_invalid_json(self):
        with patch.object(self.stdin.buffer, "read", side_effect=OSError("read failed")), \
                patch.object(cli, "parse_mixed_simulation_request") as parse:
            self.assertEqual(cli.main(["simulate-mixed", "-"]), 4)
            parse.assert_not_called()
        self.assertEqual(self.stdout.buffer.getvalue(), b"")

    def test_unexpected_encoder_error_propagates_before_output(self):
        with patch.object(cli, "encode_mixed_simulation_result", side_effect=ValueError("broken encoder")):
            with self.assertRaisesRegex(ValueError, "broken encoder"):
                cli.main(["simulate-mixed", "-"])
        self.assertEqual(self.stdout.buffer.getvalue(), b"")
        self.assertEqual(self.stderr.buffer.getvalue(), b"")

    def test_write_or_flush_failure_returns_io_status_without_retry(self):
        for method in ("write", "flush"):
            with self.subTest(method=method), \
                    patch.object(self.stdout.buffer, method, side_effect=BrokenPipeError("closed")) as failed, \
                    patch.object(cli, "_silence_failed_stream") as silence:
                self.stdin.buffer.seek(0)
                self.assertEqual(cli.main(["simulate-mixed", "-"]), 4)
                failed.assert_called_once()
                silence.assert_called_once_with(self.stdout)
        self.assertIn(b"output I/O error", self.stderr.buffer.getvalue())

    def test_failed_diagnostic_returns_io_status(self):
        self.stdin.buffer.seek(0)
        self.stdin.buffer.truncate(0)
        with patch.object(self.stderr.buffer, "write", side_effect=OSError("stderr closed")):
            self.assertEqual(cli.main(["simulate-mixed", "-"]), 4)
        self.assertEqual(json.loads(self.stdout.buffer.getvalue())["error"]["code"], "invalid_json")

    def test_interrupt_is_not_reclassified_or_written_as_json(self):
        with patch.object(cli, "execute_mixed_simulation", side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                cli.main(["simulate-mixed", "-"])
        self.assertEqual(self.stdout.buffer.getvalue(), b"")

    def test_typed_encoder_error_is_not_reclassified_as_execution_failure(self):
        error = MixedSimulationExecutionError("request")
        with patch.object(cli, "encode_mixed_simulation_result", side_effect=error):
            with self.assertRaises(MixedSimulationExecutionError) as caught:
                cli.main(["simulate-mixed", "-"])
        self.assertIs(caught.exception, error)
        self.assertEqual(self.stdout.buffer.getvalue(), b"")
        self.assertEqual(self.stderr.buffer.getvalue(), b"")

    def test_error_encoder_failure_propagates_without_partial_output(self):
        self.stdin.buffer.seek(0)
        self.stdin.buffer.truncate(0)
        with patch.object(cli, "encode_mixed_simulation_error", side_effect=ValueError("encoder failed")):
            with self.assertRaisesRegex(ValueError, "encoder failed"):
                cli.main(["simulate-mixed", "-"])
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
                    self.assertEqual(cli.main(["simulate-mixed", "-"]), 4)

    def test_failed_diagnostic_flush_returns_io_status(self):
        self.stdin.buffer.seek(0)
        self.stdin.buffer.truncate(0)
        with patch.object(self.stderr.buffer, "flush", side_effect=OSError("flush failed")) as failed:
            self.assertEqual(cli.main(["simulate-mixed", "-"]), 4)
        failed.assert_called_once()
        self.assertEqual(json.loads(self.stdout.buffer.getvalue())["kind"], "mixed_simulation_error")

    def test_input_error_does_not_execute_any_backend(self):
        self.stdin.buffer.seek(0)
        self.stdin.buffer.truncate(0)
        with patch.object(cli, "execute_mixed_simulation") as mixed, \
                patch.object(cli, "execute_ranged_simulation") as ranged, \
                patch.object(cli, "execute_ranged_balance") as balance:
            self.assertEqual(cli.main(["simulate-mixed", "-"]), 2)
            mixed.assert_not_called()
            ranged.assert_not_called()
            balance.assert_not_called()

