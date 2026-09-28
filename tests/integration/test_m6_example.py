import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


class M6ExampleTests(unittest.TestCase):
    def test_documented_public_runner_example_repeats_outside_repository(self):
        root = Path(__file__).resolve().parents[2]
        script = root / "docs" / "examples" / "m6" / "melee_scenario.py"
        environment = dict(os.environ, PYTHONPATH=str(root / "src"), PYTHONIOENCODING="utf-8")
        outputs = []
        with TemporaryDirectory() as directory:
            for _ in range(2):
                result = subprocess.run([sys.executable, str(script)], cwd=directory, env=environment,
                                        capture_output=True, text=True, encoding="utf-8", timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                report = result.stdout
                self.assertIn("seed: 42; round_budget: 3", report)
                self.assertIn("RULE-PROFILE-TALABEC-005", report)
                self.assertIn("all_opponents_in_close_range=True", report)
                self.assertIn("repeated_stagger: suffer_wound", report)
                self.assertIn("outcome: ", report)
                self.assertIn("scenario_pending: 0", report)
                self.assertEqual(sum(line.startswith("policy ") for line in report.splitlines()), 4)
                self.assertEqual(sum(line.startswith("actor ") for line in report.splitlines()), 4)
                self.assertIn("attack example:melee", report)
                outputs.append(report)
        # Replay equality, not an expectation of a particular random winner.
        self.assertEqual(outputs[0], outputs[1])
