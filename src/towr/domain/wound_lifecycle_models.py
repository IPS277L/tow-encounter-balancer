from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from towr.domain.fate_models import (
    FATE_NEAR_MISS_RULE_ID,
    FateBurnResult,
    FateNearMissBurnRequest,
)
from towr.domain.fate_near_miss_models import (
    FateNearMissApplicationResult,
)
from towr.domain.infection_models import (
    DailyWoundRegistrationResult,
    DailyWoundState,
)
from towr.domain.injury_models import (
    CharacterInjuryState,
    CharacterWoundRequest,
    CharacterWoundResult,
    CharacterWoundType,
    FixedCharacterWoundRequest,
    FixedCharacterWoundResult,
    WoundEffectResult,
    validate_character_wound_result_provenance,
    validate_fixed_character_wound_result_provenance,
)


CHARACTER_WOUND_LIFECYCLE_RULE_ID = (
    "RULE-HEALTH-005:character-wound-lifecycle"
)
FIXED_CHARACTER_WOUND_LIFECYCLE_RULE_ID = (
    "RULE-HEALTH-005:fixed-character-wound-lifecycle"
)


class CharacterWoundLifecycleOutcome(str, Enum):
    ACCEPTED = "accepted"
    NEGATED = "negated"
    NEAR_MISS = "near_miss"


@dataclass(frozen=True, slots=True)
class CharacterWoundLifecycleRollRequest:
    id: str
    target_id: str
    wound: CharacterWoundRequest
    rule_id: str = CHARACTER_WOUND_LIFECYCLE_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Wound lifecycle roll id")
        _validate_non_empty_string(
            self.target_id,
            "Wound lifecycle target_id",
        )
        if not isinstance(self.wound, CharacterWoundRequest):
            raise TypeError("wound must be a CharacterWoundRequest")
        _validate_non_empty_string(
            self.rule_id,
            "Wound lifecycle rule_id",
        )


