from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from multiprocessing import active_children
import random
import unittest
from unittest.mock import patch

from tests.unit.test_m6_npc_melee_scenario import scenario
from tests.unit.test_m6_melee_staged_evaluation import request, Stage, Window, Status
from towr.application.melee_staged_evaluation_service import evaluate_melee_candidates_staged
from towr.application.melee_staged_evaluation_errors import MeleeStagedEvaluationError
from towr.application.melee_evaluation_errors import MeleeBalanceEvaluationError
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options


class M6MeleeStagedIntegrationTests(unittest.TestCase):
    def test_real_sequential_process_reports_match_and_renaming_preserves_observations(self):
        base = request()
        candidates = (base.candidates[0], replace(base.candidates[1], scenario=scenario(sizes=(2, 1))))
        source = replace(base, candidates=candidates, stages=(Stage(2, 2), Stage(4, 1)),
                         max_total_trials=12, window=Window(F(0), F(1, 2), F(1)))
        before = deepcopy(source)
        rng_before = random.getstate()
        children_before = {child.pid for child in active_children()}
        seq = evaluate_melee_candidates_staged(source, Options(Mode.SEQUENTIAL))
        proc = evaluate_melee_candidates_staged(source, Options(Mode.PROCESS, 2, 3))
        self.assertEqual(seq, proc)
        self.assertEqual(seq.selected_candidate_ids, proc.selected_candidate_ids)
        self.assertIs(seq.source_request, source)
        self.assertIs(proc.source_request, source)
        self.assertEqual(seq.status, Status.COMPLETED)
        self.assertEqual(seq.total_trials, 12)
        self.assertEqual(source, before)
        renamed = replace(source, candidates=tuple(replace(c, candidate_id=c.candidate_id + ":renamed") for c in candidates))
        actual = evaluate_melee_candidates_staged(renamed, Options(Mode.SEQUENTIAL))
        for original, other in zip(seq.stage_reports, actual.stage_reports):
            self.assertEqual(tuple(row.assessment for row in original.candidates), tuple(row.assessment for row in other.candidates))
        self.assertEqual(actual.selected_candidate_ids, tuple(i + ":renamed" for i in seq.selected_candidate_ids))
        # Both candidates survive the first stage. Reordering may alter final ties,
        # but each candidate's observations must remain the same at both stages.
        reordered = evaluate_melee_candidates_staged(replace(source, candidates=candidates[::-1]), Options(Mode.SEQUENTIAL))
        for original, other in zip(seq.stage_reports, reordered.stage_reports, strict=True):
            self.assertEqual({r.candidate_id: r.assessment for r in original.candidates},
                             {r.candidate_id: r.assessment for r in other.candidates})
        self.assertEqual(random.getstate(), rng_before)
        self.assertEqual({child.pid for child in active_children()}, children_before)

    def test_process_startup_failure_keeps_full_error_chain_without_fallback(self):
        cause = OSError("pool startup failed")
        with patch("towr.simulation.npc_melee_parallel.ProcessPoolExecutor", side_effect=cause) as pool, \
                patch("towr.application.melee_evaluation_service.run_npc_melee_simulation") as seq:
            with self.assertRaises(MeleeStagedEvaluationError) as caught:
                evaluate_melee_candidates_staged(request(), Options(Mode.PROCESS, 2, 1))
            self.assertEqual(caught.exception.stage_index, 0)
            self.assertEqual(caught.exception.candidate_id, "candidate:0")
            self.assertIsInstance(caught.exception.__cause__, MeleeBalanceEvaluationError)
            self.assertIs(caught.exception.__cause__.__cause__, cause)
            pool.assert_called_once()
            seq.assert_not_called()
