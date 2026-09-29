from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from functools import partial
from multiprocessing import active_children
import random
import unittest
from unittest.mock import patch

from tests.integration.test_m7_npc_mixed_parallel import exact_rng
from tests.integration.test_m7_npc_mixed_simulation import four_outcome_request
from tests.unit.test_m7_npc_mixed_scenario import scenario
from tests.unit.test_m7_mixed_evaluation import request, Candidate
from towr.application.mixed_evaluation_service import evaluate_mixed_candidates
from towr.application import mixed_evaluation_service as service
from towr.balance.mixed_assessment_models import MixedAssessmentStatus, ObjectiveRateWindow
from towr.simulation.npc_mixed_models import NpcMixedOutcomeCounts
from towr.application.mixed_evaluation_errors import MixedBalanceEvaluationError
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options


class M7MixedEvaluationIntegrationTests(unittest.TestCase):
    def test_real_backends_reordering_and_renaming_preserve_candidate_observations(self):
        source = request(count=2)
        source = replace(source, candidates=(source.candidates[0], Candidate("other", scenario(sizes=(2, 2), enemy_bow=True))))
        before = deepcopy(source)
        children_before = {child.pid for child in active_children()}
        random_before = random.getstate()
        sequential = evaluate_mixed_candidates(source, Options(Mode.SEQUENTIAL))
        process = evaluate_mixed_candidates(source, Options(Mode.PROCESS, 2, 3))
        self.assertEqual(sequential, process)
        self.assertEqual(sequential, evaluate_mixed_candidates(source, Options(Mode.SEQUENTIAL)))
        self.assertEqual(sequential.selected_candidate_ids, process.selected_candidate_ids)
        self.assertEqual(sequential.total_trials, 8)
        self.assertIs(sequential.source_request, source)
        self.assertIs(process.source_request, source)
        reordered = evaluate_mixed_candidates(replace(source, candidates=source.candidates[::-1]), Options(Mode.SEQUENTIAL))
        self.assertEqual({r.candidate_id: r.assessment for r in sequential.candidates},
                         {r.candidate_id: r.assessment for r in reordered.candidates})
        renamed = replace(source, candidates=tuple(replace(c, candidate_id=c.candidate_id + ":new") for c in source.candidates))
        actual = evaluate_mixed_candidates(renamed, Options(Mode.SEQUENTIAL))
        self.assertEqual(tuple(r.assessment for r in sequential.candidates), tuple(r.assessment for r in actual.candidates))
        self.assertEqual(source, before)
        self.assertEqual(random.getstate(), random_before)
        self.assertEqual({child.pid for child in active_children()}, children_before)

    def test_pool_creation_failure_is_a_candidate_error_without_fallback(self):
        cause = OSError("pool startup failed")
        with patch("towr.simulation.npc_mixed_parallel.ProcessPoolExecutor", side_effect=cause) as pool, \
                patch("towr.application.mixed_evaluation_service.run_npc_mixed_simulation") as seq:
            with self.assertRaises(MixedBalanceEvaluationError) as caught:
                evaluate_mixed_candidates(request(), Options(Mode.PROCESS, 2, 1))
            self.assertEqual(caught.exception.candidate_id, "candidate:0")
            self.assertIs(caught.exception.__cause__, cause)
            pool.assert_called_once()
            seq.assert_not_called()

    def test_four_real_outcomes_remain_in_report_and_unsupported_prevents_selection(self):
        simulation = four_outcome_request()
        source = replace(request(count=1), candidates=(Candidate("four-outcomes", simulation.scenario),),
                         window=ObjectiveRateWindow(F(1, 4), F(1, 4), F(1, 4)))
        before, global_rng = deepcopy(source), random.getstate()
        children = {child.pid for child in active_children()}
        factory = partial(exact_rng, seeds=tuple(simulation.seed_for(i) for i in range(4)))
        sequential_runner = service.run_npc_mixed_simulation
        process_runner = service.run_npc_mixed_simulation_parallel
        # Only inject the lower-level RNG factory; both runners execute the real mixed scenario.
        with patch.object(service, "run_npc_mixed_simulation",
                          side_effect=lambda s: sequential_runner(s, rng_factory=factory)) as seq, \
             patch.object(service, "run_npc_mixed_simulation_parallel",
                          side_effect=lambda s, **kw: process_runner(s, rng_factory=factory, **kw)) as proc:
            sequential = evaluate_mixed_candidates(source, Options(Mode.SEQUENTIAL))
            process = evaluate_mixed_candidates(source, Options(Mode.PROCESS, 2, 3))
            seq.assert_called_once_with(source.simulation_requests[0])
            proc.assert_called_once_with(source.simulation_requests[0], workers=2, batch_size=3)
        self.assertEqual(sequential, process)
        self.assertEqual(sequential.total_trials, 4)
        self.assertEqual(sequential.selected_candidate_ids, ())
        assessment = sequential.candidates[0].assessment
        self.assertIs(assessment.source_request, source.simulation_requests[0])
        self.assertIs(assessment.summary.source_request, source.simulation_requests[0])
        self.assertEqual(assessment.summary.outcome_counts, NpcMixedOutcomeCounts(1, 1, 1, 1))
        self.assertEqual((assessment.summary.total_attack_count, assessment.summary.total_visited_round_count), (17, 6))
        self.assertEqual(assessment.objective_achieved_rate, source.window.target)
        self.assertIs(assessment.status, MixedAssessmentStatus.UNSUPPORTED_OBSERVATIONS)
        self.assertIsNone(assessment.window_match)
        self.assertEqual(source, before)
        self.assertEqual(random.getstate(), global_rng)
        self.assertEqual({child.pid for child in active_children()}, children)
