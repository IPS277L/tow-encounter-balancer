from __future__ import annotations

from towr.domain.resolution_models import (
    NearbyTargetStaggerResult,
    NearbyTargetsStaggerResolutionRequest,
    NearbyTargetsStaggerResolutionResult,
)
from towr.rules.dice import RandomSource
from towr.rules.stagger_impact_resolution import (
    StaggerImpactDecisionProvider,
    resolve_stagger_impact,
)


def resolve_nearby_targets_stagger(
    request: NearbyTargetsStaggerResolutionRequest,
    rng: RandomSource,
    *,
    decisions: StaggerImpactDecisionProvider | None = None,
) -> NearbyTargetsStaggerResolutionResult:
    results = tuple(
        NearbyTargetStaggerResult(
            target_id=target.target_id,
            impact=resolve_stagger_impact(
                target.impact,
                rng,
                decisions=decisions,
            ),
        )
        for target in request.targets
    )
    return NearbyTargetsStaggerResolutionResult(
        request_id=request.id,
        source_resolution_id=request.source.resolution_id,
        targets=results,
        applied_rule_ids=(request.source.rule_id,),
    )
