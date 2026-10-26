"""Public three-file process example, run from an independent directory."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class MagicParallelExampleTests(unittest.TestCase):
    def test_public_process_example_from_external_cwd(self):
        root = Path(__file__).resolve().parents[2]
        source = root / 'docs/examples/m8/magic_parallel.py'
        with tempfile.TemporaryDirectory() as directory:
            for name in ('magic_parallel.py', 'magic_simulation.py', 'magic_scenario.py'):
                shutil.copyfile(source.with_name(name), Path(directory) / name)
            result = subprocess.run([sys.executable, str(Path(directory) / source.name)], cwd=directory,
                env=dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1'),
                capture_output=True, text=True, encoding='utf-8', check=True, timeout=60)
        self.assertEqual(result.stderr, '')
        self.assertEqual(result.stdout, source.with_suffix('.output.txt').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
