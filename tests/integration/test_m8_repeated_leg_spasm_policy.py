"""Native repeated-stand trial, spawned records and explicit staged reports."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from functools import partial
from multiprocessing import active_children
import os
from random import Random, getstate
import unittest
from unittest.mock import Mock, patch

from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from tests.unit.test_m8_repeated_leg_spasm_policy import scenario, FULL, HIT
from towr.application import magic_evaluation_service as evaluation
from towr.application.magic_staged_evaluation_service import evaluate_magic_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.balance.magic_assessment import assess_magic_candidate
from towr.balance.magic_assessment_models import MagicAssessmentStatus, ObjectiveRateWindow
from towr.balance.magic_evaluation_models import MagicBalanceCandidate
from towr.balance.magic_staged_evaluation_models import MagicStagedEvaluationRequest, MagicBalanceStage
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest, NpcMagicOutcomeCounts
from towr.simulation.npc_magic_simulation import run_npc_magic_trial, run_npc_magic_simulation
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation as summarize


def scripted(seed, *, seeds, repeated=True, mixed=False, parent_pid=None):
    if parent_pid is not None and os.getpid() == parent_pid:
        raise AssertionError('spawn test executed a trial in the parent')
    index = seeds.index(seed)
    return Dice((*HIT, 10) if mixed and index == 1 else FULL if repeated else FULL[:24])


def child_random(seed, *, parent_pid):
    if os.getpid() == parent_pid:
        raise AssertionError('seeded spawn trial executed in the parent')
    return Random(seed)


class RepeatedLegSpasmPropagationTests(unittest.TestCase):
    def setUp(self):
        self.rng_before = getstate()
        self.children_before = {p.pid for p in active_children()}

    def tearDown(self):
        self.assertEqual(getstate(), self.rng_before)
        self.assertEqual({p.pid for p in active_children()}, self.children_before)

    def test_actual_trial_counts_two_stands_as_phases_not_actions(self):
        request = NpcMagicSimulationRequest(scenario(), 42, 1)
        before = deepcopy(request)
        dice = Dice(FULL)
        record = run_npc_magic_trial(request, 0, rng_factory=lambda _: dice)
        dice.exhausted()
        self.assertEqual((record.outcome, record.executed_action_count, record.started_round_count,
                          record.completed_round_count), (Outcome.ROUND_LIMIT_REACHED, 9, 3, 3))
        self.assertIs(record.source_scenario, request.scenario)
        self.assertEqual(request, before)

    def test_scripted_sequential_spawn_full_source_summary_and_denominator(self):
        request = NpcMagicSimulationRequest(scenario(), 42, 2)
        before = deepcopy(request)
        seeds = tuple(request.seed_for(i) for i in range(2))
        sequential = run_npc_magic_simulation(request, rng_factory=partial(scripted, seeds=seeds, mixed=True))
        spawned = run_npc_magic_simulation_parallel(request, workers=1, batch_size=1,
            rng_factory=partial(scripted, seeds=seeds, mixed=True, parent_pid=os.getpid()))
        self.assertEqual(sequential, spawned)
        self.assertEqual(summarize(sequential), summarize(spawned))
        self.assertEqual(spawned.outcome_counts, NpcMagicOutcomeCounts(0, 0, 1, 1))
        self.assertTrue(all(t.source_scenario is request.scenario for t in spawned.trials))
        self.assertEqual(tuple(t.seed for t in spawned.trials), seeds)
        assessment = assess_magic_candidate(request, summarize(spawned), ObjectiveRateWindow(F(0), F(1, 2), F(1)))
        self.assertEqual(assessment.unsupported_path_rate, F(1, 2))
        self.assertEqual(assessment.round_limit_rate, F(1, 2))
        self.assertIs(assessment.status, MagicAssessmentStatus.UNSUPPORTED_OBSERVATIONS)
        self.assertEqual(request, before)

    def test_default_seeded_sequential_spawn_parity_has_no_cross_runtime_oracle(self):
        request = NpcMagicSimulationRequest(scenario(miscast=True), 613, 3)
        sequential = run_npc_magic_simulation(request)
        spawned = run_npc_magic_simulation_parallel(request, workers=1, batch_size=2,
            rng_factory=partial(child_random, parent_pid=os.getpid()))
        self.assertEqual(sequential, spawned)
        self.assertEqual(summarize(sequential), summarize(spawned))
        self.assertTrue(all(t.source_scenario is request.scenario for t in spawned.trials))

    def test_detached_source_rejected_parent_side_before_rng_or_pool(self):
        for kind in ('facts', 'permission'):
            request = NpcMagicSimulationRequest(scenario(), 42, 2)
            if kind == 'facts': object.__setattr__(request.scenario.facts, 'no_external_condition_sources', 1)
            else: object.__setattr__(request.scenario, 'repeated_leg_spasm_continuation',
                                    request.scenario.repeated_leg_spasm_continuation.value)
            rng = Mock(side_effect=AssertionError('invalid source must not create RNG'))
            with patch('towr.simulation.npc_magic_parallel.ProcessPoolExecutor',
                       side_effect=AssertionError('invalid source must not open pool')) as pool:
                with self.subTest(kind=kind):
                    with self.assertRaises(TypeError): run_npc_magic_trial(request, 0, rng_factory=rng)
                    with self.assertRaises(TypeError): run_npc_magic_simulation(request, rng_factory=rng)
                    with self.assertRaises(TypeError): run_npc_magic_simulation_parallel(request, workers=1, rng_factory=rng)
                rng.assert_not_called()
                pool.assert_not_called()

    def test_explicit_list_staged_reports_preserve_new_permission_and_common_seed_prefix(self):
        candidates = (MagicBalanceCandidate('new', scenario()),
                      MagicBalanceCandidate('old', scenario(repeated=False)))
        request = MagicStagedEvaluationRequest(candidates, 42,
            (MagicBalanceStage(2, 1), MagicBalanceStage(4, 1)), 8,
            ObjectiveRateWindow(F(0), F(1, 2), F(1)))
        before = deepcopy(request)
        captured = []

        def execute(source, process=False, **kwargs):
            seeds = tuple(source.seed_for(i) for i in range(source.trials))
            factory = partial(scripted, seeds=seeds,
                repeated=source.scenario.repeated_leg_spasm_continuation is not None,
                parent_pid=os.getpid() if process else None)
            result = (run_npc_magic_simulation_parallel(source, rng_factory=factory, **kwargs) if process
                      else run_npc_magic_simulation(source, rng_factory=factory))
            captured.append(result)
            return result

        with patch.object(evaluation, 'run_npc_magic_simulation', side_effect=execute), \
                patch.object(evaluation, 'run_npc_magic_simulation_parallel',
                             side_effect=lambda source, **kw: execute(source, True, **kw)):
            sequential = evaluate_magic_candidates_staged(request, Options(Mode.SEQUENTIAL))
            spawned = evaluate_magic_candidates_staged(request, Options(Mode.PROCESS, 1, 2))
        self.assertEqual(sequential, spawned)
        self.assertEqual(sequential.total_trials, 8)
        self.assertEqual(len(sequential.stage_reports), 2)
        for report in sequential.stage_reports:
            for row in report.candidates:
                expected = next(c.scenario for c in candidates if c.candidate_id == row.candidate_id)
                self.assertIs(row.assessment.source_request.scenario, expected)
                self.assertIs(row.assessment.summary.source_request.scenario, expected)
                self.assertEqual(row.assessment.summary.trials, report.source_request.trials_per_candidate)
        for result in captured:
            self.assertEqual(tuple(t.seed for t in result.trials), tuple(result.source_request.seed_for(i)
                for i in range(result.source_request.trials)))
        self.assertEqual(captured[0].trials, captured[2].trials[:2])
        self.assertEqual(request, before)


if __name__ == '__main__':
    unittest.main()
