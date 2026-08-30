from __future__ import annotations

from dataclasses import dataclass, field, replace

from towr.domain.festering_wound_models import (
    FESTERING_WOUND_RULE_ID,
    FesteringWoundRecord,
    FesteringWoundState,
)
from towr.domain.injury_models import (
    CharacterInjuryState,
    CharacterWoundResult,
    FixedCharacterWoundResult,
    WoundRecord,
    WoundRecordOrigin,
)
from towr.domain.test_models import Skill, TestRequest, TestResult


DAILY_WOUND_REGISTRATION_RULE_ID = (
    "RULE-HEALTH-009:daily-wound-registration"
)
END_OF_DAY_INFECTION_RULE_ID = "RULE-HEALTH-009:end-of-day-infection"


CharacterWoundSourceResult = CharacterWoundResult | FixedCharacterWoundResult


@dataclass(frozen=True, slots=True)
class DailyWoundReceipt:
    id: str
    day_id: str
    target_id: str
    source_request_id: str
    wound: WoundRecord

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "daily Wound receipt id")
        _validate_non_empty_string(self.day_id, "receipt day_id")
        _validate_non_empty_string(self.target_id, "receipt target_id")
        _validate_non_empty_string(
            self.source_request_id,
            "receipt source_request_id",
        )
        if not isinstance(self.wound, WoundRecord):
            raise TypeError("receipt wound must be a WoundRecord")
        if self.wound.treated or self.wound.healed:
            raise ValueError("a new daily Wound receipt must be untreated")
        if self.wound.effect_resolved:
            raise ValueError(
                "a new daily Wound receipt precedes effect resolution"
            )


@dataclass(frozen=True, slots=True)
class DailyWoundState:
    day_id: str
    target_id: str
    receipts: tuple[DailyWoundReceipt, ...] = field(default_factory=tuple)
    closed_by_infection_id: str | None = None

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.day_id, "daily Wound day_id")
        _validate_non_empty_string(self.target_id, "daily Wound target_id")
        receipts = tuple(self.receipts)
        if not all(isinstance(item, DailyWoundReceipt) for item in receipts):
            raise TypeError("receipts must contain DailyWoundReceipt values")
        if any(item.day_id != self.day_id for item in receipts):
            raise ValueError("daily Wound receipt belongs to another day")
        if any(item.target_id != self.target_id for item in receipts):
            raise ValueError("daily Wound receipt belongs to another target")
        _validate_unique((item.id for item in receipts), "daily receipt IDs")
        _validate_unique(
            (item.source_request_id for item in receipts),
            "daily Wound source request IDs",
        )
        _validate_unique(
            (item.wound.sequence for item in receipts),
            "daily Wound sequences",
        )
        if self.closed_by_infection_id is not None:
            _validate_non_empty_string(
                self.closed_by_infection_id,
                "closed_by_infection_id",
            )
        object.__setattr__(self, "receipts", receipts)

    @property
    def wound_count(self) -> int:
        return len(self.receipts)

    @property
    def is_closed(self) -> bool:
        return self.closed_by_infection_id is not None


@dataclass(frozen=True, slots=True)
class DailyWoundRegistrationRequest:
    id: str
    state: DailyWoundState
    target_id: str
    source: CharacterWoundSourceResult
    rule_id: str = DAILY_WOUND_REGISTRATION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "daily Wound registration id")
        if not isinstance(self.state, DailyWoundState):
            raise TypeError("state must be a DailyWoundState")
        _validate_non_empty_string(self.target_id, "registration target_id")
        if not isinstance(
            self.source,
            (CharacterWoundResult, FixedCharacterWoundResult),
        ):
            raise TypeError("source must be a character Wound result")
        _validate_non_empty_string(self.rule_id, "registration rule_id")
        if self.state.is_closed:
            raise ValueError("daily Wound state is already closed")
        if self.target_id != self.state.target_id:
            raise ValueError("daily Wound registration belongs to another target")
        if self.source.request_id in {
            item.source_request_id for item in self.state.receipts
        }:
            raise ValueError("character Wound result was already registered")
        wound = _source_wound(self.source)
        if wound.sequence in {
            item.wound.sequence for item in self.state.receipts
        }:
            raise ValueError("daily Wound sequence was already registered")


