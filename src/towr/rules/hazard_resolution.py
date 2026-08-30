from __future__ import annotations

from towr.domain.condition_models import (
    Condition,
    ConditionApplicationRequest,
    ConditionApplicationResult,
    ConditionState,
    EffectApplicationRequest,
    EffectApplicationResult,
    EffectClassification,
    EffectImmunity,
    RepeatedConditionReplacement,
)
from towr.domain.injury_models import (
    CharacterInjuryState,
    CharacterWoundRequest,
    CharacterWoundType,
    ProfileInjuryState,
    ProfileNpcType,
    ProfileWoundRequest,
)
from towr.domain.resolution_models import (
    ConsumeWoundNegationRequest,
    FollowUpRequest,
    HazardExposureRequest,
    HazardResolutionRequest,
    HazardResolutionResult,
    TargetInjuryPolicy,
    TargetInjuryState,
)
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleCompletionResult,
    CharacterWoundLifecycleRollRequest,
)
from towr.rules.condition_effect_resolution import (
    resolve_condition_application,
)
from towr.rules.dice import RandomSource
from towr.rules.effect_resolution import resolve_effect_application
from towr.rules.injury_resolution import (
    WoundDecisionProvider,
    resolve_profile_wound,
)
from towr.rules.wound_lifecycle_resolution import (
    roll_character_wound_lifecycle,
)


def resolve_hazard_exposure_application(
    exposure: HazardExposureRequest,
    immunities: tuple[EffectImmunity, ...] = (),
) -> EffectApplicationResult:
    """Apply source-level immunity before an avoidance Test is rolled."""
    return resolve_effect_application(
        EffectApplicationRequest(
            id=f"{exposure.test_id}:exposure",
            source_rule_id=exposure.rule_id,
            classification=exposure.classification,
            immunities=immunities,
        )
    )


def resolve_hazard(
    request: HazardResolutionRequest,
    rng: RandomSource,
    *,
    decisions: WoundDecisionProvider | None = None,
) -> HazardResolutionResult:
    successes = request.avoidance_test.successes
    rating = request.exposure.rating
    shortfall = max(0, rating - successes)
    if shortfall == 0:
        return HazardResolutionResult(
            request_id=request.id,
            state=request.target_state,
            avoided=True,
            successes=successes,
            rating=rating,
            shortfall=0,
            character_wound=None,
            wound_effect=None,
            profile_wound=None,
            failure_conditions=(),
            follow_ups=(),
            applied_rule_ids=(request.exposure.rule_id,),
            condition_applications=(),
        )

    state = request.target_state
    character_wound = None
    wound_effect = None
    pending_character_wound = None
    profile_wound = None
    follow_ups: list[FollowUpRequest] = []
    if request.exposure.inflicts_wound:
        if request.target_policy in {
            TargetInjuryPolicy.PLAYER,
            TargetInjuryPolicy.CHAMPION,
        }:
            assert isinstance(state, CharacterInjuryState)
            subject_type = (
                CharacterWoundType.PLAYER
                if request.target_policy is TargetInjuryPolicy.PLAYER
                else CharacterWoundType.CHAMPION
            )
            pending_character_wound = roll_character_wound_lifecycle(
                CharacterWoundLifecycleRollRequest(
                    id=f"{request.id}:wound-lifecycle",
                    target_id=request.target_id,
                    wound=CharacterWoundRequest(
                        id=f"{request.id}:wound",
                        state=state,
                        base_dice=shortfall,
                        subject_type=subject_type,
                        dice_modifiers=request.wound_dice_modifiers,
                        negation_options=request.wound_negation_options,
                    ),
                ),
                rng,
                decisions=decisions,
            )
            character_wound = pending_character_wound.wound_result
            state = character_wound.state
            if character_wound.negated_by_rule_id is not None:
                follow_ups.append(
                    ConsumeWoundNegationRequest(
                        resolution_id=request.id,
                        rule_id=character_wound.negated_by_rule_id,
                    )
                )
        else:
            assert isinstance(state, ProfileInjuryState)
            npc_type = {
                TargetInjuryPolicy.MINION: ProfileNpcType.MINION,
                TargetInjuryPolicy.BRUTE: ProfileNpcType.BRUTE,
                TargetInjuryPolicy.MONSTROSITY: ProfileNpcType.MONSTROSITY,
            }[request.target_policy]
            profile_wound = resolve_profile_wound(
                ProfileWoundRequest(
                    id=f"{request.id}:wound",
                    npc_type=npc_type,
                    state=state,
                    base_wounds=shortfall,
                    additional_wounds=request.additional_profile_wounds,
                )
            )
            state = profile_wound.state
            follow_ups.append(profile_wound.state_change)

    deferred_failure_exposure = None
    if pending_character_wound is not None:
        failure_conditions = ()
        condition_applications = ()
        deferred_failure_exposure = request.exposure
    else:
        (
            state,
            failure_conditions,
            condition_applications,
        ) = _apply_failure_conditions(
            request.id,
            state,
            request.exposure.failure_conditions,
            request.exposure.repeated_condition_replacements,
            request.exposure.rule_id,
            request.exposure.classification,
        )
    applied_rule_ids = tuple(
        dict.fromkeys(
            (
                request.exposure.rule_id,
                *(
                    rule_id
                    for application in condition_applications
                    for rule_id in application.applied_rule_ids
                ),
            )
        )
    )
    return HazardResolutionResult(
        request_id=request.id,
        state=state,
        avoided=False,
        successes=successes,
        rating=rating,
        shortfall=shortfall,
        character_wound=character_wound,
        wound_effect=wound_effect,
        profile_wound=profile_wound,
        failure_conditions=failure_conditions,
        follow_ups=tuple(follow_ups),
        applied_rule_ids=applied_rule_ids,
        condition_applications=condition_applications,
        pending_character_wound=pending_character_wound,
        deferred_failure_exposure=deferred_failure_exposure,
    )


