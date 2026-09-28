from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
import unittest
from unittest.mock import patch

from tests.unit.test_m2_npc_ranged_scenario import scenario
from tests.unit.test_m5_ranged_staged_evaluation import request, Stage, Window, Status
from towr.application.ranged_staged_evaluation_service import evaluate_ranged_candidates_staged
from towr.application.ranged_staged_evaluation_errors import RangedStagedEvaluationError
from towr.application.ranged_evaluation_errors import RangedBalanceEvaluationError
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options


class M5RangedStagedIntegrationTests(unittest.TestCase):
    def test_real_sequential_process_reports_match_and_renaming_preserves_observations(self):
        base = request()
        candidates = (base.candidates[0], replace(base.candidates[1], scenario=scenario(sizes=(2, 1))))
        source = replace(base, candidates=candidates, stages=(Stage(2, 2), Stage(4, 1)),
                         max_total_trials=12, window=Window(F(0), F(1, 2), F(1)))
        before = deepcopy(source)
        seq = evaluate_ranged_candidates_staged(source, Options(Mode.SEQUENTIAL))
        proc = evaluate_ranged_candidates_staged(source, Options(Mode.PROCESS, 2, 3))
        self.assertEqual(seq, proc)
        self.assertEqual(seq.status, Status.COMPLETED)
        self.assertEqual(seq.total_trials, 12)
        self.assertEqual(source, before)
        renamed = replace(source, candidates=tuple(replace(c, candidate_id=c.candidate_id + ":renamed") for c in candidates))
        actual = evaluate_ranged_candidates_staged(renamed, Options(Mode.SEQUENTIAL))
        for original, other in zip(seq.stage_reports, actual.stage_reports):
            self.assertEqual(tuple(row.assessment for row in original.candidates), tuple(row.assessment for row in other.candidates))
        self.assertEqual(actual.selected_candidate_ids, tuple(i + ":renamed" for i in seq.selected_candidate_ids))

    def test_process_startup_failure_keeps_full_error_chain_without_fallback(self):
        cause = OSError("pool startup failed")
        with patch("towr.simulation.npc_ranged_parallel.ProcessPoolExecutor", side_effect=cause) as pool, \
                patch("towr.application.ranged_evaluation_service.run_npc_ranged_simulation") as seq:
            with self.assertRaises(RangedStagedEvaluationError) as caught:
                evaluate_ranged_candidates_staged(request(), Options(Mode.PROCESS, 2, 1))
            self.assertEqual(caught.exception.stage_index, 0)
            self.assertEqual(caught.exception.candidate_id, "candidate:0")
            self.assertIsInstance(caught.exception.__cause__, RangedBalanceEvaluationError)
            self.assertIs(caught.exception.__cause__.__cause__, cause)
            pool.assert_called_once()
            seq.assert_not_called()
