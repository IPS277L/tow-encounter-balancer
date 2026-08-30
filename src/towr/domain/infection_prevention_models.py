from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum

from towr.domain.festering_wound_models import FesteringWoundState
from towr.domain.infection_models import (
    DailyWoundState,
    _validate_current_wound_history,
)
from towr.domain.injury_models import CharacterInjuryState
from towr.domain.test_models import Skill, TestRequest, TestResult


ANATOMY_INFECTION_RECALL_RULE_ID = (
    "RULE-HEALTH-009:anatomy-infection-recall"
)
ANATOMY_INFECTION_ALLOCATION_RULE_ID = (
    "RULE-HEALTH-009:anatomy-infection-allocation"
)
AUTOMATIC_INFECTION_SUCCESS_RULE_ID = (
    "RULE-HEALTH-009:automatic-infection-success"
)
AUTOMATIC_INFECTION_SUCCESS_APPLICATION_RULE_ID = (
    "RULE-HEALTH-009:automatic-infection-success-application"
)


class InfectionPreventionRelationship(str, Enum):
    SELF = "self"
    ALLY = "ally"


@dataclass(frozen=True, slots=True)
class AnatomyInfectionRecallRequest:
    id: str
    day_id: str
    practitioner_id: str
    has_anatomy_lore: bool
    recall_test: TestRequest
    skill: Skill = Skill.RECALL
    rule_id: str = ANATOMY_INFECTION_RECALL_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Anatomy Recall request id")
        _validate_non_empty_string(self.day_id, "Anatomy Recall day_id")
        _validate_non_empty_string(
            self.practitioner_id,
            "Anatomy Recall practitioner_id",
        )
        _validate_bool(self.has_anatomy_lore, "has_anatomy_lore")
        if not isinstance(self.recall_test, TestRequest):
            raise TypeError("recall_test must be a TestRequest")
        if not isinstance(self.skill, Skill):
            raise TypeError("skill must be a Skill")
        _validate_non_empty_string(self.rule_id, "Anatomy Recall rule_id")
        if not self.has_anatomy_lore:
            raise ValueError("Infection prevention requires Anatomy Lore")
        if self.skill is not Skill.RECALL:
            raise ValueError("Infection prevention requires a Recall Test")


@dataclass(frozen=True, slots=True)
class AnatomyInfectionRecallResult:
    request_id: str
    rule_id: str
    source_request: AnatomyInfectionRecallRequest
    test_result: TestResult
    available_successes: int
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Anatomy Recall result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "Anatomy Recall result rule_id",
        )
        if not isinstance(self.source_request, AnatomyInfectionRecallRequest):
            raise TypeError("source_request must be an Anatomy Recall request")
        if not isinstance(self.test_result, TestResult):
            raise TypeError("test_result must be a TestResult")
        _validate_non_negative_int(
            self.available_successes,
            "available_successes",
        )
        source = self.source_request
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.test_result.trace.request_id != source.recall_test.id
            or self.available_successes != self.test_result.successes
        ):
            raise ValueError("Anatomy Recall result has stale provenance")
        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {self.rule_id, *self.test_result.trace.applied_rule_ids}
        if not required <= set(rule_ids):
            raise ValueError("Anatomy Recall rule trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


@dataclass(frozen=True, slots=True)
class InfectionPreventionTarget:
    daily_wounds: DailyWoundState
    relationship: InfectionPreventionRelationship

    def __post_init__(self) -> None:
        if not isinstance(self.daily_wounds, DailyWoundState):
            raise TypeError("daily_wounds must be a DailyWoundState")
        if not isinstance(self.relationship, InfectionPreventionRelationship):
            raise TypeError(
                "relationship must be an InfectionPreventionRelationship"
            )
        if not self.daily_wounds.receipts:
            raise ValueError("prevention target requires daily Wounds")
        if self.daily_wounds.is_closed:
            raise ValueError("prevention target day is already closed")

    @property
    def target_id(self) -> str:
        return self.daily_wounds.target_id


@dataclass(frozen=True, slots=True)
class AutomaticInfectionSuccessProof:
    id: str
    day_id: str
    target_id: str
    practitioner_id: str
    relationship: InfectionPreventionRelationship
    daily_wounds: DailyWoundState
    source_recall_id: str
    source_allocation_id: str
    rule_id: str = AUTOMATIC_INFECTION_SUCCESS_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "automatic Infection proof id")
        _validate_non_empty_string(self.day_id, "proof day_id")
        _validate_non_empty_string(self.target_id, "proof target_id")
        _validate_non_empty_string(
            self.practitioner_id,
            "proof practitioner_id",
        )
        if not isinstance(self.relationship, InfectionPreventionRelationship):
            raise TypeError(
                "relationship must be an InfectionPreventionRelationship"
            )
        if not isinstance(self.daily_wounds, DailyWoundState):
            raise TypeError("daily_wounds must be a DailyWoundState")
        _validate_non_empty_string(
            self.source_recall_id,
            "proof source_recall_id",
        )
        _validate_non_empty_string(
            self.source_allocation_id,
            "proof source_allocation_id",
        )
        _validate_non_empty_string(self.rule_id, "proof rule_id")
        if self.rule_id != AUTOMATIC_INFECTION_SUCCESS_RULE_ID:
            raise ValueError("automatic Infection proof requires canonical rule")
        if (
            self.day_id != self.daily_wounds.day_id
            or self.target_id != self.daily_wounds.target_id
        ):
            raise ValueError("automatic Infection proof has stale target context")
        if not self.daily_wounds.receipts or self.daily_wounds.is_closed:
            raise ValueError("automatic Infection proof requires an open day")
        if self.relationship is InfectionPreventionRelationship.SELF:
            if self.target_id != self.practitioner_id:
                raise ValueError("self prevention must target the practitioner")
        elif self.target_id == self.practitioner_id:
            raise ValueError("ally prevention must target another character")


