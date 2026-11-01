"""Actual mixed Wound9/6 manual flow from a copied public three-file bundle."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class StationaryWoundContinuationTests(unittest.TestCase):
    def test_copied_actual_chain_matches_saved_output(self):
        root = Path(__file__).resolve().parents[2]
        source = root / 'docs/examples/m8/stationary_wound_continuation.py'
        with tempfile.TemporaryDirectory() as directory:
            for name in (source.name, 'leg_spasm_stand.py', 'magic_scenario.py'):
                shutil.copyfile(source.with_name(name), Path(directory) / name)
            result = subprocess.run([sys.executable, str(Path(directory) / source.name)], cwd=directory,
                env=dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1'),
                capture_output=True, text=True, encoding='utf-8', check=True, timeout=30)
        self.assertEqual(result.stderr, '')
        self.assertEqual(result.stdout, source.with_suffix('.output.txt').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
