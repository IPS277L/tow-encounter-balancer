"""ADR-0040 assessment of actual magic outcomes in sequential and spawn runs."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from functools import partial
from multiprocessing import active_children
import os
from random import getstate
import unittest

from tests.integration.test_m8_npc_magic_parallel import scripted_rng
from tests.integration.test_m8_npc_magic_simulation import simulation_scenario
from towr.balance.magic_assessment import assess_magic_candidate
from towr.balance.magic_assessment_models import ObjectiveRateWindow, MagicAssessmentStatus as Status
from towr.simulation.npc_magic_models import NpcMagicOutcomeCounts, NpcMagicSimulationRequest
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation as summarize


class MagicAssessmentIntegrationTests(unittest.TestCase):
    def test_four_outcomes_and_independent_supported_request_have_equal_assessments(self):
        original = NpcMagicSimulationRequest(simulation_scenario(), 42, 4)
        global_rng, children = getstate(), {child.pid for child in active_children()}
        first_records = None
        try:
            for trials in (4, 3):
                with self.subTest(trials=trials):
                    source = replace(original, trials=trials)
                    before = deepcopy(source)
                    seeds = tuple(source.seed_for(i) for i in range(trials))
                    sequential = run_npc_magic_simulation(source, rng_factory=partial(scripted_rng, seeds=seeds))
                    process = run_npc_magic_simulation_parallel(source, workers=2, batch_size=3,
                        rng_factory=partial(scripted_rng, seeds=seeds, parent_pid=os.getpid()))
                    self.assertEqual(sequential, process)
                    self.assertIs(sequential.source_request, source)
                    self.assertIs(process.source_request, source)
                    self.assertTrue(all(record.source_scenario is source.scenario
                                        for result in (sequential, process) for record in result.trials))
                    if first_records is None: first_records = sequential.trials
                    else: self.assertEqual(sequential.trials, first_records[:3])
                    point = F(1, trials)
                    window = ObjectiveRateWindow(point, point, point)
                    summaries = tuple(summarize(result) for result in (sequential, process))
                    assessments = tuple(assess_magic_candidate(source, summary, window) for summary in summaries)
                    self.assertEqual(*summaries)
                    self.assertEqual(*assessments)
                    for actual, summary in zip(assessments, summaries):
                        self.assertIs(actual.source_request, source)
                        self.assertIs(actual.summary, summary)
                        self.assertIs(actual.window, window)
                        self.assertIs(summary.source_request, source)
                        self.assertEqual(summary.outcome_counts, NpcMagicOutcomeCounts(1, 1, 1, trials - 3))
                        self.assertEqual((actual.objective_achieved_rate, actual.perspective_defeated_rate,
                                          actual.round_limit_rate, actual.unsupported_path_rate),
                                         (point, point, point, F(trials - 3, trials)))
                        self.assertEqual((summary.total_action_count, summary.total_started_round_count,
                                          summary.total_completed_round_count),
                                         (24, 10, 9) if trials == 4 else (23, 9, 9))
                        if trials == 4:
                            # Goal meets the point window, but the real Miscast stop remains in N.
                            self.assertIs(actual.status, Status.UNSUPPORTED_OBSERVATIONS)
                            self.assertIsNone(actual.window_match)
                        else:
                            self.assertIs(actual.status, Status.ELIGIBLE)
                            self.assertIs(actual.window_match, True)
                    self.assertEqual(source, before)
        finally:
            self.assertEqual(getstate(), global_rng)
            self.assertEqual({child.pid for child in active_children()}, children)
