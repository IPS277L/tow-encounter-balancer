"""Finite ADR-0051 proposal remains reproducible outside the repository cwd."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class StationaryWoundTransportContractProbeTests(unittest.TestCase):
    def test_copied_finite_bundle_matches_saved_output(self):
        root = Path(__file__).resolve().parents[2]
        examples = root / 'docs/examples/m8'
        cache = root / '.cache'
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='adr0051-proof-', dir=cache) as directory:
            for name in ('stationary_wound_transport_contract_probe.py', 'generation_contract_probe.py',
                         'magic_scenario.py', 'opted_miscast.py', 'stationary_wound_runner.py'):
                shutil.copyfile(examples / name, Path(directory) / name)
            result = subprocess.run([sys.executable, str(Path(directory) / 'stationary_wound_transport_contract_probe.py')],
                cwd=directory, env=dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1'),
                capture_output=True, text=True, encoding='utf-8', check=True, timeout=45)
        self.assertEqual(result.stderr, '')
        self.assertEqual(result.stdout,
            (examples / 'stationary_wound_transport_contract_probe.output.txt').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
