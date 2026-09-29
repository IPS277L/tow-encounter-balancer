"""Public production example must run independently of the repository cwd."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CastingExampleTests(unittest.TestCase):
    def test_public_example_from_unrelated_cwd_matches_saved_observations(self):
        root = Path(__file__).resolve().parents[2]
        example = root / 'docs/examples/m8/casting_action.py'
        expected = (example.parent / 'casting_action.output.txt').read_text(encoding='utf-8')
        env = {**os.environ, 'PYTHONPATH': str(root / 'src'), 'PYTHONNOUSERSITE': '1'}
        with tempfile.TemporaryDirectory(prefix='towr-m8-example-') as cwd:
            result = subprocess.run(
                [sys.executable, str(example)], cwd=cwd, env=env,
                capture_output=True, text=True, encoding='utf-8', timeout=30,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertEqual(result.stdout, expected)


if __name__ == '__main__':
    unittest.main()
