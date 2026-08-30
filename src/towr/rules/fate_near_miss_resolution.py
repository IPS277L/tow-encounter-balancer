from __future__ import annotations

from towr.domain.fate_near_miss_models import (
    FATE_NEAR_MISS_APPLICATION_RULE_ID,
    FateNearMissApplicationRequest,
    FateNearMissApplicationResult,
    _near_miss_applied_rule_ids,
    _near_miss_effect,
)
from towr.rules.wound_table import lookup_wound


def apply_fate_near_miss(
    request: FateNearMissApplicationRequest,
) -> FateNearMissApplicationResult:
    """Consume a Near Miss burn effect and negate its exact accepted Wound."""
    if request.rule_id != FATE_NEAR_MISS_APPLICATION_RULE_ID:
        raise ValueError("Near Miss application uses an unknown rule")
    table_roll = request.wound_result.table_roll
    if table_roll.entry != lookup_wound(table_roll.total):
        raise ValueError("Near Miss requires a canonical Wounds Table result")
    effect = _near_miss_effect(request.burn)
    previous_state = request.wound_result.state
    state = request.wound_request.state
    discarded_effect = request.wound_result.effect_request
    assert discarded_effect is not None
    return FateNearMissApplicationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        session_id=request.session_id,
        target_id=request.target_id,
        fate_state=request.burn.state,
        previous_state=previous_state,
        state=state,
        cancelled_wound=previous_state.wounds[-1],
        discarded_effect_request=discarded_effect,
        previous_consumed_effect_ids=request.consumed_effect_ids,
        consumed_effect_ids=(*request.consumed_effect_ids, effect.id),
        applied_rule_ids=_near_miss_applied_rule_ids(request),
    )
