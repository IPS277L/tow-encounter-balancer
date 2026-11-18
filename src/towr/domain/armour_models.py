"""Shared, item-derived armour effects (PG1.4 IV97–98/105; GM1.1 VI85–86).

This module describes worn equipment, not a combat entity or a rules language.
The action owner supplies actual contexts such as mounted opposition or an
environmental Hazard; no item name or actor identifier selects those contexts.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from towr.domain.test_models import DiceModifier, QualityModifier, Skill, TestQuality


HEAVY_ARMOUR_AGILITY_RULE_ID = 'RULE-EQUIPMENT-006:heavy-armour-agility'
FULL_PLATE_ARMOUR_AGILITY_RULE_ID = 'RULE-EQUIPMENT-008:full-plate-armour-agility'
BARDING_AGILITY_RULE_ID = 'RULE-EQUIPMENT-006:barding-agility'
HEAVY_ARMOUR_BURDEN_RULE_ID = 'RULE-EQUIPMENT-006:heavy-armour-burden'
FULL_PLATE_ARMOUR_BURDEN_RULE_ID = 'RULE-EQUIPMENT-008:full-plate-armour-burden'
ITHILMAR_ENVIRONMENT_RULE_ID = 'RULE-MAGIC-ITEM-004:ithilmar-environment'
HELM_OF_HUNT_GLORIOUS_RULE_ID = 'RULE-MAGIC-ITEM-004:helm-of-the-hunt'
AGILULF_FIXED_RATING_RULE_ID = 'RULE-MAGIC-ITEM-004:agilulf-fixed-ratings'
METEORIC_PROTECTION_RULE_ID = 'RULE-MAGIC-ITEM-004:meteoric-iron'
BRIARROOT_RULE_ID = 'RULE-MAGIC-ITEM-004:briarroot-shield'


class BodyArmour(str, Enum):
    LIGHT = 'light_armour'
    HEAVY = 'heavy_armour'
    FULL_PLATE = 'full_plate_armour'
    AGILULF = 'armour_of_agilulf'
    METEORIC_IRON = 'armour_of_meteoric_iron'
    ITHILMAR = 'mantle_of_ithilmar'


class HelmetKind(str, Enum):
    HELMET = 'helmet'
    HUNT = 'helm_of_the_hunt'


class ShieldKind(str, Enum):
    SHIELD = 'shield'
    BRIARROOT = 'briarroot_shield'


MUNDANE_BODY_ARMOUR = frozenset((BodyArmour.LIGHT, BodyArmour.HEAVY, BodyArmour.FULL_PLATE))
MAGICAL_BODY_ARMOUR = frozenset(BodyArmour) - MUNDANE_BODY_ARMOUR


@dataclass(frozen=True, slots=True)
class ArmourLoadout:
    """Actual worn pieces and one explicitly chosen body-armour benefit source.

    GM85 permits benefits from only one magical/mundane suit, while retaining
    both suits' penalties. Shields remain carried equipment. The user explicitly
    allows Helm of the Hunt's additional benefits over body armour (ADR-0139).
    Barding's effects on a rider require an actual mounted context at execution.
    """
    body: tuple[BodyArmour, ...] = ()
    benefit: BodyArmour | None = None
    helmet: HelmetKind | None = None
    shield: ShieldKind | None = None
    barding: bool = False

    def __post_init__(self) -> None:
        if type(self.body) is not tuple or any(type(item) is not BodyArmour for item in self.body):
            raise TypeError('body armour requires a tuple of exact typed pieces')
        if len(set(self.body)) != len(self.body):
            raise ValueError('worn body armour pieces must be unique')
        if (sum(item in MUNDANE_BODY_ARMOUR for item in self.body) > 1
                or sum(item in MAGICAL_BODY_ARMOUR for item in self.body) > 1):
            raise ValueError('wear at most one mundane and one magical body-armour suit')
        if self.benefit is not None and type(self.benefit) is not BodyArmour:
            raise TypeError('the benefit source must be an exact typed body-armour piece')
        if (self.body and self.benefit not in self.body) or (not self.body and self.benefit is not None):
            raise ValueError('body armour requires exactly one actually worn benefit source')
        if self.helmet is not None and type(self.helmet) is not HelmetKind:
            raise TypeError('helmet requires its exact typed equipment kind')
        if self.shield is not None and type(self.shield) is not ShieldKind:
            raise TypeError('shield requires its exact typed equipment kind')
        _boolean(self.barding, 'Barding source')


def _boolean(value: bool, label: str) -> None:
    if type(value) is not bool:
        raise TypeError(f'{label} must be an exact bool')


def _loadout(loadout: ArmourLoadout) -> None:
    if type(loadout) is not ArmourLoadout:
        raise TypeError('armour effects require their exact typed equipment source')
    loadout.__post_init__()


def body_resilience_bonus(loadout: ArmourLoadout) -> int:
    _loadout(loadout)
    return {None: 0, BodyArmour.LIGHT: 1, BodyArmour.HEAVY: 2,
        BodyArmour.FULL_PLATE: 3, BodyArmour.AGILULF: 2,
        BodyArmour.METEORIC_IRON: 3, BodyArmour.ITHILMAR: 3}[loadout.benefit]


def helmet_resilience_bonus(loadout: ArmourLoadout) -> int:
    _loadout(loadout)
    return int(loadout.helmet is HelmetKind.HUNT)


def armour_is_worn(loadout: ArmourLoadout) -> bool:
    """Physical worn armour; a Shield or a mounted bonus is not worn armour."""
    _loadout(loadout)
    return bool(loadout.body) or loadout.helmet is not None


def armour_burden_sources(loadout: ArmourLoadout, strength: int) -> tuple[str, ...]:
    """Only armour-caused Burdened; independent Net/Wound causes stay elsewhere."""
    _loadout(loadout)
    if type(strength) is not int or strength < 1:
        raise ValueError('armour requirements need exact positive Strength')
    sources = []
    if BodyArmour.HEAVY in loadout.body and strength < 3:
        sources.append(HEAVY_ARMOUR_BURDEN_RULE_ID)
    if BodyArmour.FULL_PLATE in loadout.body and strength < 4:
        sources.append(FULL_PLATE_ARMOUR_BURDEN_RULE_ID)
    return tuple(sources)


def armour_test_modifiers(loadout: ArmourLoadout, skill: Skill, *,
        ignore_heavy: bool = False, ignore_full_plate: bool = False,
        ignore_barding: bool = False, mounted: bool = False,
        environmental: bool = False) -> tuple[DiceModifier, ...]:
    """Prepare actual item modifiers without changing Characteristics or caps.

    Only Athletics and Stealth use Agility (PG107); Dexterity uses Initiative.
    The caller establishes a mount's contextual exceptions and any environmental
    Hazard/condition context. This helper never grants a universal mount immunity.
    """
    _loadout(loadout)
    if type(skill) is not Skill:
        raise TypeError('armour preparation requires the exact tested Skill')
    for name, value in (('Heavy Armour exception', ignore_heavy),
            ('Full Plate exception', ignore_full_plate), ('Barding exception', ignore_barding),
            ('mounted context', mounted), ('environmental context', environmental)):
        _boolean(value, name)
    modifiers = []
    if skill in (Skill.ATHLETICS, Skill.STEALTH):
        if BodyArmour.HEAVY in loadout.body and not ignore_heavy:
            modifiers.append(DiceModifier(HEAVY_ARMOUR_AGILITY_RULE_ID, -1))
        if BodyArmour.FULL_PLATE in loadout.body and not ignore_full_plate:
            modifiers.append(DiceModifier(FULL_PLATE_ARMOUR_AGILITY_RULE_ID, -1))
        if loadout.barding and mounted and not ignore_barding:
            modifiers.append(DiceModifier(BARDING_AGILITY_RULE_ID, -1))
    if loadout.benefit is BodyArmour.ITHILMAR and environmental:
        modifiers.append(DiceModifier(ITHILMAR_ENVIRONMENT_RULE_ID, 1))
    return tuple(modifiers)


def armour_casting_grim(loadout: ArmourLoadout, *, working_shield: bool) -> bool:
    """Ithilmar excuses itself, without excusing another worn piece or Shield."""
    _loadout(loadout)
    _boolean(working_shield, 'working Shield')
    return (working_shield or loadout.helmet is not None
        or any(item is not BodyArmour.ITHILMAR for item in loadout.body))


def active_agilulf(loadout: ArmourLoadout) -> bool:
    """When active, the action owner sets WS/Melee/Defence exactly to five."""
    _loadout(loadout)
    return loadout.benefit is BodyArmour.AGILULF


def protects_against_mundane_armour_effects(loadout: ArmourLoadout) -> bool:
    _loadout(loadout)
    return loadout.benefit is BodyArmour.METEORIC_IRON


def armour_allows_near_miss(loadout: ArmourLoadout) -> bool:
    """The Helm prohibits Near Miss, rather than all other uses of Fate."""
    _loadout(loadout)
    return loadout.helmet is not HelmetKind.HUNT


def armour_quality_modifiers(loadout: ArmourLoadout, *, charge_attack: bool = False,
        tracking_or_pursuit: bool = False) -> tuple[QualityModifier, ...]:
    _loadout(loadout)
    _boolean(charge_attack, 'actual Charge Attack')
    _boolean(tracking_or_pursuit, 'tracking or pursuit context')
    return ((QualityModifier(HELM_OF_HUNT_GLORIOUS_RULE_ID, TestQuality.GLORIOUS),)
        if loadout.helmet is HelmetKind.HUNT and (charge_attack or tracking_or_pursuit) else ())