@dataclass(frozen=True, slots=True)
class CharacterWoundLifecycleRollResult:
    request_id: str
    rule_id: str
    source_request: CharacterWoundLifecycleRollRequest
    wound_result: CharacterWoundResult
    near_miss_eligible: bool
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Wound lifecycle roll result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "Wound lifecycle roll result rule_id",
        )
        if not isinstance(
            self.source_request,
            CharacterWoundLifecycleRollRequest,
        ):
            raise TypeError("source_request must be a lifecycle roll request")
        if not isinstance(self.wound_result, CharacterWoundResult):
            raise TypeError("wound_result must be a CharacterWoundResult")
        _validate_bool(self.near_miss_eligible, "near_miss_eligible")
        validate_character_wound_result_provenance(
            self.source_request.wound,
            self.wound_result,
        )
        expected_eligible = (
            self.wound_result.wound_accepted
            and self.wound_result.subject_type is CharacterWoundType.PLAYER
        )
        expected_rules = _ordered_rule_ids(
            *self.wound_result.applied_rule_ids,
            self.source_request.rule_id,
        )
        if (
            self.request_id != self.source_request.id
            or self.rule_id != self.source_request.rule_id
            or self.near_miss_eligible != expected_eligible
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Wound lifecycle roll result has stale provenance")


@dataclass(frozen=True, slots=True)
class CharacterWoundLifecycleCompletionRequest:
    id: str
    roll: CharacterWoundLifecycleRollResult
    current_state: CharacterInjuryState
    daily_wounds: DailyWoundState
    daily_registration_id: str | None = None
    near_miss: FateNearMissBurnRequest | None = None
    consumed_roll_ids: tuple[str, ...] = ()
    consumed_near_miss_effect_ids: tuple[str, ...] = ()
    rule_id: str = CHARACTER_WOUND_LIFECYCLE_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Wound lifecycle completion id")
        if not isinstance(self.roll, CharacterWoundLifecycleRollResult):
            raise TypeError("roll must be a Wound lifecycle roll result")
        if not isinstance(self.current_state, CharacterInjuryState):
            raise TypeError("current_state must be a CharacterInjuryState")
        if not isinstance(self.daily_wounds, DailyWoundState):
            raise TypeError("daily_wounds must be a DailyWoundState")
        if self.near_miss is not None and not isinstance(
            self.near_miss,
            FateNearMissBurnRequest,
        ):
            raise TypeError("near_miss must be a FateNearMissBurnRequest or None")
        _validate_non_empty_string(
            self.rule_id,
            "Wound lifecycle completion rule_id",
        )
        consumed_rolls = _validate_consumed_ids(
            self.consumed_roll_ids,
            "consumed Wound lifecycle roll ID",
        )
        consumed_effects = _validate_consumed_ids(
            self.consumed_near_miss_effect_ids,
            "consumed Near Miss effect ID",
        )
        if self.roll.request_id in consumed_rolls:
            raise ValueError("Wound lifecycle roll was already consumed")
        pending_state = self.roll.wound_result.state
        if (
            self.current_state.wounds != pending_state.wounds
            or self.current_state.active_wound_effects
            != pending_state.active_wound_effects
            or self.current_state.dead != pending_state.dead
        ):
            raise ValueError("Wound lifecycle current injury state is stale")
        target_id = self.roll.source_request.target_id
        if self.daily_wounds.target_id != target_id:
            raise ValueError("daily Wound state belongs to another target")

        accepted = self.roll.wound_result.wound_accepted
        if not accepted:
            if self.near_miss is not None:
                raise ValueError("Near Miss requires an accepted Wound")
            if self.daily_registration_id is not None:
                raise ValueError("a negated Wound must not be registered")
        elif self.near_miss is None:
            _validate_non_empty_string(
                self.daily_registration_id,
                "daily Wound registration id",
            )
        else:
            if not self.roll.near_miss_eligible:
                raise ValueError("only a player character can use Near Miss")
            if self.daily_registration_id is not None:
                raise ValueError("a Near Miss Wound must not be registered")
            if self.near_miss.state.actor_id != target_id:
                raise ValueError("Near Miss belongs to another actor")
            if (
                self.near_miss.wound_negation.resolution_id
                != self.roll.source_request.wound.id
                or self.near_miss.wound_negation.rule_id
                != FATE_NEAR_MISS_RULE_ID
            ):
                raise ValueError("Near Miss belongs to another Wound resolution")
        object.__setattr__(self, "consumed_roll_ids", consumed_rolls)
        object.__setattr__(
            self,
            "consumed_near_miss_effect_ids",
            consumed_effects,
        )


@dataclass(frozen=True, slots=True)
class CharacterWoundLifecycleCompletionResult:
    request_id: str
    rule_id: str
    source_request: CharacterWoundLifecycleCompletionRequest
    outcome: CharacterWoundLifecycleOutcome
    wound_result: CharacterWoundResult
    fate_burn: FateBurnResult | None
    near_miss_application: FateNearMissApplicationResult | None
    daily_registration: DailyWoundRegistrationResult | None
    wound_effect: WoundEffectResult | None
    previous_state: CharacterInjuryState
    state: CharacterInjuryState
    previous_daily_wounds: DailyWoundState
    daily_wounds: DailyWoundState
    previous_consumed_roll_ids: tuple[str, ...]
    consumed_roll_ids: tuple[str, ...]
    previous_consumed_near_miss_effect_ids: tuple[str, ...]
    consumed_near_miss_effect_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Wound lifecycle completion result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "Wound lifecycle completion result rule_id",
        )
        if not isinstance(
            self.source_request,
            CharacterWoundLifecycleCompletionRequest,
        ):
            raise TypeError("source_request must be a completion request")
        if not isinstance(self.outcome, CharacterWoundLifecycleOutcome):
            raise TypeError("outcome must be a CharacterWoundLifecycleOutcome")
        if not isinstance(self.wound_result, CharacterWoundResult):
            raise TypeError("wound_result must be a CharacterWoundResult")
        if self.fate_burn is not None and not isinstance(
            self.fate_burn,
            FateBurnResult,
        ):
            raise TypeError("fate_burn must be a FateBurnResult or None")
        if self.near_miss_application is not None and not isinstance(
            self.near_miss_application,
            FateNearMissApplicationResult,
        ):
            raise TypeError(
                "near_miss_application must be a Near Miss result or None"
            )
        if self.daily_registration is not None and not isinstance(
            self.daily_registration,
            DailyWoundRegistrationResult,
        ):
            raise TypeError(
                "daily_registration must be a registration result or None"
            )
        if self.wound_effect is not None and not isinstance(
            self.wound_effect,
            WoundEffectResult,
        ):
            raise TypeError("wound_effect must be a WoundEffectResult or None")
        if not isinstance(self.previous_state, CharacterInjuryState):
            raise TypeError("previous_state must be a CharacterInjuryState")
        if not isinstance(self.state, CharacterInjuryState):
            raise TypeError("state must be a CharacterInjuryState")
        if not isinstance(self.previous_daily_wounds, DailyWoundState):
            raise TypeError("previous_daily_wounds must be a DailyWoundState")
        if not isinstance(self.daily_wounds, DailyWoundState):
            raise TypeError("daily_wounds must be a DailyWoundState")

        source = self.source_request
        previous_rolls = _validate_consumed_ids(
            self.previous_consumed_roll_ids,
            "previous consumed Wound lifecycle roll ID",
        )
        consumed_rolls = _validate_consumed_ids(
            self.consumed_roll_ids,
            "consumed Wound lifecycle roll ID",
        )
        previous_effects = _validate_consumed_ids(
            self.previous_consumed_near_miss_effect_ids,
            "previous consumed Near Miss effect ID",
        )
        consumed_effects = _validate_consumed_ids(
            self.consumed_near_miss_effect_ids,
            "consumed Near Miss effect ID",
        )
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.wound_result != source.roll.wound_result
            or self.previous_state != source.current_state
            or self.previous_daily_wounds != source.daily_wounds
            or previous_rolls != source.consumed_roll_ids
            or consumed_rolls
            != (*source.consumed_roll_ids, source.roll.request_id)
            or previous_effects != source.consumed_near_miss_effect_ids
        ):
            raise ValueError("Wound lifecycle completion has stale provenance")

        if self.outcome is CharacterWoundLifecycleOutcome.NEAR_MISS:
            self._validate_near_miss_branch(source, consumed_effects)
        elif self.outcome is CharacterWoundLifecycleOutcome.ACCEPTED:
            self._validate_accepted_branch(source, consumed_effects)
        else:
            self._validate_negated_branch(source, consumed_effects)

        expected_rules = _completion_rule_ids(
            source,
            self.fate_burn,
            self.near_miss_application,
            self.daily_registration,
            self.wound_effect,
        )
        if self.applied_rule_ids != expected_rules:
            raise ValueError("Wound lifecycle completion trace is incomplete")
        object.__setattr__(self, "previous_consumed_roll_ids", previous_rolls)
        object.__setattr__(self, "consumed_roll_ids", consumed_rolls)
        object.__setattr__(
            self,
            "previous_consumed_near_miss_effect_ids",
            previous_effects,
        )
        object.__setattr__(
            self,
            "consumed_near_miss_effect_ids",
            consumed_effects,
        )

    def _validate_near_miss_branch(
        self,
        source: CharacterWoundLifecycleCompletionRequest,
        consumed_effects: tuple[str, ...],
    ) -> None:
        if (
            source.near_miss is None
            or self.fate_burn is None
            or self.near_miss_application is None
            or self.daily_registration is not None
            or self.wound_effect is not None
            or self.fate_burn.source_request != source.near_miss
            or self.near_miss_application.source_request.burn
            != self.fate_burn
            or self.near_miss_application.source_request.wound_request
            != source.roll.source_request.wound
            or self.near_miss_application.source_request.wound_result
            != source.roll.wound_result
            or self.near_miss_application.source_request.consumed_effect_ids
            != source.consumed_near_miss_effect_ids
            or self.state != _state_after_near_miss(source)
            or self.daily_wounds != source.daily_wounds
            or consumed_effects
            != self.near_miss_application.consumed_effect_ids
        ):
            raise ValueError("Wound lifecycle Near Miss branch is stale")

    def _validate_accepted_branch(
        self,
        source: CharacterWoundLifecycleCompletionRequest,
        consumed_effects: tuple[str, ...],
    ) -> None:
        effect_request = source.roll.wound_result.effect_request
        if (
            source.near_miss is not None
            or not source.roll.wound_result.wound_accepted
            or self.fate_burn is not None
            or self.near_miss_application is not None
            or self.daily_registration is None
            or self.wound_effect is None
            or self.daily_registration.source_request.source
            != source.roll.wound_result
            or self.daily_registration.source_request.state
            != source.daily_wounds
            or self.daily_registration.source_request.id
            != source.daily_registration_id
            or self.wound_effect.request != effect_request
            or self.state != self.wound_effect.state
            or self.daily_wounds != self.daily_registration.state
            or consumed_effects != source.consumed_near_miss_effect_ids
        ):
            raise ValueError("Wound lifecycle accepted branch is stale")

    def _validate_negated_branch(
        self,
        source: CharacterWoundLifecycleCompletionRequest,
        consumed_effects: tuple[str, ...],
    ) -> None:
        if (
            source.roll.wound_result.wound_accepted
            or source.near_miss is not None
            or self.fate_burn is not None
            or self.near_miss_application is not None
            or self.daily_registration is not None
            or self.wound_effect is not None
            or self.state != source.current_state
            or self.daily_wounds != source.daily_wounds
            or consumed_effects != source.consumed_near_miss_effect_ids
        ):
            raise ValueError("Wound lifecycle negated branch is stale")