@dataclass(frozen=True, slots=True)
class AnatomyInfectionAllocationRequest:
    id: str
    recall: AnatomyInfectionRecallResult
    targets: tuple[InfectionPreventionTarget, ...] = field(default_factory=tuple)
    consumed_recall_ids: tuple[str, ...] = field(default_factory=tuple)
    rule_id: str = ANATOMY_INFECTION_ALLOCATION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Infection allocation id")
        if not isinstance(self.recall, AnatomyInfectionRecallResult):
            raise TypeError("recall must be an Anatomy Recall result")
        targets = tuple(self.targets)
        if not all(isinstance(item, InfectionPreventionTarget) for item in targets):
            raise TypeError("targets must contain InfectionPreventionTarget values")
        _validate_non_empty_string(self.rule_id, "Infection allocation rule_id")
        if self.recall.rule_id != ANATOMY_INFECTION_RECALL_RULE_ID:
            raise ValueError("allocation requires canonical Anatomy Recall")
        if len(targets) > self.recall.available_successes:
            raise ValueError("allocation exceeds Anatomy Recall successes")
        if len({item.target_id for item in targets}) != len(targets):
            raise ValueError("Infection prevention targets must be unique")
        source = self.recall.source_request
        for target in targets:
            if target.daily_wounds.day_id != source.day_id:
                raise ValueError("prevention target belongs to another day")
            if target.relationship is InfectionPreventionRelationship.SELF:
                if target.target_id != source.practitioner_id:
                    raise ValueError("self prevention must target practitioner")
            elif target.target_id == source.practitioner_id:
                raise ValueError("ally prevention must target another character")
        consumed = _validate_consumed_ids(
            self.consumed_recall_ids,
            "consumed Recall IDs",
        )
        if self.recall.request_id in consumed:
            raise ValueError("Anatomy Recall was already allocated")
        object.__setattr__(self, "targets", targets)
        object.__setattr__(self, "consumed_recall_ids", consumed)


