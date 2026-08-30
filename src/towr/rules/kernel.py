from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from towr.domain.attack_models import (
    AttackOutcome,
    AttackResult,
    ConditionAfterGiveGroundSpec,
    ConditionOnGiveGroundOrWoundSpec,
    ConditionOnHitSpec,
    ConditionImpactSpec,
    DamageImpactSpec,
    HazardImpactSpec,
    ImpactOutcome,
    MissConsequence,
    NearbyTargetsStaggerSpec,
    ProneBeforeGiveGroundSpec,
)
from towr.domain.condition_models import (
    Condition,
    ConditionApplicationRequest,
    ConditionState,
)
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
    ConditionImpactResult,
    FollowUpRequest,
    HazardExposureRequest,
    HazardImpactResult,
    KernelAttackRequest,
    MonstrosityReactionRequest,
    NearbyTargetsStaggerRequest,
    ReplacementImpactResult,
    ResolutionResult,
    StaggerImpactRequest,
    TargetInjuryPolicy,
)
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleCompletionResult,
    CharacterWoundLifecycleOutcome,
    CharacterWoundLifecycleRollRequest,
)
from towr.rules.attack_resolution import resolve_attack
from towr.rules.condition_effect_resolution import (
    resolve_condition_application,
)
from towr.rules.dice import RandomSource
from towr.rules.injury_resolution import (
    WoundDecisionProvider,
    resolve_profile_wound,
)
from towr.rules.hazard_resolution import resolve_hazard_exposure_application
from towr.rules.monstrosity_resolution import (
    MonstrosityDecisionProvider,
    resolve_monstrosity_impact,
)
from towr.rules.stagger_impact_resolution import resolve_stagger_impact
from towr.rules.stagger_resolution import StaggerDecisionProvider
from towr.rules.test_resolution import TestDecisionProvider
from towr.rules.wound_lifecycle_resolution import (
    roll_character_wound_lifecycle,
)


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
            replacement_impact=None,
            target_state=request.target_state,
            stagger=None,
            character_wound=None,
            wound_effect=None,
            profile_wound=None,
            monstrosity_impact=None,
            follow_ups=follow_ups,
        )

    effective_request, applied_secondary_rule_ids = (
        _apply_pre_stagger_secondary(request)
    )
    if isinstance(attack.impact_spec, ConditionImpactSpec):
        result = _resolve_condition_impact(
            effective_request,
            attack,
            attack.impact_spec,
            rng,
            decisions,
        )
    elif isinstance(attack.impact_spec, HazardImpactSpec):
        result = _resolve_hazard_impact(
            effective_request,
            attack,
            attack.impact_spec,
        )
    else:
        assert isinstance(attack.impact_spec, DamageImpactSpec)
        assert attack.damage is not None
        assert attack.effective_resilience is not None
        if effective_request.target_policy is TargetInjuryPolicy.MONSTROSITY:
            result = _resolve_monstrosity(
                effective_request,
                attack,
                rng,
                decisions,
            )
        elif attack.impact is ImpactOutcome.WOUND:
            result = _resolve_wound(
                effective_request,
                attack,
                effective_request.target_state,
                rng,
                decisions,
            )
        else:
            result = _resolve_stagger_impact(
                effective_request,
                attack,
                effective_request.target_state,
                rng,
                decisions,
            )
    return _apply_post_hit_secondary(
        effective_request,
        result,
        applied_secondary_rule_ids,
    )


def _apply_pre_stagger_secondary(
    request: KernelAttackRequest,
) -> tuple[KernelAttackRequest, tuple[str, ...]]:
    state = request.target_state
    applied_rule_ids: list[str] = []
    for effect in request.attack.secondary_effects:
        if not isinstance(effect, ProneBeforeGiveGroundSpec):
            continue
        if (
            request.target_policy is TargetInjuryPolicy.MONSTROSITY
            and not effect.affects_monstrosities
        ):
            continue
        state = _with_conditions(
            state,
            state.conditions.with_condition(Condition.PRONE),
        )
        applied_rule_ids.append(effect.rule_id)
    if not applied_rule_ids:
        return request, ()
    return (
        replace(request, target_state=state),
        tuple(applied_rule_ids),
    )


