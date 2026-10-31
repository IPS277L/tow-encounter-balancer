"""Magic service/CLI through UTF-8 subprocesses and real spawn, without presets."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.unit.test_m8_magic_json import document, EXAMPLES
from towr.adapters.magic_json_schema import validate_magic_simulation_document


ROOT = Path(__file__).resolve().parents[2]


def environment():
    # Exercise byte I/O even when the host's Python text streams use ASCII.
    return dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONIOENCODING="ascii")


def invoke(*args, data=None, cwd=ROOT):
    return subprocess.run([sys.executable, "-m", "towr", *args], input=data,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          cwd=cwd, env=environment(), timeout=45)


class M8MagicCliIntegrationTests(unittest.TestCase):
    def test_late_trial_failure_emits_only_generic_error(self):
        script = """
from multiprocessing import active_children
from random import getstate
from unittest.mock import patch
from towr.cli import main
from towr.simulation import npc_magic_simulation as simulation
before, children = getstate(), {c.pid for c in active_children()}
original = simulation.run_npc_magic_trial
completed_indices = []
error = RuntimeError('private late trial failure')
error.add_note('private worker note')
def trial(request, index, **kwargs):
    if index == 1:
        raise error
    record = original(request, index, **kwargs)
    completed_indices.append(record.trial_index)
    return record
with patch.object(simulation, 'run_npc_magic_trial', side_effect=trial) as called, \
     patch('towr.application.magic_simulation_service.run_npc_magic_simulation_parallel',
           side_effect=AssertionError('backend fallback')) as fallback:
    status = main(['simulate-magic', '-'])
    assert called.call_count == 2 and completed_indices == [0]
    fallback.assert_not_called()
    assert getstate() == before and {c.pid for c in active_children()} == children
    raise SystemExit(status)
