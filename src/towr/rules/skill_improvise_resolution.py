from __future__ import annotations

from dataclasses import replace

from towr.domain.condition_models import Condition, ConditionApplicationRequest
from towr.domain.skill_improvise_models import (
    SKILL_IMPROVISE_ACTION_RULE_ID,
    SKILL_IMPROVISE_CONDITION_RULE_ID,
    SkillImproviseActionExecutionRequest,
    SkillImproviseActionExecutionResult,
    SkillImproviseConditionResolutionRequest,
    SkillImproviseConditionResolutionResult,
    _expected_condition_application,
    _test_result_id,
    _test_rule_ids,
)
from towr.domain.test_models import OpposedTestRequest
from towr.domain.turn_models import (
    ActionExecutionReceipt,
    CombatActionKind,
    ImproviseKind,
)
from towr.rules.condition_effect_resolution import resolve_condition_application
from towr.rules.dice import RandomSource
from towr.rules.opposed_test import resolve_opposed_test
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


def execute_skill_improvise_action(
    request: SkillImproviseActionExecutionRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> SkillImproviseActionExecutionResult:
    """Resolve one basic or opposed Skill Test and complete its action slot."""
    if request.rule_id != SKILL_IMPROVISE_ACTION_RULE_ID:
        raise ValueError("Skill Improvise request uses an unknown source rule")
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
    declaration = slot.declaration
    if (
        declaration.kind is not CombatActionKind.IMPROVISE
        or declaration.improvise_kind is not ImproviseKind.SKILL
    ):
        raise ValueError("only a Skill Improvise slot can use this executor")
    if declaration.improvise_approach_id != request.approach.id:
        raise ValueError("Skill Improvise approach must match the action slot")
    if declaration.improvise_produces_attack:
        raise ValueError("attacking Skill Improvise needs an attack executor")
    if slot.executed:
        raise ValueError("the Skill Improvise slot has already been executed")
    if request.actor_conditions.has(Condition.DEFENCELESS):
        raise ValueError("Defenceless characters cannot take actions")

    if isinstance(request.test, OpposedTestRequest):
        test_result = resolve_opposed_test(
            request.test,
            rng,
            decisions=decisions,
        )
    else:
        test_result = resolve_test(
            request.test,
            rng,
            decisions=decisions,
        )
    condition_application = _expected_condition_application(
        request,
        test_result,
    )
    result_id = _test_result_id(test_result)
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
    return SkillImproviseActionExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        test_result=test_result,
        condition_application=condition_application,
        previous_round_state=request.round_state,
        round_state=updated_round_state,
        slot=executed_slot,
        applied_rule_ids=tuple(
            dict.fromkeys((request.rule_id, *_test_rule_ids(test_result)))
        ),
    )


def resolve_skill_improvise_condition(
    request: SkillImproviseConditionResolutionRequest,
) -> SkillImproviseConditionResolutionResult:
    """Apply one successful approved Skill Improvise Condition effect."""
    if request.rule_id != SKILL_IMPROVISE_CONDITION_RULE_ID:
        raise ValueError("Condition resolution uses an unknown source rule")
    source = request.source.condition_application
    assert source is not None
    if source.rule_id != request.rule_id:
        raise ValueError("Condition application uses an unknown source rule")

    application = resolve_condition_application(
        ConditionApplicationRequest(
            id=source.id,
            state=request.target_state,
            condition=source.condition,
            source_rule_id=source.rule_id,
            classification=source.classification,
            immunities=request.target_immunities,
        )
    )
    return SkillImproviseConditionResolutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        source_application=source,
        target_id=request.target_id,
        application=application,
        previous_target_state=request.target_state,
        target_state=application.state,
        previous_consumed_application_ids=(
            request.consumed_application_ids
        ),
        consumed_application_ids=(
            *request.consumed_application_ids,
            source.id,
        ),
        applied_rule_ids=tuple(
            dict.fromkeys(
                (request.rule_id, *application.applied_rule_ids)
            )
        ),
    )
