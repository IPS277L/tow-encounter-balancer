from __future__ import annotations

from dataclasses import dataclass

from towr.domain.hidden_attack_models import (
    MoveQuietlyHiddenAttackExecutionRequest,
    MoveQuietlyHiddenAttackExecutionResult,
    _validate_non_empty_string,
    _validate_rule_ids,
)
from towr.domain.hidden_ranged_weapon_attack_models import (
    MoveQuietlyHiddenRangedAttackExecutionRequest,
    MoveQuietlyHiddenRangedAttackExecutionResult,
)
from towr.domain.prepared_hidden_ranged_attack_models import (
    PreparedHiddenRangedAttackExecutionRequest,
    PreparedHiddenRangedAttackExecutionResult,
)


HIDING_POSITION_REGISTRATION_RULE_ID = "RULE-COMBAT-014:revealed-hiding-position"
REGISTERED_HIDDEN_ATTACK_RULE_ID = "RULE-COMBAT-014:registered-hidden-attack"

type HiddenAttackExecutionRequest = (
    MoveQuietlyHiddenAttackExecutionRequest
    | MoveQuietlyHiddenRangedAttackExecutionRequest
    | PreparedHiddenRangedAttackExecutionRequest
)

type HiddenAttackExecutionResult = (
    MoveQuietlyHiddenAttackExecutionResult
    | MoveQuietlyHiddenRangedAttackExecutionResult
    | PreparedHiddenRangedAttackExecutionResult
)


@dataclass(frozen=True, slots=True)
class HidingPositionState:
    actor_id: str
    used_hiding_position_ids: tuple[str, ...] = ()
    consumed_attack_execution_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.actor_id, "actor_id")
        for name in ("used_hiding_position_ids", "consumed_attack_execution_ids"):
            object.__setattr__(self, name, _unique_ids(getattr(self, name), name))


@dataclass(frozen=True, slots=True)
class HidingPositionRegistrationRequest:
    id: str
    state: HidingPositionState
    execution: HiddenAttackExecutionResult
    rule_id: str = HIDING_POSITION_REGISTRATION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "registration id")
        if not isinstance(self.state, HidingPositionState):
            raise TypeError("state must be a HidingPositionState")
        if not isinstance(self.execution, (
            MoveQuietlyHiddenAttackExecutionResult,
            MoveQuietlyHiddenRangedAttackExecutionResult,
            PreparedHiddenRangedAttackExecutionResult,
        )):
            raise TypeError("registration requires a completed hidden Attack")
        if self.rule_id != HIDING_POSITION_REGISTRATION_RULE_ID:
            raise ValueError("unknown hiding position registration rule")
        _validate_hiding_position_preflight(self.state, self.hidden_request)

    @property
    def hidden_request(self) -> MoveQuietlyHiddenAttackExecutionRequest:
        if isinstance(self.execution, MoveQuietlyHiddenAttackExecutionResult):
            return self.execution.source_request
        return self.execution.source_request.hidden_attack


@dataclass(frozen=True, slots=True)
class HidingPositionRegistrationResult:
    request_id: str
    rule_id: str
    source_request: HidingPositionRegistrationRequest
    previous_state: HidingPositionState
    state: HidingPositionState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, HidingPositionRegistrationRequest):
            raise TypeError("source_request must be a registration request")
        source = self.source_request
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.previous_state != source.state
            or self.state != _registered_state(source)
        ):
            raise ValueError("hiding position registration has stale provenance")
        rules = _validate_rule_ids(self.applied_rule_ids)
        if rules != _registration_rule_ids(source):
            raise ValueError("hiding position registration trace is inconsistent")
        object.__setattr__(self, "applied_rule_ids", rules)


