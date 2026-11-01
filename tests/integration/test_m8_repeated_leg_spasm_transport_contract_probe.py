"""ADR-0054 production v4/generation proof runs from a copied six-file bundle."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class RepeatedLegSpasmTransportContractProbeTests(unittest.TestCase):
    def test_copied_finite_bundle_matches_saved_output(self):
        root = Path(__file__).resolve().parents[2]
        examples = root / 'docs/examples/m8'
        names = ('repeated_leg_spasm_transport_contract_probe.py', 'generation_contract_probe.py',
                 'stationary_wound_runner.py', 'magic_scenario.py',
                 'json/magic-simulation-v3.request.json', 'json/magic-balance-v3.request.json')
        before = {name: hashlib.sha256((examples / name).read_bytes()).hexdigest() for name in names}
        cache = root / '.cache'
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='adr0054-proof-', dir=cache) as directory:
            copied = Path(directory)
            for name in names:
                target = copied / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(examples / name, target)
            result = subprocess.run([sys.executable, str(copied / names[0])], cwd=directory,
                env=dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1'),
                capture_output=True, text=True, encoding='utf-8', check=True, timeout=45)
            self.assertEqual(before, {name: hashlib.sha256((copied / name).read_bytes()).hexdigest() for name in names})
        self.assertEqual(result.stderr, '')
        self.assertEqual(result.stdout,
            (examples / 'repeated_leg_spasm_transport_contract_probe.output.txt').read_text(encoding='utf-8'))
        self.assertEqual(before, {name: hashlib.sha256((examples / name).read_bytes()).hexdigest() for name in names})


if __name__ == '__main__':
    unittest.main()