@dataclass(frozen=True, slots=True)
class DailyWoundRegistrationResult:
    request_id: str
    rule_id: str
    source_request: DailyWoundRegistrationRequest
    receipt: DailyWoundReceipt
    previous_state: DailyWoundState
    state: DailyWoundState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "daily Wound registration result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "daily Wound registration result rule_id",
        )
        if not isinstance(self.source_request, DailyWoundRegistrationRequest):
            raise TypeError("source_request must be a registration request")
        if not isinstance(self.receipt, DailyWoundReceipt):
            raise TypeError("receipt must be a DailyWoundReceipt")
        if not isinstance(self.previous_state, DailyWoundState):
            raise TypeError("previous_state must be a DailyWoundState")
        if not isinstance(self.state, DailyWoundState):
            raise TypeError("state must be a DailyWoundState")

        source = self.source_request
        expected_receipt = _registration_receipt(source)
        expected_state = replace(
            source.state,
            receipts=(*source.state.receipts, expected_receipt),
        )
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.receipt != expected_receipt
            or self.previous_state != source.state
            or self.state != expected_state
        ):
            raise ValueError("daily Wound registration has stale provenance")
        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {self.rule_id, *source.source.applied_rule_ids}
        if not required <= set(rule_ids):
            raise ValueError("daily Wound registration trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


@dataclass(frozen=True, slots=True)
class EndOfDayInfectionRequest:
    id: str
    daily_wounds: DailyWoundState
    target_id: str
    injury_state: CharacterInjuryState
    festering_wound_state: FesteringWoundState
    endurance_test: TestRequest
    skill: Skill = Skill.ENDURANCE
    rule_id: str = END_OF_DAY_INFECTION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Infection request id")
        if not isinstance(self.daily_wounds, DailyWoundState):
            raise TypeError("daily_wounds must be a DailyWoundState")
        _validate_non_empty_string(self.target_id, "Infection target_id")
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("injury_state must be a CharacterInjuryState")
        if not isinstance(self.festering_wound_state, FesteringWoundState):
            raise TypeError(
                "festering_wound_state must be a FesteringWoundState"
            )
        if not isinstance(self.endurance_test, TestRequest):
            raise TypeError("endurance_test must be a TestRequest")
        if not isinstance(self.skill, Skill):
            raise TypeError("skill must be a Skill")
        _validate_non_empty_string(self.rule_id, "Infection rule_id")

        if self.daily_wounds.is_closed:
            raise ValueError("daily Infection was already resolved")
        if not self.daily_wounds.receipts:
            raise ValueError("Infection Test requires at least one daily Wound")
        if (
            self.target_id != self.daily_wounds.target_id
            or self.target_id != self.festering_wound_state.target_id
        ):
            raise ValueError("Infection context belongs to another target")
        if self.injury_state.dead:
            raise ValueError("a dead character cannot make an Infection Test")
        if self.skill is not Skill.ENDURANCE:
            raise ValueError("Infection requires an Endurance Test")
        if self.id in {
            item.source_infection_id
            for item in self.festering_wound_state.wounds
        }:
            raise ValueError("Infection result was already applied")
        _validate_current_wound_history(
            self.injury_state,
            self.daily_wounds.receipts,
        )


@dataclass(frozen=True, slots=True)
class EndOfDayInfectionResult:
    request_id: str
    rule_id: str
    source_request: EndOfDayInfectionRequest
    test_result: TestResult
    wound_count: int
    avoided_infection: bool
    added_festering_wound: FesteringWoundRecord | None
    previous_daily_wounds: DailyWoundState
    daily_wounds: DailyWoundState
    previous_festering_wound_state: FesteringWoundState
    festering_wound_state: FesteringWoundState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Infection result request_id",
        )
        _validate_non_empty_string(self.rule_id, "Infection result rule_id")
        if not isinstance(self.source_request, EndOfDayInfectionRequest):
            raise TypeError("source_request must be an Infection request")
        if not isinstance(self.test_result, TestResult):
            raise TypeError("test_result must be a TestResult")
        _validate_positive_int(self.wound_count, "Infection wound_count")
        _validate_bool(self.avoided_infection, "avoided_infection")
        if (
            self.added_festering_wound is not None
            and not isinstance(self.added_festering_wound, FesteringWoundRecord)
        ):
            raise TypeError(
                "added_festering_wound must be a FesteringWoundRecord or None"
            )
        if not isinstance(self.previous_daily_wounds, DailyWoundState):
            raise TypeError("previous_daily_wounds must be a DailyWoundState")
        if not isinstance(self.daily_wounds, DailyWoundState):
            raise TypeError("daily_wounds must be a DailyWoundState")
        if not isinstance(
            self.previous_festering_wound_state,
            FesteringWoundState,
        ):
            raise TypeError(
                "previous_festering_wound_state must be a FesteringWoundState"
            )
        if not isinstance(self.festering_wound_state, FesteringWoundState):
            raise TypeError("festering_wound_state must be a FesteringWoundState")

        source = self.source_request
        expected_avoided = self.test_result.successes >= source.daily_wounds.wound_count
        expected_added = _infection_festering_wound(source, expected_avoided)
        expected_festering_state = source.festering_wound_state
        if expected_added is not None:
            expected_festering_state = replace(
                source.festering_wound_state,
                wounds=(
                    *source.festering_wound_state.wounds,
                    expected_added,
                ),
            )
        expected_daily_wounds = replace(
            source.daily_wounds,
            closed_by_infection_id=source.id,
        )
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.test_result.trace.request_id != source.endurance_test.id
            or self.wound_count != source.daily_wounds.wound_count
            or self.avoided_infection != expected_avoided
            or self.added_festering_wound != expected_added
            or self.previous_daily_wounds != source.daily_wounds
            or self.daily_wounds != expected_daily_wounds
            or self.previous_festering_wound_state
            != source.festering_wound_state
            or self.festering_wound_state != expected_festering_state
        ):
            raise ValueError("Infection result has stale provenance")

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {self.rule_id, *self.test_result.trace.applied_rule_ids}
        if expected_added is not None:
            required.add(expected_added.rule_id)
        if not required <= set(rule_ids):
            raise ValueError("Infection rule trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def _source_wound(source: CharacterWoundSourceResult) -> WoundRecord:
    _validate_non_empty_string(source.request_id, "Wound result request_id")
    if not isinstance(source.state, CharacterInjuryState):
        raise TypeError("Wound result state must be a CharacterInjuryState")
    if isinstance(source, CharacterWoundResult):
        if (
            not source.wound_accepted
            or source.negated_by_rule_id is not None
            or source.effect_request is None
        ):
            raise ValueError("daily tracking requires an accepted Wound")
        effect = source.effect_request
        if effect.wound_sequence != len(source.state.wounds):
            raise ValueError("accepted Wound result has stale sequence")
        wound = source.state.wounds[effect.wound_sequence - 1]
        if (
            wound.origin is not WoundRecordOrigin.TABLE_ROLL
            or wound.entry_id is not source.table_roll.entry.id
            or wound.table_total != source.table_roll.total
            or wound.roll_values != source.table_roll.values
            or effect.id != f"{source.request_id}:effect"
            or effect.entry_id is not wound.entry_id
            or effect.rule_id != f"RULE-WOUND-TABLE:{wound.entry_id.value}"
        ):
            raise ValueError("accepted Wound result has stale provenance")
        return wound

    effect = source.effect_request
    if effect.wound_sequence != len(source.state.wounds):
        raise ValueError("fixed Wound result has stale sequence")
    wound = source.state.wounds[effect.wound_sequence - 1]
    if (
        wound.origin is not WoundRecordOrigin.FIXED_ENTRY
        or wound.entry_id is not source.entry.id
        or wound.table_total < source.entry.minimum
        or (
            source.entry.maximum is not None
            and wound.table_total > source.entry.maximum
        )
        or wound.roll_values
        or effect.id != f"{source.request_id}:effect"
        or effect.entry_id is not wound.entry_id
        or effect.rule_id != f"RULE-WOUND-TABLE:{wound.entry_id.value}"
    ):
        raise ValueError("fixed Wound result has stale provenance")
    return wound


def _registration_receipt(
    request: DailyWoundRegistrationRequest,
) -> DailyWoundReceipt:
    return DailyWoundReceipt(
        id=f"{request.id}:receipt",
        day_id=request.state.day_id,
        target_id=request.target_id,
        source_request_id=request.source.request_id,
        wound=_source_wound(request.source),
    )


def _infection_festering_wound(
    request: EndOfDayInfectionRequest,
    avoided_infection: bool,
) -> FesteringWoundRecord | None:
    if avoided_infection:
        return None
    return FesteringWoundRecord(
        id=f"{request.id}:festering-wound",
        source_infection_id=request.id,
        rule_id=FESTERING_WOUND_RULE_ID,
    )


def _validate_current_wound_history(
    state: CharacterInjuryState,
    receipts: tuple[DailyWoundReceipt, ...],
) -> None:
    by_sequence = {item.sequence: item for item in state.wounds}
    for receipt in receipts:
        current = by_sequence.get(receipt.wound.sequence)
        if current is None:
            raise ValueError("daily receipt references an unknown Wound")
        if _wound_identity(current) != _wound_identity(receipt.wound):
            raise ValueError("daily receipt belongs to another Wound identity")


def _wound_identity(wound: WoundRecord) -> tuple[object, ...]:
    return (
        wound.sequence,
        wound.entry_id,
        wound.table_total,
        wound.roll_values,
        wound.origin,
    )


def _validate_rule_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    rule_ids = tuple(values)
    if not rule_ids:
        raise ValueError("applied_rule_ids must not be empty")
    for rule_id in rule_ids:
        _validate_non_empty_string(rule_id, "applied Rule ID")
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("applied_rule_ids must be unique")
    return rule_ids


def _validate_unique(values, name: str) -> None:
    items = tuple(values)
    if len(set(items)) != len(items):
        raise ValueError(f"{name} must be unique")


def _validate_positive_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value < 1:
        raise ValueError(f"{name} must be positive")


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
