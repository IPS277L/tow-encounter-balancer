from __future__ import annotations

from towr.domain.hidden_attack_models import HiddenAttackOpportunityLossReason
from towr.domain.hidden_give_ground_models import (
    HiddenGiveGroundLossRequest,
    HiddenGiveGroundLossResult,
    _hidden_give_ground_rule_ids,
)


def lose_hidden_opportunity_after_give_ground(
    request: HiddenGiveGroundLossRequest,
) -> HiddenGiveGroundLossResult:
    """Consume the opportunity after completed Give Ground without moving again."""
    if not isinstance(request, HiddenGiveGroundLossRequest):
        raise TypeError("request must be a HiddenGiveGroundLossRequest")
    opportunity = request.move_quietly.hidden_attack_opportunity
    assert opportunity is not None
    return HiddenGiveGroundLossResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        reason=HiddenAttackOpportunityLossReason.LEFT_HIDING_POSITION,
        consumed_opportunity_ids=(*request.consumed_opportunity_ids, opportunity.id),
        applied_rule_ids=_hidden_give_ground_rule_ids(request),
    )
