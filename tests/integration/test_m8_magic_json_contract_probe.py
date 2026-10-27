"""Finite magic wire mapping through public typed APIs, from external cwd."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class MagicJsonContractProbeTests(unittest.TestCase):
    def test_public_mapping_probe_from_external_cwd(self):
        root = Path(__file__).resolve().parents[2]
        source = root / 'docs/examples/m8'
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            for name in ('json_contract_probe.py', 'magic_balance.py',
                         'magic_simulation.py', 'magic_scenario.py'):
                shutil.copyfile(source / name, target / name)
            (target / 'json').mkdir()
            fixtures = sorted((source / 'json').glob('magic-*-v1.*.json'))
            self.assertEqual(len(fixtures), 6)
            for fixture in fixtures:
                shutil.copyfile(fixture, target / 'json' / fixture.name)
            before = {p.name: p.read_bytes() for p in (target / 'json').iterdir()}
            result = subprocess.run(
                [sys.executable, str(target / 'json_contract_probe.py')], cwd=target,
                env=dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1'),
                capture_output=True, text=True, encoding='utf-8', check=True, timeout=60)
            self.assertEqual(before, {p.name: p.read_bytes() for p in (target / 'json').iterdir()})
        self.assertEqual(result.stderr, '')
        self.assertEqual(result.stdout,
                         (source / 'json_contract_probe.output.txt').read_text(encoding='utf-8'))
