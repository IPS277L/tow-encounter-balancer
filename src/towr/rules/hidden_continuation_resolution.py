from __future__ import annotations

from towr.domain.hidden_continuation_models import (
    HiddenOpportunityContinuationOutcome,
    MoveQuietlyHiddenAttackContinuationRequest,
    MoveQuietlyHiddenAttackContinuationResult,
    _continuation_loss_reason,
    _continuation_rule_ids,
)


def continue_move_quietly_hidden_attack(
    request: MoveQuietlyHiddenAttackContinuationRequest,
) -> MoveQuietlyHiddenAttackContinuationResult:
    """Keep or lose an opportunity after a completed non-attacking action."""
    if not isinstance(request, MoveQuietlyHiddenAttackContinuationRequest):
        raise TypeError("request must be a hidden continuation request")
    reason = _continuation_loss_reason(request)
    consumed = request.consumed_opportunity_ids
    if reason is not None:
        consumed = (*consumed, request.opportunity.id)
    return MoveQuietlyHiddenAttackContinuationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        outcome=(HiddenOpportunityContinuationOutcome.PRESERVED if reason is None
                 else HiddenOpportunityContinuationOutcome.LOST),
        loss_reason=reason,
        previous_consumed_opportunity_ids=request.consumed_opportunity_ids,
        consumed_opportunity_ids=consumed,
        applied_rule_ids=_continuation_rule_ids(request),
    )
