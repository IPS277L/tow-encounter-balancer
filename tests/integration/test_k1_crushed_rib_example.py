"""The public actual-consumer example runs from an isolated copied bundle."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class CrushedRibExampleTests(unittest.TestCase):
    def test_copied_actual_consumer_matches_saved_stdout_and_preserves_sources(self):
        root = Path(__file__).resolve().parents[2]
        examples = root / 'docs/examples/m8'
        names = ('crushed_rib_test.py', 'stationary_wound_runner.py', 'magic_scenario.py')
        hashes = {n: hashlib.sha256((examples / n).read_bytes()).hexdigest() for n in names}
        (root / '.cache').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='adr0055-consumer-', dir=root / '.cache') as directory:
            copied = Path(directory)
            for name in names:
                shutil.copyfile(examples / name, copied / name)
            result = subprocess.run([sys.executable, str(copied / names[0])], cwd=copied,
                env=dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1'),
                capture_output=True, text=True, encoding='utf-8', timeout=45, check=True)
            self.assertEqual(hashes, {n: hashlib.sha256((copied / n).read_bytes()).hexdigest() for n in names})
        self.assertEqual(result.stderr, '')
        self.assertEqual(result.stdout, (examples / 'crushed_rib_test.output.txt').read_text(encoding='utf-8'))
        self.assertEqual(hashes, {n: hashlib.sha256((examples / n).read_bytes()).hexdigest() for n in names})


if __name__ == '__main__':
    unittest.main()