def _apply_post_hit_secondary(
    request: KernelAttackRequest,
    result: ResolutionResult,
    applied_rule_ids: tuple[str, ...],
) -> ResolutionResult:
    follow_ups = list(result.follow_ups)
    state = result.target_state
    condition_applications = list(result.condition_applications)
    condition_on_hit_rule_ids: list[str] = []
    for effect in request.attack.secondary_effects:
        if not isinstance(effect, ConditionOnHitSpec):
            continue
        application = resolve_condition_application(
            ConditionApplicationRequest(
                id=f"{request.id}:{effect.rule_id}:on-hit-condition",
                state=state.conditions,
                condition=effect.condition,
                source_rule_id=effect.rule_id,
                classification=effect.classification,
                immunities=request.target_effect_immunities,
            )
        )
        state = _with_conditions(
            state,
            application.state,
        )
        condition_applications.append(application)
        condition_on_hit_rule_ids.extend(application.applied_rule_ids)
    outcome_condition_rule_ids: list[str] = []
    if _wound_was_accepted(result):
        for effect in request.attack.secondary_effects:
            if not isinstance(effect, ConditionOnGiveGroundOrWoundSpec):
                continue
            if any(
                application.source_rule_id == effect.rule_id
                for application in result.condition_applications
            ):
                continue
            application = resolve_condition_application(
                ConditionApplicationRequest(
                    id=f"{request.id}:{effect.rule_id}:outcome-condition",
                    state=state.conditions,
                    condition=effect.condition,
                    source_rule_id=effect.rule_id,
                    classification=effect.classification,
                    immunities=request.target_effect_immunities,
                )
            )
            state = _with_conditions(
                state,
                application.state,
            )
            condition_applications.append(application)
            outcome_condition_rule_ids.extend(application.applied_rule_ids)
    rule_ids = [
        *applied_rule_ids,
        *condition_on_hit_rule_ids,
        *outcome_condition_rule_ids,
        *result.applied_secondary_rule_ids,
    ]
    for effect in request.attack.secondary_effects:
        if not isinstance(effect, NearbyTargetsStaggerSpec):
            continue
        follow_ups.append(
            NearbyTargetsStaggerRequest(
                resolution_id=request.id,
                rule_id=effect.rule_id,
            )
        )
        rule_ids.append(effect.rule_id)
    if not rule_ids:
        return result
    return replace(
        result,
        target_state=state,
        follow_ups=tuple(follow_ups),
        applied_secondary_rule_ids=tuple(dict.fromkeys(rule_ids)),
        condition_applications=tuple(condition_applications),
    )


