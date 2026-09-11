from __future__ import annotations

from dataclasses import dataclass

from towr.domain.hidden_attack_models import (
    HIDDEN_ATTACK_OPPORTUNITY_RULE_ID,
    MoveQuietlyHiddenAttackExecutionRequest,
    _validate_consumed_ids,
    _validate_rule_ids,
)
from towr.domain.ranged_weapon_attack_models import (
    RangedWeaponAttackExecutionRequest,
    RangedWeaponAttackExecutionResult,
)


@dataclass(frozen=True, slots=True)
class MoveQuietlyHiddenRangedAttackExecutionRequest:
    id: str
    hidden_attack: MoveQuietlyHiddenAttackExecutionRequest
    ranged_attack: RangedWeaponAttackExecutionRequest
    rule_id: str = HIDDEN_ATTACK_OPPORTUNITY_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "hidden ranged Attack id")
        if not isinstance(
            self.hidden_attack,
            MoveQuietlyHiddenAttackExecutionRequest,
        ):
            raise TypeError("hidden_attack must be a hidden Attack request")
        if not isinstance(
            self.ranged_attack,
            RangedWeaponAttackExecutionRequest,
        ):
            raise TypeError("ranged_attack must be a ranged weapon request")
        _validate_non_empty_string(self.rule_id, "hidden ranged Attack rule_id")
        if self.rule_id != HIDDEN_ATTACK_OPPORTUNITY_RULE_ID:
            raise ValueError("hidden ranged Attack uses an unknown rule")
        if self.hidden_attack.rule_id != self.rule_id:
            raise ValueError("hidden ranged Attack uses another hidden rule")
        if self.hidden_attack.attack != self.ranged_attack.attack:
            raise ValueError("hidden and ranged requests must share one Attack")
        if (
            self.hidden_attack.actor_id != self.ranged_attack.attack.actor_id
            or self.hidden_attack.target_id
            != self.ranged_attack.attack.target_id
        ):
            raise ValueError("hidden ranged Attack has stale actor or target")
        identifiers = (
            self.id,
            self.hidden_attack.id,
            self.ranged_attack.id,
            self.ranged_attack.attack.id,
        )
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("hidden ranged request IDs must be distinct")


@dataclass(frozen=True, slots=True)
class MoveQuietlyHiddenRangedAttackExecutionResult:
    request_id: str
    rule_id: str
    source_request: MoveQuietlyHiddenRangedAttackExecutionRequest
    ranged_attack: RangedWeaponAttackExecutionResult
    revealed_hiding_position_id: str
    previous_consumed_opportunity_ids: tuple[str, ...]
    consumed_opportunity_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "hidden ranged Attack result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "hidden ranged Attack result rule_id",
        )
        if not isinstance(
            self.source_request,
            MoveQuietlyHiddenRangedAttackExecutionRequest,
        ):
            raise TypeError("source_request must be a hidden ranged request")
        if not isinstance(
            self.ranged_attack,
            RangedWeaponAttackExecutionResult,
        ):
            raise TypeError("ranged_attack must be a ranged weapon result")
        _validate_non_empty_string(
            self.revealed_hiding_position_id,
            "revealed_hiding_position_id",
        )

        source = self.source_request
        hidden = source.hidden_attack
        if self.request_id != source.id or self.rule_id != source.rule_id:
            raise ValueError("hidden ranged Attack result is stale")
        if self.ranged_attack.source_request != source.ranged_attack:
            raise ValueError("hidden ranged result belongs to another Attack")
        if (
            self.ranged_attack.attack.request_id != hidden.attack.id
            or self.ranged_attack.attack.actor_id != hidden.actor_id
            or self.ranged_attack.attack.target_id != hidden.target_id
            or self.revealed_hiding_position_id
            != hidden.opportunity.hiding_position_id
        ):
            raise ValueError("hidden ranged result has stale hidden provenance")

        previous = _validate_consumed_ids(
            self.previous_consumed_opportunity_ids
        )
        if previous != hidden.consumed_opportunity_ids:
            raise ValueError("hidden ranged result has stale consumption")
        consumed = _validate_consumed_ids(self.consumed_opportunity_ids)
        if consumed != (*previous, hidden.opportunity.id):
            raise ValueError(
                "consumed opportunity IDs must append the hidden opportunity"
            )
        object.__setattr__(
            self,
            "previous_consumed_opportunity_ids",
            previous,
        )
        object.__setattr__(self, "consumed_opportunity_ids", consumed)

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            hidden.move_quietly.rule_id,
            *self.ranged_attack.applied_rule_ids,
        }
        if not required <= set(rule_ids):
            raise ValueError("hidden ranged Attack trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
