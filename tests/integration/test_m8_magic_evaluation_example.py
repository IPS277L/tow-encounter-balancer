"""Public three-file evaluation bundle and its late-failure entry point."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class MagicEvaluationExampleTests(unittest.TestCase):
    def copy_bundle(self, directory):
        root = Path(__file__).resolve().parents[2]
        source = root / 'docs/examples/m8/magic_evaluation.py'
        for name in ('magic_evaluation.py', 'magic_simulation.py', 'magic_scenario.py'):
            shutil.copyfile(source.with_name(name), Path(directory) / name)
        return root, source

    def test_public_evaluation_example_from_external_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            root, source = self.copy_bundle(directory)
            result = subprocess.run([sys.executable, str(Path(directory) / source.name)], cwd=directory,
                env=dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1'),
                capture_output=True, text=True, encoding='utf-8', check=True, timeout=60)
        self.assertEqual(result.stderr, '')
        self.assertEqual(result.stdout, source.with_suffix('.output.txt').read_text(encoding='utf-8'))

    def test_late_candidate_failure_has_empty_stdout_and_preserves_cause_notes(self):
        program = '''
from pathlib import Path
import runpy
import sys
from unittest.mock import patch
from towr.application import magic_evaluation_service as service
from towr.application.magic_evaluation_errors import MagicBalanceEvaluationError

original = service.run_npc_magic_simulation
calls = 0
def fail_second(request):
    global calls
    calls += 1
    if calls == 1:
        result = original(request)
        assert result.source_request is request and len(result.trials) == 8
        Path('first-candidate.completed').write_text(str(result.source_request.trials))
        return result
    error = OSError('late candidate failure')
    error.add_note('late candidate original note')
    raise error

with patch.object(service, 'run_npc_magic_simulation', side_effect=fail_second), \\
     patch.object(service, 'run_npc_magic_simulation_parallel', side_effect=AssertionError('process must not start')) as process:
    try:
        runpy.run_path(sys.argv[1], run_name='__main__')
    except MagicBalanceEvaluationError as error:
        assert error.candidate_id == 'wizard-first'
        assert type(error.__cause__) is OSError
        assert error.__cause__.__notes__ == ['late candidate original note']
        assert calls == 2
        process.assert_not_called()
        raise
    else:
        raise AssertionError('late candidate failure must propagate')
'''
        with tempfile.TemporaryDirectory() as directory:
            root, source = self.copy_bundle(directory)
            result = subprocess.run([sys.executable, '-c', program, str(Path(directory) / source.name)], cwd=directory,
                env=dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1'),
                capture_output=True, text=True, encoding='utf-8', timeout=60)
            self.assertEqual((Path(directory) / 'first-candidate.completed').read_text(), '8')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertNotIn('AssertionError', result.stderr)
        for expected in ('candidate failed: wizard-first', 'OSError: late candidate failure',
                         'late candidate original note', 'MagicBalanceEvaluationError'):
            self.assertIn(expected, result.stderr)


if __name__ == '__main__':
    unittest.main()
