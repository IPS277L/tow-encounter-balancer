from __future__ import annotations

from dataclasses import replace

from towr.domain.festering_wound_models import (
    FESTERING_WOUNDS_RECOVERY_APPLICATION_RULE_ID,
    FesteringWoundsRecoveryApplicationRequest,
    FesteringWoundsRecoveryApplicationResult,
)


def apply_festering_wounds_recovery(
    request: FesteringWoundsRecoveryApplicationRequest,
) -> FesteringWoundsRecoveryApplicationResult:
    """Remove every Festering Wound after successful Rest and Recovery."""
    if request.rule_id != FESTERING_WOUNDS_RECOVERY_APPLICATION_RULE_ID:
        raise ValueError("Festering recovery uses an unknown rule")
    follow_up = request.endeavour.festering_wounds_recovery
    assert follow_up is not None
    return FesteringWoundsRecoveryApplicationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        target_id=request.target_id,
        previous_state=request.state,
        state=replace(request.state, wounds=()),
        recovered_wounds=request.state.wounds,
        previous_consumed_source_ids=request.consumed_source_ids,
        consumed_source_ids=(*request.consumed_source_ids, follow_up.id),
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    follow_up.rule_id,
                    *request.endeavour.applied_rule_ids,
                )
            )
        ),
    )