@dataclass(frozen=True, slots=True)
class FixedCharacterWoundLifecycleRequest:
    id: str
    target_id: str
    wound: FixedCharacterWoundRequest
    rule_id: str = FIXED_CHARACTER_WOUND_LIFECYCLE_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "fixed Wound lifecycle id")
        _validate_non_empty_string(
            self.target_id,
            "fixed Wound lifecycle target_id",
        )
        if not isinstance(self.wound, FixedCharacterWoundRequest):
            raise TypeError("wound must be a FixedCharacterWoundRequest")
        _validate_non_empty_string(
            self.rule_id,
            "fixed Wound lifecycle rule_id",
        )


@dataclass(frozen=True, slots=True)
class FixedCharacterWoundLifecyclePendingResult:
    request_id: str
    rule_id: str
    source_request: FixedCharacterWoundLifecycleRequest
    wound_result: FixedCharacterWoundResult
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "fixed Wound lifecycle result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "fixed Wound lifecycle result rule_id",
        )
        if not isinstance(
            self.source_request,
            FixedCharacterWoundLifecycleRequest,
        ):
            raise TypeError("source_request must be a fixed lifecycle request")
        if not isinstance(self.wound_result, FixedCharacterWoundResult):
            raise TypeError("wound_result must be a FixedCharacterWoundResult")
        validate_fixed_character_wound_result_provenance(
            self.source_request.wound,
            self.wound_result,
        )
        expected_rules = _ordered_rule_ids(
            *self.wound_result.applied_rule_ids,
            self.source_request.rule_id,
        )
        if (
            self.request_id != self.source_request.id
            or self.rule_id != self.source_request.rule_id
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("fixed Wound lifecycle result has stale provenance")


@dataclass(frozen=True, slots=True)
class FixedCharacterWoundLifecycleCompletionRequest:
    id: str
    pending: FixedCharacterWoundLifecyclePendingResult
    current_state: CharacterInjuryState
    daily_wounds: DailyWoundState
    daily_registration_id: str
    consumed_pending_ids: tuple[str, ...] = ()
    rule_id: str = FIXED_CHARACTER_WOUND_LIFECYCLE_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.id,
            "fixed Wound lifecycle completion id",
        )
        if not isinstance(
            self.pending,
            FixedCharacterWoundLifecyclePendingResult,
        ):
            raise TypeError("pending must be a fixed Wound lifecycle result")
        if not isinstance(self.current_state, CharacterInjuryState):
            raise TypeError("current_state must be a CharacterInjuryState")
        if not isinstance(self.daily_wounds, DailyWoundState):
            raise TypeError("daily_wounds must be a DailyWoundState")
        _validate_non_empty_string(
            self.daily_registration_id,
            "fixed Wound daily registration id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "fixed Wound lifecycle completion rule_id",
        )
        consumed = _validate_consumed_ids(
            self.consumed_pending_ids,
            "consumed fixed Wound pending ID",
        )
        if self.pending.request_id in consumed:
            raise ValueError("fixed Wound pending result was already consumed")
        pending_state = self.pending.wound_result.state
        if (
            self.current_state.wounds != pending_state.wounds
            or self.current_state.active_wound_effects
            != pending_state.active_wound_effects
            or self.current_state.dead != pending_state.dead
        ):
            raise ValueError("fixed Wound lifecycle current injury state is stale")
        if (
            self.daily_wounds.target_id
            != self.pending.source_request.target_id
        ):
            raise ValueError("daily Wound state belongs to another target")
        object.__setattr__(self, "consumed_pending_ids", consumed)


