from __future__ import annotations

from dataclasses import replace

from towr.domain.action_execution_models import (
    AttackActionExecutionRequest,
    AttackActionExecutionResult,
)
from towr.domain.turn_models import (
    ActionExecutionReceipt,
    CombatActionKind,
)
from towr.rules.dice import RandomSource
from towr.rules.kernel import ResolutionDecisionProvider, resolve_kernel_attack


ATTACK_ACTION_EXECUTION_RULE_ID = "RULE-COMBAT-004:attack-action-execution"


def execute_attack_action(
    request: AttackActionExecutionRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> AttackActionExecutionResult:
    """Execute one reserved Attack slot through the existing K1 kernel."""
    turn = request.state.active_turn
    if turn is None:
        raise ValueError("an active combat turn is required")
    if turn.actor_id != request.actor_id:
        raise ValueError("the attack actor does not own the active turn")
    if request.slot_index > len(turn.action_slots):
        raise ValueError("the requested action slot has not been reserved")
    earlier_slots = turn.action_slots[: request.slot_index - 1]
    if any(not slot.executed for slot in earlier_slots):
        raise ValueError("earlier action slots must be executed first")

    slot = turn.action_slots[request.slot_index - 1]
    if slot.declaration.kind is not CombatActionKind.ATTACK:
        raise ValueError("only an Attack action slot can use this executor")
    if slot.executed:
        raise ValueError("the Attack action slot has already been executed")

    resolution = resolve_kernel_attack(
        request.kernel_request,
        rng,
        decisions=decisions,
    )
    if resolution.request_id != request.kernel_request.id:
        raise ValueError("kernel result does not belong to the attack request")

    executed_slot = replace(
        slot,
        execution=ActionExecutionReceipt(
            id=request.id,
            executor_rule_id=ATTACK_ACTION_EXECUTION_RULE_ID,
            source_request_id=request.kernel_request.id,
            result_request_id=resolution.request_id,
        ),
    )
    updated_slots = tuple(
        executed_slot if item.index == request.slot_index else item
        for item in turn.action_slots
    )
    updated_turn = replace(turn, action_slots=updated_slots)
    updated_state = replace(request.state, active_turn=updated_turn)

    return AttackActionExecutionResult(
        request_id=request.id,
        actor_id=request.actor_id,
        target_id=request.target_id,
        slot_index=request.slot_index,
        previous_state=request.state,
        state=updated_state,
        slot=executed_slot,
        resolution=resolution,
        applied_rule_ids=(ATTACK_ACTION_EXECUTION_RULE_ID,),
    )
