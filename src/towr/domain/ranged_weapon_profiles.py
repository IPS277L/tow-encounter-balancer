from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from towr.domain.test_models import DiceModifier


RANGED_WEAPON_RELOAD_RULE_ID = "RULE-EQUIPMENT-004:reload"
RANGED_WEAPON_PROFILE_RULE_ID = "RULE-EQUIPMENT-004:ranged-weapon-profile"
REPEATER_SHOOTING_BONUS_RULE_ID = (
    "RULE-EQUIPMENT-004:repeater-shooting-bonus"
)


class RangedWeaponId(str, Enum):
    SLING = "sling"
    SHORTBOW = "shortbow"
    WARBOW = "warbow"
    LONGBOW = "longbow"
    CROSSBOW = "crossbow"
    PISTOL = "pistol"
    HANDGUN = "handgun"
    BLUNDERBUSS = "blunderbuss"
    HOCHLAND_LONG_RIFLE = "hochland_long_rifle"
    REPEATER_HANDBOW = "repeater_handbow"
    REPEATER_CROSSBOW = "repeater_crossbow"
    REPEATER_PISTOL = "repeater_pistol"
    REPEATER_HANDGUN = "repeater_handgun"


class RangedReloadTrigger(str, Enum):
    FREE_WITH_ATTACK = "free_with_attack"
    AFTER_EVERY_SHOT = "after_every_shot"
    AFTER_OPTIONAL_BONUS = "after_optional_bonus"


class RangedWeaponRange(str, Enum):
    CLOSE = "close"
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    EXTREME = "extreme"


class RangedWeaponHands(str, Enum):
    ONE_HANDED = "1h"
    TWO_HANDED = "2h"


class RangedWeaponDamageKind(str, Enum):
    FIXED = "fixed"
    STRENGTH = "strength"


_RANGE_ORDER = {
    range_band: order
    for order, range_band in enumerate(RangedWeaponRange)
}


@dataclass(frozen=True, slots=True)
class RangedWeaponCombatProfile:
    weapon_id: RangedWeaponId
    optimum_range_min: RangedWeaponRange
    optimum_range_max: RangedWeaponRange
    damage_kind: RangedWeaponDamageKind
    damage_value: int | None
    hands: RangedWeaponHands
    maximum_range_override: RangedWeaponRange | None = None
    ignores_armour: bool = False
    requires_aim_before_attack: bool = False
    requires_blackpowder_lore: bool = False
    short_range_shooting_bonus_dice: int = 0
    armoured_target_damage_bonus: int = 0
    wounds_table_bonus_dice: int = 0
    staggers_nearby_targets_on_hit: bool = False
    rule_id: str = RANGED_WEAPON_PROFILE_RULE_ID

    def __post_init__(self) -> None:
        if not isinstance(self.weapon_id, RangedWeaponId):
            raise TypeError("weapon_id must be a RangedWeaponId")
        if not isinstance(self.optimum_range_min, RangedWeaponRange):
            raise TypeError("optimum_range_min must be a RangedWeaponRange")
        if not isinstance(self.optimum_range_max, RangedWeaponRange):
            raise TypeError("optimum_range_max must be a RangedWeaponRange")
        if (
            _RANGE_ORDER[self.optimum_range_min]
            > _RANGE_ORDER[self.optimum_range_max]
        ):
            raise ValueError("optimum range must be ordered")
        if not isinstance(self.damage_kind, RangedWeaponDamageKind):
            raise TypeError("damage_kind must be a RangedWeaponDamageKind")
        if self.damage_kind is RangedWeaponDamageKind.STRENGTH:
            if self.damage_value is not None:
                raise ValueError("Strength damage has no fixed value")
        else:
            if self.damage_value is None:
                raise ValueError("fixed damage requires a value")
            _validate_positive_int(self.damage_value, "damage_value")
        if not isinstance(self.hands, RangedWeaponHands):
            raise TypeError("hands must be a RangedWeaponHands")
        if self.maximum_range_override is not None:
            if not isinstance(
                self.maximum_range_override,
                RangedWeaponRange,
            ):
                raise TypeError(
                    "maximum_range_override must be a RangedWeaponRange or None"
                )
            if self.hands is RangedWeaponHands.ONE_HANDED:
                raise ValueError("one-handed maximum range is always Long")
            if (
                _RANGE_ORDER[self.maximum_range_override]
                < _RANGE_ORDER[self.optimum_range_max]
            ):
                raise ValueError("maximum range cannot precede optimum range")
        _validate_bool(self.ignores_armour, "ignores_armour")
        _validate_bool(
            self.requires_aim_before_attack,
            "requires_aim_before_attack",
        )
        _validate_bool(
            self.requires_blackpowder_lore,
            "requires_blackpowder_lore",
        )
        _validate_non_negative_int(
            self.short_range_shooting_bonus_dice,
            "short_range_shooting_bonus_dice",
        )
        _validate_non_negative_int(
            self.armoured_target_damage_bonus,
            "armoured_target_damage_bonus",
        )
        _validate_non_negative_int(
            self.wounds_table_bonus_dice,
            "wounds_table_bonus_dice",
        )
        _validate_bool(
            self.staggers_nearby_targets_on_hit,
            "staggers_nearby_targets_on_hit",
        )
        _validate_non_empty_string(self.rule_id, "combat profile rule_id")
        if self.rule_id != RANGED_WEAPON_PROFILE_RULE_ID:
            raise ValueError("ranged combat profile uses an unknown rule")

    @property
    def maximum_range(self) -> RangedWeaponRange | None:
        if self.maximum_range_override is not None:
            return self.maximum_range_override
        if self.hands is RangedWeaponHands.ONE_HANDED:
            return RangedWeaponRange.LONG
        return None

    @property
    def has_gm_defined_maximum_range(self) -> bool:
        return self.maximum_range is None

    @property
    def reload(self) -> RangedWeaponReloadProfile:
        return ranged_weapon_reload_profile(self.weapon_id)


