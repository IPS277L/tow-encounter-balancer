from __future__ import annotations

from towr.domain.retreat_models import RUN_FOR_YOUR_LIVES_RULE_ID
from towr.domain.run_for_your_lives_trapped_capture_models import (
    RunForYourLivesTrappedCaptureRequest,
    RunForYourLivesTrappedCaptureResult,
    _capture_records,
    _state_after_capture,
)


def apply_run_for_your_lives_trapped_capture(
    request: RunForYourLivesTrappedCaptureRequest,
) -> RunForYourLivesTrappedCaptureResult:
    """Register explicit active captivity facts without resolving their aftermath."""
    if request.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
        raise ValueError("Trapped capture application uses an unknown rule")
    captures = _capture_records(request)
    return RunForYourLivesTrappedCaptureResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        captures=captures,
        previous_state=request.state,
        state=_state_after_capture(request, captures),
        applied_rule_ids=tuple(
            dict.fromkeys((*request.source_cost.applied_rule_ids, request.rule_id))
        ),
    )