def _resolve_stagger_impact(
    request: KernelAttackRequest,
    attack: AttackResult,
    state: CharacterInjuryState | ProfileInjuryState,
    rng: RandomSource,
    decisions: ResolutionDecisionProvider | None,
    *,
    replacement_impact: ReplacementImpactResult | None = None,
) -> ResolutionResult:
    impact = resolve_stagger_impact(
        StaggerImpactRequest(
            id=request.id,
            target_id=request.target_id,
            target_policy=request.target_policy,
            target_state=state,
            can_target_leave_zone=request.can_target_leave_zone,
            target_has_given_ground_this_round=(
                request.target_has_given_ground_this_round
            ),
            wound_dice_modifiers=request.wound_dice_modifiers,
            wound_negation_options=request.wound_negation_options,
            additional_profile_wounds=request.additional_profile_wounds,
            after_give_ground_effects=tuple(
                effect
                for effect in request.attack.secondary_effects
                if isinstance(effect, ConditionAfterGiveGroundSpec)
            ),
            give_ground_or_wound_effects=tuple(
                effect
                for effect in request.attack.secondary_effects
                if isinstance(effect, ConditionOnGiveGroundOrWoundSpec)
            ),
            target_effect_immunities=request.target_effect_immunities,
        ),
        rng,
        decisions=decisions,
    )
    return ResolutionResult(
        request_id=request.id,
        attack=attack,
        replacement_impact=replacement_impact,
        target_state=impact.state,
        stagger=impact.stagger,
        character_wound=impact.character_wound,
        wound_effect=impact.wound_effect,
        profile_wound=impact.profile_wound,
        monstrosity_impact=None,
        follow_ups=impact.follow_ups,
        applied_secondary_rule_ids=impact.applied_rule_ids,
        condition_applications=impact.condition_applications,
        pending_character_wound=impact.pending_character_wound,
        deferred_wound_conditions=impact.deferred_wound_conditions,
        deferred_wound_condition_immunities=(
            impact.deferred_wound_condition_immunities
        ),
    )


def _resolve_condition_impact(
    request: KernelAttackRequest,
    attack: AttackResult,
    spec: ConditionImpactSpec,
    rng: RandomSource,
    decisions: ResolutionDecisionProvider | None,
) -> ResolutionResult:
    state = request.target_state
    application = resolve_condition_application(
        ConditionApplicationRequest(
            id=f"{request.id}:condition-impact",
            state=state.conditions,
            condition=spec.condition,
            source_rule_id=spec.rule_id,
            classification=spec.classification,
            immunities=request.target_effect_immunities,
        )
    )
    result = ConditionImpactResult(application=application)
    if application.blocked:
        return ResolutionResult(
            request_id=request.id,
            attack=attack,
            replacement_impact=result,
            target_state=state,
            stagger=None,
            character_wound=None,
            wound_effect=None,
            profile_wound=None,
            monstrosity_impact=None,
            follow_ups=(),
            condition_applications=(application,),
        )
    if spec.condition is Condition.STAGGERED:
        resolved = _resolve_stagger_impact(
            request,
            attack,
            state,
            rng,
            decisions,
            replacement_impact=result,
        )
        return replace(
            resolved,
            condition_applications=(
                application,
                *resolved.condition_applications,
            ),
        )

    updated_state = _with_conditions(
        state,
        application.state,
    )
    return ResolutionResult(
        request_id=request.id,
        attack=attack,
        replacement_impact=result,
        target_state=updated_state,
        stagger=None,
        character_wound=None,
        wound_effect=None,
        profile_wound=None,
        monstrosity_impact=None,
        follow_ups=(),
        condition_applications=(application,),
    )


def _resolve_hazard_impact(
    request: KernelAttackRequest,
    attack: AttackResult,
    spec: HazardImpactSpec,
) -> ResolutionResult:
    exposure = HazardExposureRequest.from_spec(request.id, spec)
    application = resolve_hazard_exposure_application(
        exposure,
        request.target_effect_immunities,
    )
    return ResolutionResult(
        request_id=request.id,
        attack=attack,
        replacement_impact=HazardImpactResult(exposure, application),
        target_state=request.target_state,
        stagger=None,
        character_wound=None,
        wound_effect=None,
        profile_wound=None,
        monstrosity_impact=None,
        follow_ups=() if application.blocked else (exposure,),
    )


