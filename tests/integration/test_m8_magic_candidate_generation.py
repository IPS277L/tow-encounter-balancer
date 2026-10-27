"""ADR-0042 generated inputs through real sequential and spawn evaluation."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from functools import partial
from multiprocessing import active_children
import os
from random import getstate
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_m8_magic_candidate_generation_models import request, Stage, Window
from towr.application import magic_evaluation_service as bounded_service
from towr.application.magic_candidate_generation import generate_magic_candidates
from towr.application.magic_staged_evaluation_service import evaluate_magic_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.balance.magic_staged_evaluation_models import MagicStagedEvaluationStatus as Status
from towr.simulation.npc_magic_models import NpcMagicOutcomeCounts


def miss_rng(seed, *, parent_pid=None):
    """Importable finite factory; the process call must execute in its child."""
    if parent_pid is not None:
        assert os.getpid() != parent_pid, 'scripted process RNG ran in the parent'
    return SequenceRandom((10,) * 100)


def small_request():
    source = request()
    template = replace(source.template_scenario, max_rounds=1)
    return replace(source, template_scenario=template,
        stages=(Stage(2, 2), Stage(4, 1)), max_total_trials=16,
        window=Window(F(0), F(1, 2), F(1)))


class MagicGenerationBackendIntegrationTests(unittest.TestCase):
    def assert_parent_sources(self, report, source):
        self.assertIs(report.source_request, source)
        originals = {candidate.candidate_id: candidate.scenario for candidate in source.candidates}
        for stage in report.stage_reports:
            for row, candidate in zip(stage.candidates, stage.source_request.candidates, strict=True):
                assessment = row.assessment
                self.assertIs(candidate.scenario, originals[candidate.candidate_id])
                self.assertIs(assessment.source_request.scenario, candidate.scenario)
                self.assertIs(assessment.summary.source_request, assessment.source_request)
                self.assertIs(assessment.window, source.window)
                self.assertEqual(assessment.summary.trials, stage.source_request.trials_per_candidate)

    def test_generated_reports_match_repeated_sequential_and_real_spawn(self):
        source = small_request()
        before, rng_before = deepcopy(source), getstate()
        children_before = {child.pid for child in active_children()}
        generated = generate_magic_candidates(source)
        repeated = generate_magic_candidates(source)
        self.assertEqual(generated, repeated)
        self.assertIs(generated.source_request, source)
        seq = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.SEQUENTIAL))
        proc = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.PROCESS, 2, 3))
        again = evaluate_magic_candidates_staged(repeated.evaluation_request, Options(Mode.SEQUENTIAL))
        self.assertEqual(seq, proc)
        self.assertEqual(seq, again)
        self.assertEqual(seq.selected_candidate_ids, proc.selected_candidate_ids)
        self.assertEqual((seq.planned_trials, source.max_total_trials), (16, 16))
        self.assertLessEqual(seq.total_trials, seq.planned_trials)
        self.assertEqual(seq.total_trials, sum(stage.total_trials for stage in seq.stage_reports))
        self.assertEqual(len(seq.stage_reports[0].candidates), 4)
        self.assert_parent_sources(seq, generated.evaluation_request)
        self.assert_parent_sources(proc, generated.evaluation_request)
        self.assert_parent_sources(again, repeated.evaluation_request)
        # Natural draws may trigger unsupported; no percentage/survivor is fixed.
        self.assertEqual(source, before)
        self.assertEqual(getstate(), rng_before)
        self.assertEqual({child.pid for child in active_children()}, children_before)

    def test_prefix_rename_preserves_full_assessments_indexed_seeds_and_compositions(self):
        source = small_request()
        before, rng_before = deepcopy(source), getstate()
        children_before = {child.pid for child in active_children()}
        original = generate_magic_candidates(source)
        renamed = generate_magic_candidates(replace(source, candidate_id_prefix='renamed'))
        seq = evaluate_magic_candidates_staged(original.evaluation_request, Options(Mode.SEQUENTIAL))
        other = evaluate_magic_candidates_staged(renamed.evaluation_request, Options(Mode.SEQUENTIAL))
        self.assertEqual((seq.status, seq.total_trials, seq.planned_trials),
                         (other.status, other.total_trials, other.planned_trials))
        for old_candidate, new_candidate in zip(original.evaluation_request.candidates,
                renamed.evaluation_request.candidates, strict=True):
            self.assertNotEqual(old_candidate.candidate_id, new_candidate.candidate_id)
            self.assertNotEqual(old_candidate.scenario.id, new_candidate.scenario.id)
            self.assertEqual(replace(new_candidate.scenario, id=old_candidate.scenario.id), old_candidate.scenario)
        for left, right in zip(seq.stage_reports, other.stage_reports, strict=True):
            for a, b in zip(left.candidates, right.candidates, strict=True):
                self.assertEqual(a.candidate_id.removeprefix('family'), b.candidate_id.removeprefix('renamed'))
                old, new = a.assessment.source_request, b.assessment.source_request
                self.assertEqual(replace(new, scenario=replace(new.scenario, id=old.scenario.id)), old)
                self.assertEqual(tuple(old.seed_for(i) for i in range(old.trials)),
                                 tuple(new.seed_for(i) for i in range(new.trials)))
                normalized = replace(b.assessment, source_request=old,
                    summary=replace(b.assessment.summary, source_request=old))
                self.assertEqual(a.assessment, normalized)
        self.assertEqual(tuple(i.removeprefix('family') for i in seq.selected_candidate_ids),
                         tuple(i.removeprefix('renamed') for i in other.selected_candidate_ids))
        self.assert_parent_sources(seq, original.evaluation_request)
        self.assert_parent_sources(other, renamed.evaluation_request)
        self.assertEqual(source, before)
        self.assertEqual(getstate(), rng_before)
        self.assertEqual({child.pid for child in active_children()}, children_before)

    def test_scripted_generated_family_pays_full_repeated_batches_in_both_backends(self):
        source = small_request()
        before, rng_before = deepcopy(source), getstate()
        children_before = {child.pid for child in active_children()}
        generated = generate_magic_candidates(source)
        sequential_runner = bounded_service.run_npc_magic_simulation
        process_runner = bounded_service.run_npc_magic_simulation_parallel
        # Only the existing simulation RNG boundary is injected. Generation,
        # staged/bounded evaluation and sequential/spawn runners are production.
        factory = partial(miss_rng, parent_pid=os.getpid())
        with patch.object(bounded_service, 'run_npc_magic_simulation',
                side_effect=lambda s: sequential_runner(s, rng_factory=miss_rng)) as seq_calls, \
                patch.object(bounded_service, 'run_npc_magic_simulation_parallel',
                side_effect=lambda s, **kw: process_runner(s, rng_factory=factory, **kw)) as proc_calls:
            seq = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.SEQUENTIAL))
            proc = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.PROCESS, 2, 3))
        requests = [call.args[0] for call in seq_calls.call_args_list]
        self.assertEqual([s.trials for s in requests], [2, 2, 2, 2, 4, 4])
        self.assertEqual(requests, [call.args[0] for call in proc_calls.call_args_list])
        self.assertTrue(all(call.kwargs == {'workers': 2, 'batch_size': 3} for call in proc_calls.call_args_list))
        self.assertEqual(seq, proc)
        self.assertIs(seq.status, Status.COMPLETED)
        self.assertEqual(tuple(len(stage.candidates) for stage in seq.stage_reports), (4, 2))
        # Pay 4*2 + 2*4, not an incremental 4*2 + 2*(4-2).
        self.assertEqual((seq.total_trials, seq.planned_trials, source.max_total_trials), (16, 16, 16))
        for last in requests[4:]:
            first = next(s for s in requests[:4] if s.scenario is last.scenario)
            self.assertEqual(tuple(first.seed_for(i) for i in range(2)), tuple(last.seed_for(i) for i in range(2)))
        for stage in seq.stage_reports:
            for row in stage.candidates:
                assessment = row.assessment
                summary = assessment.summary
                n = assessment.source_request.trials
                self.assertEqual(summary.outcome_counts, NpcMagicOutcomeCounts(0, 0, n, 0))
                self.assertEqual((assessment.round_limit_rate, assessment.unsupported_path_rate), (F(1), F(0)))
                self.assertEqual(summary.total_action_count,
                    n * len(assessment.source_request.scenario.activation_order))
                self.assertEqual((summary.total_started_round_count, summary.total_completed_round_count), (n, n))
        self.assert_parent_sources(seq, generated.evaluation_request)
        self.assert_parent_sources(proc, generated.evaluation_request)
        self.assertEqual(source, before)
        self.assertEqual(getstate(), rng_before)
        self.assertEqual({child.pid for child in active_children()}, children_before)


if __name__ == '__main__':
    unittest.main()
