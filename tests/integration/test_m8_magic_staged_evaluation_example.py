"""Public four-file staged bundle and its late-stage failure entry point."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class MagicStagedEvaluationExampleTests(unittest.TestCase):
    def copy_bundle(self, directory):
        root = Path(__file__).resolve().parents[2]
        source = root / 'docs/examples/m8/magic_staged_evaluation.py'
        for name in ('magic_staged_evaluation.py', 'magic_evaluation.py',
                     'magic_simulation.py', 'magic_scenario.py'):
            shutil.copyfile(source.with_name(name), Path(directory) / name)
        return root, source

    def test_public_staged_example_from_external_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            root, source = self.copy_bundle(directory)
            result = subprocess.run([sys.executable, str(Path(directory) / source.name)], cwd=directory,
                env=dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1'),
                capture_output=True, text=True, encoding='utf-8', check=True, timeout=60)
        self.assertEqual(result.stderr, '')
        self.assertEqual(result.stdout, source.with_suffix('.output.txt').read_text(encoding='utf-8'))

    def test_late_stage_failure_has_empty_stdout_and_preserves_cause_notes(self):
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
from towr.balance.magic_staged_evaluation import magic_continuation_candidate_ids

original_stage = staged.evaluate_magic_candidates
original_root = staged.evaluate_magic_candidates_staged
calls = 0
root_calls = 0
first_report = None
failed_id = None
original_error = OSError('late stage candidate failure')
original_error.add_note('late stage original note')

def fail_second_stage(request, execution):
    global calls, first_report, failed_id
    calls += 1
    if calls == 1:
        first_report = original_stage(request, execution)
        assert first_report.source_request is request and first_report.total_trials == 16
        assert len(request.candidates) == 2 and request.trials_per_candidate == 8
        Path('first-stage.completed').write_text(str(first_report.total_trials))
        return first_report
    assert calls == 2
    assert tuple(candidate.candidate_id for candidate in request.candidates) == magic_continuation_candidate_ids(first_report)
    assert request.trials_per_candidate == 32 and request.candidates
    failed_id = request.candidates[0].candidate_id
    Path('failed-candidate.id').write_text(failed_id)
    with patch.object(bounded, 'run_npc_magic_simulation', side_effect=original_error) as runner:
        try:
            return original_stage(request, execution)
        finally:
            runner.assert_called_once_with(request.simulation_requests[0])

def observe_root(request, execution):
    global root_calls
    root_calls += 1
    before, rng_before = deepcopy(request), getstate()
    children_before = {child.pid for child in active_children()}
    try:
        return original_root(request, execution)
    finally:
        assert request == before and getstate() == rng_before
        assert {child.pid for child in active_children()} == children_before

with patch.object(staged, 'evaluate_magic_candidates', side_effect=fail_second_stage), \\
     patch.object(staged, 'evaluate_magic_candidates_staged', side_effect=observe_root), \\
     patch.object(bounded, 'run_npc_magic_simulation_parallel', side_effect=AssertionError('process must not start')) as process:
    try:
        runpy.run_path(sys.argv[1], run_name='__main__')
    except MagicStagedEvaluationError as error:
        assert error.stage_index == 1 and error.candidate_id == failed_id
        assert type(error.__cause__) is MagicBalanceEvaluationError
        assert error.__cause__.candidate_id == failed_id
        assert error.__cause__.__cause__ is original_error
        assert original_error.__notes__ == ['late stage original note']
        assert calls == 2 and root_calls == 1
        process.assert_not_called()
        raise
    else:
        raise AssertionError('late stage failure must propagate')
'''
        with tempfile.TemporaryDirectory() as directory:
            root, source = self.copy_bundle(directory)
            result = subprocess.run([sys.executable, '-c', program, str(Path(directory) / source.name)], cwd=directory,
                env=dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1'),
                capture_output=True, text=True, encoding='utf-8', timeout=60)
            self.assertEqual((Path(directory) / 'first-stage.completed').read_text(), '16')
            failed_id = (Path(directory) / 'failed-candidate.id').read_text()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertNotIn('AssertionError', result.stderr)
        for expected in (f'stage failed: 1; candidate: {failed_id}', 'OSError: late stage candidate failure',
                         'late stage original note', 'MagicBalanceEvaluationError', 'MagicStagedEvaluationError'):
            self.assertIn(expected, result.stderr)


if __name__ == '__main__':
    unittest.main()
