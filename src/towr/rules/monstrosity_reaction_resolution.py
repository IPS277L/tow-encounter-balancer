from __future__ import annotations

from typing import Protocol

from towr.domain.condition_models import (
    Condition,
    ConditionApplicationRequest,
    ConditionState,
)
from towr.domain.injury_models import (
    DecisionOwner,
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
    MonstrousFlightReactionContext,
    MonstrousFlightReactionSpec,
    MonstrousRegenerationReactionSpec,
    ReactorZoneHazardRequest,
    SuppressRegenerationNextTurnRequest,
    UndeadMonstrosityReactionChoice,
    UndeadMonstrosityReactionContext,
    UndeadMonstrosityReactionSpec,
    UnsteadyReactionSpec,
)
from towr.domain.test_models import Skill
from towr.rules.condition_effect_resolution import (
    resolve_condition_application,
)
from towr.rules.injury_resolution import resolve_profile_wound


class UnresolvedMonstrousFlightReactionError(RuntimeError):
    pass


class MissingUndeadMonstrosityDecisionError(RuntimeError):
    pass


class InvalidUndeadMonstrosityDecisionError(ValueError):
    pass


class UndeadMonstrosityDecisionProvider(Protocol):
    def choose_undead_monstrosity_reaction(
        self,
        *,
        request: MonstrosityReactionResolutionRequest,
        owner: DecisionOwner,
        choices: tuple[UndeadMonstrosityReactionChoice, ...],
    ) -> UndeadMonstrosityReactionChoice: ...


def resolve_monstrosity_reaction(
    request: MonstrosityReactionResolutionRequest,
    *,
    decisions: UndeadMonstrosityDecisionProvider | None = None,
) -> MonstrosityReactionResolutionResult:
    reaction = request.source.reaction
    if isinstance(reaction, UndeadMonstrosityReactionSpec):
        return _resolve_undead_monstrosity(request, reaction, decisions)
    if isinstance(reaction, MonstrousRegenerationReactionSpec):
        return _resolve_regeneration(request, reaction)
    if isinstance(reaction, UnsteadyReactionSpec):
        return _resolve_unsteady(request, reaction)
    if not isinstance(reaction, MonstrousFlightReactionSpec):
        raise TypeError("unsupported Monstrosity reaction spec")

    assert isinstance(request.context, MonstrousFlightReactionContext)
    if request.context.has_given_ground_this_turn:
        return _resolve_reaction_wound(request, reaction.rule_id)
    if not request.context.can_give_ground:
        raise UnresolvedMonstrousFlightReactionError(
            "the books do not define a fallback when Monstrous Flight "
            "cannot Give Ground"
        )
    return _resolve_reaction_give_ground(
        request,
        reaction.rule_id,
        GiveGroundDestinationPreference.VERTICAL_MIDAIR_IF_ABLE,
    )


def _resolve_undead_monstrosity(
    request: MonstrosityReactionResolutionRequest,
    reaction: UndeadMonstrosityReactionSpec,
    decisions: UndeadMonstrosityDecisionProvider | None,
) -> MonstrosityReactionResolutionResult:
    if request.context is None:
        return _resolve_reaction_wound(request, reaction.rule_id)

    assert isinstance(request.context, UndeadMonstrosityReactionContext)
    choices = [UndeadMonstrosityReactionChoice.SUFFER_WOUND]
    is_prone = request.state.conditions.has(Condition.PRONE)
    if (
        not is_prone
        and request.context.can_give_ground
        and not request.context.has_given_ground_this_round
    ):
        choices.append(UndeadMonstrosityReactionChoice.GIVE_GROUND)
    if not is_prone:
        choices.append(UndeadMonstrosityReactionChoice.FALL_PRONE)
    selected = _choose_undead_monstrosity_reaction(
        request,
        tuple(choices),
        decisions,
    )
    if selected is UndeadMonstrosityReactionChoice.GIVE_GROUND:
        return _resolve_reaction_give_ground(
            request,
            reaction.rule_id,
            GiveGroundDestinationPreference.ANY_VALID_ADJACENT,
        )
    if selected is UndeadMonstrosityReactionChoice.FALL_PRONE:
        state = _with_conditions(
            request.state,
            request.state.conditions.with_condition(Condition.PRONE),
        )
        return MonstrosityReactionResolutionResult(
            request_id=request.id,
            source_resolution_id=request.source.resolution_id,
            reaction_rule_id=reaction.rule_id,
            state=state,
            outcome=MonstrosityReactionOutcome.FALL_PRONE,
            profile_wound=None,
            follow_ups=(),
            applied_rule_ids=(reaction.rule_id,),
        )
    return _resolve_reaction_wound(request, reaction.rule_id)


