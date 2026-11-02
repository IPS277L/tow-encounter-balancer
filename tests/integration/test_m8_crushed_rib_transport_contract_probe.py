"""ADR-0058 finite specification executes from a copied public six-file bundle."""
import hashlib
import os
from pathlib import Path
from random import getstate
import shutil
import subprocess
import sys
import tempfile
import unittest


class CrushedRibTransportContractProbeTests(unittest.TestCase):
    def test_copied_public_bundle_matches_saved_output(self):
        root = Path(__file__).resolve().parents[2]
        examples = root / 'docs/examples/m8'
        names = ('crushed_rib_transport_contract_probe.py', 'crushed_rib_native.py',
                 'crushed_rib_owner.py', 'generation_contract_probe.py',
                 'stationary_wound_runner.py', 'magic_scenario.py')
        before = {name: hashlib.sha256((examples / name).read_bytes()).hexdigest() for name in names}
        rng = getstate()
        cache = root / '.cache'
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='adr0058-proof-', dir=cache) as directory:
            copied = Path(directory)
            for name in names:
                shutil.copyfile(examples / name, copied / name)
            result = subprocess.run([sys.executable, str(copied / names[0])], cwd=copied,
                env=dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1'),
                capture_output=True, text=True, encoding='utf-8', check=True, timeout=120)
            self.assertEqual(result.stderr, '')
            self.assertEqual(result.stdout,
                (examples / 'crushed_rib_transport_contract_probe.output.txt').read_text(encoding='utf-8'))
            self.assertEqual(before, {name: hashlib.sha256((copied / name).read_bytes()).hexdigest() for name in names})
        self.assertEqual(before, {name: hashlib.sha256((examples / name).read_bytes()).hexdigest() for name in names})
        self.assertEqual(getstate(), rng)


if __name__ == '__main__':
    unittest.main()
