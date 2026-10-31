"""ADR-0046 opted runtime through native trials, spawn and explicit assessment."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from functools import partial
from multiprocessing import active_children
import os
from random import Random, getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from tests.unit.test_m8_opted_miscast_runner import opted
from towr.application import magic_evaluation_service as evaluation
from towr.application.magic_evaluation_errors import MagicBalanceEvaluationError
from towr.application.ranged_simulation_models import (
    SimulationExecutionMode as Mode, SimulationExecutionOptions as Options,
)
from towr.balance.magic_assessment import assess_magic_candidate
from towr.balance.magic_assessment_models import MagicAssessmentStatus, ObjectiveRateWindow
from towr.balance.magic_evaluation_models import MagicBalanceCandidate, MagicBalanceEvaluationRequest
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome
from towr.domain.npc_roster_miscast_models import NpcRosterUnnaturalWindResult
from towr.domain.npc_roster_prone_models import NpcRosterProneStandResult, NpcRosterProneTurnEndResult
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.simulation.npc_magic_models import (
    NpcMagicOutcomeCounts, NpcMagicSimulationRequest, NpcMagicSimulationResult,
)
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation, run_npc_magic_trial
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation as summarize


# These are finite rule witnesses, not asserted Monte Carlo probabilities.
SCRIPTS = (
    (9, 9, 9, 7, 7, 7) + (10,) * 10,  # Wind, Prone end, two stands, round limit
    (10,) * 3 + (1, 2, 3, 10, 10, 10),  # completed ordinary objective
    (9, 9, 9, 1, 1, 1),  # another actual Miscast row remains unsupported
)


def opted_rng(seed, *, seeds, parent_pid=None):
    if parent_pid is not None and os.getpid() == parent_pid:
        raise AssertionError("opted trial must execute in the spawn child")
    return Dice(SCRIPTS[seeds.index(seed)])


def child_random(seed, *, parent_pid):
    if os.getpid() == parent_pid:
        raise AssertionError("opted trial must execute in the spawn child")
    return Random(seed)


class FailingMiscastDice(Dice):
    def randint(self, low, high):
        if self.calls == 3:
            raise RuntimeError("opted Miscast table RNG failed")
        return super().randint(low, high)


def failing_miscast_rng(seed, *, parent_pid=None):
    if parent_pid is not None and os.getpid() == parent_pid:
        raise AssertionError("opted trial must execute in the spawn child")
    return FailingMiscastDice((9, 9, 9))


class OptedMiscastPropagationTests(unittest.TestCase):
    def setUp(self):
        self.global_rng = getstate()
        self.children = {child.pid for child in active_children()}
        self.request = NpcMagicSimulationRequest(opted(max_rounds=1), 42, 3)
        self.seeds = tuple(self.request.seed_for(i) for i in range(3))

    def tearDown(self):
        self.assertEqual(getstate(), self.global_rng)
        self.assertEqual({child.pid for child in active_children()}, self.children)

    def test_actual_wind_journal_projects_into_trial_without_counting_phases_as_actions(self):
        before = deepcopy(self.request)
        dice = Dice(SCRIPTS[0])
        replay = run_npc_magic_scenario(self.request.scenario, dice)
        dice.exhausted()
        self.assertEqual(sum(isinstance(s.result, NpcRosterUnnaturalWindResult) for s in replay.steps), 1)
        self.assertEqual(sum(isinstance(s.result, NpcRosterProneStandResult) for s in replay.steps), 2)
        self.assertEqual(sum(isinstance(s.result, NpcRosterProneTurnEndResult) for s in replay.steps), 1)
        stream = Dice(SCRIPTS[0])
        record = run_npc_magic_trial(self.request, 0, rng_factory=lambda seed: stream)
        stream.exhausted()
        self.assertEqual((record.outcome, record.executed_action_count, record.started_round_count,
                          record.completed_round_count), (Outcome.ROUND_LIMIT_REACHED, 3, 1, 1))
        self.assertEqual((record.executed_action_count, record.started_round_count, record.completed_round_count),
                         (replay.executed_actions, replay.started_rounds, replay.completed_rounds))
        self.assertGreater(len(replay.steps), record.executed_action_count)
        self.assertIs(record.source_scenario, self.request.scenario)
        self.assertEqual(self.request, before)

    def test_scripted_sequential_spawn_full_source_parity_and_unsupported_denominator(self):
        before = deepcopy(self.request)
        sequential = run_npc_magic_simulation(self.request,
            rng_factory=partial(opted_rng, seeds=self.seeds))
        process = run_npc_magic_simulation_parallel(self.request, workers=2, batch_size=2,
            rng_factory=partial(opted_rng, seeds=self.seeds, parent_pid=os.getpid()))
        self.assertEqual(process, sequential)
        window = ObjectiveRateWindow(Fraction(1, 3), Fraction(1, 3), Fraction(1, 3))
        for result in (sequential, process):
            self.assertIs(result.source_request, self.request)
            self.assertEqual(result.outcome_counts, NpcMagicOutcomeCounts(1, 0, 1, 1))
            self.assertEqual(tuple(r.seed for r in result.trials), self.seeds)
            self.assertEqual(tuple(r.trial_index for r in result.trials), (0, 1, 2))
            for record in result.trials:
                self.assertIs(record.source_scenario, self.request.scenario)
                self.assertIs(record.source_scenario.miscast_continuation,
                              self.request.scenario.miscast_continuation)
            summary = summarize(result)
            self.assertIs(summary.source_request, self.request)
            self.assertEqual(summary.trials, 3)
            assessment = assess_magic_candidate(self.request, summary, window)
            self.assertEqual((assessment.objective_achieved_rate, assessment.round_limit_rate,
                              assessment.unsupported_path_rate), (Fraction(1, 3),) * 3)
            self.assertEqual(assessment.perspective_defeated_rate, 0)
            self.assertIs(assessment.status, MagicAssessmentStatus.UNSUPPORTED_OBSERVATIONS)
            self.assertIsNone(assessment.window_match)
        self.assertEqual(summarize(process), summarize(sequential))
        self.assertEqual(self.request, before)

    def test_default_seeded_spawn_keeps_complete_opted_records_without_exact_rate_expectations(self):
        before = deepcopy(self.request)
        sequential = run_npc_magic_simulation(self.request)
        process = run_npc_magic_simulation_parallel(self.request, workers=1, batch_size=8,
            rng_factory=partial(child_random, parent_pid=os.getpid()))
        self.assertEqual(process, sequential)
        self.assertEqual(summarize(process), summarize(sequential))
        self.assertIs(process.source_request, self.request)
        self.assertTrue(all(r.source_scenario is self.request.scenario for r in process.trials))
        self.assertEqual(self.request, before)

    def test_explicit_candidates_preserve_policy_and_all_observations_across_backends(self):
        first = self.request.scenario
        second = replace(first, id=first.id + ':other-explicit-candidate')
        source = MagicBalanceEvaluationRequest(
            (MagicBalanceCandidate('first', first), MagicBalanceCandidate('second', second)),
            42, 3, 6, ObjectiveRateWindow(Fraction(0), Fraction(1, 3), Fraction(1)), 2)
        before = deepcopy(source)
        sequential_runner = evaluation.run_npc_magic_simulation
        process_runner = evaluation.run_npc_magic_simulation_parallel
        with patch.object(evaluation, 'run_npc_magic_simulation', side_effect=lambda s:
                sequential_runner(s, rng_factory=partial(opted_rng, seeds=self.seeds))), \
                patch.object(evaluation, 'run_npc_magic_simulation_parallel', side_effect=lambda s, **kw:
                    process_runner(s, rng_factory=partial(opted_rng, seeds=self.seeds,
                                                          parent_pid=os.getpid()), **kw)):
            sequential = evaluation.evaluate_magic_candidates(source, Options(Mode.SEQUENTIAL))
            process = evaluation.evaluate_magic_candidates(source, Options(Mode.PROCESS, 2, 2))
        self.assertEqual(sequential, process)
        for report in (sequential, process):
            self.assertIs(report.source_request, source)
            self.assertEqual(report.total_trials, 6)
            self.assertEqual(report.selected_candidate_ids, ())
            for row, simulation in zip(report.candidates, source.simulation_requests, strict=True):
                self.assertIs(row.assessment.source_request, simulation)
                self.assertIs(row.assessment.summary.source_request, simulation)
                self.assertIsNotNone(simulation.scenario.miscast_continuation)
                self.assertEqual(row.assessment.summary.outcome_counts, NpcMagicOutcomeCounts(1, 0, 1, 1))
                self.assertEqual(row.assessment.unsupported_path_rate, Fraction(1, 3))
                self.assertIs(row.assessment.status, MagicAssessmentStatus.UNSUPPORTED_OBSERVATIONS)
        self.assertEqual(source, before)

    def test_same_id_and_seed_cannot_substitute_legacy_source_for_opted_records_or_summary(self):
        result = run_npc_magic_simulation(self.request, rng_factory=partial(opted_rng, seeds=self.seeds))
        legacy = replace(self.request, scenario=replace(self.request.scenario, miscast_continuation=None))
        self.assertEqual(legacy.scenario.id, self.request.scenario.id)
        self.assertEqual(legacy.seed_for(0), self.request.seed_for(0))
        with self.assertRaises(ValueError):
            NpcMagicSimulationResult(legacy, result.trials)
        window = ObjectiveRateWindow(Fraction(0), Fraction(1, 2), Fraction(1))
        with self.assertRaises(ValueError):
            assess_magic_candidate(legacy, summarize(result), window)

    def test_actual_table_rng_failure_remains_exception_in_sequential_and_process(self):
        before = deepcopy(self.request)
        with self.assertRaisesRegex(RuntimeError, 'opted Miscast table RNG failed'):
            run_npc_magic_simulation(self.request, rng_factory=failing_miscast_rng)
        with self.assertRaisesRegex(RuntimeError, 'opted Miscast table RNG failed'):
            run_npc_magic_simulation_parallel(self.request, workers=1, batch_size=3,
                rng_factory=partial(failing_miscast_rng, parent_pid=os.getpid()))
        self.assertEqual(self.request, before)

    def test_evaluation_table_failure_retains_candidate_and_cause_without_fallback(self):
        source = MagicBalanceEvaluationRequest((MagicBalanceCandidate('opted', self.request.scenario),),
            42, 3, 3, ObjectiveRateWindow(Fraction(0), Fraction(1, 2), Fraction(1)), 1)
        before = deepcopy(source)
        process_runner = evaluation.run_npc_magic_simulation_parallel
        with patch.object(evaluation, 'run_npc_magic_simulation') as sequential, \
                patch.object(evaluation, 'run_npc_magic_simulation_parallel', side_effect=lambda s, **kw:
                    process_runner(s, rng_factory=partial(failing_miscast_rng, parent_pid=os.getpid()), **kw)):
            with self.assertRaises(MagicBalanceEvaluationError) as caught:
                evaluation.evaluate_magic_candidates(source, Options(Mode.PROCESS, 1, 3))
            sequential.assert_not_called()
        self.assertEqual(caught.exception.candidate_id, 'opted')
        self.assertIsInstance(caught.exception.__cause__, RuntimeError)
        self.assertEqual(str(caught.exception.__cause__), 'opted Miscast table RNG failed')
        self.assertEqual(source, before)


if __name__ == '__main__':
    unittest.main()