def apply_hazard_character_wound_completion(
    result: HazardResolutionResult,
    completion: CharacterWoundLifecycleCompletionResult,
) -> HazardResolutionResult:
    """Commit a pending Wound before applying the Hazard failure effects."""
    if result.pending_character_wound is None:
        raise ValueError("Hazard result has no pending character Wound")
    if result.deferred_failure_exposure is None:
        raise ValueError("Hazard result has no deferred failure exposure")
    if completion.source_request.roll != result.pending_character_wound:
        raise ValueError("Wound completion belongs to another Hazard result")
    if completion.previous_state != result.state:
        raise ValueError("Hazard Wound completion used a stale target state")
    exposure = result.deferred_failure_exposure
    state, conditions, applications = _apply_failure_conditions(
        result.request_id,
        completion.state,
        exposure.failure_conditions,
        exposure.repeated_condition_replacements,
        exposure.rule_id,
        exposure.classification,
    )
    follow_ups = list(result.follow_ups)
    if completion.wound_effect is not None:
        follow_ups.extend(completion.wound_effect.follow_ups)
    applied_rule_ids = tuple(
        dict.fromkeys(
            (
                *result.applied_rule_ids,
                *(
                    rule_id
                    for application in applications
                    for rule_id in application.applied_rule_ids
                ),
            )
        )
    )
    return HazardResolutionResult(
        request_id=result.request_id,
        state=state,
        avoided=result.avoided,
        successes=result.successes,
        rating=result.rating,
        shortfall=result.shortfall,
        character_wound=result.character_wound,
        wound_effect=completion.wound_effect,
        profile_wound=result.profile_wound,
        failure_conditions=conditions,
        follow_ups=tuple(follow_ups),
        applied_rule_ids=applied_rule_ids,
        condition_applications=applications,
        pending_character_wound=None,
        deferred_failure_exposure=None,
        character_wound_completion=completion,
    )


def _apply_failure_conditions(
    request_id: str,
    state: TargetInjuryState,
    failure_conditions: tuple[Condition, ...],
    replacements: tuple[RepeatedConditionReplacement, ...],
    source_rule_id: str,
    classification: EffectClassification,
) -> tuple[
    TargetInjuryState,
    tuple[Condition, ...],
    tuple[ConditionApplicationResult, ...],
]:
    replacement_by_condition = {
        replacement.condition: replacement for replacement in replacements
    }
    applied_conditions: list[Condition] = []
    applications: list[ConditionApplicationResult] = []
    for index, condition in enumerate(failure_conditions):
        replacement = replacement_by_condition.get(condition)
        if replacement is not None and state.conditions.has(condition):
            applied_condition = replacement.replacement
            application_rule_id = replacement.rule_id
        else:
            applied_condition = condition
            application_rule_id = source_rule_id
        application = resolve_condition_application(
            ConditionApplicationRequest(
                id=(
                    f"{request_id}:failure-condition:{index}:"
                    f"{applied_condition.value}"
                ),
                state=state.conditions,
                condition=applied_condition,
                source_rule_id=application_rule_id,
                classification=classification,
            )
        )
        state = _with_condition_state(state, application.state)
        applied_conditions.append(applied_condition)
        applications.append(application)
    return state, tuple(applied_conditions), tuple(applications)


def _with_condition_state(
    state: TargetInjuryState,
    conditions: ConditionState,
) -> TargetInjuryState:
    if isinstance(state, CharacterInjuryState):
        return CharacterInjuryState(
            wounds=state.wounds,
            conditions=conditions,
            active_wound_effects=state.active_wound_effects,
            dead=state.dead,
        )
    return ProfileInjuryState(
        wounds=state.wounds,
        wound_limit=state.wound_limit,
        conditions=conditions,
        defeated=state.defeated,
    )
