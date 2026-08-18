from __future__ import annotations

from typing import Protocol

from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    DecisionOwner,
    MonstrosityImpactChoice,
    MonstrosityImpactRequest,
    MonstrosityImpactResult,
    ProfileInjuryState,
)


class MissingMonstrosityDecisionError(RuntimeError):
    pass


class InvalidMonstrosityDecisionError(ValueError):
    pass


class MonstrosityDecisionProvider(Protocol):
    def choose_monstrosity_impact(
        self,
        *,
        request: MonstrosityImpactRequest,
        owner: DecisionOwner,
        choices: tuple[MonstrosityImpactChoice, ...],
    ) -> MonstrosityImpactChoice: ...


MONSTROSITY_IMPACT_CHOICES = (
    MonstrosityImpactChoice.SUFFER_WOUND,
    MonstrosityImpactChoice.TRIGGER_REACTION,
)


def resolve_monstrosity_impact(
    request: MonstrosityImpactRequest,
    *,
    decisions: MonstrosityDecisionProvider | None = None,
) -> MonstrosityImpactResult:
    if request.state.defeated:
        raise ValueError("a defeated Monstrosity cannot suffer Damage")

    damage_exceeds_resilience = request.damage > request.resilience
    is_staggered = request.state.conditions.has(Condition.STAGGERED)
    if not damage_exceeds_resilience and not is_staggered:
        state = ProfileInjuryState(
            wounds=request.state.wounds,
            wound_limit=request.state.wound_limit,
            conditions=request.state.conditions.with_condition(Condition.STAGGERED),
            defeated=False,
        )
        return MonstrosityImpactResult(
            request_id=request.id,
            state=state,
            decision_owner=None,
            selected_choice=None,
            wound_requested=False,
            reaction_requested=False,
            staggered_applied=True,
        )

    owner = (
        DecisionOwner.ATTACKER
        if damage_exceeds_resilience
        else DecisionOwner.MONSTROSITY
    )
    if decisions is None:
        raise MissingMonstrosityDecisionError(
            "Wound/Reaction requires an explicit MonstrosityDecisionProvider"
        )
    selected = decisions.choose_monstrosity_impact(
        request=request,
        owner=owner,
        choices=MONSTROSITY_IMPACT_CHOICES,
    )
    if not isinstance(selected, MonstrosityImpactChoice):
        raise InvalidMonstrosityDecisionError(
            "Monstrosity impact decision must be a MonstrosityImpactChoice"
        )
    return MonstrosityImpactResult(
        request_id=request.id,
        state=request.state,
        decision_owner=owner,
        selected_choice=selected,
        wound_requested=selected is MonstrosityImpactChoice.SUFFER_WOUND,
        reaction_requested=selected is MonstrosityImpactChoice.TRIGGER_REACTION,
        staggered_applied=False,
    )
