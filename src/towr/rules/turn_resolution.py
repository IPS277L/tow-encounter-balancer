from __future__ import annotations

from dataclasses import replace

from towr.domain.turn_models import (
    ActionSlotGrant,
    CombatActionKind,
    CombatActionSlot,
    CombatActionSlotRequest,
    CombatActionSlotResult,
    CombatRoundAdvanceRequest,
    CombatRoundAdvanceResult,
    CombatRoundState,
    CombatTurnEndRequest,
    CombatTurnEndResult,
    CombatTurnStartRequest,
    CombatTurnStartResult,
    CombatTurnState,
    ImproviseKind,
    ManoeuvreKind,
)


COMBAT_TURN_RULE_ID = "RULE-COMBAT-001:rounds-sides-turns"
ACTION_BUDGET_RULE_ID = "RULE-COMBAT-002:action-budget"
FATE_SECOND_ACTION_RULE_ID = "RULE-FATE-001:second-action"


def start_combat_turn(
    request: CombatTurnStartRequest,
) -> CombatTurnStartResult:
    """Start one chosen participant's complete turn on the current side."""
    state = request.state
    if state.active_turn is not None:
        raise ValueError("another combat turn is already active")
    if state.round_complete:
        raise ValueError("the combat round is already complete")

    participant = state.participant_for(request.actor_id)
    if request.actor_id in state.completed_turn_entity_ids:
        raise ValueError("the participant has already completed this round")
    if participant.side is not state.next_side:
        raise ValueError("the participant does not belong to the current side")

    turn = CombatTurnState(
        actor_id=participant.entity_id,
        side=participant.side,
    )
    updated_state = replace(state, active_turn=turn)
    return CombatTurnStartResult(
        request_id=request.id,
        state=updated_state,
        turn=turn,
        applied_rule_ids=(COMBAT_TURN_RULE_ID,),
    )


def reserve_combat_action_slot(
    request: CombatActionSlotRequest,
) -> CombatActionSlotResult:
    """Validate and reserve an action slot without executing the action."""
    turn = request.state.active_turn
    if turn is None:
        raise ValueError("an active combat turn is required")
    if turn.actor_id != request.actor_id:
        raise ValueError("the action actor does not own the active turn")

    slot_count = len(turn.action_slots)
    if slot_count >= 2:
        raise ValueError("a combat turn cannot contain a third action")
    if slot_count == 0 and request.grant is not ActionSlotGrant.STANDARD:
        raise ValueError("the first action must use the standard slot")
    if slot_count == 1 and request.grant is ActionSlotGrant.STANDARD:
        raise ValueError("the second action requires Fate or an Ability")

    if turn.action_slots:
        previous = turn.action_slots[0].declaration
        current = request.declaration
        if previous.kind is current.kind:
            if current.kind is not CombatActionKind.IMPROVISE:
                raise ValueError("a combat turn cannot repeat the same action")
            if not request.allows_second_improvise:
                raise ValueError(
                    "a second Improvise requires explicit GM allowance"
                )
            if previous.improvise_approach_id == current.improvise_approach_id:
                raise ValueError(
                    "repeated Improvise actions require different approaches"
                )
        if previous.produces_attack and current.produces_attack:
            raise ValueError("a combat turn cannot contain a second attack")

    slot = CombatActionSlot(
        index=slot_count + 1,
        declaration=request.declaration,
        grant=request.grant,
        grant_rule_id=request.grant_rule_id,
    )
    updated_turn = replace(turn, action_slots=(*turn.action_slots, slot))
    updated_state = replace(request.state, active_turn=updated_turn)

    grant_rule_ids: tuple[str, ...] = ()
    if request.grant is ActionSlotGrant.FATE:
        grant_rule_ids = (FATE_SECOND_ACTION_RULE_ID,)
    elif request.grant is ActionSlotGrant.ABILITY:
        assert request.grant_rule_id is not None
        grant_rule_ids = (request.grant_rule_id,)

    return CombatActionSlotResult(
        request_id=request.id,
        state=updated_state,
        slot=slot,
        applied_rule_ids=tuple(
            dict.fromkeys((ACTION_BUDGET_RULE_ID, *grant_rule_ids))
        ),
    )


def end_combat_turn(request: CombatTurnEndRequest) -> CombatTurnEndResult:
    """Complete the active turn and expose the next side, if any."""
    turn = request.state.active_turn
    if turn is None:
        raise ValueError("an active combat turn is required")
    if turn.actor_id != request.actor_id:
        raise ValueError("only the active actor may end this combat turn")
    if not turn.action_slots:
        raise ValueError("a combat turn requires its standard action")
    if any(
        (
            slot.declaration.kind in (
                CombatActionKind.AIM,
                CombatActionKind.ATTACK,
            )
            or (
                slot.declaration.kind is CombatActionKind.IMPROVISE
                and slot.declaration.improvise_kind is ImproviseKind.SPELL
            )
            or (
                slot.declaration.kind is CombatActionKind.MANOEUVRE
                and slot.declaration.manoeuvre
                in (
                    ManoeuvreKind.RUN,
                    ManoeuvreKind.CHARGE,
                    ManoeuvreKind.MOVE_QUIETLY,
                    ManoeuvreKind.MOVE_CAREFULLY,
                )
            )
        )
        and not slot.executed
        for slot in turn.action_slots
    ):
        raise ValueError(
            "reserved Aim, Attack, Run, Charge, Move Quietly, Move Carefully, "
            "and spell Improvise actions must execute first"
        )

    updated_state = replace(
        request.state,
        completed_turn_entity_ids=(
            *request.state.completed_turn_entity_ids,
            request.actor_id,
        ),
        active_turn=None,
    )
    return CombatTurnEndResult(
        request_id=request.id,
        state=updated_state,
        completed_turn=turn,
        next_side=updated_state.next_side,
        round_complete=updated_state.round_complete,
        applied_rule_ids=(COMBAT_TURN_RULE_ID,),
    )


def advance_combat_round(
    request: CombatRoundAdvanceRequest,
) -> CombatRoundAdvanceResult:
    """Advance a completed round, preserving side order and refreshing roster."""
    if request.state.active_turn is not None:
        raise ValueError("an active combat turn must be completed first")
    if not request.state.round_complete:
        raise ValueError("all participants must complete their turns first")

    state = CombatRoundState(
        round_number=request.state.round_number + 1,
        participants=request.next_round_participants,
        side_order=request.state.side_order,
    )
    return CombatRoundAdvanceResult(
        request_id=request.id,
        state=state,
        applied_rule_ids=(COMBAT_TURN_RULE_ID,),
    )
