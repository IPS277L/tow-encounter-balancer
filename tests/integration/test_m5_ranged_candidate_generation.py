from dataclasses import replace
from fractions import Fraction as F
import unittest

from tests.unit.test_m5_ranged_candidate_generation_models import request, Stage, Window
from towr.application.ranged_candidate_generation import generate_ranged_candidates
from towr.application.ranged_staged_evaluation_service import evaluate_ranged_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options


def small_request():
    return replace(request(), stages=(Stage(1, 1), Stage(2, 1)), max_total_trials=7,
                   window=Window(F(0), F(1, 2), F(1)))


def observations(report):
    return tuple(tuple((row.assessment.summary.outcome_counts, row.assessment.summary.total_attack_count,
                        row.assessment.summary.total_visited_round_count) for row in stage.candidates)
                 for stage in report.stage_reports)


class M5RangedGenerationIntegrationTests(unittest.TestCase):
    def test_five_generated_candidates_run_through_existing_stages_in_both_backends(self):
        source = small_request()
        result = generate_ranged_candidates(source)
        self.assertEqual(result, generate_ranged_candidates(source))
        self.assertEqual(len(result.evaluation_request.candidates), 5)
        sequential = evaluate_ranged_candidates_staged(result.evaluation_request, Options(Mode.SEQUENTIAL))
        process = evaluate_ranged_candidates_staged(result.evaluation_request, Options(Mode.PROCESS, 2, 1))
        self.assertEqual(sequential, process)
        self.assertEqual(len(sequential.stage_reports[0].candidates), 5)
        self.assertEqual(sequential.total_trials, 7)

    def test_prefix_changes_preserve_observations_and_selected_composition(self):
        source = small_request()
        original = generate_ranged_candidates(source)
        renamed = generate_ranged_candidates(replace(source, candidate_id_prefix="renamed"))
        seq = evaluate_ranged_candidates_staged(original.evaluation_request, Options(Mode.SEQUENTIAL))
        other = evaluate_ranged_candidates_staged(renamed.evaluation_request, Options(Mode.SEQUENTIAL))
        self.assertEqual(observations(seq), observations(other))
        self.assertEqual(tuple(i.removeprefix("family") for i in seq.selected_candidate_ids),
                         tuple(i.removeprefix("renamed") for i in other.selected_candidate_ids))
        for left, right in zip(original.evaluation_request.candidates, renamed.evaluation_request.candidates):
            self.assertNotEqual(left.scenario.initial.current.id, right.scenario.initial.current.id)