def _resolve_wound(
    request: KernelAttackRequest,
    attack: AttackResult,
    state: CharacterInjuryState | ProfileInjuryState,
    rng: RandomSource,
    decisions: ResolutionDecisionProvider | None,
) -> ResolutionResult:
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
        return ResolutionResult(
            request_id=request.id,
            attack=attack,
            replacement_impact=None,
            target_state=wound.state,
            stagger=None,
            character_wound=wound,
            wound_effect=None,
            profile_wound=None,
            monstrosity_impact=None,
            follow_ups=tuple(follow_ups),
            pending_character_wound=pending,
            deferred_wound_conditions=tuple(
                effect
                for effect in request.attack.secondary_effects
                if isinstance(effect, ConditionOnGiveGroundOrWoundSpec)
            ) if wound.wound_accepted else (),
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
    follow_ups.append(wound.state_change)
    return ResolutionResult(
        request_id=request.id,
        attack=attack,
        replacement_impact=None,
        target_state=wound.state,
        stagger=None,
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
        assert request.monstrosity_reaction is not None
        return ResolutionResult(
            request_id=request.id,
            attack=attack,
            replacement_impact=None,
            target_state=impact.state,
            stagger=None,
            character_wound=None,
            wound_effect=None,
            profile_wound=None,
            monstrosity_impact=impact,
            follow_ups=(
                MonstrosityReactionRequest(
                    resolution_id=request.id,
                    reaction=request.monstrosity_reaction,
                    additional_profile_wounds=(
                        request.additional_profile_wounds
                    ),
                    give_ground_or_wound_effects=tuple(
                        effect
                        for effect in request.attack.secondary_effects
                        if isinstance(
                            effect,
                            ConditionOnGiveGroundOrWoundSpec,
                        )
                    ),
                    target_effect_immunities=(
                        request.target_effect_immunities
                    ),
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
            replacement_impact=result.replacement_impact,
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
        replacement_impact=None,
        target_state=impact.state,
        stagger=None,
        character_wound=None,
        wound_effect=None,
        profile_wound=None,
        monstrosity_impact=impact,
        follow_ups=(),
    )


def apply_kernel_character_wound_completion(
    result: ResolutionResult,
    completion: CharacterWoundLifecycleCompletionResult,
) -> ResolutionResult:
    """Commit a pending Wound and then Wound-dependent attack effects."""
    if result.pending_character_wound is None:
        raise ValueError("kernel result has no pending character Wound")
    if completion.source_request.roll != result.pending_character_wound:
        raise ValueError("Wound completion belongs to another kernel result")
    if completion.previous_state != result.target_state:
        raise ValueError("kernel Wound completion used a stale target state")
    follow_ups = list(result.follow_ups)
    if completion.wound_effect is not None:
        follow_ups.extend(completion.wound_effect.follow_ups)
    state = completion.state
    applications = list(result.condition_applications)
    applied_rule_ids: list[str] = []
    if completion.outcome is CharacterWoundLifecycleOutcome.ACCEPTED:
        for effect in result.deferred_wound_conditions:
            application = resolve_condition_application(
                ConditionApplicationRequest(
                    id=(
                        f"{result.request_id}:{effect.rule_id}:"
                        "outcome-condition"
                    ),
                    state=state.conditions,
                    condition=effect.condition,
                    source_rule_id=effect.rule_id,
                    classification=effect.classification,
                    immunities=(
                        result.deferred_wound_condition_immunities
                    ),
                )
            )
            state = _with_conditions(state, application.state)
            applications.append(application)
            applied_rule_ids.extend(application.applied_rule_ids)
    return replace(
        result,
        target_state=state,
        wound_effect=completion.wound_effect,
        follow_ups=tuple(follow_ups),
        applied_secondary_rule_ids=tuple(
            dict.fromkeys(
                (*result.applied_secondary_rule_ids, *applied_rule_ids)
            )
        ),
        condition_applications=tuple(applications),
        pending_character_wound=None,
        deferred_wound_conditions=(),
        deferred_wound_condition_immunities=(),
        character_wound_completion=completion,
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


def _wound_was_accepted(result: ResolutionResult) -> bool:
    if result.character_wound is not None:
        return (
            result.pending_character_wound is None
            and result.character_wound.wound_accepted
        )
    if result.profile_wound is not None:
        return result.profile_wound.wounds_inflicted > 0
    return False
