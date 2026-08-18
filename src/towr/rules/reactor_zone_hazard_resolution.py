from __future__ import annotations

from towr.domain.resolution_models import (
    ReactorZoneHazardResolutionRequest,
    ReactorZoneHazardResolutionResult,
    ReactorZoneHazardTargetResult,
    ZoneHazardResolutionRequest,
)
from towr.rules.dice import RandomSource
from towr.rules.injury_resolution import WoundDecisionProvider
from towr.rules.test_resolution import TestDecisionProvider
from towr.rules.zone_hazard_resolution import resolve_zone_hazard


def resolve_reactor_zone_hazard(
    request: ReactorZoneHazardResolutionRequest,
    rng: RandomSource,
    *,
    test_decisions: TestDecisionProvider | None = None,
    wound_decisions: WoundDecisionProvider | None = None,
) -> ReactorZoneHazardResolutionResult:
    zone_result = resolve_zone_hazard(
        ZoneHazardResolutionRequest(
            id=request.id,
            source=request.source,
            targets=request.targets,
        ),
        rng,
        test_decisions=test_decisions,
        wound_decisions=wound_decisions,
    )
    results = tuple(
        ReactorZoneHazardTargetResult(
            target_id=result.target_id,
            exposure=result.exposure,
            application=result.application,
            avoidance_test=result.avoidance_test,
            hazard=result.hazard,
        )
        for result in zone_result.targets
    )
    return ReactorZoneHazardResolutionResult(
        request_id=request.id,
        source_resolution_id=zone_result.source_resolution_id,
        reactor_target_id=request.reactor_target_id,
        targets=results,
        applied_rule_ids=zone_result.applied_rule_ids,
    )
