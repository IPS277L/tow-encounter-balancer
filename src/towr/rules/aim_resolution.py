from __future__ import annotations

from dataclasses import replace

from towr.domain.aim_models import (
    AIM_ACTION_RULE_ID,
    AIM_FOLLOW_UP_RULE_ID,
    AimActionExecutionRequest,
    AimActionExecutionResult,
    AimBonusSnapshot,
    AimFollowUpRequest,
    AimFollowUpResult,
    _expected_follow_up,
)
from towr.domain.turn_models import ActionExecutionReceipt, CombatActionKind
from towr.rules.dice import RandomSource
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


def execute_aim_action(
    request: AimActionExecutionRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> AimActionExecutionResult:
    """Resolve an Awareness Test and create a one-use Aim bonus snapshot."""
    if request.rule_id != AIM_ACTION_RULE_ID:
        raise ValueError("Aim request uses an unknown source rule")
    turn = request.round_state.active_turn
    assert turn is not None
    if request.slot_index > len(turn.action_slots):
        raise ValueError("the requested action slot has not been reserved")
    if any(
        not slot.executed
        for slot in turn.action_slots[: request.slot_index - 1]
    ):
        raise ValueError("earlier action slots must be executed first")
    slot = turn.action_slots[request.slot_index - 1]
    if slot.declaration.kind is not CombatActionKind.AIM:
        raise ValueError("only an Aim action slot can use this executor")
    if slot.executed:
        raise ValueError("the Aim action slot has already been executed")

    awareness = resolve_test(request.awareness_test, rng, decisions=decisions)
    bonus = AimBonusSnapshot(
        id=f"{request.id}:bonus",
        source_request_id=request.id,
        source_test_id=request.awareness_test.id,
        actor_id=request.actor_id,
        target_id=request.target_id,
        bonus_dice=awareness.successes,
        rule_id=request.rule_id,
    )
    executed_slot = replace(
        slot,
        execution=ActionExecutionReceipt(
            id=request.id,
            executor_rule_id=request.rule_id,
            source_request_id=request.id,
            result_request_id=awareness.trace.request_id,
            actor_id=request.actor_id,
            round_number=request.round_state.round_number,
            slot_index=slot.index,
            declaration=slot.declaration,
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
    return AimActionExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        awareness_test_result=awareness,
        bonus=bonus,
        previous_round_state=request.round_state,
        round_state=updated_round_state,
        slot=executed_slot,
        applied_rule_ids=tuple(
            dict.fromkeys((request.rule_id, *awareness.trace.applied_rule_ids))
        ),
    )


def resolve_aim_follow_up(request: AimFollowUpRequest) -> AimFollowUpResult:
    """Consume Aim on its owner's next action, applying or losing its bonus."""
    if request.rule_id != AIM_FOLLOW_UP_RULE_ID:
        raise ValueError("Aim follow-up uses an unknown source rule")
    outcome, attack, modifier = _expected_follow_up(request)
    return AimFollowUpResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        outcome=outcome,
        attack=attack,
        modifier=modifier,
        applied_rule_ids=(request.rule_id, request.aim.rule_id),
    )
