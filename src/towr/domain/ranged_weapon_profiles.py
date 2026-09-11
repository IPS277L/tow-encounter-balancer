from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from towr.domain.test_models import DiceModifier


RANGED_WEAPON_RELOAD_RULE_ID = "RULE-EQUIPMENT-004:reload"
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
