from __future__ import annotations

from dataclasses import replace

from towr.domain.magic_models import (
    MiscastPoolOutcome,
    MiscastPoolResolutionRequest,
    MiscastPoolResolutionResult,
    MiscastRollRequest,
)
from towr.domain.test_models import RerollLock


RULE_OF_NINE_RULE_ID = "RULE-MAGIC-003:rule-of-nine"
MISCAST_POOL_RULE_ID = "RULE-MAGIC-004:miscast-pool"


def rule_of_nine_reroll_lock() -> RerollLock:
    return RerollLock(rule_id=RULE_OF_NINE_RULE_ID, value=9)


def resolve_miscast_pool_increase(
    request: MiscastPoolResolutionRequest,
) -> MiscastPoolResolutionResult:
    previous = request.state.miscast_dice
    current = previous + request.source.amount
    state = replace(request.state, miscast_dice=current)
    triggered = current > request.wizard_level
    roll_request = (
        MiscastRollRequest(
            resolution_id=request.id,
            source_resolution_id=request.source.resolution_id,
            target_id=request.source.target_id,
            pool_dice_count=current,
            rule_id=request.rule_id,
        )
        if triggered
        else None
    )
    return MiscastPoolResolutionResult(
        request_id=request.id,
        target_id=request.source.target_id,
        state=state,
        previous_miscast_dice=previous,
        dice_added=request.source.amount,
        outcome=(
            MiscastPoolOutcome.MISCAST_TRIGGERED
            if triggered
            else MiscastPoolOutcome.ACCUMULATED
        ),
        roll_request=roll_request,
        applied_rule_ids=_unique_rule_ids(
            request.source.trigger_rule_id,
            request.source.rule_id,
            request.rule_id,
        ),
    )


def _unique_rule_ids(*rule_ids: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(rule_ids))