@dataclass(frozen=True, slots=True)
class RangedWeaponReloadProfile:
    weapon_id: RangedWeaponId
    trigger: RangedReloadTrigger
    required_successes: int | None
    optional_shooting_bonus_dice: int = 0
    rule_id: str = RANGED_WEAPON_RELOAD_RULE_ID

    def __post_init__(self) -> None:
        if not isinstance(self.weapon_id, RangedWeaponId):
            raise TypeError("weapon_id must be a RangedWeaponId")
        if not isinstance(self.trigger, RangedReloadTrigger):
            raise TypeError("trigger must be a RangedReloadTrigger")
        if self.required_successes is not None:
            _validate_positive_int(
                self.required_successes,
                "required_successes",
            )
        _validate_non_negative_int(
            self.optional_shooting_bonus_dice,
            "optional_shooting_bonus_dice",
        )
        _validate_non_empty_string(self.rule_id, "reload profile rule_id")
        if self.rule_id != RANGED_WEAPON_RELOAD_RULE_ID:
            raise ValueError("ranged reload profile uses an unknown rule")

        if self.trigger is RangedReloadTrigger.FREE_WITH_ATTACK:
            if (
                self.required_successes is not None
                or self.optional_shooting_bonus_dice != 0
            ):
                raise ValueError("free reload profile cannot require progress")
        elif self.trigger is RangedReloadTrigger.AFTER_EVERY_SHOT:
            if (
                self.required_successes is None
                or self.optional_shooting_bonus_dice != 0
            ):
                raise ValueError("ordinary reload profile requires only a target")
        elif (
            self.required_successes is None
            or self.optional_shooting_bonus_dice < 1
        ):
            raise ValueError("conditional reload requires its Shooting bonus")

    @property
    def requires_exacting_reload(self) -> bool:
        return self.required_successes is not None

    def optional_bonus_modifier(self) -> DiceModifier:
        if self.trigger is not RangedReloadTrigger.AFTER_OPTIONAL_BONUS:
            raise ValueError("only a Repeater profile has an optional bonus")
        return DiceModifier(
            rule_id=REPEATER_SHOOTING_BONUS_RULE_ID,
            amount=self.optional_shooting_bonus_dice,
        )


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _validate_positive_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value < 1:
        raise ValueError(f"{name} must be positive")


def _validate_non_negative_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must not be negative")


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")


