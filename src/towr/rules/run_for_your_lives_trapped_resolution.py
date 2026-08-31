from __future__ import annotations

from towr.domain.retreat_models import RUN_FOR_YOUR_LIVES_RULE_ID
from towr.domain.run_for_your_lives_trapped_models import (
    RunForYourLivesTrappedCostRequest,
    RunForYourLivesTrappedCostResult,
    TrappedEscapeCostDecision,
    _trapped_cost_application,
    _trapped_cost_proof,
    _validate_decision_for_request,
)


def resolve_run_for_your_lives_trapped_cost(
    request: RunForYourLivesTrappedCostRequest,
    decision: TrappedEscapeCostDecision,
) -> RunForYourLivesTrappedCostResult:
    """Choose one explicit Trapped escape-cost branch without applying it."""
    if request.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
        raise ValueError("Run For Your Lives Trapped cost uses an unknown rule")
    _validate_decision_for_request(request, decision)
    proof = _trapped_cost_proof(request, decision)
    consequence_id = request.source_campaign.consequence.id
    return RunForYourLivesTrappedCostResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        decision=decision,
        proof=proof,
        application_request=_trapped_cost_application(proof),
        previous_consumed_consequence_ids=request.consumed_consequence_ids,
        consumed_consequence_ids=(
            *request.consumed_consequence_ids,
            consequence_id,
        ),
        applied_rule_ids=tuple(
            dict.fromkeys(
                (*request.source_campaign.applied_rule_ids, request.rule_id)
            )
        ),
    )
