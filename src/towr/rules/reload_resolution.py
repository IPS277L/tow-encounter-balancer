from __future__ import annotations

from dataclasses import replace

from towr.domain.reload_models import (
    RELOAD_RULE_ID,
    ReloadActionExecutionRequest,
    ReloadActionExecutionResult,
    _exacting_request,
    _validate_reload_action_context,
)
from towr.domain.turn_models import ActionExecutionReceipt
from towr.rules.dice import RandomSource
from towr.rules.exacting_test_resolution import (
    resolve_exacting_test_contribution,
)
from towr.rules.test_resolution import TestDecisionProvider


def execute_reload_action(
    request: ReloadActionExecutionRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> ReloadActionExecutionResult:
    """Spend one action and make one Dexterity Test toward reloading."""
    if request.rule_id != RELOAD_RULE_ID:
        raise ValueError("reload action uses an unknown source rule")
    _validate_reload_action_context(request)
    exacting = resolve_exacting_test_contribution(
        _exacting_request(request),
        rng,
        decisions=decisions,
    )
    weapon_state = replace(
        request.weapon_state,
        exacting=exacting.progress,
        loaded=exacting.progress.completed,
    )

    turn = request.round_state.active_turn
    assert turn is not None
    slot = turn.action_slots[request.slot_index - 1]
    executed_slot = replace(
        slot,
        execution=ActionExecutionReceipt(
            id=request.id,
            executor_rule_id=request.rule_id,
            source_request_id=request.id,
            result_request_id=exacting.request_id,
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
    round_state = replace(
        request.round_state,
        active_turn=replace(turn, action_slots=updated_slots),
    )
    return ReloadActionExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        exacting=exacting,
        previous_state=request.weapon_state,
        state=weapon_state,
        previous_round_state=request.round_state,
        round_state=round_state,
        slot=executed_slot,
        applied_rule_ids=tuple(
            dict.fromkeys((request.rule_id, *exacting.applied_rule_ids))
        ),
    )
