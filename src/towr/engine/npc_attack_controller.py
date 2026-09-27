from __future__ import annotations

from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.condition_models import Condition
from towr.domain.npc_attack_selection_models import (
    NpcAttackCandidate, NpcAttackCandidateRejection as Rejection, NpcAttackSelectionBlock as Block,
    NpcAttackSelectionRequest, NpcAttackSelectionResult, RejectedNpcAttackCandidate,
)
from towr.domain.npc_roster_attack_models import (
    NpcRosterAttackExecutionRequest, NpcRosterAttackState, npc_attack_blocking_condition,
)
from towr.domain.resolution_models import FollowUpRequest, KernelAttackRequest, TargetInjuryPolicy
from towr.domain.turn_models import CombatActionKind, CombatRoundState
from towr.rules.npc_attack_preparation import prepare_npc_attack, prepare_npc_attack_protection


def select_npc_attack(request: NpcAttackSelectionRequest) -> NpcAttackSelectionResult:
    """First viable candidate in caller preference order; no RNG or state mutation."""
    if not isinstance(request, NpcAttackSelectionRequest):
        raise TypeError("request must be an NpcAttackSelectionRequest")
    blocked = _global_block(request)
    if blocked is not None:
        return NpcAttackSelectionResult(request, None, None, (), blocked)
    rejected = []
    for candidate in request.candidates:
        reason = _candidate_block(request, candidate)
        if reason is not None:
            rejected.append(RejectedNpcAttackCandidate(candidate.id, reason))
            continue
        # Only validation at these two known context boundaries becomes a rejection.
        # Unexpected failures from a reducer are not swallowed as "no candidate".
        try:
            attack_request = candidate.attack_preparation_request(request)
        except ValueError as error:
            rejected.append(RejectedNpcAttackCandidate(candidate.id, Rejection.ATTACK_CONTEXT, str(error)))
            continue
        npc = prepare_npc_attack(attack_request)
        try:
            protection_request = candidate.protection_preparation_request(request, npc)
        except ValueError as error:
            rejected.append(RejectedNpcAttackCandidate(candidate.id, Rejection.PROTECTION_CONTEXT, str(error)))
            continue
        prepared = prepare_npc_attack_protection(npc, protection_request)
        target = request.state.roster.participant(candidate.target_id)
        kernel = KernelAttackRequest(
            request.id + ":kernel", candidate.target_id, prepared.attack,
            target.definition.injury_policy, target.state.injury,
            candidate.can_target_leave_zone, candidate.target_has_given_ground_this_round,
        )
        execution = NpcRosterAttackExecutionRequest(request.state, prepared, AttackActionExecutionRequest(
            request.execution_id, request.round_state, request.actor_id, candidate.target_id, request.slot_index, kernel,
        ))
        return NpcAttackSelectionResult(request, candidate, execution, tuple(rejected), None)
    return NpcAttackSelectionResult(request, None, None, tuple(rejected), Block.NO_CANDIDATE)


def require_current_npc_attack_selection(
    selection: NpcAttackSelectionResult, state: NpcRosterAttackState, round_state: CombatRoundState,
    *, pending_follow_ups: tuple[FollowUpRequest, ...],
) -> NpcRosterAttackExecutionRequest:
    """Hand the existing executable request to the caller after exact snapshot checks."""
    if not isinstance(selection, NpcAttackSelectionResult):
        raise TypeError("selection must be an NpcAttackSelectionResult")
    source = selection.source_request
    if state != source.state or round_state != source.round_state or tuple(pending_follow_ups) != source.pending_follow_ups:
        raise ValueError("selection has stale roster/round/pending follow-ups; select again")
    if selection.execution_request is None:
        raise ValueError("selection has no executable attack")
    return selection.execution_request


def _global_block(request: NpcAttackSelectionRequest) -> Block | None:
    if request.pending_follow_ups:
        return Block.PENDING_FOLLOW_UPS
    turn = request.round_state.active_turn
    if turn is None:
        return Block.NO_ACTIVE_TURN
    if turn.actor_id != request.actor_id:
        return Block.ANOTHER_ACTIVE_ACTOR
    actor = request.state.roster.participant(request.actor_id)
    if actor.definition.injury_policy is not TargetInjuryPolicy.MINION:
        return Block.UNSUPPORTED_ACTOR
    if actor.state.injury.defeated:
        return Block.ACTOR_DEFEATED
    blocked = npc_attack_blocking_condition(actor.state.injury.conditions)
    if blocked is Condition.DEFENCELESS:
        return Block.ACTOR_DEFENCELESS
    if blocked is Condition.BROKEN:
        return Block.ACTOR_BROKEN
    if request.slot_index > len(turn.action_slots):
        return Block.SLOT_UNAVAILABLE
    slot = turn.action_slots[request.slot_index - 1]
    if slot.executed:
        return Block.SLOT_EXECUTED
    if slot.declaration.kind is not CombatActionKind.ATTACK or any(not s.executed for s in turn.action_slots[:request.slot_index - 1]):
        return Block.SLOT_UNAVAILABLE
    if request.execution_id in request.state.consumed_execution_ids:
        return Block.EXECUTION_CONSUMED
    return None


def _candidate_block(request: NpcAttackSelectionRequest, candidate: NpcAttackCandidate) -> Rejection | None:
    actor = request.state.roster.participant(request.actor_id)
    target = request.state.roster.participant(candidate.target_id)
    if candidate.attack_profile_id not in actor.state.available_attack_ids:
        return Rejection.ATTACK_UNAVAILABLE
    if target.state.actor_id == actor.state.actor_id:
        return Rejection.SELF_TARGET
    if target.definition.injury_policy is not TargetInjuryPolicy.MINION:
        return Rejection.UNSUPPORTED_TARGET
    if target.state.injury.defeated:
        return Rejection.TARGET_DEFEATED
    if target.turn_participant not in request.round_state.participants:
        return Rejection.TARGET_NOT_IN_ROUND
    profile = next(p for p in actor.definition.attacks if p.id == candidate.attack_profile_id)
    if profile.secondary_effects:
        return Rejection.UNSUPPORTED_EFFECTS
    return None