@dataclass(frozen=True, slots=True)
class FixedCharacterWoundLifecycleCompletionResult:
    request_id: str
    rule_id: str
    source_request: FixedCharacterWoundLifecycleCompletionRequest
    wound_result: FixedCharacterWoundResult
    daily_registration: DailyWoundRegistrationResult
    wound_effect: WoundEffectResult
    previous_state: CharacterInjuryState
    state: CharacterInjuryState
    previous_daily_wounds: DailyWoundState
    daily_wounds: DailyWoundState
    previous_consumed_pending_ids: tuple[str, ...]
    consumed_pending_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "fixed Wound completion result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "fixed Wound completion result rule_id",
        )
        if not isinstance(
            self.source_request,
            FixedCharacterWoundLifecycleCompletionRequest,
        ):
            raise TypeError("source_request must be a fixed completion request")
        if not isinstance(self.wound_result, FixedCharacterWoundResult):
            raise TypeError("wound_result must be a FixedCharacterWoundResult")
        if not isinstance(
            self.daily_registration,
            DailyWoundRegistrationResult,
        ):
            raise TypeError("daily_registration must be a registration result")
        if not isinstance(self.wound_effect, WoundEffectResult):
            raise TypeError("wound_effect must be a WoundEffectResult")
        if not isinstance(self.previous_state, CharacterInjuryState):
            raise TypeError("previous_state must be a CharacterInjuryState")
        if not isinstance(self.state, CharacterInjuryState):
            raise TypeError("state must be a CharacterInjuryState")
        if not isinstance(self.previous_daily_wounds, DailyWoundState):
            raise TypeError("previous_daily_wounds must be a DailyWoundState")
        if not isinstance(self.daily_wounds, DailyWoundState):
            raise TypeError("daily_wounds must be a DailyWoundState")

        source = self.source_request
        previous_consumed = _validate_consumed_ids(
            self.previous_consumed_pending_ids,
            "previous consumed fixed Wound pending ID",
        )
        consumed = _validate_consumed_ids(
            self.consumed_pending_ids,
            "consumed fixed Wound pending ID",
        )
        registration_source = self.daily_registration.source_request
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.wound_result != source.pending.wound_result
            or self.previous_state != source.current_state
            or self.previous_daily_wounds != source.daily_wounds
            or previous_consumed != source.consumed_pending_ids
            or consumed
            != (*source.consumed_pending_ids, source.pending.request_id)
            or registration_source.id != source.daily_registration_id
            or registration_source.state != source.daily_wounds
            or registration_source.target_id
            != source.pending.source_request.target_id
            or registration_source.source != source.pending.wound_result
            or self.daily_wounds != self.daily_registration.state
            or self.wound_effect.request
            != source.pending.wound_result.effect_request
            or self.state != self.wound_effect.state
        ):
            raise ValueError("fixed Wound lifecycle completion is stale")
        expected_rules = _ordered_rule_ids(
            *source.pending.applied_rule_ids,
            *self.daily_registration.applied_rule_ids,
            *self.wound_effect.applied_rule_ids,
            source.rule_id,
        )
        if self.applied_rule_ids != expected_rules:
            raise ValueError("fixed Wound lifecycle trace is incomplete")
        object.__setattr__(
            self,
            "previous_consumed_pending_ids",
            previous_consumed,
        )
        object.__setattr__(self, "consumed_pending_ids", consumed)


