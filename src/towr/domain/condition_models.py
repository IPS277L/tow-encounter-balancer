from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Condition(str, Enum):
    ABLAZE = "ablaze"
    BLINDED = "blinded"
    BROKEN = "broken"
    BURDENED = "burdened"
    CRITICALLY_INJURED = "critically_injured"
    DEAFENED = "deafened"
    DEFENCELESS = "defenceless"
    DISTRACTED = "distracted"
    DRAINED = "drained"
    PRONE = "prone"
    STAGGERED = "staggered"


class StaggerChoice(str, Enum):
    GIVE_GROUND = "give_ground"
    FALL_PRONE = "fall_prone"
    SUFFER_WOUND = "suffer_wound"


class StaggerOutcome(str, Enum):
    CONDITION_ADDED = "condition_added"
    GAVE_GROUND = "gave_ground"
    FELL_PRONE = "fell_prone"
    WOUND_REQUESTED = "wound_requested"


@dataclass(frozen=True, slots=True)
class ConditionState:
    conditions: frozenset[Condition] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        values = frozenset(self.conditions)
        if not all(isinstance(item, Condition) for item in values):
            raise TypeError("conditions must contain Condition values")
        object.__setattr__(self, "conditions", values)

    def has(self, condition: Condition) -> bool:
        return condition in self.conditions

    def with_condition(self, condition: Condition) -> ConditionState:
        if not isinstance(condition, Condition):
            raise TypeError("condition must be a Condition")
        return ConditionState(self.conditions | {condition})

    def without_condition(self, condition: Condition) -> ConditionState:
        if not isinstance(condition, Condition):
            raise TypeError("condition must be a Condition")
        return ConditionState(self.conditions - {condition})


@dataclass(frozen=True, slots=True)
class StaggerRequest:
    id: str
    state: ConditionState
    can_leave_zone: bool
    has_given_ground_this_round: bool

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            raise TypeError("stagger request id must be a string")
        if not self.id.strip():
            raise ValueError("stagger request id must not be empty")
        if not isinstance(self.state, ConditionState):
            raise TypeError("state must be a ConditionState")
        _validate_bool(self.can_leave_zone, "can_leave_zone")
        _validate_bool(
            self.has_given_ground_this_round,
            "has_given_ground_this_round",
        )


@dataclass(frozen=True, slots=True)
class StaggerResult:
    request_id: str
    state: ConditionState
    outcome: StaggerOutcome
    allowed_choices: tuple[StaggerChoice, ...]
    selected_choice: StaggerChoice | None
    wound_requested: bool
    gave_ground: bool


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")
