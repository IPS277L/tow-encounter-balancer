"""Shared weapon range eligibility (PG1.4 IV93–96; Dragon Bow GM1.1 VI82).

This prepares only range permission and the raw outside-optimum penalty. The
caller proves any actual Charge and owns visibility penalties, Aim, movement,
the Short-range Shooting bonus and other action preconditions. In particular,
Dragon Bow quality can suppress the raw penalty without granting permission.
An absent GM maximum for 2H Shooting is missing scene context, not infinity.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.test_models import DiceModifier
from towr.domain.weapon_catalog import WeaponGroup, WeaponKind, weapon_profile


OUTSIDE_OPTIMUM_RANGE_RULE_ID = 'RULE-COMBAT-006:outside-optimum-range'
_RANGES = tuple(RangedWeaponRange)
_RANGE_RANK = {value: index for index, value in enumerate(_RANGES)}


class WeaponRangeReason(str, Enum):
    IN_RANGE = 'in_range'
    OUTSIDE_OPTIMUM = 'outside_optimum'
    CHARGE_THROWING = 'charge_throwing'
    TARGET_NOT_VISIBLE = 'target_not_visible'
    SHOOTING_CHARGE_FORBIDDEN = 'shooting_charge_forbidden'
    GM_SHOOTING_MAXIMUM_REQUIRED = 'gm_shooting_maximum_required'
    TARGET_BEYOND_MAXIMUM = 'target_beyond_maximum'
    CLOSE_ENEMY_BLOCKS_SHOOTING = 'close_enemy_blocks_shooting'
    TARGET_OUTSIDE_THROWING_OPTIMUM = 'target_outside_throwing_optimum'


def _strength(value: int) -> None:
    if type(value) is not int:
        raise TypeError('actual Strength must be an exact int')
    if value < 1:
        raise ValueError('actual Strength must be positive')


def _range(value: RangedWeaponRange, label: str) -> None:
    if type(value) is not RangedWeaponRange:
        raise TypeError(label + ' requires its exact range band')


def weapon_optimum_range(kind: WeaponKind, *, strength: int
        ) -> tuple[RangedWeaponRange, RangedWeaponRange] | None:
    """Return the printed band, extending only Throwing's upper end at S≥4.

    Melee has no optimum band. Strength supplies a single extra step, even
    when greater than four; it does not change a Shooting weapon's band.
    """
    profile = weapon_profile(kind)
    _strength(strength)
    if profile.group is WeaponGroup.MELEE:
        return None
    low, high = profile.optimum_range_min, profile.optimum_range_max
    if profile.group is WeaponGroup.THROWING and strength >= 4:
        high = _RANGES[min(_RANGE_RANK[high] + 1, len(_RANGES) - 1)]
    return low, high


def weapon_target_within_optimum(kind: WeaponKind, target_range: RangedWeaponRange,
        *, strength: int) -> bool:
    """Test the actual optimum band; Melee, having no such band, returns False."""
    optimum = weapon_optimum_range(kind, strength=strength)
    _range(target_range, 'actual target range')
    return (optimum is not None
        and _RANGE_RANK[optimum[0]] <= _RANGE_RANK[target_range]
        <= _RANGE_RANK[optimum[1]])


@dataclass(frozen=True, slots=True)
class WeaponRangeContext:
    target_range: RangedWeaponRange
    strength: int
    has_enemy_in_close_range: bool = False
    charging: bool = False
    gm_shooting_maximum: RangedWeaponRange | None = None
    target_visible: bool = True

    def __post_init__(self) -> None:
        _range(self.target_range, 'actual target range')
        _strength(self.strength)
        if self.gm_shooting_maximum is not None:
            _range(self.gm_shooting_maximum, 'GM Shooting maximum')
        for name in ('has_enemy_in_close_range', 'charging', 'target_visible'):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name + ' requires an exact bool')


def _readmit_context(context: WeaponRangeContext) -> None:
    if type(context) is not WeaponRangeContext:
        raise TypeError('range assessment requires its exact WeaponRangeContext')
    context.__post_init__()


def _maximum_range(kind: WeaponKind, context: WeaponRangeContext
        ) -> RangedWeaponRange | None:
    profile = weapon_profile(kind)
    if profile.group is WeaponGroup.THROWING:
        return weapon_optimum_range(kind, strength=context.strength)[1]
    # Printed limits (Melee, 1H Shooting, Blunderbuss) cannot be expanded by
    # the GM fallback intended for otherwise unbounded 2H Shooting profiles.
    return profile.maximum_range or context.gm_shooting_maximum


def _assessment_values(kind: WeaponKind, context: WeaponRangeContext
        ) -> tuple[bool, WeaponRangeReason, tuple[DiceModifier, ...]]:
    profile = weapon_profile(kind)
    _readmit_context(context)
    if kind is WeaponKind.DRAGON_BOW and not context.target_visible:
        return False, WeaponRangeReason.TARGET_NOT_VISIBLE, ()
    if profile.group is WeaponGroup.MELEE:
        if _RANGE_RANK[context.target_range] > _RANGE_RANK[profile.maximum_range]:
            return False, WeaponRangeReason.TARGET_BEYOND_MAXIMUM, ()
        return True, WeaponRangeReason.IN_RANGE, ()
    if profile.group is WeaponGroup.THROWING:
        if context.charging:
            return True, WeaponRangeReason.CHARGE_THROWING, ()
        if not weapon_target_within_optimum(kind, context.target_range,
                strength=context.strength):
            return False, WeaponRangeReason.TARGET_OUTSIDE_THROWING_OPTIMUM, ()
        return True, WeaponRangeReason.IN_RANGE, ()
    if context.charging:
        return False, WeaponRangeReason.SHOOTING_CHARGE_FORBIDDEN, ()
    close_enemy = (context.has_enemy_in_close_range
        or context.target_range is RangedWeaponRange.CLOSE)
    if close_enemy and not weapon_target_within_optimum(kind,
            RangedWeaponRange.CLOSE, strength=context.strength):
        return False, WeaponRangeReason.CLOSE_ENEMY_BLOCKS_SHOOTING, ()
    maximum = _maximum_range(kind, context)
    if maximum is None:
        return False, WeaponRangeReason.GM_SHOOTING_MAXIMUM_REQUIRED, ()
    if _RANGE_RANK[context.target_range] > _RANGE_RANK[maximum]:
        return False, WeaponRangeReason.TARGET_BEYOND_MAXIMUM, ()
    if not weapon_target_within_optimum(kind, context.target_range,
            strength=context.strength):
        return (True, WeaponRangeReason.OUTSIDE_OPTIMUM,
            (DiceModifier(OUTSIDE_OPTIMUM_RANGE_RULE_ID, -1),))
    return True, WeaponRangeReason.IN_RANGE, ()


@dataclass(frozen=True, slots=True)
class WeaponRangeAssessment:
    """Canonical result retaining the catalogue kind and actual scene context."""
    kind: WeaponKind
    context: WeaponRangeContext
    allowed: bool
    reason: WeaponRangeReason
    dice_modifiers: tuple[DiceModifier, ...]

    def __post_init__(self) -> None:
        if type(self.allowed) is not bool:
            raise TypeError('range permission requires an exact bool')
        if type(self.reason) is not WeaponRangeReason:
            raise TypeError('range reason requires its exact typed value')
        if type(self.dice_modifiers) is not tuple:
            raise TypeError('range modifiers require an exact tuple')
        for modifier in self.dice_modifiers:
            if type(modifier) is not DiceModifier:
                raise TypeError('range modifier requires its exact DiceModifier')
            modifier.__post_init__()
            if type(modifier.amount) is not int or type(modifier.bypasses_pool_cap) is not bool:
                raise TypeError('range modifier requires exact amount and cap facts')
        expected = _assessment_values(self.kind, self.context)
        if (self.allowed, self.reason, self.dice_modifiers) != expected:
            raise ValueError('range assessment must follow its actual weapon and context')

    @property
    def optimum_range(self) -> tuple[RangedWeaponRange, RangedWeaponRange] | None:
        return weapon_optimum_range(self.kind, strength=self.context.strength)

    @property
    def maximum_range(self) -> RangedWeaponRange | None:
        """Ordinary maximum; a proven Throwing Charge is a separate exception."""
        return _maximum_range(self.kind, self.context)


def assess_weapon_attack_range(kind: WeaponKind,
        context: WeaponRangeContext) -> WeaponRangeAssessment:
    allowed, reason, modifiers = _assessment_values(kind, context)
    return WeaponRangeAssessment(kind, context, allowed, reason, modifiers)
