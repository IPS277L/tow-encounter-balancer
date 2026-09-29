from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from functools import partial
from multiprocessing import active_children
import random
import unittest

from tests.integration.test_m7_npc_mixed_parallel import exact_rng
from tests.integration.test_m7_npc_mixed_simulation import four_outcome_request
from towr.balance.mixed_assessment import assess_mixed_candidate
from towr.balance.mixed_assessment_models import ObjectiveRateWindow, MixedAssessmentStatus as Status
from towr.simulation.npc_mixed_models import NpcMixedOutcomeCounts
from towr.simulation.npc_mixed_parallel import run_npc_mixed_simulation_parallel
from towr.simulation.npc_mixed_simulation import run_npc_mixed_simulation
from towr.simulation.npc_mixed_summary import summarize_npc_mixed_simulation


class M7MixedAssessmentIntegrationTests(unittest.TestCase):
    def test_real_four_outcomes_and_supported_prefix_match_across_backends(self):
        original = four_outcome_request()
        factory = partial(exact_rng, seeds=tuple(original.seed_for(i) for i in range(4)))
        global_rng = random.getstate()
        children = {child.pid for child in active_children()}
        try:
            for trials in (4, 3):
                with self.subTest(trials=trials):
                    source = replace(original, trials=trials)
                    before = deepcopy(source)
                    sequential = run_npc_mixed_simulation(source, rng_factory=factory)
                    process = run_npc_mixed_simulation_parallel(source, workers=2, batch_size=3,
                                                               rng_factory=factory)
                    self.assertEqual(sequential, process)
                    window = ObjectiveRateWindow(F(1, trials), F(1, trials), F(1, trials))
                    summaries = tuple(summarize_npc_mixed_simulation(result) for result in (sequential, process))
                    assessments = tuple(assess_mixed_candidate(source, summary, window) for summary in summaries)
                    self.assertEqual(*summaries)
                    self.assertEqual(*assessments)
                    for actual, summary in zip(assessments, summaries):
                        self.assertIs(actual.source_request, source)
                        self.assertIs(actual.summary, summary)
                        self.assertIs(summary.source_request, source)
                        self.assertEqual(summary.outcome_counts, NpcMixedOutcomeCounts(1, 1, 1, trials - 3))
                        self.assertEqual((actual.objective_achieved_rate, actual.side_defeated_rate,
                                          actual.round_limit_rate, actual.unsupported_path_rate),
                                         (F(1, trials), F(1, trials), F(1, trials), F(trials - 3, trials)))
                        self.assertEqual((summary.total_attack_count, summary.total_visited_round_count),
                                         (17, 6) if trials == 4 else (16, 5))
                        if trials == 4:
                            # Real NO_CANDIDATE, despite the goal rate matching a point window.
                            self.assertIs(actual.status, Status.UNSUPPORTED_OBSERVATIONS)
                            self.assertIsNone(actual.window_match)
                        else:
                            self.assertIs(actual.status, Status.ELIGIBLE)
                            self.assertIs(actual.window_match, True)
                    self.assertEqual(source, before)
        finally:
            self.assertEqual(random.getstate(), global_rng)
            self.assertEqual({child.pid for child in active_children()}, children)