RANGED_WEAPON_RELOAD_PROFILES: tuple[RangedWeaponReloadProfile, ...] = (
    RangedWeaponReloadProfile(
        RangedWeaponId.SLING,
        RangedReloadTrigger.FREE_WITH_ATTACK,
        None,
    ),
    RangedWeaponReloadProfile(
        RangedWeaponId.SHORTBOW,
        RangedReloadTrigger.FREE_WITH_ATTACK,
        None,
    ),
    RangedWeaponReloadProfile(
        RangedWeaponId.WARBOW,
        RangedReloadTrigger.FREE_WITH_ATTACK,
        None,
    ),
    RangedWeaponReloadProfile(
        RangedWeaponId.LONGBOW,
        RangedReloadTrigger.FREE_WITH_ATTACK,
        None,
    ),
    RangedWeaponReloadProfile(
        RangedWeaponId.CROSSBOW,
        RangedReloadTrigger.AFTER_EVERY_SHOT,
        2,
    ),
    RangedWeaponReloadProfile(
        RangedWeaponId.PISTOL,
        RangedReloadTrigger.AFTER_EVERY_SHOT,
        3,
    ),
    RangedWeaponReloadProfile(
        RangedWeaponId.HANDGUN,
        RangedReloadTrigger.AFTER_EVERY_SHOT,
        3,
    ),
    RangedWeaponReloadProfile(
        RangedWeaponId.BLUNDERBUSS,
        RangedReloadTrigger.AFTER_EVERY_SHOT,
        3,
    ),
    RangedWeaponReloadProfile(
        RangedWeaponId.HOCHLAND_LONG_RIFLE,
        RangedReloadTrigger.AFTER_EVERY_SHOT,
        4,
    ),
    RangedWeaponReloadProfile(
        RangedWeaponId.REPEATER_HANDBOW,
        RangedReloadTrigger.AFTER_OPTIONAL_BONUS,
        3,
        1,
    ),
    RangedWeaponReloadProfile(
        RangedWeaponId.REPEATER_CROSSBOW,
        RangedReloadTrigger.AFTER_OPTIONAL_BONUS,
        3,
        1,
    ),
    RangedWeaponReloadProfile(
        RangedWeaponId.REPEATER_PISTOL,
        RangedReloadTrigger.AFTER_OPTIONAL_BONUS,
        3,
        2,
    ),
    RangedWeaponReloadProfile(
        RangedWeaponId.REPEATER_HANDGUN,
        RangedReloadTrigger.AFTER_OPTIONAL_BONUS,
        5,
        3,
    ),
)


_RELOAD_PROFILE_BY_ID = {
    profile.weapon_id: profile for profile in RANGED_WEAPON_RELOAD_PROFILES
}
if len(_RELOAD_PROFILE_BY_ID) != len(RangedWeaponId):
    raise RuntimeError("ranged reload profile catalog is incomplete")


def ranged_weapon_reload_profile(
    weapon_id: RangedWeaponId,
) -> RangedWeaponReloadProfile:
    if not isinstance(weapon_id, RangedWeaponId):
        raise TypeError("weapon_id must be a RangedWeaponId")
    return _RELOAD_PROFILE_BY_ID[weapon_id]


