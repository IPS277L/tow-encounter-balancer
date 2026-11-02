"""ADR-0057 finite manual oracle and implemented None-policy refusal bundle."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class CrushedRibNativeContractProbeTests(unittest.TestCase):
    def test_copied_finite_bundle_matches_saved_stdout(self):
        root = Path(__file__).resolve().parents[2]
        examples = root / 'docs/examples/m8'
        names = ('crushed_rib_native_contract_probe.py', 'crushed_rib_owner.py',
                 'stationary_wound_runner.py', 'generation_contract_probe.py', 'magic_scenario.py')
        expected = examples / 'crushed_rib_native_contract_probe.output.txt'
        hashed = (*names, expected.name)
        before = {name: hashlib.sha256((examples / name).read_bytes()).hexdigest() for name in hashed}
        cache = root / '.cache'
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='adr0057-proof-', dir=cache) as directory:
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
        self.assertEqual(before, {name: hashlib.sha256((examples / name).read_bytes()).hexdigest() for name in hashed})


if __name__ == '__main__':
    unittest.main()
