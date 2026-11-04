from __future__ import annotations

from dataclasses import replace

from towr.domain.recover_models import (
    END_BATTLE_WOUND_TREATMENT_RULE_ID,
    RECOVER_TREAT_WOUND_APPLICATION_RULE_ID,
    RECOVER_TREAT_WOUND_RULE_ID,
    EndBattleWoundTreatmentRequest,
    EndBattleWoundTreatmentResult,
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
    RecoverWoundTreatmentResolutionRequest,
    RecoverWoundTreatmentResolutionResult,
    _expected_end_battle_treatment_transition,
    _expected_wound_treatment_transition,
    _expected_standard_changes,
    _validate_recover_action,
    _expected_recover_execution,
)
from towr.rules.dice import RandomSource
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


def execute_recover_action(
    request: RecoverActionExecutionRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> RecoverActionExecutionResult:
    """Execute one standard or alternative Recover action."""
    _validate_recover_action(request)
    resolution = _resolve_choice(request, rng, decisions=decisions)
    return _expected_recover_execution(request, resolution)


def apply_recover_wound_treatment(
    request: RecoverWoundTreatmentResolutionRequest,
) -> RecoverWoundTreatmentResolutionResult:
    """Apply one successful Recover treatment to its exact Wound snapshot."""
    if request.rule_id != RECOVER_TREAT_WOUND_APPLICATION_RULE_ID:
        raise ValueError("treatment application uses an unknown source rule")
    state, removed_effects, removed_conditions = (
        _expected_wound_treatment_transition(request)
    )
    treatment = request.recover.resolution.treatment
    assert treatment is not None
    return RecoverWoundTreatmentResolutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        target_id=request.target_id,
        wound_sequence=treatment.wound_sequence,
        previous_state=request.injury_state,
        state=state,
        removed_effects=removed_effects,
        removed_conditions=removed_conditions,
        previous_consumed_application_ids=request.consumed_application_ids,
        consumed_application_ids=(
            *request.consumed_application_ids,
            treatment.id,
        ),
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    treatment.rule_id,
                    *request.recover.applied_rule_ids,
                )
            )
        ),
    )


def apply_end_battle_wound_treatment(
    request: EndBattleWoundTreatmentRequest,
) -> EndBattleWoundTreatmentResult:
    """Treat every untreated Wound in one confirmed end-battle window."""
    if request.rule_id != END_BATTLE_WOUND_TREATMENT_RULE_ID:
        raise ValueError("end-battle treatment uses an unknown source rule")
    state, removed_effects, removed_conditions = (
        _expected_end_battle_treatment_transition(request)
    )
    sequences = tuple(
        wound.sequence
        for wound in request.injury_state.wounds
        if not wound.treated
    )
    return EndBattleWoundTreatmentResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        target_id=request.target_id,
        treated_wound_sequences=sequences,
        previous_state=request.injury_state,
        state=state,
        removed_effects=removed_effects,
        removed_conditions=removed_conditions,
        previous_consumed_context_ids=request.consumed_context_ids,
        consumed_context_ids=(
            *request.consumed_context_ids,
            request.context.id,
        ),
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    request.context.rule_id,
                    RECOVER_TREAT_WOUND_RULE_ID,
                )
            )
        ),
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
