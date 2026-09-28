from fractions import Fraction
from functools import partial
import unittest

from tests.integration.test_m3_npc_ranged_parallel import exact_rng
from tests.unit.test_m2_npc_ranged_scenario import scenario
from towr.balance.ranged_assessment import assess_ranged_candidate
from towr.balance.ranged_assessment_models import ObjectiveRateWindow, RangedAssessmentStatus
from towr.simulation.npc_ranged_models import NpcRangedSimulationRequest
from towr.simulation.npc_ranged_parallel import run_npc_ranged_simulation_parallel
from towr.simulation.npc_ranged_simulation import run_npc_ranged_simulation
from towr.simulation.npc_ranged_summary import summarize_npc_ranged_simulation


class M5RangedAssessmentIntegrationTests(unittest.TestCase):
    def test_real_sequential_and_spawn_summaries_produce_identical_assessments(self):
        source = NpcRangedSimulationRequest(scenario(sizes=(1, 1)), 123, 3)
        factory = partial(exact_rng, seeds=tuple(source.seed_for(i) for i in range(source.trials)))
        sequential = run_npc_ranged_simulation(source, rng_factory=factory)
        process = run_npc_ranged_simulation_parallel(source, workers=2, batch_size=2, rng_factory=factory)
        window = ObjectiveRateWindow(Fraction(1, 3), Fraction(1, 3), Fraction(1, 3))
        assessments = tuple(assess_ranged_candidate(source, summarize_npc_ranged_simulation(result), window)
                            for result in (sequential, process))
        self.assertEqual(*assessments)
        actual = assessments[0]
        self.assertIs(actual.source_request, source)
        self.assertIs(actual.status, RangedAssessmentStatus.ELIGIBLE)
        self.assertIs(actual.window_match, True)
        self.assertEqual((actual.objective_achieved_rate, actual.side_defeated_rate,
                          actual.round_limit_rate, actual.unsupported_path_rate),
                         (Fraction(1, 3), Fraction(1, 3), Fraction(1, 3), Fraction(0)))
