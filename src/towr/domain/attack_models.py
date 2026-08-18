from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from towr.domain.test_models import TestRequest, TestResult


class AttackOutcome(str, Enum):
    HIT = "hit"
    MISS = "miss"


class ImpactOutcome(str, Enum):
    STAGGERED = "staggered"
    WOUND = "wound"


class MissConsequence(str, Enum):
    NONE = "none"
    STAGGER_ATTACKER = "stagger_attacker"


@dataclass(frozen=True, slots=True)
class DamageProfile:
    base: int
    success_multiplier: int = 1

    def __post_init__(self) -> None:
        _validate_non_negative_int(self.base, "base damage")
        _validate_non_negative_int(self.success_multiplier, "success multiplier")


@dataclass(frozen=True, slots=True)
class ResilienceProfile:
    toughness: int
    bonus: int = 0

    def __post_init__(self) -> None:
        _validate_non_negative_int(self.toughness, "toughness")
        _validate_non_negative_int(self.bonus, "resilience bonus")

    @property
    def total(self) -> int:
        return self.toughness + self.bonus

    @property
    def is_armoured(self) -> bool:
        return self.bonus > 0


@dataclass(frozen=True, slots=True)
class DamageModifier:
    rule_id: str
    amount: int

    def __post_init__(self) -> None:
        _validate_rule_id(self.rule_id)
        _validate_non_zero_int(self.amount, "damage modifier amount")


@dataclass(frozen=True, slots=True)
class ResilienceModifier:
    rule_id: str
    amount: int

    def __post_init__(self) -> None:
        _validate_rule_id(self.rule_id)
        _validate_non_zero_int(self.amount, "resilience modifier amount")


@dataclass(frozen=True, slots=True)
class AttackRequest:
    id: str
    attacker_test: TestRequest
    defender_test: TestRequest | None
    damage: DamageProfile
    resilience: ResilienceProfile
    is_close_range: bool
    attacker_is_staggered: bool
    ignores_armour: bool = False
    damage_modifiers: tuple[DamageModifier, ...] = field(default_factory=tuple)
    resilience_modifiers: tuple[ResilienceModifier, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            raise TypeError("attack request id must be a string")
        if not self.id.strip():
            raise ValueError("attack request id must not be empty")
        if not isinstance(self.attacker_test, TestRequest):
            raise TypeError("attacker_test must be a TestRequest")
        if self.defender_test is not None and not isinstance(
            self.defender_test, TestRequest
        ):
            raise TypeError("defender_test must be a TestRequest or None")
        if not isinstance(self.damage, DamageProfile):
            raise TypeError("damage must be a DamageProfile")
        if not isinstance(self.resilience, ResilienceProfile):
            raise TypeError("resilience must be a ResilienceProfile")
        _validate_bool(self.is_close_range, "is_close_range")
        _validate_bool(self.attacker_is_staggered, "attacker_is_staggered")
        _validate_bool(self.ignores_armour, "ignores_armour")
        object.__setattr__(self, "damage_modifiers", tuple(self.damage_modifiers))
        object.__setattr__(
            self, "resilience_modifiers", tuple(self.resilience_modifiers)
        )
        if not all(
            isinstance(item, DamageModifier) for item in self.damage_modifiers
        ):
            raise TypeError("damage_modifiers must contain DamageModifier values")
        if not all(
            isinstance(item, ResilienceModifier)
            for item in self.resilience_modifiers
        ):
            raise TypeError(
                "resilience_modifiers must contain ResilienceModifier values"
            )


@dataclass(frozen=True, slots=True)
class AttackResult:
    request_id: str
    attacker_test: TestResult
    defender_test: TestResult | None
    outcome: AttackOutcome
    success_margin: int
    damage: int | None
    effective_resilience: int | None
    impact: ImpactOutcome | None
    miss_consequence: MissConsequence
    tie_break_applied: bool
    applied_rule_ids: tuple[str, ...]


def _validate_rule_id(rule_id: str) -> None:
    if not isinstance(rule_id, str):
        raise TypeError("rule_id must be a string")
    if not rule_id.strip():
        raise ValueError("rule_id must not be empty")


def _validate_non_zero_int(value: int, name: str) -> None:
    _validate_int(value, name)
    if value == 0:
        raise ValueError(f"{name} must not be zero")


def _validate_non_negative_int(value: int, name: str) -> None:
    _validate_int(value, name)
    if value < 0:
        raise ValueError(f"{name} must not be negative")


def _validate_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")
