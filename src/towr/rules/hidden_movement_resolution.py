from __future__ import annotations

from towr.domain.hidden_attack_models import HiddenAttackOpportunityLossReason
from towr.domain.hidden_movement_models import (
    HiddenFreeMovementLossRequest,
    HiddenFreeMovementLossResult,
    _hidden_movement_rule_ids,
)


def lose_hidden_opportunity_after_free_movement(
    request: HiddenFreeMovementLossRequest,
) -> HiddenFreeMovementLossResult:
    """Consume a hidden opportunity after completed movement; do not move again."""
    if not isinstance(request, HiddenFreeMovementLossRequest):
        raise TypeError("request must be a HiddenFreeMovementLossRequest")
    opportunity = request.move_quietly.hidden_attack_opportunity
    assert opportunity is not None
    return HiddenFreeMovementLossResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        reason=HiddenAttackOpportunityLossReason.LEFT_HIDING_POSITION,
        consumed_opportunity_ids=(
            *request.consumed_opportunity_ids,
            opportunity.id,
        ),
        applied_rule_ids=_hidden_movement_rule_ids(request),
    )
