from __future__ import annotations

from typing import Protocol

from towr.domain.condition_models import (
    Condition,
    StaggerChoice,
    StaggerOutcome,
    StaggerRequest,
    StaggerResult,
)


class MissingStaggerDecisionError(RuntimeError):
    pass


class InvalidStaggerDecisionError(ValueError):
    pass


class StaggerDecisionProvider(Protocol):
    def choose_repeated_stagger(
        self,
        *,
        request: StaggerRequest,
        allowed_choices: tuple[StaggerChoice, ...],
    ) -> StaggerChoice: ...


def resolve_stagger(
    request: StaggerRequest,
    *,
    decisions: StaggerDecisionProvider | None = None,
) -> StaggerResult:
    if not request.state.has(Condition.STAGGERED):
        return StaggerResult(
            request_id=request.id,
            state=request.state.with_condition(Condition.STAGGERED),
            outcome=StaggerOutcome.CONDITION_ADDED,
            allowed_choices=(),
            selected_choice=None,
            wound_requested=False,
            gave_ground=False,
        )

    allowed_choices = _allowed_repeated_stagger_choices(request)
    if len(allowed_choices) == 1:
        selected = allowed_choices[0]
    else:
        if decisions is None:
            raise MissingStaggerDecisionError(
                "repeated Staggered requires an explicit StaggerDecisionProvider"
            )
        selected = decisions.choose_repeated_stagger(
            request=request,
            allowed_choices=allowed_choices,
        )
        if not isinstance(selected, StaggerChoice):
            raise InvalidStaggerDecisionError(
                "repeated Staggered decision must be a StaggerChoice"
            )
        if selected not in allowed_choices:
            raise InvalidStaggerDecisionError(
                f"{selected.value} is not allowed in the current context"
            )

    if selected is StaggerChoice.GIVE_GROUND:
        return StaggerResult(
            request_id=request.id,
            state=request.state,
            outcome=StaggerOutcome.GAVE_GROUND,
            allowed_choices=allowed_choices,
            selected_choice=selected,
            wound_requested=False,
            gave_ground=True,
        )
    if selected is StaggerChoice.FALL_PRONE:
        return StaggerResult(
            request_id=request.id,
            state=request.state.with_condition(Condition.PRONE),
            outcome=StaggerOutcome.FELL_PRONE,
            allowed_choices=allowed_choices,
            selected_choice=selected,
            wound_requested=False,
            gave_ground=False,
        )
    return StaggerResult(
        request_id=request.id,
        state=request.state,
        outcome=StaggerOutcome.WOUND_REQUESTED,
        allowed_choices=allowed_choices,
        selected_choice=selected,
        wound_requested=True,
        gave_ground=False,
    )


def _allowed_repeated_stagger_choices(
    request: StaggerRequest,
) -> tuple[StaggerChoice, ...]:
    choices: list[StaggerChoice] = []
    is_prone = request.state.has(Condition.PRONE)
    if (
        request.can_leave_zone
        and not request.has_given_ground_this_round
        and not is_prone
    ):
        choices.append(StaggerChoice.GIVE_GROUND)
    if not is_prone:
        choices.append(StaggerChoice.FALL_PRONE)
    choices.append(StaggerChoice.SUFFER_WOUND)
    return tuple(choices)
