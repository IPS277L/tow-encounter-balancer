from __future__ import annotations

from dataclasses import replace

from towr.domain.condition_models import Condition
from towr.domain.help_models import (
    HELP_ACTION_RULE_ID,
    HELP_BONUS_RULE_ID,
    HelpActionExecutionRequest,
    HelpActionExecutionResult,
    HelpBonusApplicationRequest,
    HelpBonusApplicationResult,
    HelpBonusSnapshot,
    _expected_help_application,
)
from towr.domain.turn_models import ActionExecutionReceipt, CombatActionKind
from towr.rules.dice import RandomSource
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


def execute_help_action(
    request: HelpActionExecutionRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> HelpActionExecutionResult:
    """Resolve one ally's Help Test and create its intended-Test bonus."""
    if request.rule_id != HELP_ACTION_RULE_ID:
        raise ValueError("Help request uses an unknown source rule")
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
    if slot.declaration.kind is not CombatActionKind.HELP:
        raise ValueError("only a Help action slot can use this executor")
    if slot.executed:
        raise ValueError("the Help action slot has already been executed")
    if request.actor_conditions.has(Condition.DEAFENED):
        raise ValueError("Deafened characters cannot use Help")
    if request.actor_conditions.has(Condition.DEFENCELESS):
        raise ValueError("Defenceless characters cannot take actions")

    help_test_result = resolve_test(
        request.help_test,
        rng,
        decisions=decisions,
    )
    bonus = HelpBonusSnapshot(
        id=f"{request.id}:bonus",
        source_request_id=request.id,
        source_test_id=request.help_test.id,
        helper_id=request.actor_id,
        beneficiary_id=request.beneficiary_id,
        beneficiary_test_id=request.beneficiary_test_id,
        help_skill=request.help_skill,
        beneficiary_skill=request.beneficiary_skill,
        bonus_dice=help_test_result.successes,
        different_skill_approved_by_gm=(
            request.different_skill_approved_by_gm
        ),
    )
    executed_slot = replace(
        slot,
        execution=ActionExecutionReceipt(
            id=request.id,
            executor_rule_id=request.rule_id,
            source_request_id=request.id,
            result_request_id=help_test_result.trace.request_id,
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
    return HelpActionExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        help_test_result=help_test_result,
        bonus=bonus,
        previous_round_state=request.round_state,
        round_state=updated_round_state,
        slot=executed_slot,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    HELP_BONUS_RULE_ID,
                    *help_test_result.trace.applied_rule_ids,
                )
            )
        ),
    )


def apply_help_bonus(
    request: HelpBonusApplicationRequest,
) -> HelpBonusApplicationResult:
    """Apply one Help snapshot to the exact allied Test it names."""
    if request.rule_id != HELP_BONUS_RULE_ID:
        raise ValueError("Help application uses an unknown source rule")
    test, modifier = _expected_help_application(request)
    return HelpBonusApplicationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        test=test,
        modifier=modifier,
        applied_rule_ids=(request.rule_id, request.help.rule_id),
    )
