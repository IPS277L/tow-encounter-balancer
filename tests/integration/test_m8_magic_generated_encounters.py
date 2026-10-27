"""Generated rosters through real Curse/defeat/scene consumers (ADR-0042).

PG1.4 Combat112, Giving Ground119, Broken122, Casting156-157, Curse162;
GM1.1 Allies and Antagonists / Minions91. Fixture facts remain authored.
"""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from functools import partial
from itertools import product
from multiprocessing import active_children
import os
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_magic_candidate_generation_models import request
from tests.unit.test_m8_npc_magic_scenario import frame, scenario
from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from towr.application.magic_candidate_generation import generate_magic_candidates
from towr.application import magic_evaluation_service as bounded_service
from towr.application.magic_staged_evaluation_service import evaluate_magic_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage as Stage, MagicStagedEvaluationStatus as Status
from towr.simulation.npc_magic_models import NpcMagicOutcomeCounts
from towr.domain.condition_models import Condition
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.npc_broken_recover_models import NpcBrokenRecoverResult
from towr.domain.npc_magic_scene_models import (
    NpcMagicAttackDeparture, NpcMagicBrokenPlan, NpcMagicBrokenPlanKind,
    NpcMagicSceneKey,
)
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult
from towr.domain.npc_roster_casting_completion_models import NpcRosterCastingCompletionResult
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_minion_attack_models import NpcRosterMinionAttackResult
from towr.domain.npc_roster_minion_defeat_models import NpcRosterMinionDefeatResult
from towr.domain.spatial_models import SpatialBattleState
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario


ENEMIES = ('enemy', 'blocker', 'far-blocker')


def missing_scene_rng(seed, *, parent_pid=None):
    if parent_pid is not None:
        assert os.getpid() != parent_pid, 'process RNG must run in a child'
    return Dice((1, 2, 3, 10, 10, 10))


def generated_family(*, movement=False, archives=False, ally_first=False):
    """Explicit finite four-Zone test arena, never a production scene mapper."""
    source = request()
    template = scenario(blocker=True, fast_blocker=True)
    positions = tuple(replace(p, zone_id='arena') for p in template.initial.spatial_state.placements)
    initial = replace(template.initial, spatial_state=SpatialBattleState(
        template.initial.spatial_state.graph, positions))
    actors = []
    for policy in template.actors:
        if policy.actor_id == 'ally':
            decisions = {d.target_id: replace(d, disposition=NpcDefeatDisposition.DISARMED_AND_SURRENDERED)
                         for d in policy.defeat_decisions}
            priority = ('far-blocker', 'enemy', 'blocker')
            policy = replace(policy, target_actor_ids=priority,
                             defeat_decisions=tuple(decisions[i] for i in priority))
        actors.append(policy)
    frames = []
    zone_vectors = product(('arena', 'middle'), repeat=3) if movement else (('arena',) * 3,)
    for zones in zone_vectors:
        placements = tuple(replace(p, zone_id=zones[ENEMIES.index(p.entity_id)])
                           if p.entity_id in ENEMIES else p for p in positions)
        live_vectors = product((True, False), repeat=3) if archives else ((True,) * 3,)
        for live_flags in live_vectors:
            live = ('wizard', 'ally', *(i for i, active in zip(ENEMIES, live_flags) if active))
            value = frame(initial, placements=placements, live=live)
            broken = tuple(NpcMagicBrokenPlan(i, NpcMagicBrokenPlanKind.SAFE_RECOVER,
                (), None, None, None, True) for i, zone in zip(ENEMIES, zones)
                if i in live and zone == 'middle')
            frames.append(replace(value, broken_plans=broken, attack_departures=tuple(
                NpcMagicAttackDeparture(i, i in ('ally', 'blocker')) for i in live)))
    template = replace(template, initial=initial, actors=tuple(actors), max_rounds=1,
        activation_order=('ally', 'wizard', *ENEMIES) if ally_first else ('wizard', 'ally', *ENEMIES),
        scene_frames=tuple(frames))
    return generate_magic_candidates(replace(source, template_scenario=template,
        facts=replace(template.facts), scene_frames=template.scene_frames))


