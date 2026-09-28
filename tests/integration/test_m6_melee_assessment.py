from fractions import Fraction
from functools import partial
import unittest

from tests.integration.test_m6_npc_melee_parallel import exact_rng
from tests.unit.test_m6_npc_melee_scenario import scenario
from towr.balance.melee_assessment import assess_melee_candidate
from towr.balance.melee_assessment_models import ObjectiveRateWindow, MeleeAssessmentStatus
from towr.simulation.npc_melee_models import NpcMeleeSimulationRequest
from towr.simulation.npc_melee_parallel import run_npc_melee_simulation_parallel
from towr.simulation.npc_melee_simulation import run_npc_melee_simulation
from towr.simulation.npc_melee_summary import summarize_npc_melee_simulation


class M6MeleeAssessmentIntegrationTests(unittest.TestCase):
    def test_real_sequential_and_spawn_summaries_produce_identical_assessments(self):
        source = NpcMeleeSimulationRequest(scenario(sizes=(1, 1)), 123, 3)
        factory = partial(exact_rng, seeds=tuple(source.seed_for(i) for i in range(source.trials)))
        sequential = run_npc_melee_simulation(source, rng_factory=factory)
        process = run_npc_melee_simulation_parallel(source, workers=2, batch_size=2, rng_factory=factory)
        window = ObjectiveRateWindow(Fraction(1, 3), Fraction(1, 3), Fraction(1, 3))
        assessments = tuple(assess_melee_candidate(source, summarize_npc_melee_simulation(result), window)
                            for result in (sequential, process))
        self.assertEqual(*assessments)
        actual = assessments[0]
        self.assertIs(actual.source_request, source)
        self.assertIs(actual.status, MeleeAssessmentStatus.ELIGIBLE)
        self.assertIs(actual.window_match, True)
        self.assertEqual((actual.objective_achieved_rate, actual.side_defeated_rate,
                          actual.round_limit_rate, actual.unsupported_path_rate),
                         (Fraction(1, 3), Fraction(1, 3), Fraction(1, 3), Fraction(0)))