@dataclass(frozen=True, slots=True)
class AnatomyInfectionAllocationResult:
    request_id: str
    rule_id: str
    source_request: AnatomyInfectionAllocationRequest
    proofs: tuple[AutomaticInfectionSuccessProof, ...]
    allocated_successes: int
    unused_successes: int
    previous_consumed_recall_ids: tuple[str, ...]
    consumed_recall_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Infection allocation result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "Infection allocation result rule_id",
        )
        if not isinstance(self.source_request, AnatomyInfectionAllocationRequest):
            raise TypeError("source_request must be an allocation request")
        proofs = tuple(self.proofs)
        if not all(isinstance(item, AutomaticInfectionSuccessProof) for item in proofs):
            raise TypeError("proofs must contain automatic Infection proofs")
        _validate_non_negative_int(
            self.allocated_successes,
            "allocated_successes",
        )
        _validate_non_negative_int(self.unused_successes, "unused_successes")
        previous_consumed = _validate_consumed_ids(
            self.previous_consumed_recall_ids,
            "previous consumed Recall IDs",
        )
        consumed = _validate_consumed_ids(
            self.consumed_recall_ids,
            "consumed Recall IDs",
        )

        source = self.source_request
        expected_proofs = _allocation_proofs(source)
        expected_consumed = (
            *source.consumed_recall_ids,
            source.recall.request_id,
        )
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or proofs != expected_proofs
            or self.allocated_successes != len(source.targets)
            or self.unused_successes
            != source.recall.available_successes - len(source.targets)
            or previous_consumed != source.consumed_recall_ids
            or consumed != expected_consumed
        ):
            raise ValueError("Infection allocation result has stale provenance")
        object.__setattr__(self, "proofs", proofs)
        object.__setattr__(
            self,
            "previous_consumed_recall_ids",
            previous_consumed,
        )
        object.__setattr__(self, "consumed_recall_ids", consumed)

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {self.rule_id, *source.recall.applied_rule_ids}
        if proofs:
            required.add(AUTOMATIC_INFECTION_SUCCESS_RULE_ID)
        if not required <= set(rule_ids):
            raise ValueError("Infection allocation rule trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


@dataclass(frozen=True, slots=True)
class AutomaticInfectionSuccessApplicationRequest:
    id: str
    allocation: AnatomyInfectionAllocationResult
    proof_id: str
    target_id: str
    daily_wounds: DailyWoundState
    injury_state: CharacterInjuryState
    festering_wound_state: FesteringWoundState
    consumed_proof_ids: tuple[str, ...] = field(default_factory=tuple)
    rule_id: str = AUTOMATIC_INFECTION_SUCCESS_APPLICATION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "automatic success application id")
        if not isinstance(self.allocation, AnatomyInfectionAllocationResult):
            raise TypeError("allocation must be an Infection allocation result")
        _validate_non_empty_string(self.proof_id, "application proof_id")
        _validate_non_empty_string(self.target_id, "application target_id")
        if not isinstance(self.daily_wounds, DailyWoundState):
            raise TypeError("daily_wounds must be a DailyWoundState")
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("injury_state must be a CharacterInjuryState")
        if not isinstance(self.festering_wound_state, FesteringWoundState):
            raise TypeError(
                "festering_wound_state must be a FesteringWoundState"
            )
        _validate_non_empty_string(self.rule_id, "application rule_id")
        if self.allocation.rule_id != ANATOMY_INFECTION_ALLOCATION_RULE_ID:
            raise ValueError("application requires canonical allocation")
        proof = _selected_proof(self.allocation, self.proof_id)
        if (
            self.target_id != proof.target_id
            or self.target_id != self.daily_wounds.target_id
            or self.target_id != self.festering_wound_state.target_id
        ):
            raise ValueError("automatic success belongs to another target")
        if self.daily_wounds != proof.daily_wounds:
            raise ValueError("automatic success uses a stale daily Wound state")
        if self.daily_wounds.is_closed:
            raise ValueError("daily Infection was already resolved")
        if not self.daily_wounds.receipts:
            raise ValueError("automatic success requires daily Wounds")
        if self.injury_state.dead:
            raise ValueError("a dead character cannot avoid Infection")
        _validate_current_wound_history(
            self.injury_state,
            self.daily_wounds.receipts,
        )
        consumed = _validate_consumed_ids(
            self.consumed_proof_ids,
            "consumed proof IDs",
        )
        if proof.id in consumed:
            raise ValueError("automatic Infection proof was already consumed")
        object.__setattr__(self, "consumed_proof_ids", consumed)


