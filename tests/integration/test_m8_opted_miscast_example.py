"""Opted runner example works as a two-file bundle outside the repository."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class OptedMiscastExampleTests(unittest.TestCase):
    def test_external_cwd_bundle_matches_saved_output(self):
        root = Path(__file__).resolve().parents[2]
        examples = root / 'docs/examples/m8'
        with tempfile.TemporaryDirectory() as directory:
            for name in ('opted_miscast.py', 'magic_scenario.py'):
                shutil.copyfile(examples / name, Path(directory) / name)
            result = subprocess.run([sys.executable, str(Path(directory) / 'opted_miscast.py')],
                cwd=directory, env=dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1'),
                capture_output=True, text=True, encoding='utf-8', check=True, timeout=30)
        self.assertEqual(result.stderr, '')
        self.assertEqual(result.stdout, (examples / 'opted_miscast.output.txt').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
