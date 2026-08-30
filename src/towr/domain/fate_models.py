from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum

from towr.domain.test_models import (
    FATE_GLORIOUS_RULE_ID,
    FateGloriousProof,
    InitialTestRoll,
    QualityModifier,
    QualityModifierSource,
    TestQuality,
    TestRequest,
)
from towr.domain.turn_models import (
    ACTION_BUDGET_RULE_ID,
    ActionSlotGrant,
    CombatActionDeclaration,
    CombatActionSlotRequest,
    CombatActionSlotResult,
)


FATE_SESSION_RULE_ID = "RULE-FATE-001:session-resource"
FATE_SECOND_ACTION_RULE_ID = "RULE-FATE-002:second-action"


class FateSpendKind(str, Enum):
    GLORIOUS_TEST = "glorious_test"
    SECOND_ACTION = "second_action"


@dataclass(frozen=True, slots=True)
class FateSpendRecord:
    id: str
    session_id: str
    actor_id: str
    kind: FateSpendKind
    subject_id: str
    rule_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Fate spend id")
        _validate_non_empty_string(self.session_id, "Fate spend session_id")
        _validate_non_empty_string(self.actor_id, "Fate spend actor_id")
        if not isinstance(self.kind, FateSpendKind):
            raise TypeError("kind must be a FateSpendKind")
        _validate_non_empty_string(self.subject_id, "Fate spend subject_id")
        _validate_non_empty_string(self.rule_id, "Fate spend rule_id")
        if (
            self.kind is FateSpendKind.GLORIOUS_TEST
            and self.rule_id != FATE_GLORIOUS_RULE_ID
        ):
            raise ValueError("Glorious Test spend requires its canonical rule")
        if (
            self.kind is FateSpendKind.SECOND_ACTION
            and self.rule_id != FATE_SECOND_ACTION_RULE_ID
        ):
            raise ValueError("second action spend requires its canonical rule")


@dataclass(frozen=True, slots=True)
class FateSessionState:
    session_id: str
    actor_id: str
    rating: int
    session_spend_limit: int
    spends: tuple[FateSpendRecord, ...] = field(default_factory=tuple)
    rule_id: str = FATE_SESSION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.session_id, "Fate session_id")
        _validate_non_empty_string(self.actor_id, "Fate actor_id")
        _validate_non_negative_int(self.rating, "Fate rating")
        _validate_non_negative_int(
            self.session_spend_limit,
            "Fate session_spend_limit",
        )
        _validate_non_empty_string(self.rule_id, "Fate session rule_id")
        if self.rule_id != FATE_SESSION_RULE_ID:
            raise ValueError("Fate session state requires its canonical rule")
        spends = tuple(self.spends)
        if not all(isinstance(item, FateSpendRecord) for item in spends):
            raise TypeError("spends must contain FateSpendRecord values")
        if len(spends) > self.session_spend_limit:
            raise ValueError("Fate spends cannot exceed the session limit")
        spend_ids = tuple(item.id for item in spends)
        if len(set(spend_ids)) != len(spend_ids):
            raise ValueError("Fate spend IDs must be unique")
        if any(
            item.session_id != self.session_id
            or item.actor_id != self.actor_id
            for item in spends
        ):
            raise ValueError("Fate spend belongs to another session or actor")
        glorious_test_ids = tuple(
            item.subject_id
            for item in spends
            if item.kind is FateSpendKind.GLORIOUS_TEST
        )
        if len(set(glorious_test_ids)) != len(glorious_test_ids):
            raise ValueError("Fate cannot make the same Test Glorious twice")
        second_action_ids = tuple(
            item.subject_id
            for item in spends
            if item.kind is FateSpendKind.SECOND_ACTION
        )
        if len(set(second_action_ids)) != len(second_action_ids):
            raise ValueError("Fate cannot grant the same second action twice")
        object.__setattr__(self, "spends", spends)

    @property
    def remaining_spends(self) -> int:
        return self.session_spend_limit - len(self.spends)


@dataclass(frozen=True, slots=True)
class FateGloriousSpendRequest:
    id: str
    state: FateSessionState
    test: TestRequest
    initial_roll: InitialTestRoll | None = None
    rule_id: str = FATE_GLORIOUS_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Fate Glorious request id")
        if not isinstance(self.state, FateSessionState):
            raise TypeError("state must be a FateSessionState")
        if not isinstance(self.test, TestRequest):
            raise TypeError("test must be a TestRequest")
        if self.initial_roll is not None:
            if not isinstance(self.initial_roll, InitialTestRoll):
                raise TypeError("initial_roll must be an InitialTestRoll")
            if self.initial_roll.request != self.test:
                raise ValueError("initial roll belongs to another Test request")
        _validate_non_empty_string(self.rule_id, "Fate Glorious rule_id")
        if self.state.remaining_spends < 1:
            raise ValueError("no Fate spends remain in this session")
        if self.id in {item.id for item in self.state.spends}:
            raise ValueError("Fate spend request was already consumed")
        if any(
            item.kind is FateSpendKind.GLORIOUS_TEST
            and item.subject_id == self.test.id
            for item in self.state.spends
        ):
            raise ValueError("Fate was already spent on this Test")
        if any(
            item.quality is TestQuality.GLORIOUS
            for item in self.test.quality_modifiers
        ):
            raise ValueError("Fate cannot be spent on an already Glorious Test")