"""
        completed = subprocess.run([sys.executable, "-c", script], input=json.dumps(document()).encode(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT, env=environment(), timeout=45)
        self.assertEqual(completed.returncode, 3, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["kind"], "magic_simulation_error")
        self.assertEqual(result["error"]["code"], "simulation_failed")
        self.assertEqual(result["request_id"], document()["request_id"])
        self.assertIsNone(result["error"]["path"])
        self.assertNotIn("summary", result)
        self.assertNotIn(b"private", completed.stdout + completed.stderr)
        self.assertNotIn(b"Traceback", completed.stderr)

    def test_command_selects_its_own_error_family_even_without_kind(self):
        families = (("simulate-magic", "magic_simulation_error"), ("simulate-mixed", "mixed_simulation_error"),
            ("balance-mixed", "mixed_balance_error"), ("simulate-melee", "melee_simulation_error"),
            ("balance-melee", "melee_balance_error"), ("simulate", "simulation_error"), ("balance", "balance_error"))
        for name, kind in families:
            with self.subTest(command=name):
                completed = invoke(name, "-", data=b"{")
                self.assertEqual(completed.returncode, 2, completed.stderr)
                self.assertEqual(json.loads(completed.stdout)["kind"], kind)

    def test_magic_and_all_six_previous_commands_reject_foreign_documents(self):
        examples = ROOT / "docs/examples"
        cases = (("simulate", "simulation_error", "m4/ranged-v1.request.json"),
            ("balance", "balance_error", "m5/json/balance-v1.request.json"),
            ("simulate-melee", "melee_simulation_error", "m6/json/melee-simulation-v1.request.json"),
            ("balance-melee", "melee_balance_error", "m6/json/melee-balance-v1.request.json"),
            ("simulate-mixed", "mixed_simulation_error", "m7/json/mixed-simulation-v1.request.json"),
            ("balance-mixed", "mixed_balance_error", "m7/json/mixed-balance-v1.request.json"))
        for name, kind, path in cases:
            for command, raw, expected_kind in ((name, json.dumps(document()).encode(), kind),
                    ("simulate-magic", (examples / path).read_bytes(), "magic_simulation_error")):
                with self.subTest(command=command, foreign=path):
                    completed = invoke(command, "-", data=raw)
                    self.assertEqual(completed.returncode, 2, completed.stderr)
                    actual = json.loads(completed.stdout)
                    self.assertEqual(actual["kind"], expected_kind)
                    self.assertEqual(actual["error"]["code"], "invalid_input")
                    self.assertNotIn("summary", actual)

    def test_relative_file_from_unrelated_cwd_matches_application_result(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            path.write_bytes((EXAMPLES / "magic-simulation-v1.request.json").read_bytes())
            completed = invoke("simulate-magic", path.name, cwd=directory)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, b"")
        self.assertTrue(completed.stdout.endswith(b"\n"))
        actual = json.loads(completed.stdout.decode("utf-8"))
        from towr.adapters.magic_simulation_json import parse_magic_simulation_request, encode_magic_simulation_result
        from towr.application.magic_simulation_service import execute_magic_simulation
        command = parse_magic_simulation_request((EXAMPLES / "magic-simulation-v1.request.json").read_bytes())
        expected = json.loads(encode_magic_simulation_result(command, execute_magic_simulation(command)))
        self.assertEqual(actual, expected)
        self.assertNotIn("trials", actual)
        validate_magic_simulation_document(actual, "result")

    def test_unicode_stdin_and_real_spawn_match_sequential(self):
        data = document()
        data["request_id"] = "перестрелка-雪"
        data["scenario"]["activation_order"].reverse()
        data["scenario"]["wizard"]["day_id"] = "день-雪"
        sequential = invoke("simulate-magic", "-", data=json.dumps(data, ensure_ascii=False).encode("utf-8"))
        self.assertEqual(sequential.returncode, 0, sequential.stderr)
        data["execution"] = {"mode": "process", "workers": 2, "batch_size": 1}
        process = invoke("simulate-magic", "-", data=json.dumps(data, ensure_ascii=False).encode("utf-8"))
        self.assertEqual(process.returncode, 0, process.stderr)
        for completed in (sequential, process):
            self.assertEqual(completed.stderr, b"")
            self.assertIn("перестрелка-雪".encode("utf-8"), completed.stdout)
        seq_doc, proc_doc = (json.loads(item.stdout.decode("utf-8")) for item in (sequential, process))
        validate_magic_simulation_document(proc_doc, "result")
        self.assertEqual(proc_doc["request"], data)
        self.assertNotIn("trials", proc_doc)
        self.assertEqual(proc_doc["summary"], seq_doc["summary"])

    def test_invalid_json_version_and_admission_have_input_exit_code(self):
        invalid = document()
        invalid["scenario"]["facts"]["targets_aware"] = False
        cases = ((b"{", "invalid_json"), (b"\xff", "invalid_json"),
                 (json.dumps(dict(document(), schema_version="3")).encode(), "unsupported_version"),
                 (json.dumps(invalid).encode(), "invalid_input"))
        for raw, code in cases:
            with self.subTest(code=code, raw=raw[:20]):
                completed = invoke("simulate-magic", "-", data=raw)
                self.assertEqual(completed.returncode, 2, completed.stderr)
                actual = json.loads(completed.stdout.decode("utf-8"))
                validate_magic_simulation_document(actual, "error")
                self.assertEqual(actual["error"]["code"], code)
                self.assertNotIn("trials", actual)
                self.assertIn(code.encode(), completed.stderr)
                self.assertNotIn(b"Traceback", completed.stderr)

    def test_missing_file_and_directory_are_io_errors_without_json(self):
        with tempfile.TemporaryDirectory() as directory:
            for path in (Path(directory) / "missing.json", Path(directory)):
                with self.subTest(path=path):
                    completed = invoke("simulate-magic", str(path))
                    self.assertEqual(completed.returncode, 4, completed.stderr)
                    self.assertEqual(completed.stdout, b"")
                    self.assertIn(b"input I/O error", completed.stderr)
                    self.assertNotIn(b"Traceback", completed.stderr)

    def test_help_and_usage_errors_do_not_emit_simulation_json(self):
        for args in (("--help",), ("simulate-magic", "--help")):
            completed = invoke(*args)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn(b"usage:", completed.stdout)
            self.assertEqual(completed.stderr, b"")
        for args in ((), ("simulate-magic",), ("unknown",), ("simulate-magic", "-", "--workers", "2")):
            completed = invoke(*args, data=b"")
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(completed.stdout, b"")
            self.assertIn(b"usage:", completed.stderr)

    def test_closed_stdout_pipe_returns_io_status_without_shutdown_traceback(self):
        with subprocess.Popen([sys.executable, "-m", "towr", "simulate-magic", "-"],
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
        with subprocess.Popen([sys.executable, "-m", "towr", "simulate-magic", "-"],
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
            "with patch('towr.simulation.npc_magic_parallel.ProcessPoolExecutor', "
            "side_effect=OSError('pool unavailable')):\n"
            "    raise SystemExit(main(['simulate-magic', '-']))\n"
        )
        data = document()
        data["execution"] = {"mode": "process", "workers": 2, "batch_size": 1}
        completed = subprocess.run([sys.executable, "-c", script], input=json.dumps(data).encode(),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   cwd=ROOT, env=environment(), timeout=45)
        self.assertEqual(completed.returncode, 3, completed.stderr)
        actual = json.loads(completed.stdout)
        validate_magic_simulation_document(actual, "error")
        self.assertEqual(actual["request_id"], data["request_id"])
        self.assertEqual(actual["error"]["code"], "simulation_failed")
        self.assertNotIn("trials", actual)
        self.assertNotIn("summary", actual)
        self.assertIn(b"simulation_failed", completed.stderr)
        self.assertNotIn(b"Traceback", completed.stderr)
