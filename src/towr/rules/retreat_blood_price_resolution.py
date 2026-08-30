from __future__ import annotations

from dataclasses import replace

from towr.domain.retreat_blood_price_models import (
    RetreatBloodPriceApplicationResult,
    RetreatBloodPriceWoundRequest,
    _ordered_rule_ids,
    _wound_lifecycle_request,
)
from towr.domain.retreat_models import RETREAT_ALTERNATIVE_PRICE_RULE_ID
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleCompletionResult,
)
from towr.rules.dice import RandomSource
from towr.rules.injury_resolution import WoundDecisionProvider
from towr.rules.wound_lifecycle_resolution import roll_character_wound_lifecycle


def begin_retreat_blood_price_application(
    request: RetreatBloodPriceWoundRequest,
    rng: RandomSource,
    *,
    decisions: WoundDecisionProvider | None = None,
) -> RetreatBloodPriceApplicationResult:
    """Roll the selected PC's one Wound and stop at the Near Miss window."""
    if request.rule_id != RETREAT_ALTERNATIVE_PRICE_RULE_ID:
        raise ValueError("Retreat blood price uses an unknown rule")
    pending = roll_character_wound_lifecycle(
        _wound_lifecycle_request(request),
        rng,
        decisions=decisions,
    )
    application_id = request.source_price.application_request.id
    return RetreatBloodPriceApplicationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        target_id=request.target_id,
        previous_state=request.state,
        state=pending.wound_result.state,
        character_wound=pending.wound_result,
        pending_character_wound=pending,
        character_wound_completion=None,
        previous_consumed_application_ids=request.consumed_application_ids,
        consumed_application_ids=(
            *request.consumed_application_ids,
            application_id,
        ),
        applied_rule_ids=_ordered_rule_ids(
            *request.source_price.applied_rule_ids,
            request.rule_id,
            *pending.applied_rule_ids,
        ),
    )


def apply_retreat_blood_price_wound_completion(
    result: RetreatBloodPriceApplicationResult,
    completion: CharacterWoundLifecycleCompletionResult,
) -> RetreatBloodPriceApplicationResult:
    """Commit the exact pending blood-price Wound after actor-owned choices."""
    if result.pending_character_wound is None:
        raise ValueError("Retreat blood price result has no pending Wound")
    if result.character_wound_completion is not None:
        raise ValueError("Retreat blood price Wound was already completed")
    if completion.source_request.roll != result.pending_character_wound:
        raise ValueError("Wound completion belongs to another Retreat blood price")
    if completion.previous_state != result.state:
        raise ValueError("Retreat blood price completion used a stale target state")
    return replace(
        result,
        state=completion.state,
        pending_character_wound=None,
        character_wound_completion=completion,
        applied_rule_ids=_ordered_rule_ids(
            *result.applied_rule_ids,
            *completion.applied_rule_ids,
        ),
    )