class GeneratedMagicEncounterIntegrationTests(unittest.TestCase):
    def test_curse_moves_only_generated_targets_in_roster_order_then_recovers_broken(self):
        generated = generated_family(movement=True)
        before, rng_before = deepcopy(generated), getstate()
        for candidate in generated.evaluation_request.candidates:
            source = candidate.scenario
            targets = tuple(p.state.actor_id for p in source.initial.roster.participants
                            if p.state.side is not source.initial.roster.participant('wizard').state.side)
            # One Casting, all failed target Willpowers, one missed ally shot,
            # then one successful Recover per Broken target. No extra action.
            rng = Dice((1, 2, 3) + (10,) * (3 * len(targets) + 6) + (1, 2, 3) * len(targets))
            with self.subTest(candidate=candidate.candidate_id):
                result = run_npc_magic_scenario(source, rng)
                rng.exhausted()
                self.assertIs(result.source, source)
                self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
                self.assertEqual((result.started_rounds, result.completed_rounds, result.executed_actions),
                                 (1, 1, len(targets) + 2))
                casts = [s.result for s in result.steps if isinstance(s.result, NpcRosterCastingResult)]
                completions = [s.result for s in result.steps if isinstance(s.result, NpcRosterCastingCompletionResult)]
                self.assertEqual(len(casts), 1)
                self.assertEqual(len(completions), 1)
                self.assertEqual(tuple(t.actor_id for t in casts[0].source.casting.targets), targets)
                completion = completions[0]
                self.assertEqual(tuple(t.actor_id for t in completion.completion.casting.targets), targets)
                self.assertEqual(completion.state.spatial_state.gave_ground_entity_ids, targets)
                self.assertTrue(all(completion.state.roster.participant(i).state.injury.conditions.has(Condition.BROKEN)
                                    for i in targets))
                self.assertEqual(tuple(s.actor_id for s in result.steps if isinstance(s.result, NpcBrokenRecoverResult)), targets)
                self.assertTrue(all(not result.current.roster.participant(i).state.injury.conditions.has(Condition.BROKEN)
                                    for i in targets))
                self.assertTrue(all(result.current.spatial_state.placement_for(i).zone_id == 'middle' for i in targets))
                self.assertIsNone(result.current.pending_movement)
                self.assertEqual(rng.calls, 9 + 6 * len(targets))
                self.assertEqual(len(source.scene_frames), 2 ** len(targets))
        self.assertEqual(generated, before)
        self.assertEqual(getstate(), rng_before)

    def test_defeat_uses_filtered_priority_and_full_decision_retains_archive_for_next_cast(self):
        generated = generated_family(archives=True, ally_first=True)
        before, rng_before = deepcopy(generated), getstate()
        for candidate in generated.evaluation_request.candidates:
            source = candidate.scenario
            enemies = source.objective.target_actor_ids
            target = source.policy_for('ally').target_actor_ids[0]
            remaining = tuple(i for i in enemies if i != target)
            rolls = (1, 2, 3, 10, 10, 10)
            if remaining:
                rolls += (10,) * (3 + 6 * len(remaining))
            rng = Dice(rolls)
            with self.subTest(candidate=candidate.candidate_id):
                result = run_npc_magic_scenario(source, rng)
                rng.exhausted()
                self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED if remaining else Outcome.OBJECTIVE_ACHIEVED)
                acknowledgements = [s.result for s in result.steps if isinstance(s.result, NpcRosterMinionDefeatResult)]
                self.assertEqual(len(acknowledgements), 1)
                decision = acknowledgements[0].source.decision
                self.assertEqual(decision, next(d for d in source.policy_for('ally').defeat_decisions if d.target_id == target))
                self.assertIs(decision.disposition, NpcDefeatDisposition.DISARMED_AND_SURRENDERED)
                self.assertTrue(decision.gm_approved)
                self.assertEqual(result.current.round_state.excluded_turn_entity_ids, (target,))
                self.assertTrue(result.current.roster.participant(target).state.injury.defeated)
                self.assertEqual(result.current.spatial_state.placements, source.initial.spatial_state.placements)
                self.assertEqual(result.current.roster, result.current.minion_attack.roster)
                self.assertEqual(result.current.roster, result.current.champion_attack.roster)
                self.assertIsNone(result.current.pending_minion_attack)
                live = tuple(p.state.actor_id for p in result.current.roster.participants if p.state.actor_id != target)
                archived_frame = source.frame_for(NpcMagicSceneKey(result.current.spatial_state.placements, live))
                self.assertIsNotNone(archived_frame)
                casts = [s.result for s in result.steps if isinstance(s.result, NpcRosterCastingResult)]
                self.assertEqual(len(casts), int(bool(remaining)))
                if casts:
                    self.assertEqual(tuple(t.actor_id for t in casts[0].source.casting.targets), remaining)
                    self.assertNotIn(target, tuple(p.entity_id for p in casts[0].source.casting.spatial_state.placements))
                attack_types = (NpcRosterMinionAttackResult, NpcRosterChampionAttackResult)
                attacks = [s.result for s in result.steps if isinstance(s.result, attack_types)]
                self.assertEqual(tuple(s.actor_id for s in result.steps if isinstance(s.result, attack_types)),
                                 ('ally', *remaining))
                for attack in attacks:
                    kernel = attack.source.attack.execution.kernel_request
                    supplied = next(d.can_leave_zone for d in source.initial_frame.attack_departures
                                    if d.actor_id == kernel.target_id)
                    self.assertIs(kernel.can_target_leave_zone, supplied)
        self.assertEqual(generated, before)
        self.assertEqual(getstate(), rng_before)

    def test_missing_projected_future_scene_stops_with_exact_pending_prefix_without_extra_rng(self):
        generated = generated_family()
        before, rng_before = deepcopy(generated), getstate()
        for candidate in generated.evaluation_request.candidates:
            source = candidate.scenario
            targets = source.objective.target_actor_ids
            rng = Dice((1, 2, 3) + ((10,) * 3 if len(targets) == 1 else ()))
            with self.subTest(candidate=candidate.candidate_id):
                result = run_npc_magic_scenario(source, rng)
                rng.exhausted()
                self.assertIs(result.outcome, Outcome.UNSUPPORTED_PATH)
                self.assertIs(result.unsupported.reason, Reason.MISSING_SCENE)
                self.assertEqual(result.executed_actions, 1)
                key = result.unsupported.required_scene_key
                self.assertIsNone(source.frame_for(key))
                self.assertEqual(tuple(p.entity_id for p in key.placements),
                                 tuple(p.entity_id for p in source.initial.spatial_state.placements))
                if len(targets) == 1:
                    self.assertIsNone(result.current.pending_movement)
                    self.assertEqual(result.current.spatial_state.gave_ground_entity_ids, targets)
                    self.assertEqual(result.unsupported.actor_id, 'ally')
                else:
                    self.assertEqual(len(result.current.pending_movement.zone.movement_follow_ups), len(targets))
                    self.assertEqual(len(result.unsupported.staged_movements), 1)
                    self.assertEqual(result.unsupported.missing_actor_ids, (targets[1],))
                    self.assertEqual(result.current.spatial_state.placements, source.initial.spatial_state.placements)
                    self.assertEqual(result.current.spatial_state.gave_ground_entity_ids, ())
                    self.assertEqual(rng.calls, 3)
        self.assertEqual(generated, before)
        self.assertEqual(getstate(), rng_before)

    def test_missing_scene_unsupported_stays_in_generated_stage_denominator_in_both_backends(self):
        source = replace(generated_family().source_request,
                         stages=(Stage(2, 2), Stage(4, 1)), max_total_trials=16)
        before, rng_before = deepcopy(source), getstate()
        children_before = {child.pid for child in active_children()}
        generated = generate_magic_candidates(source)
        seq_runner = bounded_service.run_npc_magic_simulation
        proc_runner = bounded_service.run_npc_magic_simulation_parallel
        with patch.object(bounded_service, 'run_npc_magic_simulation',
                side_effect=lambda s: seq_runner(s, rng_factory=missing_scene_rng)) as seq_calls, \
                patch.object(bounded_service, 'run_npc_magic_simulation_parallel',
                side_effect=lambda s, **kw: proc_runner(s,
                    rng_factory=partial(missing_scene_rng, parent_pid=os.getpid()), **kw)) as proc_calls:
            seq = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.SEQUENTIAL))
            proc = evaluate_magic_candidates_staged(generated.evaluation_request, Options(Mode.PROCESS, 2, 3))
        self.assertEqual(seq, proc)
        self.assertIs(seq.status, Status.NO_ELIGIBLE_CANDIDATES)
        self.assertEqual((seq.total_trials, seq.planned_trials), (8, 16))
        self.assertEqual(seq.selected_candidate_ids, ())
        self.assertEqual(len(seq.stage_reports), 1)
        self.assertEqual([c.args[0].trials for c in seq_calls.call_args_list], [2, 2, 2, 2])
        self.assertEqual([c.args[0] for c in seq_calls.call_args_list],
                         [c.args[0] for c in proc_calls.call_args_list])
        for row in seq.stage_reports[0].candidates:
            assessment = row.assessment
            self.assertEqual(assessment.summary.outcome_counts, NpcMagicOutcomeCounts(0, 0, 0, 2))
            self.assertEqual((assessment.objective_achieved_rate, assessment.unsupported_path_rate), (F(0), F(1)))
            self.assertIsNone(assessment.window_match)
            self.assertEqual((assessment.summary.total_action_count, assessment.summary.total_started_round_count,
                              assessment.summary.total_completed_round_count), (2, 2, 0))
        self.assertIs(seq.source_request, generated.evaluation_request)
        self.assertIs(proc.source_request, generated.evaluation_request)
        self.assertEqual(source, before)
        self.assertEqual(getstate(), rng_before)
        self.assertEqual({child.pid for child in active_children()}, children_before)
