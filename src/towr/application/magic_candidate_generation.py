"""Construct the complete authored magic family without simulation (ADR-0042/0047)."""
from collections.abc import Iterator
from dataclasses import replace
from itertools import product

from towr.application.magic_candidate_generation_errors import MagicCandidateGenerationError
from towr.application.magic_candidate_generation_models import (
    MagicCandidateGenerationRequest, MagicCandidateGenerationResult,
)
from towr.balance.magic_evaluation_models import MagicBalanceCandidate
from towr.balance.magic_staged_evaluation_models import MagicStagedEvaluationRequest
from towr.domain.infection_models import DailyWoundState
from towr.domain.npc_champion_attack_models import NpcChampionAttackState
from towr.domain.npc_magic_scenario_models import NpcMagicScenario
from towr.domain.npc_magic_scene_models import NpcMagicRouteFacts, NpcMagicSceneFrame, NpcMagicSceneKey
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.spatial_models import SpatialBattleState
from towr.domain.turn_models import CombatRoundState


def _count_vectors(source: MagicCandidateGenerationRequest) -> Iterator[tuple[int, ...]]:
    ranges = (range(group.minimum_count, group.maximum_count + 1) for group in source.groups)
    return (counts for counts in product(*ranges) if any(counts))


def _project_route(route: NpcMagicRouteFacts | None, keep: set[str]) -> NpcMagicRouteFacts | None:
    return None if route is None else replace(route, path_entity_ids=tuple(
        actor for actor in route.path_entity_ids if actor in keep))


def _project_frames(frames: tuple[NpcMagicSceneFrame, ...], keep: set[str]) -> tuple[NpcMagicSceneFrame, ...]:
    projected: dict[NpcMagicSceneKey, NpcMagicSceneFrame] = {}
    for frame in frames:
        value = replace(frame, key=replace(frame.key,
            placements=tuple(p for p in frame.key.placements if p.entity_id in keep),
            live_actor_ids=tuple(actor for actor in frame.key.live_actor_ids if actor in keep)),
            pair_ranges=tuple(p for p in frame.pair_ranges
                              if p.first_actor_id in keep and p.second_actor_id in keep),
            give_ground_plans=tuple(replace(p, route=_project_route(p.route, keep))
                                    for p in frame.give_ground_plans if p.actor_id in keep),
            broken_plans=tuple(replace(p, free_move_route=_project_route(p.free_move_route, keep),
                                      run_route=_project_route(p.run_route, keep))
                               for p in frame.broken_plans if p.actor_id in keep),
            attack_departures=tuple(p for p in frame.attack_departures if p.actor_id in keep))
        if value.key not in projected:
            projected[value.key] = value
        elif projected[value.key] != value:
            raise ValueError("conflicting projected magic scene frame key")
    return tuple(projected.values())


def _project_candidate(source: MagicCandidateGenerationRequest, counts: tuple[int, ...]) -> MagicBalanceCandidate:
    candidate_id = source.candidate_id_prefix + ":counts:" + ",".join(map(str, counts))
    try:
        template = source.template_scenario
        original = template.initial
        keep = {p.state.actor_id for p in original.roster.participants
                if p.state.side is template.perspective_side}
        keep.add(original.wizard.actor_id)
        keep.update(actor for group, count in zip(source.groups, counts) for actor in group.actor_ids[:count])
        roster = NpcRoster(tuple(p for p in original.roster.participants if p.state.actor_id in keep))
        combat = CombatRoundState(1, roster.turn_participants)
        spatial = SpatialBattleState(original.spatial_state.graph,
            tuple(p for p in original.spatial_state.placements if p.entity_id in keep))
        daily = DailyWoundState(original.champion_attack.daily_wounds.day_id, original.wizard.actor_id)
        initial = NpcRosterCastingState(roster, original.wizard, combat, spatial,
            champion_attack=NpcChampionAttackState(roster, combat, daily))
        policies = tuple(replace(policy,
            target_actor_ids=tuple(actor for actor in policy.target_actor_ids if actor in keep),
            defeat_decisions=tuple(d for d in policy.defeat_decisions if d.target_id in keep))
            for policy in template.actors if policy.actor_id in keep)
        # Re-admit all supplied frames and every subset. No route repair,
        # reachability pruning or missing-fact inference makes a subset valid.
        scenario = NpcMagicScenario(
            id=candidate_id, initial=initial, facts=source.facts,
            activation_order=tuple(actor for actor in template.activation_order if actor in keep),
            actors=policies, scene_frames=_project_frames(source.scene_frames, keep),
            perspective_side=template.perspective_side,
            objective=replace(template.objective,
                target_actor_ids=tuple(actor for actor in template.objective.target_actor_ids if actor in keep)),
            max_rounds=template.max_rounds, repeated_stagger_choice=template.repeated_stagger_choice,
            spell=template.spell, miscast_continuation=source.miscast_continuation,
        )
        return MagicBalanceCandidate(candidate_id, scenario)
    except Exception as error:
        raise MagicCandidateGenerationError(candidate_id, counts) from error


def generate_magic_candidates(request: MagicCandidateGenerationRequest) -> MagicCandidateGenerationResult:
    """Build every candidate or fail with its context; never return a prefix."""
    if not isinstance(request, MagicCandidateGenerationRequest):
        raise TypeError("generation requires a typed magic request")
    candidates = tuple(_project_candidate(request, counts) for counts in _count_vectors(request))
    evaluation = MagicStagedEvaluationRequest(
        candidates, request.master_seed, request.stages, request.max_total_trials, request.window,
    )
    return MagicCandidateGenerationResult(request, evaluation)
