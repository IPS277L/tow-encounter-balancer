from __future__ import annotations

from towr.domain.retreat_models import RUN_FOR_YOUR_LIVES_RULE_ID
from towr.domain.run_for_your_lives_lost_models import (
    RunForYourLivesLostRequest,
    RunForYourLivesLostResult,
    _delay_consequence,
    _state_after_registration,
)


def register_run_for_your_lives_lost(
    request: RunForYourLivesLostRequest,
) -> RunForYourLivesLostResult:
    """Register a return delay without mutating travel or campaign time."""
    if request.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
        raise ValueError("Lost application uses an unknown rule")
    consequence = _delay_consequence(request)
    return RunForYourLivesLostResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        consequence=consequence,
        previous_state=request.state,
        state=_state_after_registration(request, consequence),
        applied_rule_ids=tuple(
            dict.fromkeys((*request.source_campaign.applied_rule_ids, request.rule_id))
        ),
    )
