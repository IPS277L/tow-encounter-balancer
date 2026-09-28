import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.unit.test_m4_ranged_json import document, EXAMPLES
from towr.adapters.ranged_json_schema import validate_ranged_document


ROOT = Path(__file__).resolve().parents[2]


def environment():
    # Exercise byte I/O even when the host's Python text streams use ASCII.
    return dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONIOENCODING="ascii")


def invoke(*args, data=None, cwd=ROOT):
    return subprocess.run([sys.executable, "-m", "towr", *args], input=data,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          cwd=cwd, env=environment(), timeout=45)


class M4CliIntegrationTests(unittest.TestCase):
    def test_file_input_from_unrelated_cwd_matches_documented_result(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            path.write_bytes((EXAMPLES / "ranged-v1.request.json").read_bytes())
            completed = invoke("simulate", str(path), cwd=directory)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, b"")
        self.assertTrue(completed.stdout.endswith(b"\n"))
        actual = json.loads(completed.stdout.decode("utf-8"))
        expected = json.loads((EXAMPLES / "ranged-v1.result.json").read_text(encoding="utf-8"))
        expected["runtime"] = actual["runtime"]
        self.assertEqual(actual, expected)
        validate_ranged_document(actual, "result")

    def test_unicode_stdin_and_real_spawn_match_sequential(self):
        data = document()
        data["request_id"] = "перестрелка-雪"
        sequential = invoke("simulate", "-", data=json.dumps(data, ensure_ascii=False).encode("utf-8"))
        self.assertEqual(sequential.returncode, 0, sequential.stderr)
        data["execution"] = {"mode": "process", "workers": 2, "batch_size": 1}
        process = invoke("simulate", "-", data=json.dumps(data, ensure_ascii=False).encode("utf-8"))
        self.assertEqual(process.returncode, 0, process.stderr)
        for completed in (sequential, process):
            self.assertEqual(completed.stderr, b"")
            self.assertIn("перестрелка-雪".encode("utf-8"), completed.stdout)
        seq_doc, proc_doc = (json.loads(item.stdout.decode("utf-8")) for item in (sequential, process))
        validate_ranged_document(proc_doc, "result")
        self.assertEqual(proc_doc["request"], data)
        self.assertEqual(proc_doc["trials"], seq_doc["trials"])
        self.assertEqual(proc_doc["summary"], seq_doc["summary"])

    def test_invalid_json_version_and_admission_have_input_exit_code(self):
        invalid = document()
        invalid["scenario"]["facts"]["targets_aware"] = False
        cases = ((b"{", "invalid_json"), (b"\xff", "invalid_json"),
                 (json.dumps(dict(document(), schema_version="2")).encode(), "unsupported_version"),
                 (json.dumps(invalid).encode(), "invalid_input"))
        for raw, code in cases:
            with self.subTest(code=code, raw=raw[:20]):
                completed = invoke("simulate", "-", data=raw)
                self.assertEqual(completed.returncode, 2, completed.stderr)
                actual = json.loads(completed.stdout.decode("utf-8"))
                validate_ranged_document(actual, "error")
                self.assertEqual(actual["error"]["code"], code)
                self.assertNotIn("trials", actual)
                self.assertIn(code.encode(), completed.stderr)
                self.assertNotIn(b"Traceback", completed.stderr)

    def test_missing_file_and_directory_are_io_errors_without_json(self):
        with tempfile.TemporaryDirectory() as directory:
            for path in (Path(directory) / "missing.json", Path(directory)):
                with self.subTest(path=path):
                    completed = invoke("simulate", str(path))
                    self.assertEqual(completed.returncode, 4, completed.stderr)
                    self.assertEqual(completed.stdout, b"")
                    self.assertIn(b"input I/O error", completed.stderr)
                    self.assertNotIn(b"Traceback", completed.stderr)

    def test_help_and_usage_errors_do_not_emit_simulation_json(self):
        for args in (("--help",), ("simulate", "--help")):
            completed = invoke(*args)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn(b"usage:", completed.stdout)
            self.assertEqual(completed.stderr, b"")
        for args in ((), ("simulate",), ("unknown",), ("simulate", "-", "--workers", "2")):
            completed = invoke(*args, data=b"")
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(completed.stdout, b"")
            self.assertIn(b"usage:", completed.stderr)

    def test_closed_stdout_pipe_returns_io_status_without_shutdown_traceback(self):
        with subprocess.Popen([sys.executable, "-m", "towr", "simulate", "-"],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              cwd=ROOT, env=environment()) as process:
            process.stdout.close()
            process.stdout = None
            _, stderr = process.communicate(b"{", timeout=45)
        self.assertEqual(process.returncode, 4, stderr)
        self.assertIn(b"output I/O error", stderr)
        self.assertNotIn(b"Traceback", stderr)
        self.assertNotIn(b"Exception ignored", stderr)

    def test_closed_stderr_pipe_preserves_io_exit_code(self):
        with subprocess.Popen([sys.executable, "-m", "towr", "simulate", "-"],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              cwd=ROOT, env=environment()) as process:
            process.stderr.close()
            process.stderr = None
            stdout, _ = process.communicate(b"{", timeout=45)
        self.assertEqual(process.returncode, 4)
        self.assertEqual(json.loads(stdout)["error"]["code"], "invalid_json")

    def test_pool_failure_in_subprocess_has_execution_status_and_envelope(self):
        # Inject at the pool boundary only; no test-only CLI flag or wire option.
        script = (
            "from unittest.mock import patch\n"
            "from towr.cli import main\n"
            "with patch('towr.simulation.npc_ranged_parallel.ProcessPoolExecutor', "
            "side_effect=OSError('pool unavailable')):\n"
            "    raise SystemExit(main(['simulate', '-']))\n"
        )
        data = document()
        data["execution"] = {"mode": "process", "workers": 2, "batch_size": 1}
        completed = subprocess.run([sys.executable, "-c", script], input=json.dumps(data).encode(),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   cwd=ROOT, env=environment(), timeout=45)
        self.assertEqual(completed.returncode, 3, completed.stderr)
        actual = json.loads(completed.stdout)
        validate_ranged_document(actual, "error")
        self.assertEqual(actual["request_id"], data["request_id"])
        self.assertEqual(actual["error"]["code"], "execution_failed")
        self.assertNotIn("trials", actual)
        self.assertNotIn("summary", actual)
        self.assertIn(b"execution_failed", completed.stderr)
        self.assertNotIn(b"Traceback", completed.stderr)
