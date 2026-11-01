"""ADR-0051 actual generated Wounds through native staged and spawned reports."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from functools import partial
from multiprocessing import active_children
import os
from pathlib import Path
from random import getstate
import sys
import unittest
from unittest.mock import patch

from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from towr.application import magic_evaluation_service as evaluation
from towr.application.magic_balance_errors import MagicBalanceGenerationError
from towr.application.magic_balance_models import MagicBalanceCommand
from towr.application.magic_balance_service import execute_magic_balance
from towr.application.magic_candidate_generation import generate_magic_candidates
from towr.application.magic_candidate_generation_models import MagicCandidateGenerationRequest, MagicCompositionGroup
from towr.application.magic_staged_evaluation_service import evaluate_magic_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.balance.magic_assessment_models import MagicAssessmentStatus
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage as Stage, MagicStagedEvaluationStatus
from towr.balance.ranged_assessment_models import ObjectiveRateWindow as Window
from towr.domain.condition_models import Condition
from towr.domain.npc_champion_attack_models import NpcChampionAttackState
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandResult
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.turn_models import CombatRoundState, CombatSide
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.simulation.npc_magic_models import NpcMagicOutcomeCounts


def family(*, stationary=True, miscast=False, opposite=False):
    """Actual public Wizard4 source plus one explicit variable allied reserve."""
    examples = Path(__file__).resolve().parents[2] / 'docs/examples/m8'
    with patch.object(sys, 'path', [str(examples), *sys.path]):
        from stationary_wound_runner import authored_input
        base = authored_input(stationary=stationary, miscast=miscast)
    ally = base.initial.roster.participant('ally')
    roster = NpcRoster((*base.initial.roster.participants,
        replace(ally, state=replace(ally.state, actor_id='ally2'))))
    combat = CombatRoundState(1, roster.turn_participants)
    spatial = replace(base.initial.spatial_state, placements=(*base.initial.spatial_state.placements,
        replace(base.initial.spatial_state.placement_for('ally'), entity_id='ally2')))
    initial = replace(base.initial, roster=roster, round_state=combat, spatial_state=spatial,
        champion_attack=NpcChampionAttackState(roster, combat, base.initial.champion_attack.daily_wounds))
    ally_policy = base.policy_for('ally')
    enemy_policy = base.policy_for('enemy')
    actors = tuple(replace(p, target_actor_ids=(*p.target_actor_ids, 'ally2'),
        defeat_decisions=(*p.defeat_decisions, replace(p.defeat_decisions[0], target_id='ally2')))
        if p.actor_id == 'enemy' else p for p in base.actors)
    actors = (*actors, replace(ally_policy, actor_id='ally2', defeat_decisions=tuple(
        replace(d, attacker_id='ally2') for d in ally_policy.defeat_decisions)))
    frames = tuple(replace(frame, key=replace(frame.key,
        placements=(*frame.key.placements, replace(next(p for p in frame.key.placements
            if p.entity_id == 'ally'), entity_id='ally2')),
        live_actor_ids=(*frame.key.live_actor_ids, 'ally2')),
        pair_ranges=(*frame.pair_ranges, *(replace(p, first_actor_id='ally2')
            for p in frame.pair_ranges if p.first_actor_id == 'ally')),
        attack_departures=(*frame.attack_departures, replace(next(d for d in frame.attack_departures
            if d.actor_id == 'ally'), actor_id='ally2'))) for frame in base.scene_frames)
    template = replace(base, initial=initial, actors=actors, scene_frames=frames,
        activation_order=(*base.activation_order, 'ally2'),
        perspective_side=CombatSide.OPPOSITION if opposite else CombatSide.PLAYERS_AND_ALLIES,
        objective=NpcDefeatObjective(('enemy',) if opposite else ('wizard', 'ally', 'ally2')))
    groups = ((MagicCompositionGroup('enemy', ('enemy',), 1, 1),) if opposite else
              (MagicCompositionGroup('allies', ('ally', 'ally2'), 1, 2),))
    return MagicCandidateGenerationRequest(template, groups, template.facts, template.scene_frames,
        'generated:stationary', 2, 42, (Stage(2, 1), Stage(4, 1)), 8,
        Window(F(0), F(1, 2), F(1)), template.miscast_continuation,
        template.stationary_wound_continuation)


HIT = (1, 2, 3, 10, 10, 10)


def script(actor_count, *, stationary, other_wound=False):
    if other_wound:
        return (*HIT, 10)
    if not stationary:
        return (*HIT, 9)
    tail = (10,) * (3 + 6 * (actor_count - 2))  # Wizard then all allied archers.
    return (*HIT, 9, *tail, *HIT, 1, 5, *tail, *((10,) * (6 + len(tail))))


def generated_rng(seed, *, actor_count, stationary, seeds, mixed, parent_pid=None):
    """Top-level picklable factory; native worker execution remains real."""
    if parent_pid is not None and os.getpid() == parent_pid:
        raise AssertionError('generated trial must run in spawned child')
    index = seeds.index(seed)
    return Dice(script(actor_count, stationary=stationary, other_wound=mixed and index == 1))


class StationaryWoundGenerationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.rng_before = getstate()
        self.children_before = {p.pid for p in active_children()}

    def tearDown(self):
        self.assertEqual(getstate(), self.rng_before)
        self.assertEqual({p.pid for p in active_children()}, self.children_before)

    def assert_sources(self, report, generated):
        self.assertIs(report.source_request, generated.evaluation_request)
        originals = {c.candidate_id: c.scenario for c in generated.evaluation_request.candidates}
        for stage in report.stage_reports:
            for row in stage.candidates:
                assessment = row.assessment
                source = assessment.source_request
                self.assertIs(source.scenario, originals[row.candidate_id])
                self.assertIs(source.scenario.stationary_wound_continuation,
                              generated.source_request.stationary_wound_continuation)
                self.assertEqual(source.scenario.miscast_continuation, generated.source_request.miscast_continuation)
                self.assertIs(assessment.summary.source_request, source)
                self.assertEqual(assessment.summary.trials, source.trials)

    def scripted_reports(self, generated, *, mixed):
        sequential_runner = evaluation.run_npc_magic_simulation
        process_runner = evaluation.run_npc_magic_simulation_parallel
        captures = []

        def rng(source, process=False):
            return partial(generated_rng, actor_count=len(source.scenario.activation_order),
                stationary=source.scenario.stationary_wound_continuation is not None,
                seeds=tuple(source.seed_for(i) for i in range(source.trials)), mixed=mixed,
                parent_pid=os.getpid() if process else None)

        def sequential(source):
            result = sequential_runner(source, rng_factory=rng(source))
            captures.append(result)
            return result

        with patch.object(evaluation, 'run_npc_magic_simulation', side_effect=sequential) as seq_calls, \
                patch.object(evaluation, 'run_npc_magic_simulation_parallel', side_effect=lambda source, **kw:
                    process_runner(source, rng_factory=rng(source, True), **kw)) as proc_calls:
            seq = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.SEQUENTIAL))
            proc = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.PROCESS, 1, 2))
        self.assertEqual(seq, proc)
        self.assertEqual([c.args[0] for c in seq_calls.call_args_list], [c.args[0] for c in proc_calls.call_args_list])
        self.assertTrue(all(c.kwargs == {'workers': 1, 'batch_size': 2} for c in proc_calls.call_args_list))
        self.assert_sources(seq, generated)
        self.assert_sources(proc, generated)
        for result in captures:
            self.assertTrue(all(t.source_scenario is result.source_request.scenario for t in result.trials))
            self.assertEqual(tuple(t.seed for t in result.trials), tuple(
                result.source_request.seed_for(i) for i in range(result.source_request.trials)))
        return seq, captures

    def test_actual_generated_subsets_stand_cast_receive_six_and_expire_without_source_loss(self):
        source = family()
        before = deepcopy(source)
        generated = generate_magic_candidates(source)
        legacy = generate_magic_candidates(family(stationary=False))
        self.assertEqual(len(generated.evaluation_request.candidates), 2)
        for candidate, old in zip(generated.evaluation_request.candidates, legacy.evaluation_request.candidates, strict=True):
            actor_count = len(candidate.scenario.initial.roster.participants)
            self.assertEqual(candidate.candidate_id, old.candidate_id)
            self.assertEqual(candidate.scenario, replace(old.scenario,
                stationary_wound_continuation=source.stationary_wound_continuation))
            dice = Dice(script(actor_count, stationary=True))
            result = run_npc_magic_scenario(candidate.scenario, dice)
            dice.exhausted()
            self.assertEqual(dice.calls, 48 if actor_count == 3 else 66)
            self.assertIs(result.source, candidate.scenario)
            self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
            self.assertEqual(result.executed_actions, actor_count * 3)
            self.assertEqual(sum(isinstance(s.result, NpcRosterLegSpasmStandResult) for s in result.steps), 1)
            casts = [s.result for s in result.steps if isinstance(s.result, NpcRosterCastingResult)]
            self.assertEqual(len(casts), 3)
            self.assertTrue(all(c.source.stationary_wounds is not None for c in casts))
            injury = result.current.roster.participant('wizard').state.injury
            self.assertEqual(tuple(w.table_total for w in injury.wounds), (9, 6))
            self.assertFalse(injury.conditions.has(Condition.DRAINED))
            self.assertFalse(injury.conditions.has(Condition.PRONE))
            self.assertEqual(len(injury.active_wound_effects), 1)
            self.assertEqual(len(result.current.champion_attack.daily_wounds.receipts), 2)
            self.assertEqual(len(result.current.champion_attack.consumed_wound_roll_ids), 2)
            self.assertFalse(result.current.wound_expiries)
            self.assertEqual(sum(len(r.expired_sources) for r in result.current.wound_turn_end_receipts), 1)
            if actor_count == 3:
                self.assertNotIn('ally2', tuple(p.entity_id for p in result.current.spatial_state.placements))
                self.assertNotEqual(candidate.scenario.initial.roster, source.template_scenario.initial.roster)
            for scenario, values in ((old.scenario, script(actor_count, stationary=False)),
                                     (candidate.scenario, script(actor_count, stationary=True, other_wound=True))):
                stopped_dice = Dice(values)
                stopped = run_npc_magic_scenario(scenario, stopped_dice)
                stopped_dice.exhausted()
                self.assertEqual(stopped_dice.calls, 7)
                self.assertIs(stopped.unsupported.reason, Reason.ACTOR_INJURY)
        self.assertEqual(source, before)

    def test_four_policy_combinations_keep_unsupported_in_generated_spawn_stage_denominators(self):
        for stationary in (False, True):
            for miscast in (False, True):
                with self.subTest(stationary=stationary, miscast=miscast):
                    source = family(stationary=stationary, miscast=miscast)
                    before = deepcopy(source)
                    generated = generate_magic_candidates(source)
                    report, runs = self.scripted_reports(generated, mixed=True)
                    self.assertIs(report.status, MagicStagedEvaluationStatus.NO_ELIGIBLE_CANDIDATES)
                    self.assertEqual((report.total_trials, report.planned_trials), (4, 8))
                    self.assertEqual(report.selected_candidate_ids, ())
                    self.assertEqual(len(report.stage_reports), 1)
                    for row in report.stage_reports[0].candidates:
                        a = row.assessment
                        self.assertEqual(a.summary.trials, 2)
                        self.assertEqual(a.summary.outcome_counts, NpcMagicOutcomeCounts(0, 0,
                            int(stationary), 2 - int(stationary)))
                        self.assertEqual(a.unsupported_path_rate, F(1, 2) if stationary else F(1))
                        self.assertIs(a.status, MagicAssessmentStatus.UNSUPPORTED_OBSERVATIONS)
                        self.assertIsNone(a.window_match)
                    self.assertEqual(len(runs), 2)
                    self.assertEqual(source, before)

    def test_actual_full_repeated_stages_pay_budget_and_keep_indexed_seed_prefix(self):
        source = family(miscast=True)
        generated = generate_magic_candidates(source)
        report, runs = self.scripted_reports(generated, mixed=False)
        self.assertIs(report.status, MagicStagedEvaluationStatus.COMPLETED)
        self.assertEqual((report.total_trials, report.planned_trials), (8, 8))
        self.assertEqual([r.source_request.trials for r in runs], [2, 2, 4])
        for run in runs:
            self.assertEqual(run.outcome_counts, NpcMagicOutcomeCounts(0, 0, run.source_request.trials, 0))
        first = next(r for r in runs[:2] if r.source_request.scenario is runs[-1].source_request.scenario)
        self.assertEqual(tuple(t.seed for t in first.trials), tuple(t.seed for t in runs[-1].trials[:2]))

    def test_default_seeded_reports_match_spawn_in_both_perspectives_without_rate_predictions(self):
        for opposite in (False, True):
            with self.subTest(opposite=opposite):
                source = family(opposite=opposite, miscast=True)
                before = deepcopy(source)
                generated = generate_magic_candidates(source)
                sequential = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.SEQUENTIAL))
                spawned = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.PROCESS, 1, 2))
                self.assertEqual(sequential, spawned)
                self.assertLessEqual(sequential.total_trials, sequential.planned_trials)
                self.assert_sources(sequential, generated)
                self.assert_sources(spawned, generated)
                self.assertEqual(source, before)

    def test_native_balance_preserves_metadata_and_rejects_foreign_same_id_generation_source(self):
        source = family(miscast=True)
        before = deepcopy(source)
        definitions = tuple(dict.fromkeys(p.definition.id for p in source.template_scenario.initial.roster.participants))
        results = []
        for version in ('1', '2'):
            command = MagicBalanceCommand('native:stationary', source, Options(Mode.SEQUENTIAL), definitions, version)
            result = execute_magic_balance(command)
            self.assertIs(result.generation_result.source_request, source)
            self.assert_sources(result.evaluation_result, result.generation_result)
            results.append(result)
        self.assertEqual(results[0], results[1])
        foreign = generate_magic_candidates(family(stationary=False, miscast=True))
        self.assertEqual(foreign.source_request.template_scenario.id, source.template_scenario.id)
        with patch('towr.application.magic_balance_service.generate_magic_candidates', return_value=foreign), \
                patch('towr.application.magic_balance_service.evaluate_magic_candidates_staged') as evaluator:
            with self.assertRaises(MagicBalanceGenerationError) as caught:
                execute_magic_balance(command)
        self.assertIsInstance(caught.exception.__cause__, ValueError)
        self.assertEqual(caught.exception.schema_version, '2')
        evaluator.assert_not_called()
        self.assertEqual(source, before)


if __name__ == '__main__':
    unittest.main()
