from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from functools import partial
from multiprocessing import active_children
import random
import unittest
from unittest.mock import patch

from tests.unit.test_m7_npc_mixed_scenario import scenario
from tests.integration.test_m7_npc_mixed_parallel import exact_rng
from tests.integration.test_m7_npc_mixed_simulation import four_outcome_request
from tests.unit.test_m7_mixed_staged_evaluation import request, Stage, Window, Status
from towr.application import mixed_evaluation_service as bounded_service
from towr.balance.mixed_evaluation_models import MixedBalanceCandidate
from towr.simulation.npc_mixed_models import NpcMixedOutcomeCounts
from towr.application.mixed_staged_evaluation_service import evaluate_mixed_candidates_staged
from towr.application.mixed_staged_evaluation_errors import MixedStagedEvaluationError
from towr.application.mixed_evaluation_errors import MixedBalanceEvaluationError
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options


class M7MixedStagedIntegrationTests(unittest.TestCase):
    def test_real_sequential_process_reports_match_and_renaming_preserves_observations(self):
        base = request()
        candidates = (base.candidates[0], replace(base.candidates[1], scenario=scenario(sizes=(2, 2), enemy_bow=True)))
        source = replace(base, candidates=candidates, stages=(Stage(2, 2), Stage(4, 1)),
                         max_total_trials=12, window=Window(F(0), F(1, 2), F(1)))
        before = deepcopy(source)
        rng_before = random.getstate()
        children_before = {child.pid for child in active_children()}
        seq = evaluate_mixed_candidates_staged(source, Options(Mode.SEQUENTIAL))
        proc = evaluate_mixed_candidates_staged(source, Options(Mode.PROCESS, 2, 3))
        self.assertEqual(seq, proc)
        self.assertEqual(seq.selected_candidate_ids, proc.selected_candidate_ids)
        self.assertIs(seq.source_request, source)
        self.assertIs(proc.source_request, source)
        self.assertEqual(seq, evaluate_mixed_candidates_staged(source, Options(Mode.SEQUENTIAL)))
        self.assertLessEqual(seq.total_trials, source.planned_trials)
        self.assertEqual(seq.total_trials, sum(r.total_trials for r in seq.stage_reports))
        self.assertEqual(source, before)
        renamed = replace(source, candidates=tuple(replace(c, candidate_id=c.candidate_id + ":renamed") for c in candidates))
        actual = evaluate_mixed_candidates_staged(renamed, Options(Mode.SEQUENTIAL))
        for original, other in zip(seq.stage_reports, actual.stage_reports, strict=True):
            self.assertEqual(tuple(row.assessment for row in original.candidates), tuple(row.assessment for row in other.candidates))
        self.assertEqual(actual.selected_candidate_ids, tuple(i + ":renamed" for i in seq.selected_candidate_ids))
        # keep=2 retains every supported candidate in stage one. Reordering may
        # alter final ties, but not observations or exclusion due to unsupported.
        reordered = evaluate_mixed_candidates_staged(replace(source, candidates=candidates[::-1]), Options(Mode.SEQUENTIAL))
        for original, other in zip(seq.stage_reports, reordered.stage_reports, strict=True):
            self.assertEqual({r.candidate_id: r.assessment for r in original.candidates},
                             {r.candidate_id: r.assessment for r in other.candidates})
        self.assertEqual(random.getstate(), rng_before)
        self.assertEqual({child.pid for child in active_children()}, children_before)

    def test_process_startup_failure_keeps_full_error_chain_without_fallback(self):
        cause = OSError("pool startup failed")
        with patch("towr.simulation.npc_mixed_parallel.ProcessPoolExecutor", side_effect=cause) as pool, \
                patch("towr.application.mixed_evaluation_service.run_npc_mixed_simulation") as seq:
            with self.assertRaises(MixedStagedEvaluationError) as caught:
                evaluate_mixed_candidates_staged(request(), Options(Mode.PROCESS, 2, 1))
            self.assertEqual(caught.exception.stage_index, 0)
            self.assertEqual(caught.exception.candidate_id, "candidate:0")
            self.assertIsInstance(caught.exception.__cause__, MixedBalanceEvaluationError)
            self.assertIs(caught.exception.__cause__.__cause__, cause)
            pool.assert_called_once()
            seq.assert_not_called()

    def test_scripted_unsupported_blocks_continuation_and_final_selection_in_both_backends(self):
        simulation = four_outcome_request()
        factory = partial(exact_rng, seeds=tuple(simulation.seed_for(i) for i in range(4)))
        sequential_runner = bounded_service.run_npc_mixed_simulation
        process_runner = bounded_service.run_npc_mixed_simulation_parallel
        # The supported 3-trial prefix is outside the point window but continues.
        # The full 4-trial package is exactly in the window but unsupported.
        for first_trials, expected_status, expected_total in (
                (3, Status.COMPLETED, 7), (4, Status.NO_ELIGIBLE_CANDIDATES, 4)):
            source = replace(request(), candidates=(MixedBalanceCandidate("four-outcomes", simulation.scenario),),
                             master_seed=simulation.master_seed,
                             stages=(Stage(first_trials, 1), Stage(first_trials + 1, 1)),
                             max_total_trials=2 * first_trials + 1,
                             window=Window(F(1, 4), F(1, 4), F(1, 4)))
            before, rng_before = deepcopy(source), random.getstate()
            children_before = {child.pid for child in active_children()}
            # Inject at the existing simulation RNG boundary; both evaluators
            # and real sequential/spawn runners execute production code.
            with self.subTest(first_trials=first_trials), \
                    patch.object(bounded_service, "run_npc_mixed_simulation",
                                 side_effect=lambda s: sequential_runner(s, rng_factory=factory)) as seq, \
                    patch.object(bounded_service, "run_npc_mixed_simulation_parallel",
                                 side_effect=lambda s, **kw: process_runner(s, rng_factory=factory, **kw)) as proc:
                sequential = evaluate_mixed_candidates_staged(source, Options(Mode.SEQUENTIAL))
                process = evaluate_mixed_candidates_staged(source, Options(Mode.PROCESS, 2, 3))
                expected_trials = [3, 4] if first_trials == 3 else [4]
                self.assertEqual([c.args[0].trials for c in seq.call_args_list], expected_trials)
                self.assertEqual([c.args[0].trials for c in proc.call_args_list], expected_trials)
                self.assertTrue(all(c.kwargs == {"workers": 2, "batch_size": 3} for c in proc.call_args_list))
            self.assertEqual(sequential, process)
            self.assertIs(sequential.status, expected_status)
            self.assertEqual(sequential.total_trials, expected_total)
            self.assertEqual(sequential.selected_candidate_ids, ())
            self.assertIs(sequential.source_request, source)
            self.assertIs(process.source_request, source)
            if first_trials == 3:
                first = sequential.stage_reports[0].candidates[0].assessment
                self.assertEqual(first.summary.outcome_counts, NpcMixedOutcomeCounts(1, 1, 1, 0))
                self.assertEqual((first.summary.total_attack_count, first.summary.total_visited_round_count), (16, 5))
                self.assertIs(first.window_match, False)
                self.assertEqual(sequential.stage_reports[0].selected_candidate_ids, ())
            final = sequential.stage_reports[-1].candidates[0].assessment
            self.assertEqual(final.summary.outcome_counts, NpcMixedOutcomeCounts(1, 1, 1, 1))
            self.assertEqual((final.summary.total_attack_count, final.summary.total_visited_round_count), (17, 6))
            self.assertEqual(final.objective_achieved_rate, source.window.target)
            self.assertIsNone(final.window_match)
            self.assertEqual(source, before)
            self.assertEqual(random.getstate(), rng_before)
            self.assertEqual({child.pid for child in active_children()}, children_before)
