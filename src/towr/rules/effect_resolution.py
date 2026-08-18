from __future__ import annotations

from towr.domain.condition_models import (
    EffectApplicationRequest,
    EffectApplicationResult,
)


def resolve_effect_application(
    request: EffectApplicationRequest,
) -> EffectApplicationResult:
    """Decide whether a classified source is blocked before it takes effect."""
    blocking_immunity = next(
        (
            immunity
            for immunity in request.immunities
            if immunity.classification is request.classification
        ),
        None,
    )
    if blocking_immunity is not None:
        return EffectApplicationResult(
            request_id=request.id,
            blocked=True,
            source_rule_id=request.source_rule_id,
            blocked_by_rule_id=blocking_immunity.rule_id,
            applied_rule_ids=(blocking_immunity.rule_id,),
        )
    return EffectApplicationResult(
        request_id=request.id,
        blocked=False,
        source_rule_id=request.source_rule_id,
        blocked_by_rule_id=None,
        applied_rule_ids=(request.source_rule_id,),
    )
