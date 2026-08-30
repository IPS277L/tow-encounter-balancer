from __future__ import annotations

from towr.domain.fate_models import FateBurnResult
from towr.domain.fate_near_miss_models import (
    FateNearMissApplicationRequest,
    FateNearMissApplicationResult,
)
from towr.domain.infection_models import (
    DailyWoundRegistrationRequest,
    DailyWoundRegistrationResult,
    DailyWoundState,
)
from towr.domain.injury_models import (
    CharacterInjuryState,
    CharacterWoundType,
    WoundEffectResult,
)
from towr.domain.wound_lifecycle_models import (
    CHARACTER_WOUND_LIFECYCLE_RULE_ID,
    CharacterWoundLifecycleCompletionRequest,
    CharacterWoundLifecycleCompletionResult,
    CharacterWoundLifecycleOutcome,
    CharacterWoundLifecycleRollRequest,
    CharacterWoundLifecycleRollResult,
    _completion_rule_ids,
    _ordered_rule_ids,
    _state_after_near_miss,
)
from towr.rules.dice import RandomSource
from towr.rules.fate_near_miss_resolution import apply_fate_near_miss
from towr.rules.fate_resolution import burn_fate
from towr.rules.infection_resolution import register_daily_wound
from towr.rules.injury_resolution import (
    WoundDecisionProvider,
    resolve_character_wound,
)
from towr.rules.wound_effect_resolution import resolve_wound_effect
from towr.rules.wound_table import lookup_wound


def roll_character_wound_lifecycle(
    request: CharacterWoundLifecycleRollRequest,
    rng: RandomSource,
    *,
    decisions: WoundDecisionProvider | None = None,
) -> CharacterWoundLifecycleRollResult:
    """Roll a character Wound and stop before effects or daily tracking."""
    if request.rule_id != CHARACTER_WOUND_LIFECYCLE_RULE_ID:
        raise ValueError("Wound lifecycle roll uses an unknown rule")
    wound_result = resolve_character_wound(
        request.wound,
        rng,
        decisions=decisions,
    )
    return CharacterWoundLifecycleRollResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        wound_result=wound_result,
        near_miss_eligible=(
            wound_result.wound_accepted
            and wound_result.subject_type is CharacterWoundType.PLAYER
        ),
        applied_rule_ids=_ordered_rule_ids(
            *wound_result.applied_rule_ids,
            request.rule_id,
        ),
    )


def complete_character_wound_lifecycle(
    request: CharacterWoundLifecycleCompletionRequest,
) -> CharacterWoundLifecycleCompletionResult:
    """Close the Near Miss window, then register and resolve an accepted Wound."""
    if request.rule_id != CHARACTER_WOUND_LIFECYCLE_RULE_ID:
        raise ValueError("Wound lifecycle completion uses an unknown rule")
    if request.roll.rule_id != CHARACTER_WOUND_LIFECYCLE_RULE_ID:
        raise ValueError("Wound lifecycle roll uses an unknown rule")
    table_roll = request.roll.wound_result.table_roll
    if table_roll.entry != lookup_wound(table_roll.total):
        raise ValueError("Wound lifecycle requires a canonical Wounds Table result")

    if not request.roll.wound_result.wound_accepted:
        return _completion_result(
            request,
            outcome=CharacterWoundLifecycleOutcome.NEGATED,
            state=request.current_state,
            daily_wounds=request.daily_wounds,
        )

    if request.near_miss is not None:
        fate_burn = burn_fate(request.near_miss)
        near_miss = apply_fate_near_miss(
            FateNearMissApplicationRequest(
                id=f"{request.id}:near-miss-application",
                session_id=fate_burn.state.session_id,
                target_id=request.roll.source_request.target_id,
                burn=fate_burn,
                wound_request=request.roll.source_request.wound,
                wound_result=request.roll.wound_result,
                consumed_effect_ids=(
                    request.consumed_near_miss_effect_ids
                ),
            )
        )
        return _completion_result(
            request,
            outcome=CharacterWoundLifecycleOutcome.NEAR_MISS,
            state=_state_after_near_miss(request),
            daily_wounds=request.daily_wounds,
            fate_burn=fate_burn,
            near_miss=near_miss,
            consumed_near_miss_effect_ids=near_miss.consumed_effect_ids,
        )

    registration_id = request.daily_registration_id
    assert registration_id is not None
    registration = register_daily_wound(
        DailyWoundRegistrationRequest(
            id=registration_id,
            state=request.daily_wounds,
            target_id=request.roll.source_request.target_id,
            source=request.roll.wound_result,
        )
    )
    effect_request = request.roll.wound_result.effect_request
    assert effect_request is not None
    effect = resolve_wound_effect(
        effect_request,
        request.current_state,
    )
    return _completion_result(
        request,
        outcome=CharacterWoundLifecycleOutcome.ACCEPTED,
        state=effect.state,
        daily_wounds=registration.state,
        registration=registration,
        effect=effect,
    )


def _completion_result(
    request: CharacterWoundLifecycleCompletionRequest,
    *,
    outcome: CharacterWoundLifecycleOutcome,
    state: CharacterInjuryState,
    daily_wounds: DailyWoundState,
    fate_burn: FateBurnResult | None = None,
    near_miss: FateNearMissApplicationResult | None = None,
    registration: DailyWoundRegistrationResult | None = None,
    effect: WoundEffectResult | None = None,
    consumed_near_miss_effect_ids: tuple[str, ...] | None = None,
) -> CharacterWoundLifecycleCompletionResult:
    consumed_effects = (
        request.consumed_near_miss_effect_ids
        if consumed_near_miss_effect_ids is None
        else consumed_near_miss_effect_ids
    )
    return CharacterWoundLifecycleCompletionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        outcome=outcome,
        wound_result=request.roll.wound_result,
        fate_burn=fate_burn,
        near_miss_application=near_miss,
        daily_registration=registration,
        wound_effect=effect,
        previous_state=request.current_state,
        state=state,
        previous_daily_wounds=request.daily_wounds,
        daily_wounds=daily_wounds,
        previous_consumed_roll_ids=request.consumed_roll_ids,
        consumed_roll_ids=(
            *request.consumed_roll_ids,
            request.roll.request_id,
        ),
        previous_consumed_near_miss_effect_ids=(
            request.consumed_near_miss_effect_ids
        ),
        consumed_near_miss_effect_ids=consumed_effects,
        applied_rule_ids=_completion_rule_ids(
            request,
            fate_burn,
            near_miss,
            registration,
            effect,
        ),
    )
