from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from towr.domain.condition_models import ConditionApplicationResult
from towr.domain.injury_models import (
    CharacterInjuryState,
    DecisionOwner,
    ProfileInjuryState,
    ProfileStateChangeRequest,
    ProfileWoundResult,
)
from towr.domain.test_models import TestResult


class FoulStenchChoice(str, Enum):
    DROP_HELD_HAND_ITEM = "drop_held_hand_item"
    SUFFER_DISTRACTED = "suffer_distracted"


class FoulStenchOutcome(str, Enum):
    COVERED_NOSE_WITH_FREE_HAND = "covered_nose_with_free_hand"
    DROP_HELD_HAND_ITEM_REQUESTED = "drop_held_hand_item_requested"
    SUFFERED_DISTRACTED = "suffered_distracted"


class TrollStupidityOutcome(str, Enum):
    DISTRACTED_ACTIVE = "distracted_active"
    REMOVED_BY_WOUND = "removed_by_wound"
    REMOVED_BY_LEADERSHIP = "removed_by_leadership"
    REMOVED_EXTERNALLY = "removed_externally"
    LEADERSHIP_FAILED = "leadership_failed"
    ALREADY_SUPPRESSED = "already_suppressed"


class TrollRegenerationChoice(str, Enum):
    REGENERATE = "regenerate"
    SKIP = "skip"


class TrollRegenerationOutcome(str, Enum):
    HEALED = "healed"
    DECLINED = "declined"
    UNAVAILABLE_STAGGERED = "unavailable_staggered"
    UNAVAILABLE_UNWOUNDED = "unavailable_unwounded"
    UNAVAILABLE_FIRE_WOUNDS = "unavailable_fire_wounds"


@dataclass(frozen=True, slots=True)
class TrollStupidityState:
    rule_id: str = "RULE-NPC-021:troll-stupidity"
    suppressed_until_battle_end: bool = False

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.rule_id, "Stupidity rule_id")
        _validate_bool(
            self.suppressed_until_battle_end,
            "suppressed_until_battle_end",
        )


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


@dataclass(frozen=True, slots=True)
class TrollStupidityStartRequest:
    id: str
    target_id: str
    target_state: ProfileInjuryState
    ability_state: TrollStupidityState

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Stupidity start request id")
        _validate_non_empty_string(self.target_id, "target_id")
        if not isinstance(self.target_state, ProfileInjuryState):
            raise TypeError("target_state must be a ProfileInjuryState")
        if not isinstance(self.ability_state, TrollStupidityState):
            raise TypeError("ability_state must be a TrollStupidityState")


@dataclass(frozen=True, slots=True)
class TrollStupidityWoundRequest:
    id: str
    target_id: str
    wound: ProfileWoundResult
    ability_state: TrollStupidityState

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Stupidity Wound request id")
        _validate_non_empty_string(self.target_id, "target_id")
        if not isinstance(self.wound, ProfileWoundResult):
            raise TypeError("wound must be a ProfileWoundResult")
        if not isinstance(self.ability_state, TrollStupidityState):
            raise TypeError("ability_state must be a TrollStupidityState")


@dataclass(frozen=True, slots=True)
class TrollStupidityLeadershipRequest:
    id: str
    target_id: str
    target_state: ProfileInjuryState
    leadership_test: TestResult
    ability_state: TrollStupidityState

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Stupidity Leadership request id")
        _validate_non_empty_string(self.target_id, "target_id")
        if not isinstance(self.target_state, ProfileInjuryState):
            raise TypeError("target_state must be a ProfileInjuryState")
        if not isinstance(self.leadership_test, TestResult):
            raise TypeError("leadership_test must be a TestResult")
        if not isinstance(self.ability_state, TrollStupidityState):
            raise TypeError("ability_state must be a TrollStupidityState")


@dataclass(frozen=True, slots=True)
class TrollStupidityConditionRemovedRequest:
    id: str
    target_id: str
    target_state: ProfileInjuryState
    removal_rule_id: str
    ability_state: TrollStupidityState

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.id,
            "Stupidity Condition removal request id",
        )
        _validate_non_empty_string(self.target_id, "target_id")
        if not isinstance(self.target_state, ProfileInjuryState):
            raise TypeError("target_state must be a ProfileInjuryState")
        _validate_non_empty_string(self.removal_rule_id, "removal_rule_id")
        if not isinstance(self.ability_state, TrollStupidityState):
            raise TypeError("ability_state must be a TrollStupidityState")


@dataclass(frozen=True, slots=True)
class TrollStupidityResult:
    request_id: str
    target_id: str
    state: ProfileInjuryState
    ability_state: TrollStupidityState
    outcome: TrollStupidityOutcome
    condition_application: ConditionApplicationResult | None
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TrollRegenerationRequest:
    id: str
    target_id: str
    target_state: ProfileInjuryState
    has_non_fire_wound: bool
    rule_id: str = "RULE-NPC-023:troll-regeneration"

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Troll Regeneration request id")
        _validate_non_empty_string(self.target_id, "target_id")
        if not isinstance(self.target_state, ProfileInjuryState):
            raise TypeError("target_state must be a ProfileInjuryState")
        if self.target_state.defeated:
            raise ValueError("a defeated Troll cannot regenerate")
        _validate_bool(self.has_non_fire_wound, "has_non_fire_wound")
        if self.target_state.wounds == 0 and self.has_non_fire_wound:
            raise ValueError("an unwounded Troll cannot have a non-fire Wound")
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class TrollRegenerationResult:
    request_id: str
    target_id: str
    state: ProfileInjuryState
    outcome: TrollRegenerationOutcome
    decision_owner: DecisionOwner | None
    allowed_choices: tuple[TrollRegenerationChoice, ...]
    selected_choice: TrollRegenerationChoice | None
    wounds_healed: int
    condition_application: ConditionApplicationResult | None
    state_change: ProfileStateChangeRequest | None
    applied_rule_ids: tuple[str, ...]


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