def _completion_rule_ids(
    request: CharacterWoundLifecycleCompletionRequest,
    fate_burn: FateBurnResult | None,
    near_miss: FateNearMissApplicationResult | None,
    registration: DailyWoundRegistrationResult | None,
    effect: WoundEffectResult | None,
) -> tuple[str, ...]:
    return _ordered_rule_ids(
        *request.roll.applied_rule_ids,
        *(fate_burn.applied_rule_ids if fate_burn is not None else ()),
        *(near_miss.applied_rule_ids if near_miss is not None else ()),
        *(registration.applied_rule_ids if registration is not None else ()),
        *(effect.applied_rule_ids if effect is not None else ()),
        request.rule_id,
    )


def _state_after_near_miss(
    request: CharacterWoundLifecycleCompletionRequest,
) -> CharacterInjuryState:
    """Restore the pre-Wound injury while preserving later Condition changes."""
    pending_conditions = request.roll.wound_result.state.conditions.conditions
    current_conditions = request.current_state.conditions.conditions
    source_conditions = (
        request.roll.source_request.wound.state.conditions.conditions
    )
    added = current_conditions - pending_conditions
    removed = pending_conditions - current_conditions
    return CharacterInjuryState(
        wounds=request.roll.source_request.wound.state.wounds,
        conditions=type(request.current_state.conditions)(
            (source_conditions - removed) | added
        ),
        active_wound_effects=(
            request.roll.source_request.wound.state.active_wound_effects
        ),
        dead=request.roll.source_request.wound.state.dead,
    )


def _ordered_rule_ids(*values: str) -> tuple[str, ...]:
    rules = tuple(dict.fromkeys(values))
    for value in rules:
        _validate_non_empty_string(value, "applied Rule ID")
    return rules


def _validate_consumed_ids(
    values: tuple[str, ...],
    name: str,
) -> tuple[str, ...]:
    items = tuple(values)
    for value in items:
        _validate_non_empty_string(value, name)
    if len(set(items)) != len(items):
        raise ValueError(f"{name}s must be unique")
    return items


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")


def _validate_non_empty_string(value: str | None, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
