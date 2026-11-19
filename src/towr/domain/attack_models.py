from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from towr.domain.condition_models import (
    Condition,
    EffectClassification,
    RepeatedConditionReplacement,
)
from towr.domain.test_models import Skill, TestRequest, TestResult
from towr.domain.brawn_impact_models import BrawnDisplacementImpactSpec


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
    armoured: bool | None = field(default=None, kw_only=True)
    mundane_armour_ward: bool = field(default=False, kw_only=True)

    def __post_init__(self) -> None:
        _validate_non_negative_int(self.toughness, "toughness")
        _validate_non_negative_int(self.bonus, "resilience bonus")
        if self.armoured is not None and type(self.armoured) is not bool:
            raise TypeError("armoured must be an exact boolean or None")
        _validate_bool(self.mundane_armour_ward, "mundane_armour_ward")

    @property
    def total(self) -> int:
        return self.toughness + self.bonus

    @property
    def is_armoured(self) -> bool:
        return self.armoured if self.armoured is not None else self.bonus > 0


@dataclass(frozen=True, slots=True)
class DamageModifier:
    rule_id: str
    amount: int
    armour_specific: bool = field(default=False, kw_only=True)
    magical_source: bool = field(default=False, kw_only=True)

    def __post_init__(self) -> None:
        _validate_rule_id(self.rule_id)
        _validate_non_zero_int(self.amount, "damage modifier amount")
        _validate_bool(self.armour_specific, "armour_specific")
        _validate_bool(self.magical_source, "magical_source")


@dataclass(frozen=True, slots=True)
class ResilienceModifier:
    rule_id: str
    amount: int

    def __post_init__(self) -> None:
        _validate_rule_id(self.rule_id)
        _validate_non_zero_int(self.amount, "resilience modifier amount")


@dataclass(frozen=True, slots=True)
class DamageImpactSpec:
    """Base weapon impact; contributor modifiers retain their own origins.

    ``magical_source`` describes this primary Damage/ignores-armour source. It
    never grants magical provenance to another weapon's DamageModifier.
    """
    damage: DamageProfile
    resilience: ResilienceProfile
    ignores_armour: bool = False
    damage_modifiers: tuple[DamageModifier, ...] = field(default_factory=tuple)
    resilience_modifiers: tuple[ResilienceModifier, ...] = field(
        default_factory=tuple
    )
    magical_source: bool = field(default=False, kw_only=True)

    def __post_init__(self) -> None:
        if not isinstance(self.damage, DamageProfile):
            raise TypeError("damage must be a DamageProfile")
        if not isinstance(self.resilience, ResilienceProfile):
            raise TypeError("resilience must be a ResilienceProfile")
        _validate_bool(self.ignores_armour, "ignores_armour")
        _validate_bool(self.magical_source, "magical_source")
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


def _target_armour_ward(spec: DamageImpactSpec) -> bool:
    """Read exact target protection without combining independent origins."""
    if not isinstance(spec, DamageImpactSpec):
        raise TypeError('armour protection requires a DamageImpactSpec')
    _validate_bool(spec.magical_source, 'magical_source')
    _validate_bool(spec.ignores_armour, 'ignores_armour')
    if not isinstance(spec.resilience, ResilienceProfile):
        raise TypeError('armour protection requires its full ResilienceProfile')
    _validate_bool(spec.resilience.mundane_armour_ward, 'mundane_armour_ward')
    return spec.resilience.mundane_armour_ward


def effective_damage_modifiers(spec: DamageImpactSpec) -> tuple[DamageModifier, ...]:
    """GM85 Meteoric Iron cancels mundane bonuses against armoured targets.

    Each modifier owns its origin independently of the primary weapon. Other
    damage (including penalties) and the original prepared source remain intact.
    The same projection serves actual damage and tactical estimates.
    """
    ward = _target_armour_ward(spec)
    modifiers = tuple(spec.damage_modifiers)
    for modifier in modifiers:
        if not isinstance(modifier, DamageModifier):
            raise TypeError('damage protection requires typed DamageModifiers')
        _validate_bool(modifier.armour_specific, 'armour_specific')
        _validate_bool(modifier.magical_source, 'magical_source')
    return tuple(modifier for modifier in modifiers
        if not (ward and modifier.armour_specific and modifier.amount > 0
            and not modifier.magical_source))


def effective_ignores_armour(spec: DamageImpactSpec) -> bool:
    """Retain a weapon's printed trait, cancel only its mundane application."""
    ward = _target_armour_ward(spec)
    return spec.ignores_armour and (spec.magical_source or not ward)


def armour_ward_cancels_effects(spec: DamageImpactSpec) -> bool:
    """Whether this damage event actually invokes the GM85 protection rule."""
    ward = _target_armour_ward(spec)
    modifiers = effective_damage_modifiers(spec)
    return ward and ((spec.ignores_armour and not spec.magical_source)
        or len(modifiers) != len(spec.damage_modifiers))


@dataclass(frozen=True, slots=True)
class ConditionImpactSpec:
    condition: Condition
    rule_id: str
    classification: EffectClassification = EffectClassification.UNCLASSIFIED

    def __post_init__(self) -> None:
        if not isinstance(self.condition, Condition):
            raise TypeError("condition must be a Condition")
        _validate_rule_id(self.rule_id)
        if not isinstance(self.classification, EffectClassification):
            raise TypeError(
                "classification must be an EffectClassification"
            )


