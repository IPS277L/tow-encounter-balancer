"""The finite transport proof is reproducible as a copied four-file bundle."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class OptInTransportContractProbeTests(unittest.TestCase):
    def test_external_cwd_bundle_matches_saved_output(self):
        root = Path(__file__).resolve().parents[2]
        examples = root / 'docs/examples/m8'
        cache = root / '.cache'
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='adr0047-proof-', dir=cache) as directory:
            for name in ('opt_in_transport_contract_probe.py', 'generation_contract_probe.py',
                         'magic_scenario.py', 'opted_miscast.py'):
                shutil.copyfile(examples / name, Path(directory) / name)
            result = subprocess.run([sys.executable, str(Path(directory) / 'opt_in_transport_contract_probe.py')],
                cwd=directory, env=dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1'),
                capture_output=True, text=True, encoding='utf-8', check=True, timeout=30)
        self.assertEqual(result.stderr, '')
        self.assertEqual(result.stdout,
            (examples / 'opt_in_transport_contract_probe.output.txt').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
