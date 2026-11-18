"""Inventory facts and an explicit admission to the currently executable loadout.

Every supplied weapon remains an independent item. The first held weapon is
the initial primary; other held and carried implements retain their own source.
"""
from dataclasses import dataclass,field
from enum import Enum

from towr.domain.armour_models import ArmourLoadout,BodyArmour,HelmetKind,ShieldKind
from towr.domain.pc_melee_models import PcMeleeWeapon,PcWeaponHand,PcTwoHandedGrip
from towr.domain.potion_models import ConsumableKind, ConsumableItem
from towr.domain.pc_combat_equipment_models import PcWeaponItem,PcItemLocation
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_inventory_models import weapon_reload_target


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
    FULL_PLATE = 'full_plate_armour'
    AGILULF = 'armour_of_agilulf'
    METEORIC_IRON = 'armour_of_meteoric_iron'
    ITHILMAR = 'mantle_of_ithilmar'
    BRIARROOT = 'briarroot_shield'
    HUNT = 'helm_of_the_hunt'
    BARDING = 'barding'


def _id(value):
    if type(value) is not str or not value.strip():
        raise ValueError('inventory item needs a nonempty instance ID')


@dataclass(frozen=True, slots=True)
class WeaponItem:
    id: str
    weapon: PcMeleeWeapon
    location: ItemLocation
    initially_loaded: bool | None = field(default=None,kw_only=True)

    def __post_init__(self):
        _id(self.id)
        if type(self.weapon) is not PcMeleeWeapon or type(self.location) is not ItemLocation:
            raise TypeError('weapon and location must be typed')
        if self.location is ItemLocation.WORN:
            raise ValueError('weapons must be held or carried')
        if self.initially_loaded is not None and type(self.initially_loaded) is not bool:
            raise TypeError('initial item charge must be an exact bool or None')
        if weapon_reload_target(self.weapon) is not None:
            if self.initially_loaded is None:
                raise ValueError('each Exacting item requires its explicit initial loaded bool')
        elif self.initially_loaded is not None:
            raise ValueError('only an Exacting weapon has an initial loaded flag')


@dataclass(frozen=True, slots=True)
class ArmourItem:
    id: str
    kind: ArmourItemKind
    location: ItemLocation

    def __post_init__(self):
        _id(self.id)
        if type(self.kind) is not ArmourItemKind or type(self.location) is not ItemLocation:
            raise TypeError('armour kind and location must be typed')
        allowed = ((ItemLocation.CARRIED, ItemLocation.LEFT, ItemLocation.RIGHT)
            if self.kind in (ArmourItemKind.SHIELD,ArmourItemKind.BRIARROOT)
            else (ItemLocation.CARRIED, ItemLocation.WORN))
        if self.location not in allowed:
            raise ValueError('armour location is incompatible with this item')


@dataclass(frozen=True, slots=True)
class EncounterEquipment:
    weapons: tuple[WeaponItem, ...]
    armour: tuple[ArmourItem, ...]
    armour_benefit_id: str | None = None

    def __post_init__(self):
        for values, cls in ((self.weapons, WeaponItem), (self.armour, ArmourItem)):
            if type(values) is not tuple or any(type(item) is not cls for item in values):
                raise TypeError('equipment needs typed inventory tuples')
            for item in values:
                item.__post_init__()
        ids = tuple(item.id for item in (*self.weapons, *self.armour))
        if len(ids) != len(set(ids)):
            raise ValueError('inventory instance IDs must be unique')
        if self.armour_benefit_id is not None:
            _id(self.armour_benefit_id)

    def combat_loadout(self, strength: int, *, mount=None):
        """Compile supported inventory, or explain the missing combat capability."""
        self.__post_init__()
        if type(strength) is not int or strength < 1:
            raise ValueError('Strength must be a positive integer')
        active = tuple(w for w in self.weapons if w.location is not ItemLocation.CARRIED)
        if not active:
            raise ValueError('Начальный состав требует хотя бы одно оружие в руках (Weapons).')
        primary = active[0]
        hand = PcWeaponHand.LEFT if primary.location is ItemLocation.LEFT else PcWeaponHand.RIGHT
        ordered=(primary,*(item for item in self.weapons if item is not primary))
        combat_equipment=tuple(PcWeaponItem(item.id,item.weapon,
            PcItemLocation.CARRIED if item.location is ItemLocation.CARRIED else PcItemLocation.HELD,
            None if item.location is ItemLocation.CARRIED else PcTwoHandedGrip.BOTH
                if item.location is ItemLocation.BOTH else PcWeaponHand.LEFT
                if item.location is ItemLocation.LEFT else PcWeaponHand.RIGHT,
            initially_loaded=item.initially_loaded) for item in ordered)
        occupied=set()
        for item in combat_equipment:
            if item.location is not PcItemLocation.HELD:
                continue
            hands=(PcWeaponHand.LEFT,PcWeaponHand.RIGHT) if item.hand is PcTwoHandedGrip.BOTH else (item.hand,)
            if any(held in occupied for held in hands):
                raise ValueError('Оружие (Weapons) занимает одну и ту же руку.')
            occupied.update(hands)
        held_shields = tuple(a for a in self.armour if a.kind in (
            ArmourItemKind.SHIELD,ArmourItemKind.BRIARROOT) and a.location is not ItemLocation.CARRIED)
        if len(held_shields) > 1:
            raise ValueError('Несколько активных щитов пока не поддержаны.')
        if held_shields and (PcWeaponHand.LEFT if held_shields[0].location is ItemLocation.LEFT
                else PcWeaponHand.RIGHT) in occupied:
            raise ValueError('Оружие и щит занимают одну и ту же руку.')
        worn = tuple(a for a in self.armour if a.location is ItemLocation.WORN)
        body = tuple(a for a in worn if a.kind.value in {kind.value for kind in BodyArmour})
        helmets=tuple(a for a in worn if a.kind in (ArmourItemKind.HELMET,ArmourItemKind.HUNT))
        barding=tuple(a for a in worn if a.kind is ArmourItemKind.BARDING)
        if len(helmets)>1 or len(barding)>1:
            raise ValueError('Допустим один шлем (Helmet) и один комплект конской брони (Barding).')
        if barding and mount is None:
            raise ValueError('Конская броня (Barding) требует фактического маунта (Mount).')
        selected=next((a for a in body if a.id==self.armour_benefit_id),None)
        if self.armour_benefit_id is not None and selected is None:
            raise ValueError('Источник защиты должен ссылаться на надетую броню (Armour).')
        if len(body)==1 and selected is None:
            selected=body[0]
        if len(body)>1 and selected is None:
            raise ValueError('При сочетании брони (Armour) выберите явный источник её преимуществ.')
        protection=ArmourLoadout(tuple(BodyArmour(a.kind.value) for a in body),
            None if selected is None else BodyArmour(selected.kind.value),
            None if not helmets else HelmetKind(helmets[0].kind.value),
            None if not held_shields else ShieldKind(held_shields[0].kind.value),bool(barding))
        return dict(weapon=primary.weapon, armour=protection,
            shield=bool(held_shields), weapon_hand=hand, backup_weapon_policy=None,
            combat_equipment=combat_equipment)
