from __future__ import annotations

from dataclasses import dataclass, field, replace

from towr.domain.downtime_models import (
    FESTERING_WOUNDS_RECOVERY_RULE_ID,
    REST_AND_RECOVERY_ENDEAVOUR_RULE_ID,
    RestAndRecoveryEndeavourResult,
)
from towr.domain.injury_models import WoundDiceModifier


FESTERING_WOUND_RULE_ID = "RULE-HEALTH-009:festering-wound"
FESTERING_WOUND_DICE_RULE_ID = "RULE-HEALTH-009:untreated-dice"
FESTERING_WOUNDS_RECOVERY_APPLICATION_RULE_ID = (
    "RULE-HEALTH-009:rest-and-recovery-application"
)


@dataclass(frozen=True, slots=True)
class FesteringWoundRecord:
    id: str
    source_infection_id: str
    rule_id: str = FESTERING_WOUND_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Festering Wound id")
        _validate_non_empty_string(
            self.source_infection_id,
            "source_infection_id",
        )
        _validate_non_empty_string(self.rule_id, "Festering Wound rule_id")
        if self.rule_id != FESTERING_WOUND_RULE_ID:
            raise ValueError("Festering Wound requires its canonical rule")


@dataclass(frozen=True, slots=True)
class FesteringWoundState:
    target_id: str
    wounds: tuple[FesteringWoundRecord, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.target_id, "Festering Wound target_id")
        wounds = tuple(self.wounds)
        if not all(isinstance(item, FesteringWoundRecord) for item in wounds):
            raise TypeError(
                "wounds must contain FesteringWoundRecord values"
            )
        _validate_unique((item.id for item in wounds), "Festering Wound IDs")
        _validate_unique(
            (item.source_infection_id for item in wounds),
            "source Infection IDs",
        )
        object.__setattr__(self, "wounds", wounds)

    @property
    def active_count(self) -> int:
        return len(self.wounds)

    @property
    def additional_untreated_dice(self) -> int:
        return self.active_count

    @property
    def wound_table_dice_modifiers(self) -> tuple[WoundDiceModifier, ...]:
        if not self.wounds:
            return ()
        return (
            WoundDiceModifier(
                rule_id=FESTERING_WOUND_DICE_RULE_ID,
                amount=self.additional_untreated_dice,
            ),
        )


@dataclass(frozen=True, slots=True)
class FesteringWoundsRecoveryApplicationRequest:
    id: str
    endeavour: RestAndRecoveryEndeavourResult
    target_id: str
    state: FesteringWoundState
    consumed_source_ids: tuple[str, ...] = field(default_factory=tuple)
    rule_id: str = FESTERING_WOUNDS_RECOVERY_APPLICATION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Festering recovery application id")
        if not isinstance(self.endeavour, RestAndRecoveryEndeavourResult):
            raise TypeError(
                "endeavour must be a Rest and Recovery Endeavour result"
            )
        _validate_non_empty_string(self.target_id, "recovery target_id")
        if not isinstance(self.state, FesteringWoundState):
            raise TypeError("state must be a FesteringWoundState")
        _validate_non_empty_string(self.rule_id, "recovery application rule_id")

        if (
            self.endeavour.rule_id != REST_AND_RECOVERY_ENDEAVOUR_RULE_ID
            or not self.endeavour.succeeded
        ):
            raise ValueError(
                "Festering recovery requires a successful canonical Endeavour"
            )
        follow_up = self.endeavour.festering_wounds_recovery
        if (
            follow_up is None
            or follow_up.rule_id != FESTERING_WOUNDS_RECOVERY_RULE_ID
        ):
            raise ValueError(
                "Festering recovery requires its canonical follow-up"
            )
        if (
            self.target_id != follow_up.target_id
            or self.target_id != self.endeavour.source_request.target_id
            or self.target_id != self.state.target_id
        ):
            raise ValueError("Festering recovery belongs to another target")

        consumed = _validate_consumed_source_ids(self.consumed_source_ids)
        if follow_up.id in consumed:
            raise ValueError("Festering recovery follow-up was already consumed")
        object.__setattr__(self, "consumed_source_ids", consumed)


@dataclass(frozen=True, slots=True)
class FesteringWoundsRecoveryApplicationResult:
    request_id: str
    rule_id: str
    source_request: FesteringWoundsRecoveryApplicationRequest
    target_id: str
    previous_state: FesteringWoundState
    state: FesteringWoundState
    recovered_wounds: tuple[FesteringWoundRecord, ...]
    previous_consumed_source_ids: tuple[str, ...]
    consumed_source_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Festering recovery result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "Festering recovery result rule_id",
        )
        if not isinstance(
            self.source_request,
            FesteringWoundsRecoveryApplicationRequest,
        ):
            raise TypeError(
                "source_request must be a Festering recovery request"
            )
        _validate_non_empty_string(self.target_id, "recovery result target_id")
        if not isinstance(self.previous_state, FesteringWoundState):
            raise TypeError("previous_state must be a FesteringWoundState")
        if not isinstance(self.state, FesteringWoundState):
            raise TypeError("state must be a FesteringWoundState")
        recovered = tuple(self.recovered_wounds)
        if not all(isinstance(item, FesteringWoundRecord) for item in recovered):
            raise TypeError(
                "recovered_wounds must contain FesteringWoundRecord values"
            )

        source = self.source_request
        follow_up = source.endeavour.festering_wounds_recovery
        assert follow_up is not None
        expected_state = replace(source.state, wounds=())
        expected_consumed = (*source.consumed_source_ids, follow_up.id)
        previous_consumed = _validate_consumed_source_ids(
            self.previous_consumed_source_ids
        )
        consumed = _validate_consumed_source_ids(self.consumed_source_ids)
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.target_id != source.target_id
            or self.previous_state != source.state
            or self.state != expected_state
            or recovered != source.state.wounds
            or previous_consumed != source.consumed_source_ids
            or consumed != expected_consumed
        ):
            raise ValueError("Festering recovery result has stale provenance")
        object.__setattr__(self, "recovered_wounds", recovered)
        object.__setattr__(
            self,
            "previous_consumed_source_ids",
            previous_consumed,
        )
        object.__setattr__(self, "consumed_source_ids", consumed)

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            follow_up.rule_id,
            *source.endeavour.applied_rule_ids,
        }
        if not required <= set(rule_ids):
            raise ValueError("Festering recovery rule trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def _validate_consumed_source_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    items = tuple(values)
    for item in items:
        _validate_non_empty_string(item, "consumed source id")
    if len(set(items)) != len(items):
        raise ValueError("consumed source IDs must be unique")
    return items


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


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
