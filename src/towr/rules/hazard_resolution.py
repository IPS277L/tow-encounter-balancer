from __future__ import annotations

from towr.domain.condition_models import Condition, ConditionState
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
    HazardResolutionRequest,
    HazardResolutionResult,
    TargetInjuryPolicy,
    TargetInjuryState,
)
from towr.rules.dice import RandomSource
from towr.rules.injury_resolution import (
    WoundDecisionProvider,
    resolve_character_wound,
    resolve_profile_wound,
)
from towr.rules.wound_effect_resolution import resolve_wound_effect


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
        )

    state = request.target_state
    character_wound = None
    wound_effect = None
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
            character_wound = resolve_character_wound(
                CharacterWoundRequest(
                    id=f"{request.id}:wound",
                    state=state,
                    base_dice=shortfall,
                    subject_type=subject_type,
                    dice_modifiers=request.wound_dice_modifiers,
                    negation_options=request.wound_negation_options,
                ),
                rng,
                decisions=decisions,
            )
            state = character_wound.state
            if character_wound.effect_request is not None:
                wound_effect = resolve_wound_effect(
                    character_wound.effect_request,
                    character_wound.state,
                )
                state = wound_effect.state
                follow_ups.extend(wound_effect.follow_ups)
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

    state = _with_failure_conditions(
        state,
        request.exposure.failure_conditions,
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
        failure_conditions=request.exposure.failure_conditions,
        follow_ups=tuple(follow_ups),
        applied_rule_ids=(request.exposure.rule_id,),
    )


def _with_failure_conditions(
    state: TargetInjuryState,
    failure_conditions: tuple[Condition, ...],
) -> TargetInjuryState:
    conditions = _add_conditions(state.conditions, failure_conditions)
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


def _add_conditions(
    state: ConditionState,
    failure_conditions: tuple[Condition, ...],
) -> ConditionState:
    for condition in failure_conditions:
        state = state.with_condition(condition)
    return state
