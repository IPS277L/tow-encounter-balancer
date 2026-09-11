from __future__ import annotations

from towr.domain.retreat_models import RUN_FOR_YOUR_LIVES_RULE_ID
from towr.domain.run_for_your_lives_indebted_models import (
    RunForYourLivesIndebtedRequest,
    RunForYourLivesIndebtedResult,
    _debt_obligation,
    _state_after_registration,
)


def register_run_for_your_lives_indebted(
    request: RunForYourLivesIndebtedRequest,
) -> RunForYourLivesIndebtedResult:
    """Register an outstanding rescue debt without resolving repayment."""
    if request.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
        raise ValueError("Indebted application uses an unknown rule")
    obligation = _debt_obligation(request)
    return RunForYourLivesIndebtedResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        obligation=obligation,
        previous_state=request.state,
        state=_state_after_registration(request, obligation),
        applied_rule_ids=tuple(
            dict.fromkeys((*request.source_campaign.applied_rule_ids, request.rule_id))
        ),
    )
