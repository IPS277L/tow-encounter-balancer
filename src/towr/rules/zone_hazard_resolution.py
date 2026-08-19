from __future__ import annotations

from towr.domain.resolution_models import (
    HazardExposureRequest,
    HazardResolutionRequest,
    IdentifiedHazardTarget,
    ZoneHazardRequest,
    ZoneHazardResolutionRequest,
    ZoneHazardResolutionResult,
    ZoneHazardTargetResult,
)
from towr.domain.test_models import TestResult
from towr.rules.dice import RandomSource
from towr.rules.hazard_resolution import (
    resolve_hazard,
    resolve_hazard_exposure_application,
)
from towr.rules.injury_resolution import WoundDecisionProvider
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


def resolve_zone_hazard(
    request: ZoneHazardResolutionRequest,
    rng: RandomSource,
    *,
    test_decisions: TestDecisionProvider | None = None,
    wound_decisions: WoundDecisionProvider | None = None,
) -> ZoneHazardResolutionResult:
    results: list[ZoneHazardTargetResult] = []
    for target in request.targets:
        exposure = hazard_exposure(request.source, target)
        application = resolve_hazard_exposure_application(
            exposure,
            target.target_effect_immunities,
        )
        if application.blocked:
            results.append(
                ZoneHazardTargetResult(
                    target_id=target.target_id,
                    exposure=exposure,
                    application=application,
                    avoidance_test=None,
                    hazard=None,
                )
            )
            continue
        avoidance_test = resolve_test(
            target.avoidance_test,
            rng,
            decisions=test_decisions,
        )
        hazard = resolve_hazard(
            hazard_resolution_request(
                request.id,
                target,
                exposure,
                avoidance_test,
            ),
            rng,
            decisions=wound_decisions,
        )
        results.append(
            ZoneHazardTargetResult(
                target_id=target.target_id,
                exposure=exposure,
                application=application,
                avoidance_test=avoidance_test,
                hazard=hazard,
            )
        )
    return ZoneHazardResolutionResult(
        request_id=request.id,
        source_resolution_id=request.source.resolution_id,
        targets=tuple(results),
        applied_rule_ids=ordered_unique_rule_ids(results),
    )


def hazard_resolution_request(
    request_id: str,
    target: IdentifiedHazardTarget,
    exposure: HazardExposureRequest,
    avoidance_test: TestResult,
) -> HazardResolutionRequest:
    return HazardResolutionRequest(
        id=f"{request_id}:{target.target_id}:hazard",
        exposure=exposure,
        avoidance_test=avoidance_test,
        target_policy=target.target_policy,
        target_state=target.target_state,
        wound_dice_modifiers=target.wound_dice_modifiers,
        wound_negation_options=target.wound_negation_options,
        additional_profile_wounds=target.additional_profile_wounds,
    )


def hazard_exposure(
    source: ZoneHazardRequest,
    target: IdentifiedHazardTarget,
) -> HazardExposureRequest:
    avoidance_skill = (
        target.selected_avoidance_skill or source.avoidance_skill
    )
    return HazardExposureRequest(
        resolution_id=source.resolution_id,
        test_id=target.avoidance_test.id,
        rating=source.rating,
        avoidance_skill=avoidance_skill,
        rule_id=source.rule_id,
        inflicts_wound=source.inflicts_wound,
        failure_conditions=source.failure_conditions,
        classification=source.classification,
        repeated_condition_replacements=(
            source.repeated_condition_replacements
        ),
    )


def ordered_unique_rule_ids(
    results: list[ZoneHazardTargetResult],
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            rule_id
            for result in results
            for rule_id in (
                *result.application.applied_rule_ids,
                *(
                    result.hazard.applied_rule_ids
                    if result.hazard is not None
                    else ()
                ),
            )
        )
    )
