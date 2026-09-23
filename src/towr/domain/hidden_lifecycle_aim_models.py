from __future__ import annotations

from dataclasses import dataclass

from towr.domain.aim_consumption_models import AimConsumptionState, _unique_ids
from towr.domain.aim_models import _validate_non_empty_string
from towr.domain.hidden_lifecycle_models import (
    HiddenLifecycleApplicationResult,
    HiddenLifecycleState,
    _validate_lifecycle_attack,
)
from towr.domain.prepared_hidden_ranged_attack_models import PreparedHiddenRangedAttackExecutionResult
from towr.domain.registered_hidden_aim_models import (
    RegisteredHiddenAimAttackExecutionRequest,
    RegisteredHiddenAimAttackExecutionResult,
    _validate_registered_hidden_aim_preflight,
)


HIDDEN_LIFECYCLE_AIM_ATTACK_RULE_ID = "RULE-COMBAT-014:hidden-lifecycle-aim-attack"


@dataclass(frozen=True, slots=True)
class HiddenLifecycleAimAttackExecutionRequest:
    id: str
    state: HiddenLifecycleState
    attack: RegisteredHiddenAimAttackExecutionRequest
    rule_id: str = HIDDEN_LIFECYCLE_AIM_ATTACK_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "hidden lifecycle Aim Attack id")
        if self.rule_id != HIDDEN_LIFECYCLE_AIM_ATTACK_RULE_ID:
            raise ValueError("unknown hidden lifecycle Aim Attack rule")
        _validate_lifecycle_aim_attack(self.state, self.attack)


@dataclass(frozen=True, slots=True)
class HiddenLifecycleAimAttackExecutionResult:
    request_id: str
    rule_id: str
    source_request: HiddenLifecycleAimAttackExecutionRequest
    attack: RegisteredHiddenAimAttackExecutionResult
    lifecycle: HiddenLifecycleApplicationResult
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, HiddenLifecycleAimAttackExecutionRequest):
            raise TypeError("source_request must be a hidden lifecycle Aim Attack request")
        if not isinstance(self.attack, RegisteredHiddenAimAttackExecutionResult):
            raise TypeError("attack must be a registered hidden Aim Attack result")
        if not isinstance(self.lifecycle, HiddenLifecycleApplicationResult):
            raise TypeError("lifecycle must be a HiddenLifecycleApplicationResult")
        source = self.source_request
        if (
            self.request_id != source.id or self.rule_id != source.rule_id
            or self.attack.source_request != source.attack
            or self.lifecycle.request_id != f"{source.id}:hidden-lifecycle"
            or self.lifecycle.previous_state != source.state
            or self.lifecycle.completed != self.attack.hidden_attack
        ):
            raise ValueError("hidden lifecycle Aim Attack has stale provenance")
        rules = _unique_ids(self.applied_rule_ids, "hidden lifecycle Aim Attack rules")
        if rules != _lifecycle_aim_rule_ids(source, self.attack, self.lifecycle):
            raise ValueError("hidden lifecycle Aim Attack trace is inconsistent")
        object.__setattr__(self, "applied_rule_ids", rules)

    @property
    def state(self) -> HiddenLifecycleState:
        return self.lifecycle.state

    @property
    def aim_state(self) -> AimConsumptionState:
        return self.attack.aim_state

    @property
    def execution(self) -> PreparedHiddenRangedAttackExecutionResult:
        return self.attack.execution


def _validate_lifecycle_aim_attack(
    state: HiddenLifecycleState,
    attack: RegisteredHiddenAimAttackExecutionRequest,
) -> None:
    if not isinstance(attack, RegisteredHiddenAimAttackExecutionRequest):
        raise TypeError("attack must be a RegisteredHiddenAimAttackExecutionRequest")
    _validate_lifecycle_attack(state, attack.attack)
    _validate_registered_hidden_aim_preflight(attack.aim_state, attack.attack)


def _lifecycle_aim_rule_ids(
    request: HiddenLifecycleAimAttackExecutionRequest,
    attack: RegisteredHiddenAimAttackExecutionResult,
    lifecycle: HiddenLifecycleApplicationResult,
) -> tuple[str, ...]:
    return tuple(dict.fromkeys((request.rule_id, *attack.applied_rule_ids, *lifecycle.applied_rule_ids)))
