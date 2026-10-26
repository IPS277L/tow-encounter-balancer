"""The production example runs as one copied file, without repo examples/tests."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class MagicScenarioExampleTests(unittest.TestCase):
    def test_standalone_public_example_from_external_cwd(self):
        root = Path(__file__).resolve().parents[2]
        source = root / 'docs/examples/m8/magic_scenario.py'
        with tempfile.TemporaryDirectory() as directory:
            example = Path(directory) / source.name
            shutil.copyfile(source, example)
            result = subprocess.run([sys.executable, str(example)], cwd=directory,
                env=dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1'),
                capture_output=True, text=True, encoding='utf-8', check=True, timeout=30)
        self.assertEqual(result.stderr, '')
        self.assertEqual(result.stdout, source.with_suffix('.output.txt').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
