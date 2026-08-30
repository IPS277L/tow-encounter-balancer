from __future__ import annotations

from towr.domain.fate_models import (
    FATE_SESSION_RULE_ID,
    FateGloriousSpendRequest,
    FateGloriousSpendResult,
    _expected_fate_glorious_spend,
)
from towr.domain.test_models import FATE_GLORIOUS_RULE_ID


def spend_fate_for_glorious(
    request: FateGloriousSpendRequest,
) -> FateGloriousSpendResult:
    """Spend one session Fate before or after the initial roll."""
    if request.rule_id != FATE_GLORIOUS_RULE_ID:
        raise ValueError("Fate Glorious spend uses an unknown rule")
    spend, proof, state, test = _expected_fate_glorious_spend(request)
    return FateGloriousSpendResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        previous_state=request.state,
        state=state,
        spend=spend,
        proof=proof,
        test=test,
        applied_rule_ids=(FATE_SESSION_RULE_ID, request.rule_id),
    )
