"""ADR-0040 application evaluation over actual magic simulation backends."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from functools import partial
from multiprocessing import active_children
import os
from random import getstate
import unittest
from unittest.mock import patch

from tests.integration.test_m8_npc_magic_parallel import scripted_rng
from tests.integration.test_m8_npc_magic_simulation import simulation_scenario
from tests.unit.test_m8_magic_evaluation import request
from towr.application import magic_evaluation_service as service
from towr.application.magic_evaluation_errors import MagicBalanceEvaluationError
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.balance.magic_assessment_models import MagicAssessmentStatus as Status, ObjectiveRateWindow
from towr.balance.magic_evaluation_models import MagicBalanceCandidate as Candidate, MagicBalanceEvaluationRequest as Request
from towr.simulation.npc_magic_models import NpcMagicOutcomeCounts


class MagicEvaluationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.global_rng = getstate()
        self.children = {child.pid for child in active_children()}

    def tearDown(self):
        self.assertEqual(getstate(), self.global_rng)
        self.assertEqual({child.pid for child in active_children()}, self.children)

    def test_real_alternatives_have_equal_reports_across_backends_repeat_reorder_and_rename(self):
        first = simulation_scenario()
        second = replace(first, actors=tuple(replace(actor, target_actor_ids=('wizard', 'ally'))
            if actor.actor_id == 'enemy' else actor for actor in first.actors))
        source = Request((Candidate('ally-first', first), Candidate('wizard-first', second)),
                         42, 4, 8, ObjectiveRateWindow(F(0), F(1, 2), F(1)), 2)
        before = deepcopy(source)
        sequential = service.evaluate_magic_candidates(source, Options(Mode.SEQUENTIAL))
        process = service.evaluate_magic_candidates(source, Options(Mode.PROCESS, 2, 3))
        self.assertEqual(sequential, process)
        self.assertEqual(sequential, service.evaluate_magic_candidates(source, Options(Mode.SEQUENTIAL)))
        for report in (sequential, process):
            self.assertIs(report.source_request, source)
            self.assertEqual(report.total_trials, source.planned_trials)
            self.assertEqual(tuple(r.candidate_id for r in report.candidates), ('ally-first', 'wizard-first'))
            for row, simulation in zip(report.candidates, source.simulation_requests):
                self.assertIs(row.assessment.source_request, simulation)
                self.assertIs(row.assessment.summary.source_request, simulation)
        reordered = service.evaluate_magic_candidates(replace(source, candidates=source.candidates[::-1]), Options(Mode.SEQUENTIAL))
        self.assertEqual({r.candidate_id: r.assessment for r in sequential.candidates},
                         {r.candidate_id: r.assessment for r in reordered.candidates})
        renamed = replace(source, candidates=tuple(replace(c, candidate_id=c.candidate_id + ':new') for c in source.candidates))
        actual = service.evaluate_magic_candidates(renamed, Options(Mode.SEQUENTIAL))
        self.assertEqual(tuple(r.assessment for r in sequential.candidates), tuple(r.assessment for r in actual.candidates))
        self.assertEqual(actual.total_trials, 8)
        self.assertEqual(source, before)

    def test_pool_startup_failure_stays_candidate_error_without_sequential_fallback(self):
        cause = OSError('magic pool startup failed')
        source = request()
        before = deepcopy(source)
        with patch('towr.simulation.npc_magic_parallel.ProcessPoolExecutor', side_effect=cause) as pool, \
                patch.object(service, 'run_npc_magic_simulation') as seq:
            with self.assertRaises(MagicBalanceEvaluationError) as caught:
                service.evaluate_magic_candidates(source, Options(Mode.PROCESS, 2, 1))
            self.assertEqual(caught.exception.candidate_id, source.candidates[0].candidate_id)
            self.assertIs(caught.exception.__cause__, cause)
            pool.assert_called_once()
            seq.assert_not_called()
        self.assertEqual(source, before)

    def test_real_four_outcomes_and_independent_supported_request_keep_all_observations(self):
        scenario = simulation_scenario()
        sequential_runner, process_runner = service.run_npc_magic_simulation, service.run_npc_magic_simulation_parallel
        for trials in (4, 3):
            point = F(1, trials)
            source = Request((Candidate('scripted', scenario),), 42, trials, trials,
                             ObjectiveRateWindow(point, point, point), 1)
            before = deepcopy(source)
            simulation = source.simulation_requests[0]
            seeds = tuple(simulation.seed_for(index) for index in range(trials))
            factory = partial(scripted_rng, seeds=seeds)
            child_factory = partial(scripted_rng, seeds=seeds, parent_pid=os.getpid())
            # Inject only at the existing simulation boundary; both execute actual scenarios.
            with self.subTest(trials=trials), \
                    patch.object(service, 'run_npc_magic_simulation',
                        side_effect=lambda s: sequential_runner(s, rng_factory=factory)) as seq, \
                    patch.object(service, 'run_npc_magic_simulation_parallel',
                        side_effect=lambda s, **kw: process_runner(s, rng_factory=child_factory, **kw)) as proc:
                sequential = service.evaluate_magic_candidates(source, Options(Mode.SEQUENTIAL))
                process = service.evaluate_magic_candidates(source, Options(Mode.PROCESS, 2, 3))
                seq.assert_called_once_with(simulation)
                proc.assert_called_once_with(simulation, workers=2, batch_size=3)
            self.assertEqual(sequential, process)
            for report in (sequential, process):
                self.assertIs(report.source_request, source)
                self.assertEqual(report.total_trials, trials)
                assessment = report.candidates[0].assessment
                self.assertIs(assessment.source_request, simulation)
                self.assertIs(assessment.summary.source_request, simulation)
                self.assertIs(assessment.window, source.window)
                self.assertEqual(assessment.summary.outcome_counts, NpcMagicOutcomeCounts(1, 1, 1, trials - 3))
                self.assertEqual((assessment.summary.total_action_count, assessment.summary.total_started_round_count,
                                  assessment.summary.total_completed_round_count), (24, 10, 9) if trials == 4 else (23, 9, 9))
                self.assertEqual((assessment.objective_achieved_rate, assessment.perspective_defeated_rate,
                                  assessment.round_limit_rate, assessment.unsupported_path_rate),
                                 (point, point, point, F(trials - 3, trials)))
                if trials == 4:
                    self.assertIs(assessment.status, Status.UNSUPPORTED_OBSERVATIONS)
                    self.assertIsNone(assessment.window_match)
                    self.assertEqual(report.selected_candidate_ids, ())
                else:
                    self.assertIs(assessment.status, Status.ELIGIBLE)
                    self.assertIs(assessment.window_match, True)
                    self.assertEqual(report.selected_candidate_ids, ('scripted',))
            self.assertEqual(source, before)
