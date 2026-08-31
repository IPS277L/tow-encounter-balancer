from __future__ import annotations

from towr.domain.retreat_models import RUN_FOR_YOUR_LIVES_RULE_ID
from towr.domain.run_for_your_lives_exposed_models import (
    RunForYourLivesExposedRequest,
    RunForYourLivesExposedResult,
    _intelligence_exposure,
    _state_after_registration,
)


def register_run_for_your_lives_exposed(
    request: RunForYourLivesExposedRequest,
) -> RunForYourLivesExposedResult:
    """Register explicit enemy intelligence without exploiting it."""
    if request.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
        raise ValueError("Exposed application uses an unknown rule")
    exposure = _intelligence_exposure(request)
    return RunForYourLivesExposedResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        exposure=exposure,
        previous_state=request.state,
        state=_state_after_registration(request, exposure),
        applied_rule_ids=tuple(
            dict.fromkeys((*request.source_campaign.applied_rule_ids, request.rule_id))
        ),
    )
