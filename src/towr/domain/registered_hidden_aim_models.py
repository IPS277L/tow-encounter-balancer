from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from towr.domain.aim_consumption_models import (
    AimAttackConsumptionResult,
    AimConsumptionState,
    _unique_ids,
    _validate_prepared_aim_attack_preflight,
)
from towr.domain.aim_models import _validate_non_empty_string
from towr.domain.hiding_position_models import (
    HidingPositionState,
    RegisteredHiddenAttackExecutionRequest,
    RegisteredHiddenAttackExecutionResult,
    _validate_hiding_position_preflight,
)
from towr.domain.prepared_hidden_ranged_attack_models import (
    PreparedHiddenRangedAttackExecutionRequest,
    PreparedHiddenRangedAttackExecutionResult,
)


REGISTERED_HIDDEN_AIM_ATTACK_RULE_ID = "RULE-COMBAT-004:registered-hidden-aim-attack"


@dataclass(frozen=True, slots=True)
class RegisteredHiddenAimAttackExecutionRequest:
    id: str
    aim_state: AimConsumptionState
    attack: RegisteredHiddenAttackExecutionRequest
    rule_id: str = REGISTERED_HIDDEN_AIM_ATTACK_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "registered hidden Aim Attack id")
        if self.rule_id != REGISTERED_HIDDEN_AIM_ATTACK_RULE_ID:
            raise ValueError("unknown registered hidden Aim Attack rule")
        _validate_registered_hidden_aim_preflight(self.aim_state, self.attack)


@dataclass(frozen=True, slots=True)
class RegisteredHiddenAimAttackExecutionResult:
    request_id: str
    rule_id: str
    source_request: RegisteredHiddenAimAttackExecutionRequest
    hidden_attack: RegisteredHiddenAttackExecutionResult
    aim_registration: AimAttackConsumptionResult
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, RegisteredHiddenAimAttackExecutionRequest):
            raise TypeError("source_request must be a registered hidden Aim Attack request")
        if not isinstance(self.hidden_attack, RegisteredHiddenAttackExecutionResult):
            raise TypeError("hidden_attack must be a registered hidden Attack result")
        if not isinstance(self.aim_registration, AimAttackConsumptionResult):
            raise TypeError("aim_registration must be an AimAttackConsumptionResult")
        execution = self.hidden_attack.execution
        if not isinstance(execution, PreparedHiddenRangedAttackExecutionResult):
            raise TypeError("hidden Attack must contain a prepared ranged execution")
        source = self.source_request
        if (
            self.request_id != source.id or self.rule_id != source.rule_id
            or self.hidden_attack.source_request != source.attack
            or self.aim_registration.source_request.id != f"{source.id}:aim-registration"
            or self.aim_registration.previous_state != source.aim_state
            or self.aim_registration.source_request.execution != execution.prepared_attack.execution
        ):
            raise ValueError("registered hidden Aim Attack has stale provenance")
        rules = _unique_ids(self.applied_rule_ids, "registered hidden Aim Attack rules")
        if rules != _registered_hidden_aim_rule_ids(source, self.hidden_attack, self.aim_registration):
            raise ValueError("registered hidden Aim Attack trace is inconsistent")
        object.__setattr__(self, "applied_rule_ids", rules)

    @property
    def execution(self) -> PreparedHiddenRangedAttackExecutionResult:
        return cast(PreparedHiddenRangedAttackExecutionResult, self.hidden_attack.execution)

    @property
    def aim_state(self) -> AimConsumptionState:
        return self.aim_registration.state

    @property
    def hiding_position_state(self) -> HidingPositionState:
        return self.hidden_attack.state


def _validate_registered_hidden_aim_preflight(
    aim_state: AimConsumptionState,
    request: RegisteredHiddenAttackExecutionRequest,
) -> None:
    if not isinstance(request, RegisteredHiddenAttackExecutionRequest):
        raise TypeError("attack must be a RegisteredHiddenAttackExecutionRequest")
    if not isinstance(request.attack, PreparedHiddenRangedAttackExecutionRequest):
        raise TypeError("registered hidden Aim Attack requires the prepared branch")
    _validate_hiding_position_preflight(request.state, request.hidden_request)
    _validate_prepared_aim_attack_preflight(aim_state, request.attack.prepared_attack)


def _registered_hidden_aim_rule_ids(
    request: RegisteredHiddenAimAttackExecutionRequest,
    hidden_attack: RegisteredHiddenAttackExecutionResult,
    aim_registration: AimAttackConsumptionResult,
) -> tuple[str, ...]:
    return tuple(dict.fromkeys((
        request.rule_id, *hidden_attack.applied_rule_ids, *aim_registration.applied_rule_ids,
    )))
