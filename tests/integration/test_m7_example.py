import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


class M7ExampleTests(unittest.TestCase):
    def test_public_mixed_runner_example_outside_repository_matches_documented_scripts(self):
        root = Path(__file__).resolve().parents[2]
        script = root / "docs/examples/m7/mixed_scenario.py"
        expected = script.with_suffix('.output.txt').read_text(encoding='utf-8')
        environment = dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONIOENCODING='utf-8')
        with TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(script)], cwd=directory, env=environment,
                                    capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        # Exact counts concern authored dice only. Seeded runs assert replay,
        # never a particular winner or Monte Carlo percentage.
        self.assertEqual(result.stdout, expected)
