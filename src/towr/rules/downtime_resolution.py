from __future__ import annotations

from towr.domain.downtime_models import (
    FESTERING_WOUNDS_RECOVERY_RULE_ID,
    REST_AND_RECOVERY_ENDEAVOUR_RULE_ID,
    FesteringWoundsRecoveryRequest,
    RestAndRecoveryEndeavourRequest,
    RestAndRecoveryEndeavourResult,
)
from towr.rules.dice import RandomSource
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


def execute_rest_and_recovery_endeavour(
    request: RestAndRecoveryEndeavourRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> RestAndRecoveryEndeavourResult:
    """Resolve the Endurance Test for one Rest and Recovery Endeavour."""
    if request.rule_id != REST_AND_RECOVERY_ENDEAVOUR_RULE_ID:
        raise ValueError("Rest and Recovery uses an unknown source rule")

    test_result = resolve_test(
        request.endurance_test,
        rng,
        decisions=decisions,
    )
    festering_wounds_recovery = None
    if test_result.succeeded:
        festering_wounds_recovery = FesteringWoundsRecoveryRequest(
            id=f"{request.id}:festering-wounds",
            target_id=request.target_id,
            source_endeavour_id=request.id,
            source_test_id=request.endurance_test.id,
            rule_id=FESTERING_WOUNDS_RECOVERY_RULE_ID,
        )

    return RestAndRecoveryEndeavourResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        test_result=test_result,
        succeeded=test_result.succeeded,
        festering_wounds_recovery=festering_wounds_recovery,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    *test_result.trace.applied_rule_ids,
                )
            )
        ),
    )
