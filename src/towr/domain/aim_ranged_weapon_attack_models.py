from __future__ import annotations

from dataclasses import dataclass

from towr.domain.aim_models import (
    AimFollowUpOutcome,
    AimFollowUpResult,
)
from towr.domain.ranged_weapon_attack_models import (
    RangedWeaponAttackExecutionRequest,
    RangedWeaponAttackExecutionResult,
)
from towr.domain.test_models import Skill


AIM_RANGED_ATTACK_EXECUTION_RULE_ID = (
    "RULE-COMBAT-004:aim-ranged-attack-execution"
)


@dataclass(frozen=True, slots=True)
class AimRangedWeaponAttackExecutionRequest:
    id: str
    aim_follow_up: AimFollowUpResult
    ranged_attack: RangedWeaponAttackExecutionRequest
    consumed_aim_follow_up_ids: tuple[str, ...] = ()
    rule_id: str = AIM_RANGED_ATTACK_EXECUTION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Aim ranged Attack id")
        if not isinstance(self.aim_follow_up, AimFollowUpResult):
            raise TypeError("aim_follow_up must be an AimFollowUpResult")
        if not isinstance(
            self.ranged_attack,
            RangedWeaponAttackExecutionRequest,
        ):
            raise TypeError("ranged_attack must be a ranged weapon request")
        _validate_non_empty_string(self.rule_id, "Aim ranged Attack rule_id")
        if self.rule_id != AIM_RANGED_ATTACK_EXECUTION_RULE_ID:
            raise ValueError("Aim ranged Attack uses an unknown rule")

        follow_up = self.aim_follow_up
        if follow_up.outcome is not AimFollowUpOutcome.APPLIED_TO_RANGED_ATTACK:
            raise ValueError("Aim bonus was not applied to this ranged Attack")
        if follow_up.source_request.attack_skill is not Skill.SHOOTING:
            raise ValueError("profile-aware Aim execution requires Shooting")
        if follow_up.attack is None:
            raise ValueError("applied Aim follow-up requires a prepared Attack")
        if self.ranged_attack.attack != follow_up.attack:
            raise ValueError("Aim and ranged requests must share the prepared Attack")

        consumed = _validate_ids(
            self.consumed_aim_follow_up_ids,
            "consumed Aim follow-up ID",
        )
        if follow_up.request_id in consumed:
            raise ValueError("Aim follow-up was already consumed")
        object.__setattr__(self, "consumed_aim_follow_up_ids", consumed)

        identifiers = (
            self.id,
            follow_up.request_id,
            self.ranged_attack.id,
            self.ranged_attack.attack.id,
        )
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Aim ranged request IDs must be distinct")


@dataclass(frozen=True, slots=True)
class AimRangedWeaponAttackExecutionResult:
    request_id: str
    rule_id: str
    source_request: AimRangedWeaponAttackExecutionRequest
    ranged_attack: RangedWeaponAttackExecutionResult
    previous_consumed_aim_follow_up_ids: tuple[str, ...]
    consumed_aim_follow_up_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Aim ranged Attack result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "Aim ranged Attack result rule_id",
        )
        if not isinstance(
            self.source_request,
            AimRangedWeaponAttackExecutionRequest,
        ):
            raise TypeError("source_request must be an Aim ranged request")
        if not isinstance(
            self.ranged_attack,
            RangedWeaponAttackExecutionResult,
        ):
            raise TypeError("ranged_attack must be a ranged weapon result")

        source = self.source_request
        follow_up = source.aim_follow_up
        if self.request_id != source.id or self.rule_id != source.rule_id:
            raise ValueError("Aim ranged Attack result is stale")
        if self.ranged_attack.source_request != source.ranged_attack:
            raise ValueError("Aim ranged result belongs to another Attack")

        previous = _validate_ids(
            self.previous_consumed_aim_follow_up_ids,
            "previous consumed Aim follow-up ID",
        )
        if previous != source.consumed_aim_follow_up_ids:
            raise ValueError("Aim ranged result has stale consumption")
        consumed = _validate_ids(
            self.consumed_aim_follow_up_ids,
            "consumed Aim follow-up ID",
        )
        if consumed != (*previous, follow_up.request_id):
            raise ValueError("consumed Aim IDs must append the follow-up")
        object.__setattr__(
            self,
            "previous_consumed_aim_follow_up_ids",
            previous,
        )
        object.__setattr__(self, "consumed_aim_follow_up_ids", consumed)

        rule_ids = _validate_ids(self.applied_rule_ids, "applied Rule ID")
        required = {
            self.rule_id,
            *follow_up.applied_rule_ids,
            *self.ranged_attack.applied_rule_ids,
        }
        if not required <= set(rule_ids):
            raise ValueError("Aim ranged Attack trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def _validate_ids(values: tuple[str, ...], name: str) -> tuple[str, ...]:
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
