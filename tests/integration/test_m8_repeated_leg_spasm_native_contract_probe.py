"""ADR-0053 contract probe copied independently of the repository examples."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class RepeatedLegSpasmNativeContractProbeTests(unittest.TestCase):
    def test_copied_contract_probe_matches_saved_output(self):
        root = Path(__file__).resolve().parents[2]
        source = root / 'docs/examples/m8/repeated_leg_spasm_native_contract_probe.py'
        with tempfile.TemporaryDirectory() as directory:
            for name in (source.name, 'stationary_wound_runner.py', 'magic_scenario.py'):
                shutil.copyfile(source.with_name(name), Path(directory) / name)
            result = subprocess.run([sys.executable, str(Path(directory) / source.name)], cwd=directory,
                env=dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1'),
                capture_output=True, text=True, encoding='utf-8', check=True, timeout=30)
        self.assertEqual(result.stderr, '')
        self.assertEqual(result.stdout, source.with_suffix('.output.txt').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
