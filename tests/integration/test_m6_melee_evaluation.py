from copy import deepcopy
from dataclasses import replace
from multiprocessing import active_children
import random
import unittest
from unittest.mock import patch

from tests.unit.test_m6_npc_melee_scenario import scenario
from tests.unit.test_m6_melee_evaluation import request, Candidate
from towr.application.melee_evaluation_service import evaluate_melee_candidates
from towr.application.melee_evaluation_errors import MeleeBalanceEvaluationError
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options


class M6MeleeEvaluationIntegrationTests(unittest.TestCase):
    def test_real_backends_reordering_and_renaming_preserve_candidate_observations(self):
        source = request(count=2)
        source = replace(source, candidates=(source.candidates[0], Candidate("other", scenario(sizes=(2, 1)))))
        before = deepcopy(source)
        children_before = {child.pid for child in active_children()}
        random_before = random.getstate()
        sequential = evaluate_melee_candidates(source, Options(Mode.SEQUENTIAL))
        process = evaluate_melee_candidates(source, Options(Mode.PROCESS, 2, 3))
        self.assertEqual(sequential, process)
        self.assertEqual(sequential.selected_candidate_ids, process.selected_candidate_ids)
        self.assertEqual(sequential.total_trials, 8)
        self.assertIs(sequential.source_request, source)
        self.assertIs(process.source_request, source)
        reordered = evaluate_melee_candidates(replace(source, candidates=source.candidates[::-1]), Options(Mode.SEQUENTIAL))
        self.assertEqual({r.candidate_id: r.assessment for r in sequential.candidates},
                         {r.candidate_id: r.assessment for r in reordered.candidates})
        renamed = replace(source, candidates=tuple(replace(c, candidate_id=c.candidate_id + ":new") for c in source.candidates))
        actual = evaluate_melee_candidates(renamed, Options(Mode.SEQUENTIAL))
        self.assertEqual(tuple(r.assessment for r in sequential.candidates), tuple(r.assessment for r in actual.candidates))
        self.assertEqual(source, before)
        self.assertEqual(random.getstate(), random_before)
        self.assertEqual({child.pid for child in active_children()}, children_before)

    def test_pool_creation_failure_is_a_candidate_error_without_fallback(self):
        cause = OSError("pool startup failed")
        with patch("towr.simulation.npc_melee_parallel.ProcessPoolExecutor", side_effect=cause) as pool, \
                patch("towr.application.melee_evaluation_service.run_npc_melee_simulation") as seq:
            with self.assertRaises(MeleeBalanceEvaluationError) as caught:
                evaluate_melee_candidates(request(), Options(Mode.PROCESS, 2, 1))
            self.assertEqual(caught.exception.candidate_id, "candidate:0")
            self.assertIs(caught.exception.__cause__, cause)
            pool.assert_called_once()
            seq.assert_not_called()
