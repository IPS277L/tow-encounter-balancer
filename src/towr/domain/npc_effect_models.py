from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from towr.domain.condition_models import ConditionApplicationResult
from towr.domain.injury_models import (
    CharacterInjuryState,
    DecisionOwner,
    ProfileInjuryState,
)


class FoulStenchChoice(str, Enum):
    DROP_HELD_HAND_ITEM = "drop_held_hand_item"
    SUFFER_DISTRACTED = "suffer_distracted"


class FoulStenchOutcome(str, Enum):
    COVERED_NOSE_WITH_FREE_HAND = "covered_nose_with_free_hand"
    DROP_HELD_HAND_ITEM_REQUESTED = "drop_held_hand_item_requested"
    SUFFERED_DISTRACTED = "suffered_distracted"


@dataclass(frozen=True, slots=True)
class DropHeldHandItemRequest:
    resolution_id: str
    target_id: str
    rule_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(self.target_id, "target_id")
        _validate_non_empty_string(self.rule_id, "rule_id")


FoulStenchTargetState = CharacterInjuryState | ProfileInjuryState


@dataclass(frozen=True, slots=True)
class FoulStenchRequest:
    """Resolve Foul Stench for one enemy after a Wyvern enters its Zone."""

    id: str
    target_id: str
    target_state: FoulStenchTargetState
    has_free_hand: bool
    has_droppable_hand_item: bool
    rule_id: str = "RULE-NPC-017:foul-stench"

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Foul Stench request id")
        _validate_non_empty_string(self.target_id, "target_id")
        if not isinstance(
            self.target_state,
            (CharacterInjuryState, ProfileInjuryState),
        ):
            raise TypeError("target_state must be an injury state")
        _validate_bool(self.has_free_hand, "has_free_hand")
        _validate_bool(
            self.has_droppable_hand_item,
            "has_droppable_hand_item",
        )
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class FoulStenchResult:
    request_id: str
    target_id: str
    state: FoulStenchTargetState
    outcome: FoulStenchOutcome
    decision_owner: DecisionOwner | None
    allowed_choices: tuple[FoulStenchChoice, ...]
    selected_choice: FoulStenchChoice | None
    follow_ups: tuple[DropHeldHandItemRequest, ...]
    condition_application: ConditionApplicationResult | None
    applied_rule_ids: tuple[str, ...]


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
