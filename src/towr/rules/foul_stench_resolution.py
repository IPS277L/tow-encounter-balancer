from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from towr.domain.condition_models import Condition, ConditionApplicationRequest
from towr.domain.injury_models import DecisionOwner
from towr.domain.npc_effect_models import (
    DropHeldHandItemRequest,
    FoulStenchChoice,
    FoulStenchOutcome,
    FoulStenchRequest,
    FoulStenchResult,
)
from towr.rules.condition_effect_resolution import resolve_condition_application


class MissingFoulStenchDecisionError(RuntimeError):
    pass


class InvalidFoulStenchDecisionError(ValueError):
    pass


class FoulStenchDecisionProvider(Protocol):
    def choose_foul_stench_response(
        self,
        *,
        request: FoulStenchRequest,
        owner: DecisionOwner,
        choices: tuple[FoulStenchChoice, ...],
    ) -> FoulStenchChoice: ...


def resolve_foul_stench(
    request: FoulStenchRequest,
    *,
    decisions: FoulStenchDecisionProvider | None = None,
) -> FoulStenchResult:
    if request.has_free_hand:
        return FoulStenchResult(
            request_id=request.id,
            target_id=request.target_id,
            state=request.target_state,
            outcome=FoulStenchOutcome.COVERED_NOSE_WITH_FREE_HAND,
            decision_owner=None,
            allowed_choices=(),
            selected_choice=None,
            follow_ups=(),
            condition_application=None,
            applied_rule_ids=(request.rule_id,),
        )

    choices = (
        (
            FoulStenchChoice.DROP_HELD_HAND_ITEM,
            FoulStenchChoice.SUFFER_DISTRACTED,
        )
        if request.has_droppable_hand_item
        else (FoulStenchChoice.SUFFER_DISTRACTED,)
    )
    selected = _choose_response(request, choices, decisions)
    if selected is FoulStenchChoice.DROP_HELD_HAND_ITEM:
        return FoulStenchResult(
            request_id=request.id,
            target_id=request.target_id,
            state=request.target_state,
            outcome=FoulStenchOutcome.DROP_HELD_HAND_ITEM_REQUESTED,
            decision_owner=DecisionOwner.TARGET,
            allowed_choices=choices,
            selected_choice=selected,
            follow_ups=(
                DropHeldHandItemRequest(
                    resolution_id=request.id,
                    target_id=request.target_id,
                    rule_id=request.rule_id,
                ),
            ),
            condition_application=None,
            applied_rule_ids=(request.rule_id,),
        )

    application = resolve_condition_application(
        ConditionApplicationRequest(
            id=f"{request.id}:{request.target_id}:distracted",
            state=request.target_state.conditions,
            condition=Condition.DISTRACTED,
            source_rule_id=request.rule_id,
        )
    )
    return FoulStenchResult(
        request_id=request.id,
        target_id=request.target_id,
        state=replace(request.target_state, conditions=application.state),
        outcome=FoulStenchOutcome.SUFFERED_DISTRACTED,
        decision_owner=(
            DecisionOwner.TARGET if len(choices) > 1 else None
        ),
        allowed_choices=choices,
        selected_choice=selected,
        follow_ups=(),
        condition_application=application,
        applied_rule_ids=application.applied_rule_ids,
    )


def _choose_response(
    request: FoulStenchRequest,
    choices: tuple[FoulStenchChoice, ...],
    decisions: FoulStenchDecisionProvider | None,
) -> FoulStenchChoice:
    if len(choices) == 1:
        return choices[0]
    if decisions is None:
        raise MissingFoulStenchDecisionError(
            "Foul Stench requires an explicit target decision"
        )
    selected = decisions.choose_foul_stench_response(
        request=request,
        owner=DecisionOwner.TARGET,
        choices=choices,
    )
    if not isinstance(selected, FoulStenchChoice) or selected not in choices:
        raise InvalidFoulStenchDecisionError(
            "Foul Stench decision must be one of the available choices"
        )
    return selected