RANGED_WEAPON_COMBAT_PROFILES: tuple[RangedWeaponCombatProfile, ...] = (
    RangedWeaponCombatProfile(
        weapon_id=RangedWeaponId.SLING,
        optimum_range_min=RangedWeaponRange.MEDIUM,
        optimum_range_max=RangedWeaponRange.MEDIUM,
        damage_kind=RangedWeaponDamageKind.STRENGTH,
        damage_value=None,
        hands=RangedWeaponHands.ONE_HANDED,
    ),
    RangedWeaponCombatProfile(
        weapon_id=RangedWeaponId.SHORTBOW,
        optimum_range_min=RangedWeaponRange.SHORT,
        optimum_range_max=RangedWeaponRange.MEDIUM,
        damage_kind=RangedWeaponDamageKind.FIXED,
        damage_value=3,
        hands=RangedWeaponHands.TWO_HANDED,
        short_range_shooting_bonus_dice=1,
    ),
    RangedWeaponCombatProfile(
        weapon_id=RangedWeaponId.WARBOW,
        optimum_range_min=RangedWeaponRange.MEDIUM,
        optimum_range_max=RangedWeaponRange.LONG,
        damage_kind=RangedWeaponDamageKind.FIXED,
        damage_value=3,
        hands=RangedWeaponHands.TWO_HANDED,
    ),
    RangedWeaponCombatProfile(
        weapon_id=RangedWeaponId.LONGBOW,
        optimum_range_min=RangedWeaponRange.MEDIUM,
        optimum_range_max=RangedWeaponRange.LONG,
        damage_kind=RangedWeaponDamageKind.FIXED,
        damage_value=4,
        hands=RangedWeaponHands.TWO_HANDED,
    ),
    RangedWeaponCombatProfile(
        weapon_id=RangedWeaponId.CROSSBOW,
        optimum_range_min=RangedWeaponRange.SHORT,
        optimum_range_max=RangedWeaponRange.LONG,
        damage_kind=RangedWeaponDamageKind.FIXED,
        damage_value=4,
        hands=RangedWeaponHands.TWO_HANDED,
        armoured_target_damage_bonus=1,
    ),
    RangedWeaponCombatProfile(
        weapon_id=RangedWeaponId.PISTOL,
        optimum_range_min=RangedWeaponRange.CLOSE,
        optimum_range_max=RangedWeaponRange.SHORT,
        damage_kind=RangedWeaponDamageKind.FIXED,
        damage_value=5,
        hands=RangedWeaponHands.ONE_HANDED,
        ignores_armour=True,
        requires_blackpowder_lore=True,
    ),
    RangedWeaponCombatProfile(
        weapon_id=RangedWeaponId.HANDGUN,
        optimum_range_min=RangedWeaponRange.MEDIUM,
        optimum_range_max=RangedWeaponRange.LONG,
        damage_kind=RangedWeaponDamageKind.FIXED,
        damage_value=5,
        hands=RangedWeaponHands.TWO_HANDED,
        ignores_armour=True,
        requires_blackpowder_lore=True,
    ),
    RangedWeaponCombatProfile(
        weapon_id=RangedWeaponId.BLUNDERBUSS,
        optimum_range_min=RangedWeaponRange.SHORT,
        optimum_range_max=RangedWeaponRange.SHORT,
        damage_kind=RangedWeaponDamageKind.FIXED,
        damage_value=4,
        hands=RangedWeaponHands.TWO_HANDED,
        maximum_range_override=RangedWeaponRange.MEDIUM,
        requires_blackpowder_lore=True,
        short_range_shooting_bonus_dice=2,
        staggers_nearby_targets_on_hit=True,
    ),
    RangedWeaponCombatProfile(
        weapon_id=RangedWeaponId.HOCHLAND_LONG_RIFLE,
        optimum_range_min=RangedWeaponRange.MEDIUM,
        optimum_range_max=RangedWeaponRange.EXTREME,
        damage_kind=RangedWeaponDamageKind.FIXED,
        damage_value=6,
        hands=RangedWeaponHands.TWO_HANDED,
        ignores_armour=True,
        requires_aim_before_attack=True,
        requires_blackpowder_lore=True,
        wounds_table_bonus_dice=1,
    ),
    RangedWeaponCombatProfile(
        weapon_id=RangedWeaponId.REPEATER_HANDBOW,
        optimum_range_min=RangedWeaponRange.CLOSE,
        optimum_range_max=RangedWeaponRange.SHORT,
        damage_kind=RangedWeaponDamageKind.FIXED,
        damage_value=4,
        hands=RangedWeaponHands.ONE_HANDED,
    ),
    RangedWeaponCombatProfile(
        weapon_id=RangedWeaponId.REPEATER_CROSSBOW,
        optimum_range_min=RangedWeaponRange.SHORT,
        optimum_range_max=RangedWeaponRange.MEDIUM,
        damage_kind=RangedWeaponDamageKind.FIXED,
        damage_value=4,
        hands=RangedWeaponHands.TWO_HANDED,
    ),
    RangedWeaponCombatProfile(
        weapon_id=RangedWeaponId.REPEATER_PISTOL,
        optimum_range_min=RangedWeaponRange.CLOSE,
        optimum_range_max=RangedWeaponRange.SHORT,
        damage_kind=RangedWeaponDamageKind.FIXED,
        damage_value=5,
        hands=RangedWeaponHands.ONE_HANDED,
        ignores_armour=True,
        requires_blackpowder_lore=True,
    ),
    RangedWeaponCombatProfile(
        weapon_id=RangedWeaponId.REPEATER_HANDGUN,
        optimum_range_min=RangedWeaponRange.SHORT,
        optimum_range_max=RangedWeaponRange.LONG,
        damage_kind=RangedWeaponDamageKind.FIXED,
        damage_value=5,
        hands=RangedWeaponHands.TWO_HANDED,
        ignores_armour=True,
        requires_blackpowder_lore=True,
    ),
)


_COMBAT_PROFILE_BY_ID = {
    profile.weapon_id: profile for profile in RANGED_WEAPON_COMBAT_PROFILES
}
if len(_COMBAT_PROFILE_BY_ID) != len(RangedWeaponId):
    raise RuntimeError("ranged combat profile catalog is incomplete")


def ranged_weapon_combat_profile(
    weapon_id: RangedWeaponId,
) -> RangedWeaponCombatProfile:
    if not isinstance(weapon_id, RangedWeaponId):
        raise TypeError("weapon_id must be a RangedWeaponId")
    return _COMBAT_PROFILE_BY_ID[weapon_id]
