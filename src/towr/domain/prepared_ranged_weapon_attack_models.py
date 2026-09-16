from __future__ import annotations

from dataclasses import dataclass

from towr.domain.aim_ranged_weapon_attack_models import (
    AimRangedWeaponAttackExecutionRequest,
    AimRangedWeaponAttackExecutionResult,
)
from towr.domain.ranged_weapon_attack_models import (
    RangedWeaponAttackExecutionResult,
)
from towr.domain.ranged_weapon_attack_preparation_models import (
    RangedWeaponAttackPreparationResult,
)


PREPARED_RANGED_ATTACK_EXECUTION_RULE_ID = (
    "RULE-EQUIPMENT-004:prepared-ranged-attack-execution"
)


@dataclass(frozen=True, slots=True)
class PreparedRangedWeaponAttackExecutionRequest:
    id: str
    preparation: RangedWeaponAttackPreparationResult
    consumed_aim_follow_up_ids: tuple[str, ...] = ()
    rule_id: str = PREPARED_RANGED_ATTACK_EXECUTION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "prepared ranged Attack id")
        if not isinstance(self.preparation, RangedWeaponAttackPreparationResult):
            raise TypeError("preparation must be a ranged Attack preparation result")
        _validate_non_empty_string(self.rule_id, "prepared ranged Attack rule_id")
        if self.rule_id != PREPARED_RANGED_ATTACK_EXECUTION_RULE_ID:
            raise ValueError("prepared ranged Attack uses an unknown rule")
        consumed = _validate_ids(
            self.consumed_aim_follow_up_ids, "consumed Aim follow-up ID"
        )
        object.__setattr__(self, "consumed_aim_follow_up_ids", consumed)

        prepared = self.preparation
        identifiers = (
            self.id,
            prepared.request_id,
            prepared.execution.id,
            prepared.execution.attack.id,
        )
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("prepared ranged request IDs must be distinct")
        if prepared.aim_follow_up is not None:
            if self.id == prepared.aim_follow_up.request_id:
                raise ValueError("prepared ranged and Aim follow-up IDs must differ")
            # Validate binding and replay before any executor can use RNG.
            _aim_request_for(self)


@dataclass(frozen=True, slots=True)
class PreparedRangedWeaponAttackExecutionResult:
    request_id: str
    rule_id: str
    source_request: PreparedRangedWeaponAttackExecutionRequest
    execution: RangedWeaponAttackExecutionResult | AimRangedWeaponAttackExecutionResult
    previous_consumed_aim_follow_up_ids: tuple[str, ...]
    consumed_aim_follow_up_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "prepared ranged result request_id")
        _validate_non_empty_string(self.rule_id, "prepared ranged result rule_id")
        if not isinstance(self.source_request, PreparedRangedWeaponAttackExecutionRequest):
            raise TypeError("source_request must be a prepared ranged Attack request")
        source = self.source_request
        if self.request_id != source.id or self.rule_id != source.rule_id:
            raise ValueError("prepared ranged Attack result is stale")

        if source.preparation.aim_follow_up is None:
            if not isinstance(self.execution, RangedWeaponAttackExecutionResult):
                raise TypeError("direct prepared Attack requires a ranged result")
            expected_consumed = source.consumed_aim_follow_up_ids
        else:
            if not isinstance(self.execution, AimRangedWeaponAttackExecutionResult):
                raise TypeError("aimed prepared Attack requires an Aim ranged result")
            if self.execution.source_request != _aim_request_for(source):
                raise ValueError("prepared result has an inconsistent Aim execution")
            expected_consumed = self.execution.consumed_aim_follow_up_ids
        if self.ranged_attack.source_request != source.preparation.execution:
            raise ValueError("prepared result belongs to another ranged Attack")

        previous = _validate_ids(
            self.previous_consumed_aim_follow_up_ids, "previous consumed Aim follow-up ID"
        )
        consumed = _validate_ids(self.consumed_aim_follow_up_ids, "consumed Aim follow-up ID")
        if previous != source.consumed_aim_follow_up_ids or consumed != expected_consumed:
            raise ValueError("prepared ranged result has inconsistent Aim consumption")
        object.__setattr__(self, "previous_consumed_aim_follow_up_ids", previous)
        object.__setattr__(self, "consumed_aim_follow_up_ids", consumed)

        rule_ids = _validate_ids(self.applied_rule_ids, "applied Rule ID")
        if rule_ids != _applied_rule_ids(source, self.execution):
            raise ValueError("prepared ranged Attack trace is inconsistent")
        object.__setattr__(self, "applied_rule_ids", rule_ids)

    @property
    def ranged_attack(self) -> RangedWeaponAttackExecutionResult:
        """Expose the sole weapon/Attack transition without duplicating it."""
        if isinstance(self.execution, AimRangedWeaponAttackExecutionResult):
            return self.execution.ranged_attack
        return self.execution


def _aim_request_for(
    request: PreparedRangedWeaponAttackExecutionRequest,
) -> AimRangedWeaponAttackExecutionRequest:
    follow_up = request.preparation.aim_follow_up
    if follow_up is None:
        raise ValueError("prepared Attack has no Aim follow-up")
    return AimRangedWeaponAttackExecutionRequest(
        id=f"{request.id}:aim-execution",
        aim_follow_up=follow_up,
        ranged_attack=request.preparation.execution,
        consumed_aim_follow_up_ids=request.consumed_aim_follow_up_ids,
    )


def _applied_rule_ids(
    request: PreparedRangedWeaponAttackExecutionRequest,
    execution: RangedWeaponAttackExecutionResult | AimRangedWeaponAttackExecutionResult,
) -> tuple[str, ...]:
    return tuple(dict.fromkeys((
        request.rule_id,
        *request.preparation.applied_rule_ids,
        *execution.applied_rule_ids,
    )))


def _validate_ids(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    if isinstance(values, str):
        raise TypeError(f"{name}s must be a sequence of IDs, not a string")
    identifiers = tuple(values)
    for identifier in identifiers:
        _validate_non_empty_string(identifier, name)
    if len(set(identifiers)) != len(identifiers):
        raise ValueError(f"{name}s must be unique")
    return identifiers


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