def _choose_undead_monstrosity_reaction(
    request: MonstrosityReactionResolutionRequest,
    choices: tuple[UndeadMonstrosityReactionChoice, ...],
    decisions: UndeadMonstrosityDecisionProvider | None,
) -> UndeadMonstrosityReactionChoice:
    if len(choices) == 1:
        return choices[0]
    if decisions is None:
        raise MissingUndeadMonstrosityDecisionError(
            "mounted Undead Monstrosity requires an explicit decision"
        )
    selected = decisions.choose_undead_monstrosity_reaction(
        request=request,
        owner=DecisionOwner.MONSTROSITY,
        choices=choices,
    )
    if not isinstance(selected, UndeadMonstrosityReactionChoice):
        raise InvalidUndeadMonstrosityDecisionError(
            "Undead Monstrosity decision must be a valid choice"
        )
    if selected not in choices:
        raise InvalidUndeadMonstrosityDecisionError(
            f"Undead Monstrosity choice is not available: {selected.value}"
        )
    return selected


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


def _resolve_reaction_give_ground(
    request: MonstrosityReactionResolutionRequest,
    reaction_rule_id: str,
    destination_preference: GiveGroundDestinationPreference,
) -> MonstrosityReactionResolutionResult:
    effects = request.source.give_ground_or_wound_effects
    condition_follow_ups = tuple(
        ConditionAfterGiveGroundRequest(
            resolution_id=request.source.resolution_id,
            condition=effect.condition,
            rule_id=effect.rule_id,
            classification=effect.classification,
            target_effect_immunities=(
                request.source.target_effect_immunities
            ),
        )
        for effect in effects
    )
    return MonstrosityReactionResolutionResult(
        request_id=request.id,
        source_resolution_id=request.source.resolution_id,
        reaction_rule_id=reaction_rule_id,
        state=request.state,
        outcome=MonstrosityReactionOutcome.GIVE_GROUND,
        profile_wound=None,
        follow_ups=(
            GiveGroundRequest(
                resolution_id=request.source.resolution_id,
                destination_preference=destination_preference,
            ),
            *condition_follow_ups,
        ),
        applied_rule_ids=(
            reaction_rule_id,
            *(effect.rule_id for effect in effects),
        ),
    )


def _resolve_reaction_wound(
    request: MonstrosityReactionResolutionRequest,
    reaction_rule_id: str,
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
    applications = []
    if wound.wounds_inflicted > 0:
        for effect in effects:
            application = resolve_condition_application(
                ConditionApplicationRequest(
                    id=f"{request.id}:{effect.rule_id}:outcome-condition",
                    state=state.conditions,
                    condition=effect.condition,
                    source_rule_id=effect.rule_id,
                    classification=effect.classification,
                    immunities=request.source.target_effect_immunities,
                )
            )
            state = _with_conditions(
                state,
                application.state,
            )
            applications.append(application)
    return MonstrosityReactionResolutionResult(
        request_id=request.id,
        source_resolution_id=request.source.resolution_id,
        reaction_rule_id=reaction_rule_id,
        state=state,
        outcome=MonstrosityReactionOutcome.SUFFER_WOUND,
        profile_wound=wound,
        follow_ups=(wound.state_change,),
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    reaction_rule_id,
                    *wound.applied_rule_ids,
                    *(
                        rule_id
                        for application in applications
                        for rule_id in application.applied_rule_ids
                    ),
                )
            )
        ),
        condition_applications=tuple(applications),
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
