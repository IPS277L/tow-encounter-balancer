import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


class M7SimulationExampleTests(unittest.TestCase):
    def test_public_simulation_example_repeats_outside_repository(self):
        root = Path(__file__).resolve().parents[2]
        script = root / 'docs/examples/m7/mixed_simulation.py'
        environment = dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONIOENCODING='utf-8')
        outputs = []
        with TemporaryDirectory() as directory:
            for _ in range(2):
                result = subprocess.run([sys.executable, str(script)], cwd=directory, env=environment,
                                        capture_output=True, text=True, encoding='utf-8', timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, '')
                report = result.stdout
                self.assertIn('seed_scheme=towr:npc-mixed-trial:v1', report)
                for case in ('3x2_one_archer', '2x2_two_archers'):
                    self.assertIn(f'case: {case}; master_seed=42; trials=8; round_budget=2', report)
                self.assertEqual(report.count('denominator=ALL 8 trials'), 2)
                self.assertEqual(report.count('Full result and summary replay equal'), 2)
                self.assertEqual(sum(line.startswith('  trial ') for line in report.splitlines()), 16)
                self.assertIn('Unsupported remains separate', report)
                outputs.append(report)
        # Reproducibility, not a fixed random winner or exact Monte Carlo rate.
        self.assertEqual(outputs[0], outputs[1])
