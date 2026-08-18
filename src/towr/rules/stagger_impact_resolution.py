from __future__ import annotations

from typing import Protocol

from towr.domain.condition_models import (
    ConditionState,
    StaggerRequest,
    StaggerResult,
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
    ConditionAfterGiveGroundRequest,
    ConsumeWoundNegationRequest,
    FollowUpRequest,
    GiveGroundRequest,
    StaggerImpactRequest,
    StaggerImpactResult,
    TargetInjuryPolicy,
    TargetInjuryState,
)
from towr.rules.dice import RandomSource
from towr.rules.injury_resolution import (
    WoundDecisionProvider,
    resolve_character_wound,
    resolve_profile_wound,
)
from towr.rules.stagger_resolution import (
    StaggerDecisionProvider,
    resolve_stagger,
)
from towr.rules.wound_effect_resolution import resolve_wound_effect


class StaggerImpactDecisionProvider(
    StaggerDecisionProvider,
    WoundDecisionProvider,
    Protocol,
):
    pass


def resolve_stagger_impact(
    request: StaggerImpactRequest,
    rng: RandomSource,
    *,
    decisions: StaggerImpactDecisionProvider | None = None,
) -> StaggerImpactResult:
    stagger = resolve_stagger(
        StaggerRequest(
            id=f"{request.id}:stagger",
            state=request.target_state.conditions,
            can_leave_zone=request.can_target_leave_zone,
            has_given_ground_this_round=(
                request.target_has_given_ground_this_round
            ),
        ),
        decisions=decisions,
    )
    state = _with_conditions(request.target_state, stagger.state)
    if stagger.gave_ground:
        condition_follow_ups = tuple(
            ConditionAfterGiveGroundRequest(
                resolution_id=request.id,
                condition=effect.condition,
                rule_id=effect.rule_id,
            )
            for effect in request.after_give_ground_effects
        )
        return StaggerImpactResult(
            request_id=request.id,
            state=state,
            stagger=stagger,
            character_wound=None,
            wound_effect=None,
            profile_wound=None,
            follow_ups=(
                GiveGroundRequest(resolution_id=request.id),
                *condition_follow_ups,
            ),
            applied_rule_ids=tuple(
                effect.rule_id for effect in request.after_give_ground_effects
            ),
        )
    if not stagger.wound_requested:
        return StaggerImpactResult(
            request_id=request.id,
            state=state,
            stagger=stagger,
            character_wound=None,
            wound_effect=None,
            profile_wound=None,
            follow_ups=(),
            applied_rule_ids=(),
        )
    return _resolve_stagger_wound(request, state, stagger, rng, decisions)


def _resolve_stagger_wound(
    request: StaggerImpactRequest,
    state: TargetInjuryState,
    stagger: StaggerResult,
    rng: RandomSource,
    decisions: StaggerImpactDecisionProvider | None,
) -> StaggerImpactResult:
    follow_ups: list[FollowUpRequest] = []
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
        wound = resolve_character_wound(
            CharacterWoundRequest(
                id=f"{request.id}:wound",
                state=state,
                subject_type=subject_type,
                dice_modifiers=request.wound_dice_modifiers,
                negation_options=request.wound_negation_options,
            ),
            rng,
            decisions=decisions,
        )
        wound_effect = None
        target_state = wound.state
        if wound.effect_request is not None:
            wound_effect = resolve_wound_effect(
                wound.effect_request,
                wound.state,
            )
            target_state = wound_effect.state
            follow_ups.extend(wound_effect.follow_ups)
        if wound.negated_by_rule_id is not None:
            follow_ups.append(
                ConsumeWoundNegationRequest(
                    resolution_id=request.id,
                    rule_id=wound.negated_by_rule_id,
                )
            )
        return StaggerImpactResult(
            request_id=request.id,
            state=target_state,
            stagger=stagger,
            character_wound=wound,
            wound_effect=wound_effect,
            profile_wound=None,
            follow_ups=tuple(follow_ups),
            applied_rule_ids=(),
        )

    assert isinstance(state, ProfileInjuryState)
    npc_type = {
        TargetInjuryPolicy.MINION: ProfileNpcType.MINION,
        TargetInjuryPolicy.BRUTE: ProfileNpcType.BRUTE,
        TargetInjuryPolicy.MONSTROSITY: ProfileNpcType.MONSTROSITY,
    }[request.target_policy]
    wound = resolve_profile_wound(
        ProfileWoundRequest(
            id=f"{request.id}:wound",
            npc_type=npc_type,
            state=state,
            additional_wounds=request.additional_profile_wounds,
        )
    )
    return StaggerImpactResult(
        request_id=request.id,
        state=wound.state,
        stagger=stagger,
        character_wound=None,
        wound_effect=None,
        profile_wound=wound,
        follow_ups=(wound.state_change,),
        applied_rule_ids=(),
    )


def _with_conditions(
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
