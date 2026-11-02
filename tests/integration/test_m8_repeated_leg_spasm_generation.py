"""ADR-0054 actual generated repeats and full native staged report sources."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from functools import partial
from itertools import product
from multiprocessing import active_children
import os
from random import getstate
import unittest
from unittest.mock import patch

from tests.integration.test_m8_stationary_wound_generation import family as base_family, HIT
from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from towr.application import magic_evaluation_service as evaluation
from towr.application.magic_candidate_generation import generate_magic_candidates
from towr.application.magic_staged_evaluation_service import evaluate_magic_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.balance.magic_staged_evaluation_models import MagicStagedEvaluationStatus
from towr.domain.condition_models import Condition
from towr.domain.npc_magic_scenario_models import (
    NpcMagicCrushedRibPolicy as CrushedRib, NpcMagicRepeatedLegSpasmPolicy as Repeated,
)
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandResult
from towr.domain.npc_roster_repeated_leg_spasm_models import NpcRosterRepeatedLegSpasmStandResult
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.simulation.npc_magic_models import NpcMagicOutcomeCounts


POLICY = Repeated.STAND_ONCE_WITH_JOURNAL_WITNESSES
CRUSHED_RIB_POLICY = CrushedRib.NEXT_TEST_WITH_JOURNAL_WITNESSES


def family(*, miscast=False, stationary=True, repeated=True, crushed_rib=False, opposite=False):
    base = base_family(miscast=miscast, stationary=stationary, opposite=opposite)
    policy = POLICY if repeated else None
    return replace(base, template_scenario=replace(base.template_scenario,
                   repeated_leg_spasm_continuation=policy,
                   crushed_rib_continuation=CRUSHED_RIB_POLICY if crushed_rib else None),
                   repeated_leg_spasm_continuation=policy,
                   crushed_rib_continuation=CRUSHED_RIB_POLICY if crushed_rib else None)


def script(actor_count, *, stationary=True, repeated=True, tail_kind='normal'):
    if tail_kind == 'wound10': return (*HIT, 10)
    if not stationary: return (*HIT, 9)
    tail = (10,) * (3 + 6 * (actor_count - 2))
    prefix = (*HIT, 9, *tail, *HIT, 4, 5)
    if not repeated: return prefix
    prefix = (*prefix, *tail)
    if tail_kind == 'six': return (*prefix, *HIT, 1, 2, 3, *tail)
    if tail_kind == 'third9': return (*prefix, *HIT, 3, 3, 3)
    return (*prefix, *((10,) * (6 + len(tail))))


def generated_rng(seed, *, actor_count, seeds, mixed, parent_pid=None):
    if parent_pid is not None and os.getpid() == parent_pid:
        raise AssertionError('native spawned candidate must run in child process')
    return Dice(script(actor_count, tail_kind='wound10' if mixed and seeds.index(seed) == 1 else 'normal'))


class RepeatedLegSpasmGenerationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.rng_before = getstate()
        self.children_before = {child.pid for child in active_children()}

    def tearDown(self):
        self.assertEqual(getstate(), self.rng_before)
        self.assertEqual({child.pid for child in active_children()}, self.children_before)

    def test_twelve_generated_policy_combinations_keep_crushed_permission_in_three_and_four_actor_subsets(self):
        for miscast, stationary, repeated, crushed_rib in product((False, True), repeat=4):
            if repeated and not stationary: continue
            source = family(miscast=miscast, stationary=stationary, repeated=repeated,
                            crushed_rib=crushed_rib)
            before = deepcopy(source)
            generated = generate_magic_candidates(source)
            self.assertEqual((source.candidate_count, source.planned_trials), (2, 8))
            for candidate in generated.evaluation_request.candidates:
                actors = len(candidate.scenario.activation_order)
                dice = Dice(script(actors, stationary=stationary, repeated=repeated))
                result = run_npc_magic_scenario(candidate.scenario, dice)
                dice.exhausted()
                with self.subTest(miscast=miscast, stationary=stationary, repeated=repeated,
                                  crushed_rib=crushed_rib, actors=actors):
                    self.assertIs(result.source, candidate.scenario)
                    self.assertIs(candidate.scenario.crushed_rib_continuation,
                                  CRUSHED_RIB_POLICY if crushed_rib else None)
                    self.assertEqual(sum(isinstance(s.result, NpcRosterLegSpasmStandResult) for s in result.steps), int(stationary))
                    self.assertEqual(sum(isinstance(s.result, NpcRosterRepeatedLegSpasmStandResult) for s in result.steps), int(repeated))
                    if repeated:
                        self.assertEqual(dice.calls, 48 if actors == 3 else 66)
                        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
                        self.assertEqual((result.executed_actions, result.completed_rounds), (3 * actors, 3))
                    else:
                        self.assertEqual(dice.calls, (24 if actors == 3 else 30) if stationary else 7)
                        self.assertIs(result.unsupported.reason, Reason.ACTOR_INJURY)
            self.assertEqual(source, before)

    def test_generated_post_repeat_six_expires_and_third_nine_stops_without_reopening_permission(self):
        generated = generate_magic_candidates(family(miscast=True))
        for candidate in generated.evaluation_request.candidates:
            actors = len(candidate.scenario.activation_order)
            for kind in ('six', 'third9', 'wound10'):
                dice = Dice(script(actors, tail_kind=kind))
                result = run_npc_magic_scenario(candidate.scenario, dice)
                dice.exhausted()
                injury = result.current.roster.participant('wizard').state.injury
                if kind == 'six':
                    self.assertEqual(dice.calls, 51 if actors == 3 else 69)
                    self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
                    self.assertEqual(tuple(w.table_total for w in injury.wounds), (9, 9, 6))
                    self.assertFalse(injury.conditions.has(Condition.DRAINED))
                    self.assertFalse(result.current.wound_expiries)
                    self.assertEqual(sum(len(end.expired_sources) for end in result.current.wound_turn_end_receipts), 1)
                    self.assertEqual(len(result.current.champion_attack.daily_wounds.receipts), 3)
                    self.assertEqual(len(injury.active_wound_effects), 2)
                else:
                    self.assertIs(result.unsupported.reason, Reason.ACTOR_INJURY)
                    if kind == 'third9':
                        self.assertEqual(dice.calls, 42 if actors == 3 else 54)
                        self.assertEqual(tuple(w.table_total for w in injury.wounds), (9, 9, 9))
                        self.assertEqual(sum(isinstance(s.result, NpcRosterRepeatedLegSpasmStandResult) for s in result.steps), 1)
                    else:
                        self.assertEqual(dice.calls, 7)

    def assert_sources(self, report, generated):
        self.assertIs(report.source_request, generated.evaluation_request)
        originals = {c.candidate_id: c.scenario for c in generated.evaluation_request.candidates}
        for stage in report.stage_reports:
            for row in stage.candidates:
                assessment = row.assessment
                self.assertIs(assessment.source_request.scenario, originals[row.candidate_id])
                self.assertIs(assessment.source_request.scenario.repeated_leg_spasm_continuation, POLICY)
                self.assertIs(assessment.source_request.scenario.crushed_rib_continuation,
                              generated.source_request.crushed_rib_continuation)
                self.assertEqual(assessment.source_request.scenario.miscast_continuation,
                                 generated.source_request.miscast_continuation)
                self.assertIs(assessment.summary.source_request, assessment.source_request)
                self.assertEqual(assessment.summary.trials, assessment.source_request.trials)

    def test_actual_sequential_spawn_stages_preserve_sources_denominator_budget_and_seed_prefix(self):
        sequential_runner = evaluation.run_npc_magic_simulation
        spawned_runner = evaluation.run_npc_magic_simulation_parallel
        for crushed_rib, mixed in ((True, False), (False, True)):
            generated = generate_magic_candidates(family(miscast=True, crushed_rib=crushed_rib))
            before = deepcopy(generated)
            captures = []

            def factory(source, process=False):
                return partial(generated_rng, actor_count=len(source.scenario.activation_order),
                    seeds=tuple(source.seed_for(i) for i in range(source.trials)), mixed=mixed,
                    parent_pid=os.getpid() if process else None)

            def sequential(source):
                result = sequential_runner(source, rng_factory=factory(source))
                captures.append(result)
                return result

            with (patch.object(evaluation, 'run_npc_magic_simulation', side_effect=sequential) as seq,
                  patch.object(evaluation, 'run_npc_magic_simulation_parallel', side_effect=lambda source, **kw:
                      spawned_runner(source, rng_factory=factory(source, True), **kw)) as proc):
                a = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.SEQUENTIAL))
                b = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.PROCESS, 1, 2))
            self.assertEqual(a, b)
            self.assertEqual([c.args[0] for c in seq.call_args_list], [c.args[0] for c in proc.call_args_list])
            self.assert_sources(a, generated)
            self.assert_sources(b, generated)
            if mixed:
                self.assertIs(a.status, MagicStagedEvaluationStatus.NO_ELIGIBLE_CANDIDATES)
                self.assertEqual((a.total_trials, a.planned_trials), (4, 8))
                for row in a.stage_reports[0].candidates:
                    self.assertEqual(row.assessment.summary.outcome_counts, NpcMagicOutcomeCounts(0, 0, 1, 1))
                    self.assertEqual(row.assessment.summary.trials, 2)
                    self.assertEqual(row.assessment.unsupported_path_rate, Fraction(1, 2))
            else:
                self.assertIs(a.status, MagicStagedEvaluationStatus.COMPLETED)
                self.assertEqual((a.total_trials, a.planned_trials), (8, 8))
                self.assertEqual([r.source_request.trials for r in captures], [2, 2, 4])
                first = next(r for r in captures[:2] if r.source_request.scenario is captures[-1].source_request.scenario)
                self.assertEqual(tuple(t.seed for t in first.trials), tuple(t.seed for t in captures[-1].trials[:2]))
            self.assertEqual(generated, before)

    def test_default_seeded_reports_match_process_in_both_perspectives(self):
        for opposite in (False, True):
            generated = generate_magic_candidates(family(miscast=True, opposite=opposite))
            sequential = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.SEQUENTIAL))
            spawned = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.PROCESS, 1, 2))
            self.assertEqual(sequential, spawned)
            self.assert_sources(sequential, generated)
            self.assert_sources(spawned, generated)
            self.assertLessEqual(sequential.total_trials, sequential.planned_trials)


if __name__ == '__main__':
    unittest.main()
