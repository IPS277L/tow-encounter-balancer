from __future__ import annotations

from towr.domain.retreat_models import RUN_FOR_YOUR_LIVES_RULE_ID
from towr.domain.run_for_your_lives_trapped_other_models import (
    RunForYourLivesTrappedOtherRequest,
    RunForYourLivesTrappedOtherResult,
    _other_cost,
    _state_after_registration,
)


def apply_run_for_your_lives_trapped_other(
    request: RunForYourLivesTrappedOtherRequest,
) -> RunForYourLivesTrappedOtherResult:
    """Register an opaque GM-defined escape price without interpreting it."""
    if request.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
        raise ValueError("Trapped other application uses an unknown rule")
    cost = _other_cost(request)
    return RunForYourLivesTrappedOtherResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        cost=cost,
        previous_state=request.state,
        state=_state_after_registration(request, cost),
        applied_rule_ids=tuple(
            dict.fromkeys((*request.source_cost.applied_rule_ids, request.rule_id))
        ),
    )