@dataclass(frozen=True, slots=True)
class RegisteredHiddenAttackExecutionRequest:
    id: str
    state: HidingPositionState
    attack: HiddenAttackExecutionRequest
    rule_id: str = REGISTERED_HIDDEN_ATTACK_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "registered hidden Attack id")
        if not isinstance(self.state, HidingPositionState):
            raise TypeError("state must be a HidingPositionState")
        if not isinstance(self.attack, (
            MoveQuietlyHiddenAttackExecutionRequest,
            MoveQuietlyHiddenRangedAttackExecutionRequest,
            PreparedHiddenRangedAttackExecutionRequest,
        )):
            raise TypeError("attack must be a hidden Attack execution request")
        if self.rule_id != REGISTERED_HIDDEN_ATTACK_RULE_ID:
            raise ValueError("unknown registered hidden Attack rule")
        _validate_hiding_position_preflight(self.state, self.hidden_request)

    @property
    def hidden_request(self) -> MoveQuietlyHiddenAttackExecutionRequest:
        if isinstance(self.attack, MoveQuietlyHiddenAttackExecutionRequest):
            return self.attack
        return self.attack.hidden_attack


@dataclass(frozen=True, slots=True)
class RegisteredHiddenAttackExecutionResult:
    request_id: str
    rule_id: str
    source_request: RegisteredHiddenAttackExecutionRequest
    registration: HidingPositionRegistrationResult
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, RegisteredHiddenAttackExecutionRequest):
            raise TypeError("source_request must be a registered hidden Attack request")
        if not isinstance(self.registration, HidingPositionRegistrationResult):
            raise TypeError("registration must be a HidingPositionRegistrationResult")
        source = self.source_request
        registration_source = self.registration.source_request
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or registration_source.id != f"{source.id}:registration"
            or registration_source.state != source.state
            or self.execution.source_request != source.attack
        ):
            raise ValueError("registered hidden Attack result has stale provenance")
        rules = _validate_rule_ids(self.applied_rule_ids)
        if rules != _registered_attack_rule_ids(source, self.registration):
            raise ValueError("registered hidden Attack trace is inconsistent")
        object.__setattr__(self, "applied_rule_ids", rules)

    @property
    def execution(self) -> HiddenAttackExecutionResult:
        return self.registration.source_request.execution

    @property
    def previous_state(self) -> HidingPositionState:
        return self.registration.previous_state

    @property
    def state(self) -> HidingPositionState:
        return self.registration.state


def _validate_hiding_position_preflight(
    state: HidingPositionState,
    hidden: MoveQuietlyHiddenAttackExecutionRequest,
) -> None:
    if state.actor_id != hidden.actor_id:
        raise ValueError("hidden Attack belongs to another actor")
    if hidden.attack.id in state.consumed_attack_execution_ids:
        raise ValueError("hidden Attack execution was already registered")
    if hidden.opportunity.hiding_position_id in state.used_hiding_position_ids:
        raise ValueError("hiding position was already used")
    if (
        hidden.move_quietly.source_request.used_hiding_position_ids
        != state.used_hiding_position_ids
    ):
        raise ValueError("Move Quietly used a stale hiding position snapshot")


def _registered_attack_rule_ids(
    request: RegisteredHiddenAttackExecutionRequest,
    registration: HidingPositionRegistrationResult,
) -> tuple[str, ...]:
    return tuple(dict.fromkeys((request.rule_id, *registration.applied_rule_ids)))


def _registered_state(request: HidingPositionRegistrationRequest) -> HidingPositionState:
    return HidingPositionState(
        actor_id=request.state.actor_id,
        used_hiding_position_ids=(
            *request.state.used_hiding_position_ids,
            request.execution.revealed_hiding_position_id,
        ),
        consumed_attack_execution_ids=(
            *request.state.consumed_attack_execution_ids,
            request.hidden_request.attack.id,
        ),
    )


def _registration_rule_ids(request: HidingPositionRegistrationRequest) -> tuple[str, ...]:
    return tuple(dict.fromkeys((request.rule_id, *request.execution.applied_rule_ids)))


def _unique_ids(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    if isinstance(values, str):
        raise TypeError(f"{name} must be an ID collection")
    identifiers = tuple(values)
    for identifier in identifiers:
        _validate_non_empty_string(identifier, name)
    if len(set(identifiers)) != len(identifiers):
        raise ValueError(f"{name} must be unique")
    return identifiers
