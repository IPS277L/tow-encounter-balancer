from collections.abc import Iterator
from dataclasses import replace
from itertools import product

from towr.application.ranged_candidate_generation_errors import RangedCandidateGenerationError
from towr.application.ranged_candidate_generation_models import (
    RangedCandidateGenerationRequest, RangedCandidateGenerationResult,
)
from towr.balance.ranged_evaluation_models import RangedBalanceCandidate
from towr.balance.ranged_staged_evaluation_models import RangedStagedEvaluationRequest
from towr.domain.npc_ranged_scenario_models import NpcRangedActorPolicy, NpcRangedScenario
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.npc_roster_models import NpcRoster


def _count_vectors(source: RangedCandidateGenerationRequest) -> Iterator[tuple[int, ...]]:
    ranges = (range(group.minimum_count, group.maximum_count + 1) for group in source.groups)
    return (counts for counts in product(*ranges) if any(counts))


def _project_candidate(source: RangedCandidateGenerationRequest, counts: tuple[int, ...]) -> RangedBalanceCandidate:
    candidate_id = source.candidate_id_prefix + ":counts:" + ",".join(map(str, counts))
    try:
        template = source.template_scenario
        current, spatial = template.initial.current, template.initial.spatial_state
        original_roster = current.state.roster
        keep = {p.state.actor_id for p in original_roster.participants if p.state.side is template.perspective_side}
        keep.update(actor for group, count in zip(source.groups, counts) for actor in group.actor_ids[:count])
        roster = NpcRoster(tuple(p for p in original_roster.participants if p.state.actor_id in keep))
        combat = replace(current.round_state, participants=tuple(p for p in current.round_state.participants
                                                               if p.entity_id in keep))
        initial_current = replace(current, id=candidate_id + ":initial", state=NpcRosterAttackState(roster),
                                  round_state=combat, actor_order=tuple(actor for actor in current.actor_order if actor in keep))
        initial_spatial = replace(spatial, placements=tuple(p for p in spatial.placements if p.entity_id in keep))
        policies = tuple(NpcRangedActorPolicy(
            policy.actor_id, tuple(actor for actor in policy.target_actor_ids if actor in keep),
            tuple(decision for decision in policy.defeat_decisions if decision.target_id in keep),
        ) for policy in template.actor_policies if policy.actor_id in keep)
        objective = replace(template.objective, target_actor_ids=tuple(actor for actor in template.objective.target_actor_ids
                                                                     if actor in keep))
        scenario = NpcRangedScenario(
            replace(template.initial, current=initial_current, spatial_state=initial_spatial),
            source.facts, policies, template.repeated_stagger_choice, template.perspective_side, objective,
        )
        return RangedBalanceCandidate(candidate_id, scenario)
    except Exception as error:
        raise RangedCandidateGenerationError(candidate_id, counts) from error


def generate_ranged_candidates(request: RangedCandidateGenerationRequest) -> RangedCandidateGenerationResult:
    """Build the complete admitted family; execution remains an explicit separate call."""
    if not isinstance(request, RangedCandidateGenerationRequest):
        raise TypeError("generation requires a typed request")
    candidates = tuple(_project_candidate(request, counts) for counts in _count_vectors(request))
    evaluation = RangedStagedEvaluationRequest(
        candidates, request.master_seed, request.stages, request.max_total_trials, request.window,
    )
    return RangedCandidateGenerationResult(request, evaluation)
