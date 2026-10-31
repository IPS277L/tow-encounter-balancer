"""ADR-0047 generated opt-in sources through actual Wind and staged spawn."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from functools import partial
from multiprocessing import active_children
import os
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_magic_candidate_generation_models import request, Stage, Window
from tests.unit.test_m8_miscast_continuation_policy import continuation_policy
from tests.unit.test_m8_npc_magic_scenario import frame
from tests.unit.test_m8_npc_magic_scenario_runner import departures, Dice
from towr.application import magic_evaluation_service as evaluation
from towr.application.magic_candidate_generation import generate_magic_candidates
from towr.application.magic_staged_evaluation_service import evaluate_magic_candidates_staged
from towr.application.ranged_simulation_models import (
    SimulationExecutionMode as Mode, SimulationExecutionOptions as Options,
)
from towr.balance.magic_assessment_models import MagicAssessmentStatus
from towr.balance.magic_staged_evaluation_models import MagicStagedEvaluationStatus
from towr.domain.condition_models import Condition
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome
from towr.domain.npc_roster_miscast_models import NpcRosterUnnaturalWindResult
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.simulation.npc_magic_models import NpcMagicOutcomeCounts


def family(*, opted=True):
    """All reserve actors are authored in one open Zone; omitted actors are absent."""
    source = request()
    old = source.template_scenario
    initial = replace(old.initial, spatial_state=replace(old.initial.spatial_state,
        placements=tuple(replace(p, zone_id='arena') for p in old.initial.spatial_state.placements)))
    template = departures(replace(old, initial=initial, max_rounds=1,
        activation_order=tuple(p.state.actor_id for p in initial.roster.participants),
        scene_frames=(frame(initial),)))
    policy = continuation_policy() if opted else None
    template = replace(template, miscast_continuation=policy)
    return replace(source, template_scenario=template, scene_frames=template.scene_frames,
        miscast_continuation=policy, stages=(Stage(2, 2), Stage(4, 1)),
        max_total_trials=16, window=Window(F(0), F(1, 2), F(1)))


def script(actor_count, kind):
    # Prone Wizard remains prone until its next activation, so every incoming
    # shot loses one die. Ally also shoots a still-Prone opponent before stand.
    if kind == 'wind':
        return (9, 9, 9, 7, 7, 7) + (10,) * (5 * (actor_count - 1))
    if kind == 'other-row':
        return (9, 9, 9, 1, 1, 1)
    return (10,) * (3 + 6 * (actor_count - 1))


def generated_rng(seed, *, actor_count, seeds=None, parent_pid=None):
    """Picklable finite factory; no executor/source substitution in workers."""
    if parent_pid is not None and os.getpid() == parent_pid:
        raise AssertionError('generated opt-in RNG must execute in a spawn child')
    kind = 'wind' if seeds is None else ('wind', 'ordinary', 'other-row')[seeds.index(seed)]
    return Dice(script(actor_count, kind))


class OptedMagicGenerationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.rng_before = getstate()
        self.children_before = {child.pid for child in active_children()}

    def tearDown(self):
        self.assertEqual(getstate(), self.rng_before)
        self.assertEqual({child.pid for child in active_children()}, self.children_before)

    def assert_sources(self, report, generated):
        self.assertIs(report.source_request, generated.evaluation_request)
        originals = {c.candidate_id: c.scenario for c in generated.evaluation_request.candidates}
        for stage in report.stage_reports:
            for row in stage.candidates:
                assessment = row.assessment
                source = assessment.source_request
                self.assertIs(source.scenario, originals[row.candidate_id])
                self.assertIs(source.scenario.miscast_continuation,
                              generated.source_request.miscast_continuation)
                self.assertIs(assessment.summary.source_request, source)
                self.assertEqual(assessment.summary.trials, source.trials)

    def scripted_reports(self, generated, *, mixed=False):
        sequential_runner = evaluation.run_npc_magic_simulation
        process_runner = evaluation.run_npc_magic_simulation_parallel
        captures = []

        def factory(source, process=False):
            return partial(generated_rng, actor_count=len(source.scenario.activation_order),
                seeds=tuple(source.seed_for(i) for i in range(source.trials)) if mixed else None,
                parent_pid=os.getpid() if process else None)

        def sequential(source):
            result = sequential_runner(source, rng_factory=factory(source))
            captures.append(result)
            return result

        # Only existing RNG injection boundaries are patched. Generation,
        # staged/bounded assessment and both executors remain production.
        with patch.object(evaluation, 'run_npc_magic_simulation', side_effect=sequential) as seq_calls, \
                patch.object(evaluation, 'run_npc_magic_simulation_parallel',
                    side_effect=lambda s, **kw: process_runner(s, rng_factory=factory(s, True), **kw)) as proc_calls:
            seq = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.SEQUENTIAL))
            proc = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.PROCESS, 2, 2))
        self.assertEqual(seq, proc)
        self.assertEqual([c.args[0] for c in seq_calls.call_args_list],
                         [c.args[0] for c in proc_calls.call_args_list])
        self.assertTrue(all(c.kwargs == {'workers': 2, 'batch_size': 2} for c in proc_calls.call_args_list))
        self.assert_sources(seq, generated)
        self.assert_sources(proc, generated)
        for result in captures:
            self.assertTrue(all(r.source_scenario is result.source_request.scenario for r in result.trials))
        return seq, captures

    def test_generated_wind_targets_only_retained_live_actors_and_none_keeps_legacy_sources(self):
        source = family()
        before = deepcopy(source)
        generated = generate_magic_candidates(source)
        legacy_source = family(opted=False)
        legacy = generate_magic_candidates(legacy_source)
        self.assertEqual(generate_magic_candidates(replace(legacy_source, miscast_continuation=None)), legacy)
        reserve_ids = {p.state.actor_id for p in source.template_scenario.initial.roster.participants}
        self.assertEqual(len(generated.evaluation_request.candidates), 4)
        for candidate, old in zip(generated.evaluation_request.candidates,
                                  legacy.evaluation_request.candidates, strict=True):
            with self.subTest(candidate=candidate.candidate_id):
                scenario = candidate.scenario
                self.assertEqual(replace(scenario, miscast_continuation=None), old.scenario)
                self.assertEqual(candidate.candidate_id, old.candidate_id)
                self.assertIs(scenario.miscast_continuation, source.miscast_continuation)
                expected = tuple(p.state.actor_id for p in scenario.initial.roster.participants)
                dice = Dice(script(len(expected), 'wind'))
                result = run_npc_magic_scenario(scenario, dice)
                dice.exhausted()
                winds = [s for s in result.steps if isinstance(s.result, NpcRosterUnnaturalWindResult)]
                self.assertEqual(len(winds), 1)
                wind = winds[0]
                self.assertEqual(tuple(t.target_id for t in wind.result.wind.targets), expected)
                self.assertEqual(tuple(p.entity_id for p in wind.before.spatial_state.placements), expected)
                self.assertTrue(all(p.state.injury.conditions.has(Condition.PRONE)
                                    for p in wind.after.roster.participants))
                self.assertTrue((reserve_ids - set(expected)).isdisjoint(
                    t.target_id for t in wind.result.wind.targets))
                self.assertEqual(result.outcome, Outcome.ROUND_LIMIT_REACHED)
                self.assertEqual(result.executed_actions, len(expected))
                # None still stops immediately at the original pending phase.
                legacy_dice = Dice((9, 9, 9))
                stopped = run_npc_magic_scenario(old.scenario, legacy_dice)
                legacy_dice.exhausted()
                self.assertEqual(stopped.outcome, Outcome.UNSUPPORTED_PATH)
                self.assertEqual(stopped.executed_actions, 1)
        self.assertEqual(source, before)

    def test_generated_default_seeded_reports_match_real_spawn_without_rate_predictions(self):
        source = family()
        before = deepcopy(source)
        generated = generate_magic_candidates(source)
        sequential = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.SEQUENTIAL))
        process = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.PROCESS, 2, 3))
        self.assertEqual(sequential, process)
        self.assertEqual(sequential.planned_trials, 16)
        self.assertLessEqual(sequential.total_trials, sequential.planned_trials)
        self.assert_sources(sequential, generated)
        self.assert_sources(process, generated)
        self.assertEqual(source, before)

    def test_generated_wind_pays_full_repeated_stage_budget_and_preserves_seed_prefixes(self):
        source = family()
        before = deepcopy(source)
        generated = generate_magic_candidates(source)
        report, runs = self.scripted_reports(generated)
        self.assertIs(report.status, MagicStagedEvaluationStatus.COMPLETED)
        self.assertEqual([r.source_request.trials for r in runs], [2, 2, 2, 2, 4, 4])
        self.assertEqual((report.total_trials, report.planned_trials, source.max_total_trials), (16, 16, 16))
        for run in runs:
            n = run.source_request.trials
            self.assertEqual(run.outcome_counts, NpcMagicOutcomeCounts(0, 0, n, 0))
            self.assertTrue(all(r.executed_action_count == len(run.source_request.scenario.activation_order)
                                for r in run.trials))
        for last in runs[4:]:
            first = next(r for r in runs[:4] if r.source_request.scenario is last.source_request.scenario)
            self.assertEqual(tuple(r.seed for r in first.trials), tuple(r.seed for r in last.trials[:2]))
        self.assertEqual(source, before)

    def test_generated_other_row_stays_in_denominator_and_stops_stages_without_partial_family(self):
        source = replace(family(), stages=(Stage(3, 2), Stage(6, 1)), max_total_trials=24)
        before = deepcopy(source)
        generated = generate_magic_candidates(source)
        report, runs = self.scripted_reports(generated, mixed=True)
        self.assertIs(report.status, MagicStagedEvaluationStatus.NO_ELIGIBLE_CANDIDATES)
        self.assertEqual((report.total_trials, report.planned_trials), (12, 24))
        self.assertEqual(report.selected_candidate_ids, ())
        self.assertEqual(len(report.stage_reports), 1)
        self.assertEqual(len(runs), 4)
        for row in report.stage_reports[0].candidates:
            assessment = row.assessment
            self.assertEqual(assessment.summary.outcome_counts, NpcMagicOutcomeCounts(0, 0, 2, 1))
            self.assertEqual(assessment.summary.trials, 3)
            self.assertEqual((assessment.round_limit_rate, assessment.unsupported_path_rate), (F(2, 3), F(1, 3)))
            self.assertIs(assessment.status, MagicAssessmentStatus.UNSUPPORTED_OBSERVATIONS)
            self.assertIsNone(assessment.window_match)
        self.assertEqual(source, before)


if __name__ == '__main__':
    unittest.main()
