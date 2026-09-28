import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


class M5ExampleTests(unittest.TestCase):
    def test_documented_script_runs_outside_repo_with_equal_sequential_process_reports(self):
        root = Path(__file__).resolve().parents[2]
        script = root / "docs" / "examples" / "m5" / "ranged_balance.py"
        environment = dict(os.environ, PYTHONPATH=str(root / "src"), PYTHONIOENCODING="utf-8")
        outputs = []
        with TemporaryDirectory() as directory:
            for mode in ("sequential", "process"):
                result = subprocess.run([sys.executable, str(script), "--mode", mode], cwd=directory,
                                        env=environment, capture_output=True, text=True, encoding="utf-8", timeout=120)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                execution, report = result.stdout.split("\n", 1)
                self.assertTrue(execution.startswith(f"execution: {mode}"))
                self.assertIn("candidates: 5; max_candidates: 5", report)
                self.assertIn("planned_trials: 136; max_total_trials: 136", report)
                self.assertIn("actual_trials: 136", report)
                self.assertIn("final_selected:", report)
                outputs.append(report)
        # No expectation of a particular Monte Carlo objective rate or selected ID.
        self.assertEqual(outputs[0], outputs[1])
