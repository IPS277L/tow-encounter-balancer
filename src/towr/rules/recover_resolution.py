from __future__ import annotations

from dataclasses import replace

from towr.domain.condition_models import Condition
from towr.domain.recover_models import (
    RECOVER_ACTION_RULE_ID,
    RecoverActionExecutionRequest,
    RecoverActionExecutionResult,
    RecoverConditionRemovalChoice,
    RecoverConditionRemovalResult,
    RecoverMode,
    RecoverStandardChoice,
    RecoverStandardResult,
    RecoverTreatWoundChoice,
    RecoverTreatWoundResult,
    RecoverWoundTreatmentApplicationRequest,
    _expected_standard_changes,
    _resolution_result_id,
)
from towr.domain.turn_models import ActionExecutionReceipt, CombatActionKind
from towr.rules.dice import RandomSource
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


def execute_recover_action(
    request: RecoverActionExecutionRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> RecoverActionExecutionResult:
    """Execute one standard or alternative Recover action."""
    if request.rule_id != RECOVER_ACTION_RULE_ID:
        raise ValueError("Recover request uses an unknown source rule")
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
    if slot.declaration.kind is not CombatActionKind.RECOVER:
        raise ValueError("only a Recover action slot can use this executor")
    if slot.executed:
        raise ValueError("the Recover action slot has already been executed")
    if request.actor_conditions.has(Condition.DEFENCELESS):
        raise ValueError("Defenceless characters cannot take actions")
    if (
        request.actor_conditions.has(Condition.BROKEN)
        and request.actor_has_enemy_in_zone
    ):
        raise ValueError("Broken characters can Recover only in a safe Zone")

    resolution = _resolve_choice(request, rng, decisions=decisions)
    result_id = _resolution_result_id(request, resolution)
    executed_slot = replace(
        slot,
        execution=ActionExecutionReceipt(
            id=request.id,
            executor_rule_id=request.rule_id,
            source_request_id=request.id,
            result_request_id=result_id,
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
    return RecoverActionExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        resolution=resolution,
        previous_round_state=request.round_state,
        round_state=updated_round_state,
        slot=executed_slot,
        applied_rule_ids=_applied_rule_ids(request, resolution),
    )


def _resolve_choice(
    request: RecoverActionExecutionRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None,
):
    choice = request.choice
    if isinstance(choice, RecoverStandardChoice):
        return _resolve_standard(choice)
    if isinstance(choice, RecoverTreatWoundChoice):
        return _resolve_treatment(request, choice, rng, decisions=decisions)
    assert isinstance(choice, RecoverConditionRemovalChoice)
    return _resolve_condition_removal(choice, rng, decisions=decisions)


def _resolve_standard(choice: RecoverStandardChoice) -> RecoverStandardResult:
    removed_dice = min(1, choice.magic_state.miscast_dice)
    return RecoverStandardResult(
        source=choice,
        condition_changes=_expected_standard_changes(choice),
        previous_magic_state=choice.magic_state,
        magic_state=replace(
            choice.magic_state,
            miscast_dice=choice.magic_state.miscast_dice - removed_dice,
        ),
        miscast_dice_removed=removed_dice,
        mount_follow_up=choice.mount,
        object_interaction_follow_up=choice.object_interaction,
    )


def _resolve_treatment(
    request: RecoverActionExecutionRequest,
    choice: RecoverTreatWoundChoice,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None,
) -> RecoverTreatWoundResult:
    if not choice.has_required_trappings:
        raise ValueError("Wound treatment requires suitable trappings")
    automatic = choice.automatic_lore_id is not None
    test_result = None
    if not automatic:
        assert choice.recall_test is not None
        test_result = resolve_test(choice.recall_test, rng, decisions=decisions)
    succeeded = automatic or (test_result is not None and test_result.succeeded)
    treatment = None
    if succeeded:
        treatment = RecoverWoundTreatmentApplicationRequest(
            id=f"{request.id}:treatment",
            source_action_id=request.id,
            actor_id=request.actor_id,
            target_id=choice.target.entity_id,
            injury_state=choice.injury_state,
            wound_sequence=choice.wound_sequence,
            automatic_lore_id=choice.automatic_lore_id,
            source_test_id=(
                None if test_result is None else test_result.trace.request_id
            ),
        )
    return RecoverTreatWoundResult(
        source=choice,
        test_result=test_result,
        automatically_succeeded=automatic,
        treatment=treatment,
    )


def _resolve_condition_removal(
    choice: RecoverConditionRemovalChoice,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None,
) -> RecoverConditionRemovalResult:
    if not choice.underlying_cause_allows_removal:
        raise ValueError("an ongoing cause prevents Condition removal")
    result = resolve_test(choice.test, rng, decisions=decisions)
    removed = result.succeeded
    return RecoverConditionRemovalResult(
        source=choice,
        test_result=result,
        previous_conditions=choice.target.conditions,
        conditions=(
            choice.target.conditions.without_condition(choice.condition)
            if removed
            else choice.target.conditions
        ),
        removed=removed,
    )


def _applied_rule_ids(request, resolution) -> tuple[str, ...]:
    values = [request.rule_id]
    if isinstance(resolution, RecoverTreatWoundResult):
        values.append(resolution.source.rule_id)
        if resolution.test_result is not None:
            values.extend(resolution.test_result.trace.applied_rule_ids)
    elif isinstance(resolution, RecoverConditionRemovalResult):
        values.append(resolution.source.rule_id)
        values.extend(resolution.test_result.trace.applied_rule_ids)
    return tuple(dict.fromkeys(values))
