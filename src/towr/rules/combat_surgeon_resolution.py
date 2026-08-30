from __future__ import annotations

from towr.domain.combat_surgeon_models import (
    COMBAT_SURGEON_RULE_ID,
    CombatSurgeonTreatmentRequest,
    CombatSurgeonTreatmentResult,
    _expected_suppression,
)
from towr.rules.dice import RandomSource
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


def resolve_combat_surgeon_treatment(
    request: CombatSurgeonTreatmentRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> CombatSurgeonTreatmentResult:
    """Try to suppress one treated Wound's until-healed effects this battle."""
    if request.rule_id != COMBAT_SURGEON_RULE_ID:
        raise ValueError("Combat Surgeon request uses an unknown source rule")
    recall = resolve_test(request.recall_test, rng, decisions=decisions)
    return CombatSurgeonTreatmentResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        recall_test_result=recall,
        suppression=_expected_suppression(request, recall),
        previous_state=request.injury_state,
        state=request.injury_state,
        previous_consumed_treatment_result_ids=(
            request.consumed_treatment_result_ids
        ),
        consumed_treatment_result_ids=(
            *request.consumed_treatment_result_ids,
            request.treatment.request_id,
        ),
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    request.treatment.rule_id,
                    *recall.trace.applied_rule_ids,
                )
            )
        ),
    )
