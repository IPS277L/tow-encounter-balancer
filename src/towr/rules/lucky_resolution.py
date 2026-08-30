from __future__ import annotations

from towr.domain.lucky_models import (
    LUCKY_RULE_ID,
    LuckyGamblingTestPreparationRequest,
    LuckyGamblingTestPreparationResult,
    _expected_lucky_gambling_test,
)


def prepare_lucky_gambling_test(
    request: LuckyGamblingTestPreparationRequest,
) -> LuckyGamblingTestPreparationResult:
    """Make an eligible game-of-chance Test Glorious without spending Fate."""
    if request.rule_id != LUCKY_RULE_ID:
        raise ValueError("Lucky gambling preparation uses an unknown rule")
    proof, test = _expected_lucky_gambling_test(request)
    return LuckyGamblingTestPreparationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        proof=proof,
        test=test,
        applied_rule_ids=(request.rule_id,),
    )
