from __future__ import annotations

from towr.domain.retreat_misfortune_price_models import (
    RetreatMisfortunePriceApplicationResult,
    RetreatMisfortunePriceCampaignRequest,
    _ordered_rule_ids,
    _registered_opportunity,
    _state_after_registration,
)
from towr.domain.retreat_models import RETREAT_ALTERNATIVE_PRICE_RULE_ID


def apply_retreat_misfortune_price(
    request: RetreatMisfortunePriceCampaignRequest,
) -> RetreatMisfortunePriceApplicationResult:
    """Register one explicit golden opportunity without executing its content."""
    if request.rule_id != RETREAT_ALTERNATIVE_PRICE_RULE_ID:
        raise ValueError("Retreat misfortune price uses an unknown rule")
    opportunity = _registered_opportunity(request)
    return RetreatMisfortunePriceApplicationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        opportunity=opportunity,
        previous_state=request.campaign_state,
        state=_state_after_registration(request, opportunity),
        applied_rule_ids=_ordered_rule_ids(
            *request.source_price.applied_rule_ids,
            request.rule_id,
        ),
    )
