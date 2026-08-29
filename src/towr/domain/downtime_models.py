from __future__ import annotations

from dataclasses import dataclass

from towr.domain.injury_models import CharacterInjuryState
from towr.domain.test_models import Skill, TestRequest, TestResult


REST_AND_RECOVERY_ENDEAVOUR_RULE_ID = (
    "RULE-DOWNTIME-002:rest-and-recovery"
)
FESTERING_WOUNDS_RECOVERY_RULE_ID = (
    "RULE-HEALTH-009:rest-and-recovery"
)


@dataclass(frozen=True, slots=True)
class RestAndRecoveryEndeavourRequest:
    id: str
    downtime_id: str
    target_id: str
    injury_state: CharacterInjuryState
    endurance_test: TestRequest
    skill: Skill = Skill.ENDURANCE
    rule_id: str = REST_AND_RECOVERY_ENDEAVOUR_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Endeavour request id")
        _validate_non_empty_string(self.downtime_id, "downtime_id")
        _validate_non_empty_string(self.target_id, "Endeavour target_id")
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("injury_state must be a CharacterInjuryState")
        if not isinstance(self.endurance_test, TestRequest):
            raise TypeError("endurance_test must be a TestRequest")
        if not isinstance(self.skill, Skill):
            raise TypeError("skill must be a Skill")
        _validate_non_empty_string(self.rule_id, "Endeavour rule_id")

        if self.skill is not Skill.ENDURANCE:
            raise ValueError("Rest and Recovery requires an Endurance Test")
        if self.injury_state.dead:
            raise ValueError("a dead character cannot undertake recovery")


@dataclass(frozen=True, slots=True)
class FesteringWoundsRecoveryRequest:
    id: str
    target_id: str
    source_endeavour_id: str
    source_test_id: str
    rule_id: str = FESTERING_WOUNDS_RECOVERY_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Festering Wounds request id")
        _validate_non_empty_string(
            self.target_id,
            "Festering Wounds target_id",
        )
        _validate_non_empty_string(
            self.source_endeavour_id,
            "source_endeavour_id",
        )
        _validate_non_empty_string(self.source_test_id, "source_test_id")
        _validate_non_empty_string(self.rule_id, "Festering Wounds rule_id")


@dataclass(frozen=True, slots=True)
class RestAndRecoveryEndeavourResult:
    request_id: str
    rule_id: str
    source_request: RestAndRecoveryEndeavourRequest
    test_result: TestResult
    succeeded: bool
    festering_wounds_recovery: FesteringWoundsRecoveryRequest | None
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Endeavour result request_id")
        _validate_non_empty_string(self.rule_id, "Endeavour result rule_id")
        if not isinstance(
            self.source_request,
            RestAndRecoveryEndeavourRequest,
        ):
            raise TypeError(
                "source_request must be a Rest and Recovery request"
            )
        if not isinstance(self.test_result, TestResult):
            raise TypeError("test_result must be a TestResult")
        _validate_bool(self.succeeded, "succeeded")
        if self.festering_wounds_recovery is not None and not isinstance(
            self.festering_wounds_recovery,
            FesteringWoundsRecoveryRequest,
        ):
            raise TypeError(
                "festering_wounds_recovery must be a request or None"
            )

        source = self.source_request
        if self.request_id != source.id or self.rule_id != source.rule_id:
            raise ValueError("Endeavour result has stale provenance")
        if self.test_result.trace.request_id != source.endurance_test.id:
            raise ValueError("Endeavour Test result has stale provenance")
        if self.succeeded != self.test_result.succeeded:
            raise ValueError("Endeavour outcome disagrees with its Test")

        follow_up = self.festering_wounds_recovery
        if self.succeeded != (follow_up is not None):
            raise ValueError(
                "successful recovery must recover all Festering Wounds"
            )
        if follow_up is not None and (
            follow_up.rule_id != FESTERING_WOUNDS_RECOVERY_RULE_ID
            or follow_up.target_id != source.target_id
            or follow_up.source_endeavour_id != source.id
            or follow_up.source_test_id != source.endurance_test.id
        ):
            raise ValueError("Festering Wounds follow-up has stale provenance")

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            *self.test_result.trace.applied_rule_ids,
        }
        if not required <= set(rule_ids):
            raise ValueError("Endeavour rule trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def _validate_rule_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    rule_ids = tuple(values)
    if not rule_ids:
        raise ValueError("applied_rule_ids must not be empty")
    for rule_id in rule_ids:
        _validate_non_empty_string(rule_id, "applied Rule ID")
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("applied_rule_ids must be unique")
    return rule_ids


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")
