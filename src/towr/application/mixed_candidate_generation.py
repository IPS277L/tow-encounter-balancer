from collections.abc import Iterator
from dataclasses import replace
from itertools import product

from towr.application.mixed_candidate_generation_errors import MixedCandidateGenerationError
from towr.application.mixed_candidate_generation_models import (
    MixedCandidateGenerationRequest, MixedCandidateGenerationResult,
)
from towr.balance.mixed_evaluation_models import MixedBalanceCandidate
from towr.balance.mixed_staged_evaluation_models import MixedStagedEvaluationRequest
from towr.domain.npc_mixed_scenario_models import NpcMixedActorPolicy, NpcMixedScenario
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.npc_roster_models import NpcRoster


def _count_vectors(source: MixedCandidateGenerationRequest) -> Iterator[tuple[int, ...]]:
    ranges = (range(group.minimum_count, group.maximum_count + 1) for group in source.groups)
    return (counts for counts in product(*ranges) if any(counts))


def _project_candidate(source: MixedCandidateGenerationRequest, counts: tuple[int, ...]) -> MixedBalanceCandidate:
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
        pairs = tuple(pair for pair in source.pair_ranges
                      if pair.first_actor_id in keep and pair.second_actor_id in keep)
        policies = tuple(NpcMixedActorPolicy(
            policy.actor_id, tuple(actor for actor in policy.target_actor_ids if actor in keep),
            tuple(decision for decision in policy.defeat_decisions if decision.target_id in keep),
            outnumbering_bonus_approved=policy.outnumbering_bonus_approved,
            can_leave_zone=policy.can_leave_zone,
        ) for policy in template.actor_policies if policy.actor_id in keep)
        objective = replace(template.objective, target_actor_ids=tuple(actor for actor in template.objective.target_actor_ids
                                                                     if actor in keep))
        # A valid reserve need not have valid subsets: re-admit every projected
        # scenario, including both roles and each actor's initial target.
        scenario = NpcMixedScenario(
            replace(template.initial, current=initial_current, spatial_state=initial_spatial),
            source.facts, pairs, policies, template.repeated_stagger_choice, template.perspective_side, objective,
        )
        return MixedBalanceCandidate(candidate_id, scenario)
    except Exception as error:
        raise MixedCandidateGenerationError(candidate_id, counts) from error


def generate_mixed_candidates(request: MixedCandidateGenerationRequest) -> MixedCandidateGenerationResult:
    """Build the complete admitted family; never skip an inadmissible subset."""
    if not isinstance(request, MixedCandidateGenerationRequest):
        raise TypeError("generation requires a typed mixed request")
    candidates = tuple(_project_candidate(request, counts) for counts in _count_vectors(request))
    evaluation = MixedStagedEvaluationRequest(
        candidates, request.master_seed, request.stages, request.max_total_trials, request.window,
    )
    return MixedCandidateGenerationResult(request, evaluation)
