"""Finite assessment-contract evidence runs without repository tests or tools."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class MagicAssessmentContractProbeTests(unittest.TestCase):
    def test_public_assessment_probe_from_external_cwd(self):
        root = Path(__file__).resolve().parents[2]
        source = root / 'docs/examples/m8/assessment_contract_probe.py'
        with tempfile.TemporaryDirectory() as directory:
            for name in ('assessment_contract_probe.py', 'magic_simulation.py', 'magic_scenario.py'):
                shutil.copyfile(source.with_name(name), Path(directory) / name)
            result = subprocess.run([sys.executable, str(Path(directory) / source.name)], cwd=directory,
                env=dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1'),
                capture_output=True, text=True, encoding='utf-8', check=True, timeout=60)
        self.assertEqual(result.stderr, '')
        self.assertEqual(result.stdout, source.with_suffix('.output.txt').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
