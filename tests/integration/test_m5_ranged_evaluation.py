from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.unit.test_m2_npc_ranged_scenario import scenario
from tests.unit.test_m5_ranged_evaluation import request, Candidate
from towr.application.ranged_evaluation_service import evaluate_ranged_candidates
from towr.application.ranged_evaluation_errors import RangedBalanceEvaluationError
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options


class M5RangedEvaluationIntegrationTests(unittest.TestCase):
    def test_real_backends_reordering_and_renaming_preserve_candidate_observations(self):
        source = request(count=2)
        source = replace(source, candidates=(source.candidates[0], Candidate("other", scenario(sizes=(2, 1)))))
        before = deepcopy(source)
        sequential = evaluate_ranged_candidates(source, Options(Mode.SEQUENTIAL))
        process = evaluate_ranged_candidates(source, Options(Mode.PROCESS, 2, 3))
        self.assertEqual(sequential, process)
        self.assertEqual(sequential.selected_candidate_ids, process.selected_candidate_ids)
        self.assertEqual(sequential.total_trials, 8)
        reordered = evaluate_ranged_candidates(replace(source, candidates=source.candidates[::-1]), Options(Mode.SEQUENTIAL))
        self.assertEqual({r.candidate_id: r.assessment for r in sequential.candidates},
                         {r.candidate_id: r.assessment for r in reordered.candidates})
        renamed = replace(source, candidates=tuple(replace(c, candidate_id=c.candidate_id + ":new") for c in source.candidates))
        actual = evaluate_ranged_candidates(renamed, Options(Mode.SEQUENTIAL))
        self.assertEqual(tuple(r.assessment for r in sequential.candidates), tuple(r.assessment for r in actual.candidates))
        self.assertEqual(source, before)

    def test_pool_creation_failure_is_a_candidate_error_without_fallback(self):
        cause = OSError("pool startup failed")
        with patch("towr.simulation.npc_ranged_parallel.ProcessPoolExecutor", side_effect=cause) as pool, \
                patch("towr.application.ranged_evaluation_service.run_npc_ranged_simulation") as seq:
            with self.assertRaises(RangedBalanceEvaluationError) as caught:
                evaluate_ranged_candidates(request(), Options(Mode.PROCESS, 2, 1))
            self.assertEqual(caught.exception.candidate_id, "candidate:0")
            self.assertIs(caught.exception.__cause__, cause)
            pool.assert_called_once()
            seq.assert_not_called()
