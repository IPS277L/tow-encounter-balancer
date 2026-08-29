from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from towr.domain.injury_models import CharacterInjuryState, DecisionOwner
from towr.domain.test_models import Skill, TestRequest, TestResult


DOWNTIME_SURGERY_RULE_ID = "RULE-HEALTH-010:downtime-surgery"
SURGERY_FAILURE_RISK_RULE_ID = "RULE-HEALTH-010:surgery-failure-risk"


class SurgeryFailureRisk(str, Enum):
    PERMANENT_DISFIGUREMENT = "permanent_disfigurement"
    DEATH = "death"


@dataclass(frozen=True, slots=True)
class DowntimeSurgeryRequest:
    id: str
    downtime_id: str
    surgeon_id: str
    target_id: str
    injury_state: CharacterInjuryState
    wound_sequence: int
    dexterity_test: TestRequest
    surgeon_has_anatomy_lore: bool
    has_operating_theatre: bool
    has_specialist_medical_tools: bool
    has_time_to_work: bool
    has_recovery_supports: bool
    skill: Skill = Skill.DEXTERITY
    rule_id: str = DOWNTIME_SURGERY_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "surgery request id")
        _validate_non_empty_string(self.downtime_id, "downtime_id")
        _validate_non_empty_string(self.surgeon_id, "surgeon_id")
        _validate_non_empty_string(self.target_id, "surgery target_id")
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("injury_state must be a CharacterInjuryState")
        _validate_positive_int(self.wound_sequence, "wound_sequence")
        if not isinstance(self.dexterity_test, TestRequest):
            raise TypeError("dexterity_test must be a TestRequest")
        for value, name in (
            (self.surgeon_has_anatomy_lore, "surgeon_has_anatomy_lore"),
            (self.has_operating_theatre, "has_operating_theatre"),
            (
                self.has_specialist_medical_tools,
                "has_specialist_medical_tools",
            ),
            (self.has_time_to_work, "has_time_to_work"),
            (self.has_recovery_supports, "has_recovery_supports"),
        ):
            _validate_bool(value, name)
        if not isinstance(self.skill, Skill):
            raise TypeError("skill must be a Skill")
        _validate_non_empty_string(self.rule_id, "surgery rule_id")

        if self.injury_state.dead:
            raise ValueError("a dead character cannot undergo surgery")
        if self.skill is not Skill.DEXTERITY:
            raise ValueError("downtime surgery requires a Dexterity Test")
        if not self.surgeon_has_anatomy_lore:
            raise ValueError("downtime surgery requires Anatomy Lore")
        if not self.has_operating_theatre:
            raise ValueError("downtime surgery requires an operating theatre")
        if not self.has_specialist_medical_tools:
            raise ValueError("downtime surgery requires specialist medical tools")
        if not self.has_time_to_work:
            raise ValueError("downtime surgery requires time to work")
        if not self.has_recovery_supports:
            raise ValueError(
                "downtime surgery requires crutches or prosthetic supports"
            )

        wounds_by_sequence = {
            wound.sequence: wound for wound in self.injury_state.wounds
        }
        if self.wound_sequence not in wounds_by_sequence:
            raise ValueError("surgery references an unknown Wound")
        wound = wounds_by_sequence[self.wound_sequence]
        if wound.healed:
            raise ValueError("surgery requires a Wound that is not healed")
        if not wound.treated:
            raise ValueError("surgery requires a treated Wound")
        if not wound.effect_resolved:
            raise ValueError("surgery requires a resolved Wound effect")


@dataclass(frozen=True, slots=True)
class SurgeryFailureRiskRequest:
    id: str
    source_surgery_id: str
    source_test_id: str
    surgeon_id: str
    target_id: str
    wound_sequence: int
    possible_risks: tuple[SurgeryFailureRisk, ...] = (
        SurgeryFailureRisk.PERMANENT_DISFIGUREMENT,
        SurgeryFailureRisk.DEATH,
    )
    decision_owner: DecisionOwner = DecisionOwner.GM
    rule_id: str = SURGERY_FAILURE_RISK_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "surgery failure risk id")
        _validate_non_empty_string(
            self.source_surgery_id,
            "source_surgery_id",
        )
        _validate_non_empty_string(self.source_test_id, "source_test_id")
        _validate_non_empty_string(self.surgeon_id, "surgeon_id")
        _validate_non_empty_string(self.target_id, "surgery target_id")
        _validate_positive_int(self.wound_sequence, "wound_sequence")
        risks = tuple(self.possible_risks)
        if risks != (
            SurgeryFailureRisk.PERMANENT_DISFIGUREMENT,
            SurgeryFailureRisk.DEATH,
        ):
            raise ValueError(
                "surgery failure must expose both book-defined risks"
            )
        object.__setattr__(self, "possible_risks", risks)
        if self.decision_owner is not DecisionOwner.GM:
            raise ValueError("the GM resolves surgery failure risk")
        _validate_non_empty_string(self.rule_id, "surgery failure rule_id")


@dataclass(frozen=True, slots=True)
class DowntimeSurgeryResult:
    request_id: str
    rule_id: str
    source_request: DowntimeSurgeryRequest
    test_result: TestResult
    succeeded: bool
    previous_state: CharacterInjuryState
    state: CharacterInjuryState
    failure_risk: SurgeryFailureRiskRequest | None
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "surgery result request_id")
        _validate_non_empty_string(self.rule_id, "surgery result rule_id")
        if not isinstance(self.source_request, DowntimeSurgeryRequest):
            raise TypeError("source_request must be a surgery request")
        if not isinstance(self.test_result, TestResult):
            raise TypeError("test_result must be a TestResult")
        _validate_bool(self.succeeded, "succeeded")
        if not isinstance(self.previous_state, CharacterInjuryState):
            raise TypeError("previous_state must be a CharacterInjuryState")
        if not isinstance(self.state, CharacterInjuryState):
            raise TypeError("state must be a CharacterInjuryState")
        if self.failure_risk is not None and not isinstance(
            self.failure_risk,
            SurgeryFailureRiskRequest,
        ):
            raise TypeError("failure_risk must be a request or None")

        source = self.source_request
        if self.request_id != source.id or self.rule_id != source.rule_id:
            raise ValueError("surgery result has stale provenance")
        if self.test_result.trace.request_id != source.dexterity_test.id:
            raise ValueError("surgery Test result has stale provenance")
        if self.succeeded != self.test_result.succeeded:
            raise ValueError("surgery outcome disagrees with its Test")
        if (
            self.previous_state != source.injury_state
            or self.state != source.injury_state
        ):
            raise ValueError("surgery proof must not mutate injury state")
        if self.succeeded == (self.failure_risk is not None):
            raise ValueError(
                "only failed surgery creates a failure-risk request"
            )
        risk = self.failure_risk
        if risk is not None and (
            risk.rule_id != SURGERY_FAILURE_RISK_RULE_ID
            or risk.source_surgery_id != source.id
            or risk.source_test_id != source.dexterity_test.id
            or risk.surgeon_id != source.surgeon_id
            or risk.target_id != source.target_id
            or risk.wound_sequence != source.wound_sequence
        ):
            raise ValueError("surgery failure risk has stale provenance")

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            *self.test_result.trace.applied_rule_ids,
        }
        if risk is not None:
            required.add(risk.rule_id)
        if not required <= set(rule_ids):
            raise ValueError("surgery rule trace is incomplete")
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


def _validate_positive_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value < 1:
        raise ValueError(f"{name} must be positive")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")
