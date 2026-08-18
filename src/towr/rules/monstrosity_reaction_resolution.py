from __future__ import annotations

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import (
    ProfileInjuryState,
    ProfileNpcType,
    ProfileWoundRequest,
)
from towr.domain.resolution_models import (
    ConditionAfterGiveGroundRequest,
    GiveGroundDestinationPreference,
    GiveGroundRequest,
    MonstrosityReactionOutcome,
    MonstrosityReactionResolutionRequest,
    MonstrosityReactionResolutionResult,
    MonstrousFlightReactionSpec,
    MonstrousRegenerationReactionSpec,
    ReactorZoneHazardRequest,
    SuppressRegenerationNextTurnRequest,
    UnsteadyReactionSpec,
)
from towr.domain.test_models import Skill
from towr.rules.injury_resolution import resolve_profile_wound


class UnresolvedMonstrousFlightReactionError(RuntimeError):
    pass


def resolve_monstrosity_reaction(
    request: MonstrosityReactionResolutionRequest,
) -> MonstrosityReactionResolutionResult:
    reaction = request.source.reaction
    if isinstance(reaction, MonstrousRegenerationReactionSpec):
        return _resolve_regeneration(request, reaction)
    if isinstance(reaction, UnsteadyReactionSpec):
        return _resolve_unsteady(request, reaction)
    if not isinstance(reaction, MonstrousFlightReactionSpec):
        raise TypeError("unsupported Monstrosity reaction spec")

    assert request.has_given_ground_this_turn is not None
    assert request.can_give_ground is not None
    if request.has_given_ground_this_turn:
        return _resolve_flight_wound(request, reaction)
    if not request.can_give_ground:
        raise UnresolvedMonstrousFlightReactionError(
            "the books do not define a fallback when Monstrous Flight "
            "cannot Give Ground"
        )
    return _resolve_flight_give_ground(request, reaction)


def _resolve_regeneration(
    request: MonstrosityReactionResolutionRequest,
    reaction: MonstrousRegenerationReactionSpec,
) -> MonstrosityReactionResolutionResult:
    return MonstrosityReactionResolutionResult(
        request_id=request.id,
        source_resolution_id=request.source.resolution_id,
        reaction_rule_id=reaction.rule_id,
        state=request.state,
        outcome=MonstrosityReactionOutcome.REGENERATION_SUPPRESSED,
        profile_wound=None,
        follow_ups=(
            SuppressRegenerationNextTurnRequest(
                resolution_id=request.source.resolution_id,
                rule_id=reaction.rule_id,
            ),
        ),
        applied_rule_ids=(reaction.rule_id,),
    )


def _resolve_unsteady(
    request: MonstrosityReactionResolutionRequest,
    reaction: UnsteadyReactionSpec,
) -> MonstrosityReactionResolutionResult:
    was_already_prone = request.state.conditions.has(Condition.PRONE)
    if was_already_prone:
        state = request.state
        outcome = MonstrosityReactionOutcome.ALREADY_PRONE
        follow_ups = ()
    else:
        state = _with_conditions(
            request.state,
            request.state.conditions.with_condition(Condition.PRONE),
        )
        outcome = MonstrosityReactionOutcome.FALL_PRONE
        follow_ups = (
            ReactorZoneHazardRequest(
                resolution_id=request.source.resolution_id,
                rating=3,
                avoidance_skill=Skill.ATHLETICS,
                rule_id=reaction.rule_id,
                inflicts_wound=True,
                failure_conditions=(),
            ),
        )
    return MonstrosityReactionResolutionResult(
        request_id=request.id,
        source_resolution_id=request.source.resolution_id,
        reaction_rule_id=reaction.rule_id,
        state=state,
        outcome=outcome,
        profile_wound=None,
        follow_ups=follow_ups,
        applied_rule_ids=(reaction.rule_id,),
    )


def _resolve_flight_give_ground(
    request: MonstrosityReactionResolutionRequest,
    reaction: MonstrousFlightReactionSpec,
) -> MonstrosityReactionResolutionResult:
    effects = request.source.give_ground_or_wound_effects
    condition_follow_ups = tuple(
        ConditionAfterGiveGroundRequest(
            resolution_id=request.source.resolution_id,
            condition=effect.condition,
            rule_id=effect.rule_id,
        )
        for effect in effects
    )
    return MonstrosityReactionResolutionResult(
        request_id=request.id,
        source_resolution_id=request.source.resolution_id,
        reaction_rule_id=reaction.rule_id,
        state=request.state,
        outcome=MonstrosityReactionOutcome.GIVE_GROUND,
        profile_wound=None,
        follow_ups=(
            GiveGroundRequest(
                resolution_id=request.source.resolution_id,
                destination_preference=(
                    GiveGroundDestinationPreference.VERTICAL_MIDAIR_IF_ABLE
                ),
            ),
            *condition_follow_ups,
        ),
        applied_rule_ids=(
            reaction.rule_id,
            *(effect.rule_id for effect in effects),
        ),
    )


def _resolve_flight_wound(
    request: MonstrosityReactionResolutionRequest,
    reaction: MonstrousFlightReactionSpec,
) -> MonstrosityReactionResolutionResult:
    wound = resolve_profile_wound(
        ProfileWoundRequest(
            id=f"{request.id}:wound",
            npc_type=ProfileNpcType.MONSTROSITY,
            state=request.state,
            additional_wounds=request.source.additional_profile_wounds,
        )
    )
    state = wound.state
    effects = request.source.give_ground_or_wound_effects
    if wound.wounds_inflicted > 0:
        for effect in effects:
            state = _with_conditions(
                state,
                state.conditions.with_condition(effect.condition),
            )
    return MonstrosityReactionResolutionResult(
        request_id=request.id,
        source_resolution_id=request.source.resolution_id,
        reaction_rule_id=reaction.rule_id,
        state=state,
        outcome=MonstrosityReactionOutcome.SUFFER_WOUND,
        profile_wound=wound,
        follow_ups=(wound.state_change,),
        applied_rule_ids=(
            reaction.rule_id,
            *wound.applied_rule_ids,
            *(effect.rule_id for effect in effects),
        ),
    )


def _with_conditions(
    state: ProfileInjuryState,
    conditions: ConditionState,
) -> ProfileInjuryState:
    return ProfileInjuryState(
        wounds=state.wounds,
        wound_limit=state.wound_limit,
        conditions=conditions,
        defeated=state.defeated,
    )
