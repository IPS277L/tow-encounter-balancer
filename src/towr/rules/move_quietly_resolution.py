from __future__ import annotations

from dataclasses import replace

from towr.domain.condition_models import Condition
from towr.domain.move_quietly_models import (
    MOVE_QUIETLY_RULE_ID,
    MOVE_QUIETLY_TIE_RULE_ID,
    MoveQuietlyActionExecutionRequest,
    MoveQuietlyActionExecutionResult,
    MoveQuietlyHiddenAttackOpportunity,
    MoveQuietlyHidingChoice,
    MoveQuietlyOutcome,
)
from towr.domain.movement_models import MovementSpeed
from towr.domain.test_models import OpposedSide
from towr.domain.turn_models import (
    ActionExecutionReceipt,
    CombatActionKind,
    ManoeuvreKind,
)
from towr.rules.dice import RandomSource
from towr.rules.free_movement_resolution import (
    FREE_MOVEMENT_RULE_ID,
    resolve_free_movement,
)
from towr.rules.opposed_test import resolve_opposed_test
from towr.rules.test_resolution import TestDecisionProvider


def execute_move_quietly_action(
    request: MoveQuietlyActionExecutionRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> MoveQuietlyActionExecutionResult:
    """Resolve Stealth versus the most vigilant enemy and optional hiding."""
    if request.rule_id != MOVE_QUIETLY_RULE_ID:
        raise ValueError("Move Quietly request uses an unknown source rule")
    turn = request.round_state.active_turn
    assert turn is not None
    if request.slot_index > len(turn.action_slots):
        raise ValueError("the requested action slot has not been reserved")
    earlier_slots = turn.action_slots[: request.slot_index - 1]
    if any(not slot.executed for slot in earlier_slots):
        raise ValueError("earlier action slots must be executed first")
    slot = turn.action_slots[request.slot_index - 1]
    if (
        slot.declaration.kind is not CombatActionKind.MANOEUVRE
        or slot.declaration.manoeuvre is not ManoeuvreKind.MOVE_QUIETLY
    ):
        raise ValueError("only Move Quietly can use this executor")
    if slot.executed:
        raise ValueError("the Move Quietly slot has already been executed")

    if request.speed is MovementSpeed.SLOW:
        raise ValueError("Slow creatures cannot Move Quietly")
    if request.actor_conditions.has(Condition.BURDENED):
        raise ValueError("Burdened creatures cannot use Manoeuvres")
    if request.actor_conditions.has(Condition.PRONE):
        raise ValueError("Prone creatures cannot Move Quietly out of their Zone")
    if request.actor_conditions.has(Condition.DEFENCELESS):
        raise ValueError("Defenceless creatures cannot Move Quietly")

    prepared_movement = None
    if request.hiding_choice is MoveQuietlyHidingChoice.HIDE_IN_CURRENT_ZONE:
        if request.actor_id in request.spatial_state.free_move_used_entity_ids:
            raise ValueError("the actor's free movement was already used")
    elif request.free_movement is not None:
        prepared_movement = resolve_free_movement(request.free_movement)

    opposed = resolve_opposed_test(
        request.opposed_test,
        rng,
        decisions=decisions,
    )
    contest_won = opposed.winner is OpposedSide.INITIATOR
    hiding_requested = (
        request.hiding_choice is not MoveQuietlyHidingChoice.DECLINE
    )
    if contest_won and hiding_requested:
        movement_result = prepared_movement
        if movement_result is None:
            spatial_state = replace(
                request.spatial_state,
                free_move_used_entity_ids=(
                    *request.spatial_state.free_move_used_entity_ids,
                    request.actor_id,
                ),
            )
        else:
            spatial_state = movement_result.state
        outcome = MoveQuietlyOutcome.HIDDEN
        assert request.hiding_position_id is not None
        hidden = MoveQuietlyHiddenAttackOpportunity(
            id=f"{request.id}:hidden",
            source_request_id=request.id,
            actor_id=request.actor_id,
            hiding_position_id=request.hiding_position_id,
            unaware_enemy_ids=tuple(
                item.entity_id for item in request.observers
            ),
            rule_id=request.rule_id,
        )
    else:
        movement_result = None
        spatial_state = request.spatial_state
        hidden = None
        outcome = (
            MoveQuietlyOutcome.SUCCEEDED_WITHOUT_HIDING
            if contest_won
            else MoveQuietlyOutcome.FAILED
        )

    executed_slot = replace(
        slot,
        execution=ActionExecutionReceipt(
            id=request.id,
            executor_rule_id=request.rule_id,
            source_request_id=request.id,
            result_request_id=opposed.request_id,
        ),
    )
    updated_slots = tuple(
        executed_slot if item.index == request.slot_index else item
        for item in turn.action_slots
    )
    updated_round_state = replace(
        request.round_state,
        active_turn=replace(turn, action_slots=updated_slots),
    )
    movement_rule_ids = ()
    if outcome is MoveQuietlyOutcome.HIDDEN:
        movement_rule_ids = (
            (FREE_MOVEMENT_RULE_ID,)
            if movement_result is None
            else movement_result.applied_rule_ids
        )
    return MoveQuietlyActionExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        actor_id=request.actor_id,
        slot_index=request.slot_index,
        selected_observer=request.selected_observer,
        opposed_test_request=request.opposed_test,
        opposed_test_result=opposed,
        outcome=outcome,
        free_movement_result=movement_result,
        hidden_attack_opportunity=hidden,
        previous_round_state=request.round_state,
        round_state=updated_round_state,
        previous_spatial_state=request.spatial_state,
        spatial_state=spatial_state,
        slot=executed_slot,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    MOVE_QUIETLY_TIE_RULE_ID,
                    *opposed.initiator.trace.applied_rule_ids,
                    *opposed.opponent.trace.applied_rule_ids,
                    *movement_rule_ids,
                )
            )
        ),
    )