@dataclass(frozen=True, slots=True)
class AutomaticInfectionSuccessApplicationResult:
    request_id: str
    rule_id: str
    source_request: AutomaticInfectionSuccessApplicationRequest
    proof: AutomaticInfectionSuccessProof
    target_id: str
    previous_daily_wounds: DailyWoundState
    daily_wounds: DailyWoundState
    injury_state: CharacterInjuryState
    previous_festering_wound_state: FesteringWoundState
    festering_wound_state: FesteringWoundState
    previous_consumed_proof_ids: tuple[str, ...]
    consumed_proof_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "automatic success result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "automatic success result rule_id",
        )
        if not isinstance(
            self.source_request,
            AutomaticInfectionSuccessApplicationRequest,
        ):
            raise TypeError("source_request must be an application request")
        if not isinstance(self.proof, AutomaticInfectionSuccessProof):
            raise TypeError("proof must be an automatic Infection proof")
        _validate_non_empty_string(self.target_id, "result target_id")
        if not isinstance(self.previous_daily_wounds, DailyWoundState):
            raise TypeError("previous_daily_wounds must be a DailyWoundState")
        if not isinstance(self.daily_wounds, DailyWoundState):
            raise TypeError("daily_wounds must be a DailyWoundState")
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("injury_state must be a CharacterInjuryState")
        if not isinstance(
            self.previous_festering_wound_state,
            FesteringWoundState,
        ):
            raise TypeError(
                "previous_festering_wound_state must be a FesteringWoundState"
            )
        if not isinstance(self.festering_wound_state, FesteringWoundState):
            raise TypeError("festering_wound_state must be a FesteringWoundState")
        previous_consumed = _validate_consumed_ids(
            self.previous_consumed_proof_ids,
            "previous consumed proof IDs",
        )
        consumed = _validate_consumed_ids(
            self.consumed_proof_ids,
            "consumed proof IDs",
        )

        source = self.source_request
        expected_proof = _selected_proof(source.allocation, source.proof_id)
        expected_daily = replace(
            source.daily_wounds,
            closed_by_infection_id=source.id,
        )
        expected_consumed = (*source.consumed_proof_ids, expected_proof.id)
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.proof != expected_proof
            or self.target_id != source.target_id
            or self.previous_daily_wounds != source.daily_wounds
            or self.daily_wounds != expected_daily
            or self.injury_state != source.injury_state
            or self.previous_festering_wound_state
            != source.festering_wound_state
            or self.festering_wound_state != source.festering_wound_state
            or previous_consumed != source.consumed_proof_ids
            or consumed != expected_consumed
        ):
            raise ValueError("automatic Infection success has stale provenance")
        object.__setattr__(
            self,
            "previous_consumed_proof_ids",
            previous_consumed,
        )
        object.__setattr__(self, "consumed_proof_ids", consumed)

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            expected_proof.rule_id,
            *source.allocation.applied_rule_ids,
        }
        if not required <= set(rule_ids):
            raise ValueError("automatic Infection success trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def _allocation_proofs(
    request: AnatomyInfectionAllocationRequest,
) -> tuple[AutomaticInfectionSuccessProof, ...]:
    source = request.recall.source_request
    return tuple(
        AutomaticInfectionSuccessProof(
            id=f"{request.id}:proof:{index}",
            day_id=target.daily_wounds.day_id,
            target_id=target.target_id,
            practitioner_id=source.practitioner_id,
            relationship=target.relationship,
            daily_wounds=target.daily_wounds,
            source_recall_id=request.recall.request_id,
            source_allocation_id=request.id,
        )
        for index, target in enumerate(request.targets, start=1)
    )


def _selected_proof(
    allocation: AnatomyInfectionAllocationResult,
    proof_id: str,
) -> AutomaticInfectionSuccessProof:
    matching = tuple(item for item in allocation.proofs if item.id == proof_id)
    if len(matching) != 1:
        raise ValueError("allocation does not contain the selected proof")
    return matching[0]


def _validate_consumed_ids(
    values: tuple[str, ...],
    name: str,
) -> tuple[str, ...]:
    items = tuple(values)
    for item in items:
        _validate_non_empty_string(item, name[:-1])
    if len(set(items)) != len(items):
        raise ValueError(f"{name} must be unique")
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


def _validate_non_negative_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must not be negative")


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
