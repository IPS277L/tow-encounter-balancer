"""Explicit reserve -> public magic generator -> staged evaluation (ADR-0042).

Keep magic_scenario.py beside this file. Numeric profiles and every scene/GM
assertion are authored, not presets.
"""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from itertools import product
from multiprocessing import active_children
from random import getstate
import sys

from magic_scenario import authored_scenario
from towr.application.magic_candidate_generation import generate_magic_candidates
from towr.application.magic_candidate_generation_errors import MagicCandidateGenerationError
from towr.application.magic_candidate_generation_models import MagicCandidateGenerationRequest, MagicCompositionGroup
from towr.application.magic_staged_evaluation_errors import MagicStagedEvaluationError
from towr.application.magic_staged_evaluation_service import evaluate_magic_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.balance.magic_staged_evaluation import magic_continuation_candidate_ids
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage
from towr.balance.magic_evaluation_models import MagicBalanceEvaluationResult
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.npc_champion_attack_models import NpcChampionAttackState
from towr.domain.npc_magic_scene_models import (
    NpcMagicAttackDeparture, NpcMagicBrokenPlan, NpcMagicBrokenPlanKind,
    NpcMagicGiveGroundPlan, NpcMagicPairRange, NpcMagicRouteFacts, NpcMagicSceneFrame, NpcMagicSceneKey,
)
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.spatial_models import SpatialBattleState


def build_request() -> MagicCandidateGenerationRequest:
    # PG1.4 Equipment p94; Rules pp112,114-115,119,122;
    # Magic pp156-157,162; Wounds pp190-191. GM1.1 pp91-92.
    base = authored_scenario()
    enemies = ('E1', 'E2', 'E3')
    prototype = base.initial.roster.participant('enemy')
    # Author the full reserve first; generation only selects existing actors.
    roster = NpcRoster((*base.initial.roster.participants[:2], *(replace(prototype,
        state=replace(prototype.state, actor_id=actor)) for actor in enemies)))
    combat = replace(base.initial.round_state, participants=roster.turn_participants)
    enemy_position = base.initial.spatial_state.placement_for('enemy')
    spatial = SpatialBattleState(base.initial.spatial_state.graph,
        (*tuple(p for p in base.initial.spatial_state.placements if p.entity_id != 'enemy'),
         *(replace(enemy_position, entity_id=actor) for actor in enemies)))
    initial = NpcRosterCastingState(roster, base.initial.wizard, combat, spatial,
        champion_attack=NpcChampionAttackState(roster, combat, base.initial.champion_attack.daily_wounds))
    priority = ('E3', 'E2', 'E1')
    ally = base.policy_for('ally')
    ally = replace(ally, target_actor_ids=priority,
        defeat_decisions=tuple(replace(ally.defeat_decisions[0], target_id=actor) for actor in priority))
    actors = (base.policy_for('wizard'), ally, *(replace(base.policy_for('enemy'), actor_id=actor,
        defeat_decisions=tuple(replace(d, attacker_id=actor) for d in base.policy_for('enemy').defeat_decisions))
        for actor in enemies))
    frames = []
    ids = ('wizard', 'ally', *enemies)
    # This finite family explicitly supplies arena/shelter positions and live
    # subsets. It does not infer routes/awareness/GM decisions from a roster.
    # Wizard/ally stay at arena; retained archived placements remain in keys.
    route = NpcMagicRouteFacts((), False, False)
    for zones in product(('arena', 'shelter'), repeat=3):
        placements = tuple(replace(p, zone_id=zones[enemies.index(p.entity_id)])
                           if p.entity_id in enemies else p for p in spatial.placements)
        for flags in product((True, False), repeat=4):
            live = ('wizard', *(actor for actor, active in zip(('ally', *enemies), flags) if active))
            retained_enemies = tuple(i for i in enemies if i in live)
            pairs = tuple(NpcMagicPairRange(friendly, enemy,
                Range.SHORT if zones[enemies.index(enemy)] == 'arena' else Range.MEDIUM, False, False)
                for friendly in ('wizard', 'ally') if friendly in live for enemy in retained_enemies)
            ground = tuple(NpcMagicGiveGroundPlan(i, True,
                'shelter' if zones[enemies.index(i)] == 'arena' else 'boundary', route, False)
                for i in retained_enemies)
            broken = tuple(NpcMagicBrokenPlan(i, NpcMagicBrokenPlanKind.SAFE_RECOVER,
                (), None, None, None, True) for i in retained_enemies if zones[enemies.index(i)] == 'shelter')
            frames.append(NpcMagicSceneFrame(NpcMagicSceneKey(placements, live), pairs,
                base.initial_frame.zone_ranges, ground, broken,
                tuple(NpcMagicAttackDeparture(i, True) for i in live)))
    template = replace(base, id='example:magic:reserve', initial=initial, actors=actors,
        activation_order=ids, objective=NpcDefeatObjective(priority), scene_frames=tuple(frames), max_rounds=1)
    return MagicCandidateGenerationRequest(
        template, (MagicCompositionGroup('A', ('E2', 'E1'), 1, 2), MagicCompositionGroup('B', ('E3',), 0, 1)),
        replace(template.facts), tuple(replace(f) for f in template.scene_frames),
        'magic', 4, 42, (MagicBalanceStage(8, 2), MagicBalanceStage(32, 1)), 96,
        ObjectiveRateWindow(Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)),
    )