@dataclass(frozen=True, slots=True)
class HazardImpactSpec:
    rating: int
    avoidance_skill: Skill
    rule_id: str
    inflicts_wound: bool = True
    failure_conditions: tuple[Condition, ...] = field(default_factory=tuple)
    classification: EffectClassification = EffectClassification.UNCLASSIFIED
    repeated_condition_replacements: tuple[
        RepeatedConditionReplacement, ...
    ] = field(default_factory=tuple)

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
        replacements = tuple(self.repeated_condition_replacements)
        if not all(
            isinstance(item, RepeatedConditionReplacement)
            for item in replacements
        ):
            raise TypeError(
                "repeated_condition_replacements must contain "
                "RepeatedConditionReplacement values"
            )
        replaced_conditions = tuple(item.condition for item in replacements)
        if len(set(replaced_conditions)) != len(replaced_conditions):
            raise ValueError(
                "repeated Condition replacements must be unique"
            )
        if not set(replaced_conditions).issubset(conditions):
            raise ValueError(
                "repeated Condition replacements must target failure_conditions"
            )
        if not self.inflicts_wound and not conditions:
            raise ValueError(
                "a Hazard must inflict a Wound or at least one Condition"
            )
        if not isinstance(self.classification, EffectClassification):
            raise TypeError(
                "classification must be an EffectClassification"
            )
        object.__setattr__(self, "failure_conditions", conditions)
        object.__setattr__(
            self,
            "repeated_condition_replacements",
            replacements,
        )


ImpactSpec = DamageImpactSpec | ConditionImpactSpec | HazardImpactSpec | BrawnDisplacementImpactSpec


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


@dataclass(frozen=True, slots=True)
class ConditionAfterGiveGroundSpec:
    """Apply a non-Staggered Condition after the target Gives Ground."""

    condition: Condition
    rule_id: str
    classification: EffectClassification = EffectClassification.UNCLASSIFIED

    def __post_init__(self) -> None:
        if not isinstance(self.condition, Condition):
            raise TypeError("condition must be a Condition")
        if self.condition is Condition.STAGGERED:
            raise ValueError(
                "Staggered after Give Ground requires the Stagger impact policy"
            )
        _validate_rule_id(self.rule_id)
        if not isinstance(self.classification, EffectClassification):
            raise TypeError(
                "classification must be an EffectClassification"
            )


@dataclass(frozen=True, slots=True)
class ConditionOnHitSpec:
    """Apply a non-Staggered Condition after resolving normal Damage."""

    condition: Condition
    rule_id: str
    classification: EffectClassification = EffectClassification.UNCLASSIFIED

    def __post_init__(self) -> None:
        if not isinstance(self.condition, Condition):
            raise TypeError("condition must be a Condition")
        if self.condition is Condition.STAGGERED:
            raise ValueError(
                "Staggered on hit requires the Stagger impact policy"
            )
        _validate_rule_id(self.rule_id)
        if not isinstance(self.classification, EffectClassification):
            raise TypeError(
                "classification must be an EffectClassification"
            )


@dataclass(frozen=True, slots=True)
class ConditionOnGiveGroundOrWoundSpec:
    """Apply a Condition after Give Ground or an accepted Wound."""

    condition: Condition
    rule_id: str
    classification: EffectClassification = EffectClassification.UNCLASSIFIED

    def __post_init__(self) -> None:
        if not isinstance(self.condition, Condition):
            raise TypeError("condition must be a Condition")
        if self.condition is Condition.STAGGERED:
            raise ValueError(
                "Staggered requires the Stagger impact policy"
            )
        _validate_rule_id(self.rule_id)
        if not isinstance(self.classification, EffectClassification):
            raise TypeError(
                "classification must be an EffectClassification"
            )


SecondaryEffectSpec = (
    ProneBeforeGiveGroundSpec
    | NearbyTargetsStaggerSpec
    | ConditionAfterGiveGroundSpec
    | ConditionOnHitSpec
    | ConditionOnGiveGroundOrWoundSpec
)


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
            (DamageImpactSpec, ConditionImpactSpec, HazardImpactSpec, BrawnDisplacementImpactSpec),
        ):
            raise TypeError("impact_spec must be an ImpactSpec")
        if isinstance(self.impact_spec, BrawnDisplacementImpactSpec):
            if type(self.impact_spec) is not BrawnDisplacementImpactSpec:
                raise TypeError('Brawn displacement requires its exact committed source')
            from dataclasses import replace
            replace(self.impact_spec)
        _validate_bool(self.is_close_range, "is_close_range")
        _validate_bool(self.attacker_is_staggered, "attacker_is_staggered")
        if self.close_miss_stagger_immunity_rule_id is not None:
            _validate_rule_id(self.close_miss_stagger_immunity_rule_id)
        effects = tuple(self.secondary_effects)
        if not all(
            isinstance(
                item,
                (
                    ProneBeforeGiveGroundSpec,
                    NearbyTargetsStaggerSpec,
                    ConditionAfterGiveGroundSpec,
                    ConditionOnHitSpec,
                    ConditionOnGiveGroundOrWoundSpec,
                ),
            )
            for item in effects
        ):
            raise TypeError(
                "secondary_effects must contain SecondaryEffectSpec values"
            )
        rule_ids = tuple(item.rule_id for item in effects)
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("secondary effect rule_ids must be unique")
        damage_only_effects = (
            ConditionOnHitSpec,
            ConditionOnGiveGroundOrWoundSpec,
        )
        if any(
            isinstance(item, damage_only_effects) for item in effects
        ) and not isinstance(self.impact_spec, DamageImpactSpec):
            raise ValueError(
                "on-hit/outcome Conditions require a normal DamageImpactSpec"
            )
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
