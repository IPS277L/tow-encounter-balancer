"""Inventory facts and an explicit admission to the currently executable loadout.

An inventory can be described/saved before every carried item's combat use is
implemented. Compilation never silently selects one of two active weapons.
"""
from dataclasses import dataclass
from enum import Enum

from towr.application.encounter_character import EncounterArmour
from towr.domain.pc_melee_models import PcMeleeWeapon, PcWeaponHand, PcBackupWeaponPolicy
from towr.domain.pc_weapon_models import pc_weapon_requires_two_hands
from towr.domain.potion_models import ConsumableKind, ConsumableItem


class ItemLocation(str, Enum):
    CARRIED = 'carried'
    LEFT = 'left_hand'
    RIGHT = 'right_hand'
    BOTH = 'both_hands'
    WORN = 'worn'


class ArmourItemKind(str, Enum):
    LIGHT = 'light_armour'
    HEAVY = 'heavy_armour'
    HELMET = 'helmet'
    SHIELD = 'shield'


def _id(value):
    if type(value) is not str or not value.strip():
        raise ValueError('inventory item needs a nonempty instance ID')


@dataclass(frozen=True, slots=True)
class WeaponItem:
    id: str
    weapon: PcMeleeWeapon
    location: ItemLocation

    def __post_init__(self):
        _id(self.id)
        if type(self.weapon) is not PcMeleeWeapon or type(self.location) is not ItemLocation:
            raise TypeError('weapon and location must be typed')
        if self.location is ItemLocation.WORN:
            raise ValueError('weapons must be held or carried')


@dataclass(frozen=True, slots=True)
class ArmourItem:
    id: str
    kind: ArmourItemKind
    location: ItemLocation

    def __post_init__(self):
        _id(self.id)
        if type(self.kind) is not ArmourItemKind or type(self.location) is not ItemLocation:
            raise TypeError('armour kind and location must be typed')
        allowed = (ItemLocation.CARRIED, ItemLocation.LEFT, ItemLocation.RIGHT) if self.kind is ArmourItemKind.SHIELD else (ItemLocation.CARRIED, ItemLocation.WORN)
        if self.location not in allowed:
            raise ValueError('armour location is incompatible with this item')


@dataclass(frozen=True, slots=True)
class EncounterEquipment:
    weapons: tuple[WeaponItem, ...]
    armour: tuple[ArmourItem, ...]

    def __post_init__(self):
        for values, cls in ((self.weapons, WeaponItem), (self.armour, ArmourItem)):
            if type(values) is not tuple or any(type(item) is not cls for item in values):
                raise TypeError('equipment needs typed inventory tuples')
            for item in values:
                item.__post_init__()
        ids = tuple(item.id for item in (*self.weapons, *self.armour))
        if len(ids) != len(set(ids)):
            raise ValueError('inventory instance IDs must be unique')

    def combat_loadout(self, strength: int):
        """Compile supported inventory, or explain the missing combat capability."""
        self.__post_init__()
        if type(strength) is not int or strength < 1:
            raise ValueError('Strength must be a positive integer')
        if len(self.weapons) > strength or sum(pc_weapon_requires_two_hands(w.weapon) for w in self.weapons) > 1:
            raise ValueError('Переноска этого оружия вызывает Burdened (PG92); такой инвентарь пока не поддержан симуляцией.')
        active = tuple(w for w in self.weapons if w.location is not ItemLocation.CARRIED)
        if len(active) != 1:
            raise ValueError('Для симуляции пока нужно одно активное оружие; бой двумя оружиями ещё не реализован.')
        primary, = active
        two_hands = pc_weapon_requires_two_hands(primary.weapon)
        if (primary.location is ItemLocation.BOTH) != two_hands:
            raise ValueError('Начальный хват не соответствует числу рук оружия.')
        hand = PcWeaponHand.LEFT if primary.location is ItemLocation.LEFT else PcWeaponHand.RIGHT
        held_shields = tuple(a for a in self.armour if a.kind is ArmourItemKind.SHIELD and a.location is not ItemLocation.CARRIED)
        if len(held_shields) > 1:
            raise ValueError('Несколько активных щитов пока не поддержаны.')
        if held_shields and (two_hands or held_shields[0].location is primary.location):
            raise ValueError('Оружие и щит занимают одну и ту же руку.')
        if any(a.location is ItemLocation.CARRIED for a in self.armour):
            raise ValueError('Смена запасной брони/щита пока не поддержана симуляцией.')
        worn = tuple(a for a in self.armour if a.location is ItemLocation.WORN)
        body = tuple(a for a in worn if a.kind in (ArmourItemKind.LIGHT, ArmourItemKind.HEAVY))
        if len(body) > 1 or sum(a.kind is ArmourItemKind.HELMET for a in worn) > 1:
            raise ValueError('Наложение нескольких комплектов брони/шлемов пока не поддержано.')
        if any(a.kind is ArmourItemKind.HEAVY for a in body):
            raise ValueError('Heavy Armour требует Agility/Burdened effects; симуляция пока не поддержана.')
        backup = tuple(w for w in self.weapons if w.location is ItemLocation.CARRIED)
        if len(backup) > 1 or (backup and not two_hands):
            raise ValueError('Смена этого набора запасного оружия пока не поддержана симуляцией.')
        backup_policy = None
        if backup:
            backup_policy = PcBackupWeaponPolicy(backup[0].weapon, hand)
        return dict(weapon=primary.weapon, armour=EncounterArmour.LIGHT if body else EncounterArmour.NONE,
            shield=bool(held_shields), weapon_hand=hand, backup_weapon_policy=backup_policy)