def print_report(report: MagicBalanceEvaluationResult) -> None:
    source = report.source_request
    print(f'seed: {source.master_seed}; seed_scheme: {report.seed_scheme}; trials_per_candidate: {source.trials_per_candidate}')
    print(f'window: min={source.window.minimum}, target={source.window.target}, max={source.window.maximum}; top_k: {source.top_k}')
    print(f'budget per evaluation: planned={source.planned_trials}; actual={report.total_trials}; max={source.max_total_trials}')
    for row in report.candidates:
        a = row.assessment
        summary, scenario = a.summary, a.source_request.scenario
        counts = summary.outcome_counts
        print(f'candidate: {row.candidate_id}; round_budget: {scenario.max_rounds}; '
              f'perspective: {scenario.perspective_side.value}; objective:{scenario.objective.target_actor_ids}')
        print(f'  counts goal/perspective_defeated/round_limit_reached/unsupported: {counts.objective_achieved}/'
              f'{counts.perspective_defeated}/{counts.round_limit_reached}/{counts.unsupported_path}')
        print(f'  rates goal/perspective_defeated/round_limit/unsupported: {a.objective_achieved_rate}, '
              f'{a.perspective_defeated_rate}, {a.round_limit_rate}, {a.unsupported_path_rate}')
        print(f'  actions: {summary.total_action_count}; started/completed rounds: '
              f'{summary.total_started_round_count}/{summary.total_completed_round_count}; '
              f'status: {a.status.value}; window_match: {a.window_match}')
    print(f'selected: {report.selected_candidate_ids}')


def main() -> None:
    source = build_request()
    before, rng_before = deepcopy(source), getstate()
    children_before = {child.pid for child in active_children()}
    generated = generate_magic_candidates(source)
    evaluation = generated.evaluation_request
    sequential = evaluate_magic_candidates_staged(evaluation, SimulationExecutionOptions(SimulationExecutionMode.SEQUENTIAL))
    process = evaluate_magic_candidates_staged(
        evaluation, SimulationExecutionOptions(SimulationExecutionMode.PROCESS, workers=2, batch_size=3))
    # Full equality without fixing a Monte Carlo percentage, survivor or winner.
    assert sequential == process
    assert sequential.selected_candidate_ids == process.selected_candidate_ids
    assert generated.source_request is source
    assert sequential.source_request is process.source_request is evaluation
    assert len(evaluation.candidates) == source.candidate_count == 4
    assert sequential.total_trials <= sequential.planned_trials == source.planned_trials == source.max_total_trials == 96
    for result in (sequential, process):
        for stage in result.stage_reports:
            for row, expected in zip(stage.candidates, stage.source_request.simulation_requests, strict=True):
                assert row.assessment.source_request is row.assessment.summary.source_request is expected
                assert row.assessment.window is source.window
    assert source == before and getstate() == rng_before
    assert {child.pid for child in active_children()} == children_before
    # Publish the whole catalog and reports only after both successful calls.
    print('profiles: authored Champion-Wizard Level2 Casting/Willpower3d/3 RES4; Shooting Minions3d/3 Dam3 RES3')
    print('rules: BOOK-PLAYER-GUIDE 1.4 / Combat p112; Broken p122; Magic pp156-157,162; Wounds pp190-191')
    print('NPC injury policies: BOOK-GM-GUIDE 1.1 / Allies and Antagonists pp91-92')
    print('candidates change opposing Minion counts; fixed profiles/policies/scene facts; all unsupported trials remain in N')
    print('reserve: wizard,ally,E1,E2,E3; fixed Wizard and perspective players_and_allies; max_rounds=1')
    print('family scenes: arena-shelter-boundary; explicit ranges/routes/Recover/departures and live keys with archives')
    print(f'authored frames: {len(source.scene_frames)}; omitted reserve actors are absent, not defeated')
    for group in source.groups:
        print(f'group {group.group_id}: reserve={group.actor_ids}; counts={group.minimum_count}..{group.maximum_count}')
    print(f'generated: {source.candidate_count}; max_candidates: {source.max_candidates}')
    for candidate in evaluation.candidates:
        scenario = candidate.scenario
        print(f'candidate: {candidate.candidate_id}; actors={scenario.activation_order}; '
              f'objective={scenario.objective.target_actor_ids}; frames={len(scenario.scene_frames)}')
    print('stages (full trials per candidate, keep): ' + str(tuple(
        (stage.trials_per_candidate, stage.keep) for stage in source.stages)))
    print(f'staged budget per evaluation: planned={sequential.planned_trials}; actual={sequential.total_trials}; max={source.max_total_trials}')
    for index, report in enumerate(sequential.stage_reports):
        print(f'stage index: {index}')
        print_report(report)
        if index < len(source.stages) - 1:
            print(f'continuation IDs (not local selected): {magic_continuation_candidate_ids(report)}')
    print(f'staged status: {sequential.status.value}; final selected: {sequential.selected_candidate_ids}')
    print('sequential/process full reports and selected IDs: equal; process workers=2 batch_size=3')
    print(f'two complete evaluations: {sequential.total_trials + process.total_trials} trials; each stage reruns its full batch from index 0')
    print('input/global RNG unchanged; no remaining child processes; finite observations, not a difficulty preset')


if __name__ == '__main__':
    try:
        main()
    except MagicCandidateGenerationError as error:
        print(f'generation failed: candidate={error.candidate_id}; counts={error.counts}; cause={error.__cause__}', file=sys.stderr)
        raise
    except MagicStagedEvaluationError as error:
        print(f'evaluation failed: stage={error.stage_index}; candidate={error.candidate_id}; cause={error.__cause__}', file=sys.stderr)
        raise
