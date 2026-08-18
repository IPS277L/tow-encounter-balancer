from __future__ import annotations

from towr.domain.resolution_models import (
    HazardExposureRequest,
    HazardResolutionRequest,
    IdentifiedHazardTarget,
    ReactorZoneHazardRequest,
    ReactorZoneHazardResolutionRequest,
    ReactorZoneHazardResolutionResult,
    ReactorZoneHazardTargetResult,
)
from towr.domain.test_models import TestResult
from towr.rules.dice import RandomSource
from towr.rules.hazard_resolution import resolve_hazard
from towr.rules.injury_resolution import WoundDecisionProvider
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


def resolve_reactor_zone_hazard(
    request: ReactorZoneHazardResolutionRequest,
    rng: RandomSource,
    *,
    test_decisions: TestDecisionProvider | None = None,
    wound_decisions: WoundDecisionProvider | None = None,
) -> ReactorZoneHazardResolutionResult:
    results: list[ReactorZoneHazardTargetResult] = []
    for target in request.targets:
        exposure = _exposure(request.source, target)
        avoidance_test = resolve_test(
            target.avoidance_test,
            rng,
            decisions=test_decisions,
        )
        hazard = resolve_hazard(
            _hazard_request(request, target, exposure, avoidance_test),
            rng,
            decisions=wound_decisions,
        )
        results.append(
            ReactorZoneHazardTargetResult(
                target_id=target.target_id,
                exposure=exposure,
                avoidance_test=avoidance_test,
                hazard=hazard,
            )
        )
    return ReactorZoneHazardResolutionResult(
        request_id=request.id,
        source_resolution_id=request.source.resolution_id,
        reactor_target_id=request.reactor_target_id,
        targets=tuple(results),
        applied_rule_ids=(request.source.rule_id,),
    )


def _hazard_request(
    request: ReactorZoneHazardResolutionRequest,
    target: IdentifiedHazardTarget,
    exposure: HazardExposureRequest,
    avoidance_test: TestResult,
) -> HazardResolutionRequest:
    return HazardResolutionRequest(
        id=f"{request.id}:{target.target_id}:hazard",
        exposure=exposure,
        avoidance_test=avoidance_test,
        target_policy=target.target_policy,
        target_state=target.target_state,
        wound_dice_modifiers=target.wound_dice_modifiers,
        wound_negation_options=target.wound_negation_options,
        additional_profile_wounds=target.additional_profile_wounds,
    )


def _exposure(
    source: ReactorZoneHazardRequest,
    target: IdentifiedHazardTarget,
) -> HazardExposureRequest:
    return HazardExposureRequest(
        resolution_id=source.resolution_id,
        test_id=target.avoidance_test.id,
        rating=source.rating,
        avoidance_skill=source.avoidance_skill,
        rule_id=source.rule_id,
        inflicts_wound=source.inflicts_wound,
        failure_conditions=source.failure_conditions,
    )