@dataclass(frozen=True, slots=True)
class FateGloriousSpendResult:
    request_id: str
    rule_id: str
    source_request: FateGloriousSpendRequest
    previous_state: FateSessionState
    state: FateSessionState
    spend: FateSpendRecord
    proof: FateGloriousProof
    test: TestRequest
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Fate Glorious result request_id",
        )
        _validate_non_empty_string(self.rule_id, "Fate Glorious result rule_id")
        if not isinstance(self.source_request, FateGloriousSpendRequest):
            raise TypeError("source_request must be a Fate Glorious request")
        if not isinstance(self.previous_state, FateSessionState):
            raise TypeError("previous_state must be a FateSessionState")
        if not isinstance(self.state, FateSessionState):
            raise TypeError("state must be a FateSessionState")
        if not isinstance(self.spend, FateSpendRecord):
            raise TypeError("spend must be a FateSpendRecord")
        if not isinstance(self.proof, FateGloriousProof):
            raise TypeError("proof must be a FateGloriousProof")
        if not isinstance(self.test, TestRequest):
            raise TypeError("test must be a TestRequest")

        expected_spend, expected_proof, expected_state, expected_test = (
            _expected_fate_glorious_spend(self.source_request)
        )
        if (
            self.request_id != self.source_request.id
            or self.rule_id != self.source_request.rule_id
            or self.previous_state != self.source_request.state
            or self.spend != expected_spend
            or self.proof != expected_proof
            or self.state != expected_state
            or self.test != expected_test
        ):
            raise ValueError("Fate Glorious result has stale provenance")

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {self.rule_id, self.state.rule_id}
        if not required <= set(rule_ids):
            raise ValueError("Fate Glorious rule trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


@dataclass(frozen=True, slots=True)
class FateSecondActionProof:
    id: str
    session_id: str
    actor_id: str
    slot_request_id: str
    round_number: int
    slot_index: int
    declaration: CombatActionDeclaration
    source_spend_id: str
    rule_id: str = FATE_SECOND_ACTION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Fate second action proof id")
        _validate_non_empty_string(
            self.session_id,
            "Fate second action proof session_id",
        )
        _validate_non_empty_string(
            self.actor_id,
            "Fate second action proof actor_id",
        )
        _validate_non_empty_string(
            self.slot_request_id,
            "Fate second action proof slot_request_id",
        )
        _validate_positive_int(
            self.round_number,
            "Fate second action proof round_number",
        )
        _validate_positive_int(
            self.slot_index,
            "Fate second action proof slot_index",
        )
        if self.slot_index != 2:
            raise ValueError("Fate second action proof requires slot 2")
        if not isinstance(self.declaration, CombatActionDeclaration):
            raise TypeError("declaration must be a CombatActionDeclaration")
        _validate_non_empty_string(
            self.source_spend_id,
            "Fate second action proof source_spend_id",
        )
        _validate_non_empty_string(self.rule_id, "Fate second action rule_id")
        if self.rule_id != FATE_SECOND_ACTION_RULE_ID:
            raise ValueError("Fate second action proof requires its canonical rule")


@dataclass(frozen=True, slots=True)
class FateSecondActionSpendRequest:
    id: str
    state: FateSessionState
    slot_request: CombatActionSlotRequest
    rule_id: str = FATE_SECOND_ACTION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Fate second action request id")
        if not isinstance(self.state, FateSessionState):
            raise TypeError("state must be a FateSessionState")
        if not isinstance(self.slot_request, CombatActionSlotRequest):
            raise TypeError("slot_request must be a CombatActionSlotRequest")
        _validate_non_empty_string(self.rule_id, "Fate second action rule_id")
        if self.state.remaining_spends < 1:
            raise ValueError("no Fate spends remain in this session")
        if self.state.actor_id != self.slot_request.actor_id:
            raise ValueError("Fate state belongs to another action actor")
        if self.slot_request.grant is not ActionSlotGrant.FATE:
            raise ValueError("second action slot request must use a Fate grant")
        if self.id in {item.id for item in self.state.spends}:
            raise ValueError("Fate spend request was already consumed")
        if any(
            item.kind is FateSpendKind.SECOND_ACTION
            and item.subject_id == self.slot_request.id
            for item in self.state.spends
        ):
            raise ValueError("Fate was already spent on this second action")


@dataclass(frozen=True, slots=True)
class FateSecondActionSpendResult:
    request_id: str
    rule_id: str
    source_request: FateSecondActionSpendRequest
    previous_state: FateSessionState
    state: FateSessionState
    spend: FateSpendRecord
    proof: FateSecondActionProof
    slot_result: CombatActionSlotResult
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Fate second action result request_id",
        )
        _validate_non_empty_string(self.rule_id, "Fate second action rule_id")
        if not isinstance(self.source_request, FateSecondActionSpendRequest):
            raise TypeError("source_request must be a Fate second action request")
        if not isinstance(self.previous_state, FateSessionState):
            raise TypeError("previous_state must be a FateSessionState")
        if not isinstance(self.state, FateSessionState):
            raise TypeError("state must be a FateSessionState")
        if not isinstance(self.spend, FateSpendRecord):
            raise TypeError("spend must be a FateSpendRecord")
        if not isinstance(self.proof, FateSecondActionProof):
            raise TypeError("proof must be a FateSecondActionProof")
        if not isinstance(self.slot_result, CombatActionSlotResult):
            raise TypeError("slot_result must be a CombatActionSlotResult")

        expected_spend, expected_proof, expected_state = (
            _expected_fate_second_action_spend(self.source_request)
        )
        slot_request = self.source_request.slot_request
        slot = self.slot_result.slot
        source_turn = slot_request.state.active_turn
        if source_turn is None:
            raise ValueError("Fate second action result has no source turn")
        expected_turn = replace(
            source_turn,
            action_slots=(*source_turn.action_slots, slot),
        )
        expected_round_state = replace(
            slot_request.state,
            active_turn=expected_turn,
        )
        if (
            self.request_id != self.source_request.id
            or self.rule_id != self.source_request.rule_id
            or self.previous_state != self.source_request.state
            or self.spend != expected_spend
            or self.proof != expected_proof
            or self.state != expected_state
            or self.slot_result.request_id != slot_request.id
            or slot.index != 2
            or slot.declaration != slot_request.declaration
            or slot.grant is not ActionSlotGrant.FATE
            or slot.execution is not None
            or self.slot_result.state != expected_round_state
            or self.slot_result.applied_rule_ids
            != (ACTION_BUDGET_RULE_ID, self.rule_id)
        ):
            raise ValueError("Fate second action result has stale provenance")

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        expected_rule_ids = tuple(
            dict.fromkeys(
                (
                    self.state.rule_id,
                    *self.slot_result.applied_rule_ids,
                )
            )
        )
        if rule_ids != expected_rule_ids or self.rule_id not in rule_ids:
            raise ValueError("Fate second action rule trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def _expected_fate_glorious_spend(
    request: FateGloriousSpendRequest,
) -> tuple[
    FateSpendRecord,
    FateGloriousProof,
    FateSessionState,
    TestRequest,
]:
    proof_id = f"{request.id}:proof"
    spend = FateSpendRecord(
        id=request.id,
        session_id=request.state.session_id,
        actor_id=request.state.actor_id,
        kind=FateSpendKind.GLORIOUS_TEST,
        subject_id=request.test.id,
        rule_id=request.rule_id,
    )
    proof = FateGloriousProof(
        id=proof_id,
        session_id=request.state.session_id,
        actor_id=request.state.actor_id,
        test_id=request.test.id,
        source_spend_id=spend.id,
        rule_id=request.rule_id,
    )
    state = replace(
        request.state,
        spends=(*request.state.spends, spend),
    )
    test = replace(
        request.test,
        quality_modifiers=(
            *request.test.quality_modifiers,
            QualityModifier(
                rule_id=request.rule_id,
                quality=TestQuality.GLORIOUS,
                source=QualityModifierSource.FATE,
                source_id=proof.id,
            ),
        ),
    )
    return spend, proof, state, test


def _expected_fate_second_action_spend(
    request: FateSecondActionSpendRequest,
) -> tuple[FateSpendRecord, FateSecondActionProof, FateSessionState]:
    slot_request = request.slot_request
    spend = FateSpendRecord(
        id=request.id,
        session_id=request.state.session_id,
        actor_id=request.state.actor_id,
        kind=FateSpendKind.SECOND_ACTION,
        subject_id=slot_request.id,
        rule_id=request.rule_id,
    )
    proof = FateSecondActionProof(
        id=f"{request.id}:proof",
        session_id=request.state.session_id,
        actor_id=request.state.actor_id,
        slot_request_id=slot_request.id,
        round_number=slot_request.state.round_number,
        slot_index=2,
        declaration=slot_request.declaration,
        source_spend_id=spend.id,
        rule_id=request.rule_id,
    )
    state = replace(request.state, spends=(*request.state.spends, spend))
    return spend, proof, state


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
