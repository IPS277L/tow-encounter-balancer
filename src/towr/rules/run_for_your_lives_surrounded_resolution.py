from __future__ import annotations

from towr.domain.retreat_models import RUN_FOR_YOUR_LIVES_RULE_ID
from towr.domain.run_for_your_lives_surrounded_models import (
    RunForYourLivesSurroundedRequest,
    RunForYourLivesSurroundedResult,
    _conflict_opportunity,
    _state_after_registration,
)


def register_run_for_your_lives_surrounded(
    request: RunForYourLivesSurroundedRequest,
) -> RunForYourLivesSurroundedResult:
    """Register an explicit conflict hook without starting or resolving it."""
    if request.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
        raise ValueError("Surrounded application uses an unknown rule")
    opportunity = _conflict_opportunity(request)
    return RunForYourLivesSurroundedResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        opportunity=opportunity,
        previous_state=request.state,
        state=_state_after_registration(request, opportunity),
        applied_rule_ids=tuple(
            dict.fromkeys((*request.source_campaign.applied_rule_ids, request.rule_id))
        ),
    )
