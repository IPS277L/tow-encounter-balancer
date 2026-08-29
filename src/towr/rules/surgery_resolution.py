from __future__ import annotations

from towr.domain.injury_models import HealingRequirement
from towr.domain.surgery_models import (
    DOWNTIME_SURGERY_RULE_ID,
    SURGERY_FAILURE_RISK_RULE_ID,
    DowntimeSurgeryRequest,
    DowntimeSurgeryResult,
    SurgeryFailureRiskRequest,
)
from towr.rules.dice import RandomSource
from towr.rules.test_resolution import TestDecisionProvider, resolve_test
from towr.rules.wound_table import lookup_wound


def resolve_downtime_surgery(
    request: DowntimeSurgeryRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> DowntimeSurgeryResult:
    """Attempt ordinary downtime surgery on one surgery-required Wound."""
    if request.rule_id != DOWNTIME_SURGERY_RULE_ID:
        raise ValueError("downtime surgery uses an unknown source rule")
    wound = request.injury_state.wounds[request.wound_sequence - 1]
    entry = lookup_wound(wound.table_total)
    if entry.id is not wound.entry_id:
        raise ValueError("Wound history conflicts with the Wound table")
    if entry.healing is not HealingRequirement.SURGERY_AND_RECOVERY:
        raise ValueError("surgery requires a surgery-and-recovery Wound")

    test_result = resolve_test(
        request.dexterity_test,
        rng,
        decisions=decisions,
    )
    failure_risk = None
    if not test_result.succeeded:
        failure_risk = SurgeryFailureRiskRequest(
            id=f"{request.id}:failure-risk",
            source_surgery_id=request.id,
            source_test_id=request.dexterity_test.id,
            surgeon_id=request.surgeon_id,
            target_id=request.target_id,
            wound_sequence=request.wound_sequence,
            rule_id=SURGERY_FAILURE_RISK_RULE_ID,
        )

    return DowntimeSurgeryResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        test_result=test_result,
        succeeded=test_result.succeeded,
        previous_state=request.injury_state,
        state=request.injury_state,
        failure_risk=failure_risk,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    *test_result.trace.applied_rule_ids,
                    *((failure_risk.rule_id,) if failure_risk else ()),
                )
            )
        ),
    )
