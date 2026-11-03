"""Copied actual-consumer evidence for the ADR-0061 contract preparation."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class BatteredLegNativeContractProbeTests(unittest.TestCase):
    def test_copied_public_bundle_matches_saved_stdout_without_source_mutation(self):
        self.run_bundle('battered_leg_native_contract_probe')

    def test_copied_automatic_native_bundle_matches_saved_stdout_without_source_mutation(self):
        self.run_bundle('battered_leg_native')

    def run_bundle(self, name):
        root = Path(__file__).resolve().parents[2]
        examples = root / 'docs/examples/m8'
        names = (name + '.py', 'magic_scenario.py')
        expected = examples / (name + '.output.txt')
        hashed = (*names, expected.name)
        before = {name: hashlib.sha256((examples / name).read_bytes()).hexdigest() for name in hashed}
        cache = root / '.cache'
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='adr0061-proof-', dir=cache) as directory:
            copied = Path(directory)
            for name in names:
                shutil.copyfile(examples / name, copied / name)
            result = subprocess.run([sys.executable, str(copied / names[0])], cwd=directory,
                env=dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1'),
                capture_output=True, text=True, encoding='utf-8', check=True, timeout=45)
            self.assertEqual({name: before[name] for name in names},
                {name: hashlib.sha256((copied / name).read_bytes()).hexdigest() for name in names})
        self.assertEqual(result.stderr, '')
        self.assertEqual(result.stdout, expected.read_text(encoding='utf-8'))
        self.assertEqual(before,
            {name: hashlib.sha256((examples / name).read_bytes()).hexdigest() for name in hashed})


if __name__ == '__main__':
    unittest.main()
