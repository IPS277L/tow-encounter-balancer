from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from towr.domain.condition_models import (
    Condition,
    ConditionApplicationRequest,
)
from towr.domain.injury_models import (
    DecisionOwner,
    ProfileNpcType,
    ProfileStateChangeRequest,
)
from towr.domain.npc_effect_models import (
    TrollRegenerationChoice,
    TrollRegenerationOutcome,
    TrollRegenerationRequest,
    TrollRegenerationResult,
)
from towr.rules.condition_effect_resolution import (
    resolve_condition_application,
)


class MissingTrollRegenerationDecisionError(RuntimeError):
    pass


class InvalidTrollRegenerationDecisionError(ValueError):
    pass


class TrollRegenerationDecisionProvider(Protocol):
    def choose_troll_regeneration(
        self,
        *,
        request: TrollRegenerationRequest,
        owner: DecisionOwner,
        choices: tuple[TrollRegenerationChoice, ...],
    ) -> TrollRegenerationChoice: ...


def resolve_troll_regeneration(
    request: TrollRegenerationRequest,
    *,
    decisions: TrollRegenerationDecisionProvider | None = None,
) -> TrollRegenerationResult:
    if request.target_state.conditions.has(Condition.STAGGERED):
        return _unavailable(
            request,
            TrollRegenerationOutcome.UNAVAILABLE_STAGGERED,
        )
    if request.target_state.wounds == 0:
        return _unavailable(
            request,
            TrollRegenerationOutcome.UNAVAILABLE_UNWOUNDED,
        )
    if not request.has_non_fire_wound:
        return _unavailable(
            request,
            TrollRegenerationOutcome.UNAVAILABLE_FIRE_WOUNDS,
        )

    choices = (
        TrollRegenerationChoice.REGENERATE,
        TrollRegenerationChoice.SKIP,
    )
    selected = _choose(request, choices, decisions)
    if selected is TrollRegenerationChoice.SKIP:
        return TrollRegenerationResult(
            request_id=request.id,
            target_id=request.target_id,
            state=request.target_state,
            outcome=TrollRegenerationOutcome.DECLINED,
            decision_owner=DecisionOwner.ACTOR,
            allowed_choices=choices,
            selected_choice=selected,
            wounds_healed=0,
            condition_application=None,
            state_change=None,
            applied_rule_ids=(request.rule_id,),
        )

    application = resolve_condition_application(
        ConditionApplicationRequest(
            id=f"{request.id}:{request.target_id}:staggered",
            state=request.target_state.conditions,
            condition=Condition.STAGGERED,
            source_rule_id=request.rule_id,
        )
    )
    state = replace(
        request.target_state,
        wounds=request.target_state.wounds - 1,
        conditions=application.state,
    )
    state_change = ProfileStateChangeRequest(
        npc_type=ProfileNpcType.BRUTE,
        previous_wounds=request.target_state.wounds,
        current_wounds=state.wounds,
        defeated=False,
    )
    return TrollRegenerationResult(
        request_id=request.id,
        target_id=request.target_id,
        state=state,
        outcome=TrollRegenerationOutcome.HEALED,
        decision_owner=DecisionOwner.ACTOR,
        allowed_choices=choices,
        selected_choice=selected,
        wounds_healed=1,
        condition_application=application,
        state_change=state_change,
        applied_rule_ids=application.applied_rule_ids,
    )


def _choose(
    request: TrollRegenerationRequest,
    choices: tuple[TrollRegenerationChoice, ...],
    decisions: TrollRegenerationDecisionProvider | None,
) -> TrollRegenerationChoice:
    if decisions is None:
        raise MissingTrollRegenerationDecisionError(
            "available Troll Regeneration requires an explicit decision"
        )
    selected = decisions.choose_troll_regeneration(
        request=request,
        owner=DecisionOwner.ACTOR,
        choices=choices,
    )
    if not isinstance(selected, TrollRegenerationChoice):
        raise InvalidTrollRegenerationDecisionError(
            "Troll Regeneration decision must be a valid choice"
        )
    if selected not in choices:
        raise InvalidTrollRegenerationDecisionError(
            "Troll Regeneration choice is not available"
        )
    return selected


def _unavailable(
    request: TrollRegenerationRequest,
    outcome: TrollRegenerationOutcome,
) -> TrollRegenerationResult:
    return TrollRegenerationResult(
        request_id=request.id,
        target_id=request.target_id,
        state=request.target_state,
        outcome=outcome,
        decision_owner=None,
        allowed_choices=(),
        selected_choice=None,
        wounds_healed=0,
        condition_application=None,
        state_change=None,
        applied_rule_ids=(request.rule_id,),
    )
