"""Public two-file generation bundle and late generation/evaluation failures."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class MagicBalanceExampleTests(unittest.TestCase):
    def copy_bundle(self, directory):
        root = Path(__file__).resolve().parents[2]
        source = root / 'docs/examples/m8/magic_balance.py'
        for name in ('magic_balance.py', 'magic_scenario.py'):
            shutil.copyfile(source.with_name(name), Path(directory) / name)
        return root, source

    def test_public_balance_example_from_external_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            root, source = self.copy_bundle(directory)
            result = subprocess.run([sys.executable, str(Path(directory) / source.name)], cwd=directory,
                env=dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1'),
                capture_output=True, text=True, encoding='utf-8', check=True, timeout=60)
        self.assertEqual(result.stderr, '')
        self.assertEqual(result.stdout, source.with_suffix('.output.txt').read_text(encoding='utf-8'))

    def test_late_generation_failure_preserves_candidate_counts_cause_and_empty_stdout(self):
        program = '''
from copy import deepcopy
from multiprocessing import active_children
from pathlib import Path
from random import getstate
import runpy
import sys
from unittest.mock import patch
from towr.application import magic_candidate_generation as generation
from towr.application import magic_staged_evaluation_service as staged
from towr.application import magic_evaluation_service as bounded
from towr.application.magic_candidate_generation_errors import MagicCandidateGenerationError

original_admit = generation.NpcMagicScenario
original_generate = generation.generate_magic_candidates
calls = 0
root_calls = 0
failed_id = None
original_error = OSError('late generation admission failure')
original_error.add_note('late generation original note')

def fail_second_admission(*args, **kwargs):
    global calls, failed_id
    calls += 1
    if calls == 1:
        result = original_admit(*args, **kwargs)
        assert result.id == kwargs['id']
        Path('first-generation.completed').write_text('1')
        return result
    assert calls == 2
    failed_id = kwargs['id']
    Path('failed-generation.id').write_text(failed_id)
    raise original_error

def observe_generation(request):
    global root_calls
    root_calls += 1
    before, rng_before = deepcopy(request), getstate()
    children_before = {child.pid for child in active_children()}
    try:
        return original_generate(request)
    finally:
        assert request == before and getstate() == rng_before
        assert {child.pid for child in active_children()} == children_before

with patch.object(generation, 'NpcMagicScenario', side_effect=fail_second_admission), \\
     patch.object(generation, 'generate_magic_candidates', side_effect=observe_generation), \\
     patch.object(staged, 'evaluate_magic_candidates_staged', side_effect=AssertionError('evaluation must not start')) as evaluation, \\
     patch.object(bounded, 'run_npc_magic_simulation_parallel', side_effect=AssertionError('process must not start')) as process:
    try:
        runpy.run_path(sys.argv[1], run_name='__main__')
    except MagicCandidateGenerationError as error:
        assert error.candidate_id == failed_id and error.counts == (1, 1)
        assert error.__cause__ is original_error
        assert original_error.__notes__ == ['late generation original note']
        assert calls == 2 and root_calls == 1
        evaluation.assert_not_called()
        process.assert_not_called()
        raise
    else:
        raise AssertionError('late generation failure must propagate')
'''
        with tempfile.TemporaryDirectory() as directory:
            root, source = self.copy_bundle(directory)
            result = subprocess.run([sys.executable, '-c', program, str(Path(directory) / source.name)], cwd=directory,
                env=dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1'),
                capture_output=True, text=True, encoding='utf-8', timeout=60)
            self.assertEqual((Path(directory) / 'first-generation.completed').read_text(), '1')
            failed_id = (Path(directory) / 'failed-generation.id').read_text()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertNotIn('AssertionError', result.stderr)
        for expected in (f'generation failed: candidate={failed_id}; counts=(1, 1)',
                         'OSError: late generation admission failure', 'late generation original note',
                         'MagicCandidateGenerationError'):
            self.assertIn(expected, result.stderr)

    def test_late_evaluation_failure_preserves_stage_candidate_cause_and_empty_stdout(self):
        program = '''
from copy import deepcopy
from multiprocessing import active_children
from pathlib import Path
from random import getstate
import runpy
import sys
from unittest.mock import patch
from towr.application import magic_evaluation_service as bounded
from towr.application import magic_staged_evaluation_service as staged
from towr.application.magic_evaluation_errors import MagicBalanceEvaluationError
from towr.application.magic_staged_evaluation_errors import MagicStagedEvaluationError

original_runner = bounded.run_npc_magic_simulation
original_evaluate = staged.evaluate_magic_candidates_staged
calls = 0
root_calls = 0
failed_id = None
original_error = OSError('late generated candidate failure')
original_error.add_note('late evaluation original note')

def fail_second_candidate(request):
    global calls, failed_id
    calls += 1
    if calls == 1:
        result = original_runner(request)
        assert result.source_request is request and len(result.trials) == 8
        assert request.trials == 8
        Path('first-evaluation.completed').write_text(str(len(result.trials)))
        return result
    assert calls == 2
    failed_id = request.scenario.id
    Path('failed-evaluation.id').write_text(failed_id)
    raise original_error

def observe_evaluation(request, execution):
    global root_calls
    root_calls += 1
    before, rng_before = deepcopy(request), getstate()
    children_before = {child.pid for child in active_children()}
    try:
        return original_evaluate(request, execution)
    finally:
        assert request == before and getstate() == rng_before
        assert {child.pid for child in active_children()} == children_before

with patch.object(bounded, 'run_npc_magic_simulation', side_effect=fail_second_candidate), \\
     patch.object(staged, 'evaluate_magic_candidates_staged', side_effect=observe_evaluation), \\
     patch.object(bounded, 'run_npc_magic_simulation_parallel', side_effect=AssertionError('process must not start')) as process:
    try:
        runpy.run_path(sys.argv[1], run_name='__main__')
    except MagicStagedEvaluationError as error:
        assert error.stage_index == 0 and error.candidate_id == failed_id
        assert type(error.__cause__) is MagicBalanceEvaluationError
        assert error.__cause__.candidate_id == failed_id
        assert error.__cause__.__cause__ is original_error
        assert original_error.__notes__ == ['late evaluation original note']
        assert calls == 2 and root_calls == 1
        process.assert_not_called()
        raise
    else:
        raise AssertionError('late generated candidate failure must propagate')
'''
        with tempfile.TemporaryDirectory() as directory:
            root, source = self.copy_bundle(directory)
            result = subprocess.run([sys.executable, '-c', program, str(Path(directory) / source.name)], cwd=directory,
                env=dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1'),
                capture_output=True, text=True, encoding='utf-8', timeout=60)
            self.assertEqual((Path(directory) / 'first-evaluation.completed').read_text(), '8')
            failed_id = (Path(directory) / 'failed-evaluation.id').read_text()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertNotIn('AssertionError', result.stderr)
        for expected in (f'evaluation failed: stage=0; candidate={failed_id}',
                         'OSError: late generated candidate failure', 'late evaluation original note',
                         'MagicBalanceEvaluationError', 'MagicStagedEvaluationError'):
            self.assertIn(expected, result.stderr)


if __name__ == '__main__':
    unittest.main()
