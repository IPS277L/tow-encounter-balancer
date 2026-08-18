from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from towr.domain.condition_models import Condition
from towr.domain.test_models import Skill, TestRequest, TestResult


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
class DamageImpactSpec:
    damage: DamageProfile
    resilience: ResilienceProfile
    ignores_armour: bool = False
    damage_modifiers: tuple[DamageModifier, ...] = field(default_factory=tuple)
    resilience_modifiers: tuple[ResilienceModifier, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        if not isinstance(self.damage, DamageProfile):
            raise TypeError("damage must be a DamageProfile")
        if not isinstance(self.resilience, ResilienceProfile):
            raise TypeError("resilience must be a ResilienceProfile")
        _validate_bool(self.ignores_armour, "ignores_armour")
        object.__setattr__(self, "damage_modifiers", tuple(self.damage_modifiers))
        object.__setattr__(
            self,
            "resilience_modifiers",
            tuple(self.resilience_modifiers),
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
class ConditionImpactSpec:
    condition: Condition
    rule_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.condition, Condition):
            raise TypeError("condition must be a Condition")
        _validate_rule_id(self.rule_id)


@dataclass(frozen=True, slots=True)
class HazardImpactSpec:
    rating: int
    avoidance_skill: Skill
    rule_id: str
    inflicts_wound: bool = True
    failure_conditions: tuple[Condition, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_positive_int(self.rating, "Hazard rating")
        if not isinstance(self.avoidance_skill, Skill):
            raise TypeError("avoidance_skill must be a Skill")
        _validate_rule_id(self.rule_id)
        _validate_bool(self.inflicts_wound, "inflicts_wound")
        conditions = tuple(self.failure_conditions)
        if not all(isinstance(item, Condition) for item in conditions):
            raise TypeError("failure_conditions must contain Condition values")
        if len(set(conditions)) != len(conditions):
            raise ValueError("failure_conditions must be unique")
        if not self.inflicts_wound and not conditions:
            raise ValueError(
                "a Hazard must inflict a Wound or at least one Condition"
            )
        object.__setattr__(self, "failure_conditions", conditions)


ImpactSpec = DamageImpactSpec | ConditionImpactSpec | HazardImpactSpec


@dataclass(frozen=True, slots=True)
class ProneBeforeGiveGroundSpec:
    """Inflict Prone on a hit before resolving any repeated Staggered."""

    rule_id: str
    affects_monstrosities: bool = True

    def __post_init__(self) -> None:
        _validate_rule_id(self.rule_id)
        _validate_bool(self.affects_monstrosities, "affects_monstrosities")


@dataclass(frozen=True, slots=True)
class NearbyTargetsStaggerSpec:
    """On a hit, request Staggered for creatures near the primary target."""

    rule_id: str

    def __post_init__(self) -> None:
        _validate_rule_id(self.rule_id)


SecondaryEffectSpec = ProneBeforeGiveGroundSpec | NearbyTargetsStaggerSpec


@dataclass(frozen=True, slots=True)
class AttackRequest:
    id: str
    attacker_test: TestRequest
    defender_test: TestRequest | None
    impact_spec: ImpactSpec
    is_close_range: bool
    attacker_is_staggered: bool
    close_miss_stagger_immunity_rule_id: str | None = None
    secondary_effects: tuple[SecondaryEffectSpec, ...] = field(
        default_factory=tuple
    )

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
        if not isinstance(
            self.impact_spec,
            (DamageImpactSpec, ConditionImpactSpec, HazardImpactSpec),
        ):
            raise TypeError("impact_spec must be an ImpactSpec")
        _validate_bool(self.is_close_range, "is_close_range")
        _validate_bool(self.attacker_is_staggered, "attacker_is_staggered")
        if self.close_miss_stagger_immunity_rule_id is not None:
            _validate_rule_id(self.close_miss_stagger_immunity_rule_id)
        effects = tuple(self.secondary_effects)
        if not all(
            isinstance(
                item,
                (ProneBeforeGiveGroundSpec, NearbyTargetsStaggerSpec),
            )
            for item in effects
        ):
            raise TypeError(
                "secondary_effects must contain SecondaryEffectSpec values"
            )
        rule_ids = tuple(item.rule_id for item in effects)
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("secondary effect rule_ids must be unique")
        object.__setattr__(self, "secondary_effects", effects)


@dataclass(frozen=True, slots=True)
class AttackResult:
    request_id: str
    attacker_test: TestResult
    defender_test: TestResult | None
    outcome: AttackOutcome
    success_margin: int
    impact_spec: ImpactSpec
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


def _validate_positive_int(value: int, name: str) -> None:
    _validate_int(value, name)
    if value < 1:
        raise ValueError(f"{name} must be positive")


def _validate_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")
