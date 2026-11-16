"""Concrete PC weapon instances and their carried/held/dropped locations.

The source remains distinct from the per-encounter inventory. No weapon rule
is selected by an item identifier, and a dropped item never implies a pickup.
"""
from __future__ import annotations

from dataclasses import dataclass,replace
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from towr.domain.pc_melee_models import PcMeleeWeapon,PcWeaponHand,PcTwoHandedGrip


class PcItemLocation(str,Enum):
    HELD='held'
    CARRIED='carried'
    DROPPED='dropped'


def _identifier(value):
    if type(value) is not str or not value.strip():
        raise TypeError('weapon inventory needs exact nonempty identifiers')


@dataclass(frozen=True,slots=True)
class PcWeaponItem:
    id: str
    weapon: PcMeleeWeapon
    location: PcItemLocation
    hand: PcWeaponHand | PcTwoHandedGrip | None

    def __post_init__(self):
        from towr.domain.pc_melee_models import PcMeleeWeapon,PcWeaponHand,PcTwoHandedGrip
        from towr.domain.pc_weapon_models import pc_weapon_requires_two_hands
        _identifier(self.id)
        if type(self.weapon) is not PcMeleeWeapon or type(self.location) is not PcItemLocation:
            raise TypeError('weapon item needs its exact weapon and location enums')
        if self.location is not PcItemLocation.HELD:
            if self.hand is not None:
                raise ValueError('a carried/dropped weapon has no held hand')
        elif pc_weapon_requires_two_hands(self.weapon):
            if self.hand is not PcTwoHandedGrip.BOTH:
                raise ValueError('a held two-handed weapon needs its actual two-handed grip')
        elif type(self.hand) is not PcWeaponHand:
            raise TypeError('a held one-handed weapon needs its exact hand')


@dataclass(frozen=True,slots=True)
class PcWeaponInventoryState:
    items: tuple[PcWeaponItem,...]
    active_item_id: str

    def __post_init__(self):
        _identifier(self.active_item_id)
        if (type(self.items) is not tuple or not 1<=len(self.items)<=2
                or any(type(item) is not PcWeaponItem for item in self.items)):
            raise TypeError('weapon inventory needs one or two ordered typed items')
        for item in self.items:
            replace(item)
        ids=tuple(item.id for item in self.items)
        if len(set(ids))!=len(ids) or self.active_item_id not in ids:
            raise ValueError('weapon inventory needs distinct source items and an actual active item')
        held=tuple(item for item in self.items if item.location is PcItemLocation.HELD)
        if len(held)>1 or (held and held[0].id!=self.active_item_id):
            raise ValueError('only the selected active weapon may be held')

    @property
    def active(self):
        return next(item for item in self.items if item.id==self.active_item_id)


def validate_pc_combat_equipment(participant):
    """Re-admit complete initial inventory against the executable loadout."""
    from towr.domain.pc_melee_models import PcMeleeParticipant,PcMeleePolicy,PcTwoHandedGrip,PC_RANGED_WEAPONS
    if type(participant) is not PcMeleeParticipant:
        raise TypeError('combat equipment requires its exact participant source')
    items=getattr(participant,'combat_equipment',None)
    if items is None:
        if participant.policy is PcMeleePolicy.AUTOMATIC_COMBAT and participant.pc.weapon in PC_RANGED_WEAPONS:
            raise ValueError('automatic ranged combat requires its complete concrete source weapon items')
        return
    if participant.policy is not PcMeleePolicy.AUTOMATIC_COMBAT:
        raise ValueError('concrete combat equipment currently belongs to automatic combat')
    if type(items) is not tuple or not items or any(type(item) is not PcWeaponItem for item in items):
        raise TypeError('combat equipment needs an ordered typed tuple')
    inventory=PcWeaponInventoryState(items,items[0].id)
    primary=inventory.active
    if (primary.weapon is not participant.pc.weapon or primary.location is not PcItemLocation.HELD
            or primary.hand is not participant.initial_weapon_hand):
        raise ValueError('initial primary item differs from its complete weapon/grip source')
    backup=participant.backup_weapon_policy
    if backup is None:
        if len(items)!=1:
            raise ValueError('extra weapon item requires its complete backup source')
    elif (len(items)!=2 or items[1].weapon is not backup.weapon
            or items[1].location is not PcItemLocation.CARRIED or items[1].hand is not None):
        raise ValueError('backup source must match the second carried weapon item')
    if (participant.shield is not None and (primary.hand is PcTwoHandedGrip.BOTH
            or primary.hand is participant.shield.initial_hand)):
        raise ValueError('initial weapon inventory conflicts with the held Shield')


def validate_pc_weapon_inventory(member,participant):
    """Check membership and mirrors; chronological changes belong to proofs."""
    source=getattr(participant,'combat_equipment',None)
    inventory=getattr(member,'weapon_inventory',None)
    if member.actor_id!=participant.actor_id:
        raise ValueError('weapon inventory belongs to another source actor')
    if source is None:
        if inventory is not None:
            raise ValueError('runtime inventory cannot be invented without complete source items')
        return
    if type(inventory) is not PcWeaponInventoryState:
        raise TypeError('runtime weapon inventory must retain its exact typed state')
    replace(inventory)
    if tuple((item.id,item.weapon) for item in inventory.items)!=tuple((item.id,item.weapon) for item in source):
        raise ValueError('runtime inventory changed source membership, order or weapon kinds')
    active=inventory.active
    expected_backup=active.id!=source[0].id
    if type(member.using_backup_weapon) is not bool or member.using_backup_weapon is not expected_backup:
        raise ValueError('active inventory item and backup mirror disagree')
    if ((active.location is PcItemLocation.HELD and active.hand is not member.weapon_hand)
            or (active.location is not PcItemLocation.HELD and member.weapon_hand is not None)):
        raise ValueError('active inventory location and actual weapon hand disagree')
