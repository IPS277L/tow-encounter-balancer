from __future__ import annotations

from towr.domain.campaign_consequence_models import (
    RunForYourLivesCampaignApplicationRequest,
    RunForYourLivesCampaignApplicationResult,
    _registered_consequence,
    _state_after_registration,
)
from towr.domain.retreat_models import RUN_FOR_YOUR_LIVES_RULE_ID


def register_run_for_your_lives_campaign_consequence(
    request: RunForYourLivesCampaignApplicationRequest,
) -> RunForYourLivesCampaignApplicationResult:
    """Register an authored table consequence without executing its effects."""
    if request.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
        raise ValueError("Run For Your Lives campaign application uses unknown rule")
    consequence = _registered_consequence(request)
    return RunForYourLivesCampaignApplicationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        consequence=consequence,
        previous_state=request.campaign_state,
        state=_state_after_registration(request, consequence),
        applied_rule_ids=(request.rule_id,),
    )
