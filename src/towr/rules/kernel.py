from __future__ import annotations

from typing import Protocol

from towr.domain.attack_models import (
    AttackOutcome,
    AttackResult,
    ImpactOutcome,
    MissConsequence,
)
from towr.domain.condition_models import ConditionState, StaggerRequest, StaggerResult
from towr.domain.injury_models import (
    CharacterInjuryState,
    CharacterWoundRequest,
    CharacterWoundType,
    MonstrosityImpactRequest,
    ProfileInjuryState,
    ProfileNpcType,
    ProfileWoundRequest,
)
from towr.domain.resolution_models import (
    AttackerStaggerRequest,
    ConsumeWoundNegationRequest,
    GiveGroundRequest,
    FollowUpRequest,
    KernelAttackRequest,
    MonstrosityReactionRequest,
    ResolutionResult,
    TargetInjuryPolicy,
)
from towr.rules.attack_resolution import resolve_attack
from towr.rules.dice import RandomSource
from towr.rules.injury_resolution import (
    WoundDecisionProvider,
    resolve_character_wound,
    resolve_profile_wound,
)
from towr.rules.monstrosity_resolution import (
    MonstrosityDecisionProvider,
    resolve_monstrosity_impact,
)
from towr.rules.stagger_resolution import (
    StaggerDecisionProvider,
    resolve_stagger,
)
from towr.rules.test_resolution import TestDecisionProvider
from towr.rules.wound_effect_resolution import resolve_wound_effect


class ResolutionDecisionProvider(
    TestDecisionProvider,
    StaggerDecisionProvider,
    WoundDecisionProvider,
    MonstrosityDecisionProvider,
    Protocol,
):
    pass


def resolve_kernel_attack(
    request: KernelAttackRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> ResolutionResult:
    attack = resolve_attack(request.attack, rng, decisions=decisions)
    if attack.outcome is AttackOutcome.MISS:
        follow_ups = ()
        if attack.miss_consequence is MissConsequence.STAGGER_ATTACKER:
            follow_ups = (AttackerStaggerRequest(attack_id=request.attack.id),)
        return ResolutionResult(
            request_id=request.id,
            attack=attack,
            target_state=request.target_state,
            stagger=None,
            character_wound=None,
            wound_effect=None,
            profile_wound=None,
            monstrosity_impact=None,
            follow_ups=follow_ups,
        )

    assert attack.damage is not None
    assert attack.effective_resilience is not None
    if request.target_policy is TargetInjuryPolicy.MONSTROSITY:
        return _resolve_monstrosity(request, attack, rng, decisions)

    if attack.impact is ImpactOutcome.WOUND:
        return _resolve_wound(request, attack, request.target_state, rng, decisions)

    state = request.target_state
    stagger = resolve_stagger(
        StaggerRequest(
            id=f"{request.id}:stagger",
            state=state.conditions,
            can_leave_zone=request.can_target_leave_zone,
            has_given_ground_this_round=(
                request.target_has_given_ground_this_round
            ),
        ),
        decisions=decisions,
    )
    updated_state = _with_conditions(state, stagger.state)
    follow_ups = ()
    if stagger.gave_ground:
        follow_ups = (GiveGroundRequest(resolution_id=request.id),)
    if stagger.wound_requested:
        wound_result = _resolve_wound(
            request,
            attack,
            updated_state,
            rng,
            decisions,
            stagger=stagger,
            initial_follow_ups=follow_ups,
        )
        return wound_result
    return ResolutionResult(
        request_id=request.id,
        attack=attack,
        target_state=updated_state,
        stagger=stagger,
        character_wound=None,
        wound_effect=None,
        profile_wound=None,
        monstrosity_impact=None,
        follow_ups=follow_ups,
    )


def _resolve_wound(
    request: KernelAttackRequest,
    attack: AttackResult,
    state: CharacterInjuryState | ProfileInjuryState,
    rng: RandomSource,
    decisions: ResolutionDecisionProvider | None,
    *,
    stagger: StaggerResult | None = None,
    initial_follow_ups: tuple[FollowUpRequest, ...] = (),
) -> ResolutionResult:
    follow_ups: list[FollowUpRequest] = list(initial_follow_ups)
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
        effect = None
        target_state = wound.state
        if wound.effect_request is not None:
            effect = resolve_wound_effect(wound.effect_request, wound.state)
            target_state = effect.state
            follow_ups.extend(effect.follow_ups)
        if wound.negated_by_rule_id is not None:
            follow_ups.append(
                ConsumeWoundNegationRequest(
                    resolution_id=request.id,
                    rule_id=wound.negated_by_rule_id,
                )
            )
        return ResolutionResult(
            request_id=request.id,
            attack=attack,
            target_state=target_state,
            stagger=stagger,
            character_wound=wound,
            wound_effect=effect,
            profile_wound=None,
            monstrosity_impact=None,
            follow_ups=tuple(follow_ups),
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
    follow_ups.append(wound.state_change)
    return ResolutionResult(
        request_id=request.id,
        attack=attack,
        target_state=wound.state,
        stagger=stagger,
        character_wound=None,
        wound_effect=None,
        profile_wound=wound,
        monstrosity_impact=None,
        follow_ups=tuple(follow_ups),
    )


def _resolve_monstrosity(
    request: KernelAttackRequest,
    attack: AttackResult,
    rng: RandomSource,
    decisions: ResolutionDecisionProvider | None,
) -> ResolutionResult:
    assert isinstance(request.target_state, ProfileInjuryState)
    assert attack.damage is not None
    assert attack.effective_resilience is not None
    impact = resolve_monstrosity_impact(
        MonstrosityImpactRequest(
            id=f"{request.id}:monstrosity-impact",
            state=request.target_state,
            damage=attack.damage,
            resilience=attack.effective_resilience,
        ),
        decisions=decisions,
    )
    if impact.reaction_requested:
        assert request.monstrosity_reaction_rule_id is not None
        return ResolutionResult(
            request_id=request.id,
            attack=attack,
            target_state=impact.state,
            stagger=None,
            character_wound=None,
            wound_effect=None,
            profile_wound=None,
            monstrosity_impact=impact,
            follow_ups=(
                MonstrosityReactionRequest(
                    resolution_id=request.id,
                    reaction_rule_id=request.monstrosity_reaction_rule_id,
                ),
            ),
        )
    if impact.wound_requested:
        result = _resolve_wound(
            request,
            attack,
            impact.state,
            rng,
            decisions,
        )
        return ResolutionResult(
            request_id=result.request_id,
            attack=result.attack,
            target_state=result.target_state,
            stagger=result.stagger,
            character_wound=result.character_wound,
            wound_effect=result.wound_effect,
            profile_wound=result.profile_wound,
            monstrosity_impact=impact,
            follow_ups=result.follow_ups,
        )
    return ResolutionResult(
        request_id=request.id,
        attack=attack,
        target_state=impact.state,
        stagger=None,
        character_wound=None,
        wound_effect=None,
        profile_wound=None,
        monstrosity_impact=impact,
        follow_ups=(),
    )


def _with_conditions(
    state: CharacterInjuryState | ProfileInjuryState,
    conditions: ConditionState,
) -> CharacterInjuryState | ProfileInjuryState:
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
