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
from towr.domain.resolution_models import (
    MonstrousRegenerationChoice,
    MonstrousRegenerationEndTurnRequest,
    MonstrousRegenerationEndTurnResult,
    MonstrousRegenerationOutcome,
    SuppressRegenerationNextTurnRequest,
)
from towr.rules.condition_effect_resolution import (
    resolve_condition_application,
)


class MissingMonstrousRegenerationDecisionError(RuntimeError):
    pass


class InvalidMonstrousRegenerationDecisionError(ValueError):
    pass


class MonstrousRegenerationDecisionProvider(Protocol):
    def choose_monstrous_regeneration(
        self,
        *,
        request: MonstrousRegenerationEndTurnRequest,
        owner: DecisionOwner,
        choices: tuple[MonstrousRegenerationChoice, ...],
    ) -> MonstrousRegenerationChoice: ...


def resolve_monstrous_regeneration_end_turn(
    request: MonstrousRegenerationEndTurnRequest,
    *,
    decisions: MonstrousRegenerationDecisionProvider | None = None,
) -> MonstrousRegenerationEndTurnResult:
    if request.pending_suppression is not None:
        return _unavailable(
            request,
            MonstrousRegenerationOutcome.SUPPRESSED_AND_CONSUMED,
            consumed_suppression=request.pending_suppression,
        )
    if request.target_state.wounds == 0:
        return _unavailable(
            request,
            MonstrousRegenerationOutcome.UNAVAILABLE_UNWOUNDED,
        )
    if not request.has_non_fire_wound:
        return _unavailable(
            request,
            MonstrousRegenerationOutcome.UNAVAILABLE_FIRE_WOUNDS,
        )

    choices = (
        MonstrousRegenerationChoice.REGENERATE,
        MonstrousRegenerationChoice.SKIP,
    )
    selected = _choose(request, choices, decisions)
    if selected is MonstrousRegenerationChoice.SKIP:
        return MonstrousRegenerationEndTurnResult(
            request_id=request.id,
            target_id=request.target_id,
            state=request.target_state,
            outcome=MonstrousRegenerationOutcome.DECLINED,
            decision_owner=DecisionOwner.ACTOR,
            allowed_choices=choices,
            selected_choice=selected,
            wounds_healed=0,
            condition_application=None,
            state_change=None,
            consumed_suppression=None,
            applied_rule_ids=(request.rule_id,),
        )

    application = None
    conditions = request.target_state.conditions
    if not conditions.has(Condition.STAGGERED):
        application = resolve_condition_application(
            ConditionApplicationRequest(
                id=f"{request.id}:{request.target_id}:staggered",
                state=conditions,
                condition=Condition.STAGGERED,
                source_rule_id=request.rule_id,
            )
        )
        conditions = application.state

    state = replace(
        request.target_state,
        wounds=request.target_state.wounds - 1,
        conditions=conditions,
    )
    state_change = ProfileStateChangeRequest(
        npc_type=ProfileNpcType.MONSTROSITY,
        previous_wounds=request.target_state.wounds,
        current_wounds=state.wounds,
        defeated=False,
    )
    return MonstrousRegenerationEndTurnResult(
        request_id=request.id,
        target_id=request.target_id,
        state=state,
        outcome=MonstrousRegenerationOutcome.HEALED,
        decision_owner=DecisionOwner.ACTOR,
        allowed_choices=choices,
        selected_choice=selected,
        wounds_healed=1,
        condition_application=application,
        state_change=state_change,
        consumed_suppression=None,
        applied_rule_ids=(request.rule_id,),
    )


def _choose(
    request: MonstrousRegenerationEndTurnRequest,
    choices: tuple[MonstrousRegenerationChoice, ...],
    decisions: MonstrousRegenerationDecisionProvider | None,
) -> MonstrousRegenerationChoice:
    if decisions is None:
        raise MissingMonstrousRegenerationDecisionError(
            "available Monstrous Regeneration requires an explicit decision"
        )
    selected = decisions.choose_monstrous_regeneration(
        request=request,
        owner=DecisionOwner.ACTOR,
        choices=choices,
    )
    if not isinstance(selected, MonstrousRegenerationChoice):
        raise InvalidMonstrousRegenerationDecisionError(
            "Monstrous Regeneration decision must be a valid choice"
        )
    if selected not in choices:
        raise InvalidMonstrousRegenerationDecisionError(
            "Monstrous Regeneration choice is not available"
        )
    return selected


def _unavailable(
    request: MonstrousRegenerationEndTurnRequest,
    outcome: MonstrousRegenerationOutcome,
    *,
    consumed_suppression: SuppressRegenerationNextTurnRequest | None = None,
) -> MonstrousRegenerationEndTurnResult:
    return MonstrousRegenerationEndTurnResult(
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
        consumed_suppression=consumed_suppression,
        applied_rule_ids=(request.rule_id,),
    )
