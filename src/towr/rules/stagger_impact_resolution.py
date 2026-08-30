from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from towr.domain.attack_models import ConditionOnGiveGroundOrWoundSpec
from towr.domain.condition_models import (
    ConditionApplicationRequest,
    ConditionState,
    EffectImmunity,
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
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleCompletionResult,
    CharacterWoundLifecycleOutcome,
    CharacterWoundLifecycleRollRequest,
)
from towr.rules.condition_effect_resolution import (
    resolve_condition_application,
)
from towr.rules.dice import RandomSource
from towr.rules.injury_resolution import (
    WoundDecisionProvider,
    resolve_profile_wound,
)
from towr.rules.stagger_resolution import (
    StaggerDecisionProvider,
    resolve_stagger,
)
from towr.rules.wound_lifecycle_resolution import (
    roll_character_wound_lifecycle,
)


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
        give_ground_effects = (
            *request.after_give_ground_effects,
            *request.give_ground_or_wound_effects,
        )
        condition_follow_ups = tuple(
            ConditionAfterGiveGroundRequest(
                resolution_id=request.id,
                condition=effect.condition,
                rule_id=effect.rule_id,
                classification=effect.classification,
                target_effect_immunities=request.target_effect_immunities,
            )
            for effect in give_ground_effects
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
                effect.rule_id for effect in give_ground_effects
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
    result = _resolve_stagger_wound(request, state, stagger, rng, decisions)
    return _apply_conditions_after_accepted_wound(
        result,
        request.give_ground_or_wound_effects,
        request.target_effect_immunities,
    )


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
        pending = roll_character_wound_lifecycle(
            CharacterWoundLifecycleRollRequest(
                id=f"{request.id}:wound-lifecycle",
                target_id=request.target_id,
                wound=CharacterWoundRequest(
                    id=f"{request.id}:wound",
                    state=state,
                    subject_type=subject_type,
                    dice_modifiers=request.wound_dice_modifiers,
                    negation_options=request.wound_negation_options,
                ),
            ),
            rng,
            decisions=decisions,
        )
        wound = pending.wound_result
        if wound.negated_by_rule_id is not None:
            follow_ups.append(
                ConsumeWoundNegationRequest(
                    resolution_id=request.id,
                    rule_id=wound.negated_by_rule_id,
                )
            )
        return StaggerImpactResult(
            request_id=request.id,
            state=wound.state,
            stagger=stagger,
            character_wound=wound,
            wound_effect=None,
            profile_wound=None,
            follow_ups=tuple(follow_ups),
            applied_rule_ids=(),
            pending_character_wound=pending,
            deferred_wound_conditions=(
                request.give_ground_or_wound_effects
                if wound.wound_accepted
                else ()
            ),
            deferred_wound_condition_immunities=(
                request.target_effect_immunities
                if wound.wound_accepted
                else ()
            ),
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


def apply_stagger_character_wound_completion(
    result: StaggerImpactResult,
    completion: CharacterWoundLifecycleCompletionResult,
) -> StaggerImpactResult:
    """Commit a pending character Wound, then its outcome Conditions."""
    if result.pending_character_wound is None:
        raise ValueError("Stagger impact has no pending character Wound")
    if completion.source_request.roll != result.pending_character_wound:
        raise ValueError("Wound completion belongs to another Stagger impact")
    if completion.previous_state != result.state:
        raise ValueError("Stagger impact Wound completion used a stale state")
    follow_ups = list(result.follow_ups)
    if completion.wound_effect is not None:
        follow_ups.extend(completion.wound_effect.follow_ups)
    committed = replace(
        result,
        state=completion.state,
        wound_effect=completion.wound_effect,
        follow_ups=tuple(follow_ups),
        pending_character_wound=None,
        deferred_wound_conditions=(),
        deferred_wound_condition_immunities=(),
        character_wound_completion=completion,
    )
    if completion.outcome is not CharacterWoundLifecycleOutcome.ACCEPTED:
        return committed
    return _apply_conditions_after_accepted_wound(
        committed,
        result.deferred_wound_conditions,
        result.deferred_wound_condition_immunities,
    )


def _apply_conditions_after_accepted_wound(
    result: StaggerImpactResult,
    effects: tuple[ConditionOnGiveGroundOrWoundSpec, ...],
    target_effect_immunities: tuple[EffectImmunity, ...],
) -> StaggerImpactResult:
    character_wound_accepted = (
        result.character_wound is not None
        and result.character_wound.wound_accepted
        and result.pending_character_wound is None
    )
    profile_wound_accepted = (
        result.profile_wound is not None
        and result.profile_wound.wounds_inflicted > 0
    )
    if not effects or not (
        character_wound_accepted or profile_wound_accepted
    ):
        return result

    state = result.state
    new_applications = []
    for effect in effects:
        application = resolve_condition_application(
            ConditionApplicationRequest(
                id=f"{result.request_id}:{effect.rule_id}:condition",
                state=state.conditions,
                condition=effect.condition,
                source_rule_id=effect.rule_id,
                classification=effect.classification,
                immunities=target_effect_immunities,
            )
        )
        state = _with_conditions(
            state,
            application.state,
        )
        new_applications.append(application)
    return replace(
        result,
        state=state,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    *result.applied_rule_ids,
                    *(
                        rule_id
                        for application in new_applications
                        for rule_id in application.applied_rule_ids
                    ),
                )
            )
        ),
        condition_applications=(
            *result.condition_applications,
            *new_applications,
        ),
    )
