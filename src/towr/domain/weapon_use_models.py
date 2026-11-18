"""Frozen physical sources for one Attack or Protection Test (PG68/92/94).

Selecting sources does not combine base Damage, execute Traits, determine
range eligibility or spend an action. Those responsibilities stay with the
actual Test/action owners. Item origin namespaces never select the actor.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.ranged_weapon_profiles import RangedWeaponHands
from towr.domain.test_models import Skill
from towr.domain.weapon_catalog import WeaponGroup, WeaponKind, WeaponProfile, WeaponTrait, weapon_profile
from towr.domain.weapon_inventory_models import (
    WeaponGrip, WeaponInventoryState, WeaponItemLocation, WeaponUnitState,
)


_BOTH_HANDS = (WeaponGrip.LEFT, WeaponGrip.RIGHT)


def _identifier(value, label):
    if type(value) is not str or not value.strip():
        raise TypeError(label+' requires an exact nonempty identifier')


def _facts(actor_id, inventory, usable_hands):
    _identifier(actor_id, 'weapon-use actor')
    if type(inventory) is not WeaponInventoryState:
        raise TypeError('weapon use requires its exact typed inventory snapshot')
    replace(inventory)
    if type(usable_hands) is not tuple or any(type(hand) is not WeaponGrip for hand in usable_hands):
        raise TypeError('usable hands require an exact tuple of typed hands')
    if len(set(usable_hands)) != len(usable_hands) or WeaponGrip.BOTH in usable_hands:
        raise ValueError('usable hands are distinct Left/Right hands, never a Both grip')


def _item_ids(item_ids):
    if type(item_ids) is not tuple:
        raise TypeError('weapon source IDs require an exact tuple')
    for item_id in item_ids:
        _identifier(item_id, 'weapon source')
    if len(set(item_ids)) != len(item_ids):
        raise ValueError('the same physical weapon cannot contribute twice')


def _hands(item):
    return _BOTH_HANDS if item.grip is WeaponGrip.BOTH else (item.grip,)


def _held_item(inventory, item_id, usable_hands):
    _identifier(item_id, 'weapon source')
    try:
        item = inventory.item(item_id)
    except KeyError:
        raise ValueError('weapon use references an absent physical unit') from None
    if item.location is not WeaponItemLocation.HELD:
        raise ValueError('only an actual held weapon can supply this Test')
    if any(hand not in usable_hands for hand in _hands(item)):
        raise ValueError('every hand used by the weapon must be currently usable')
    return item


def _dual_pair(items):
    if len(items) != 2:
        raise ValueError('a combined weapon use contains exactly two physical implements')
    for item in items:
        profile = weapon_profile(item.kind)
        if (profile.group is not WeaponGroup.MELEE or profile.hands is not RangedWeaponHands.ONE_HANDED
                or not profile.dual_wield_allowed or item.grip is WeaponGrip.BOTH):
            raise ValueError('only two permitted held 1H Melee weapons can contribute together')
    if items[0].grip is items[1].grip:
        raise ValueError('a combined use requires two distinct actual hands')


def _ordered_hands(items, shield_hand=None):
    used = {hand for item in items for hand in _hands(item)}
    if shield_hand is not None:
        used.add(shield_hand)
    return tuple(hand for hand in _BOTH_HANDS if hand in used)


@dataclass(frozen=True, slots=True)
class WeaponUse:
    actor_id: str
    inventory: WeaponInventoryState
    primary_item_id: str | None
    contributor_item_ids: tuple[str, ...] = ()
    usable_hands: tuple[WeaponGrip, ...] = _BOTH_HANDS

    def __post_init__(self):
        _facts(self.actor_id, self.inventory, self.usable_hands)
        _item_ids(self.contributor_item_ids)
        if self.primary_item_id is None:
            if self.contributor_item_ids:
                raise ValueError('Unarmed has no physical primary or weapon contributors')
            return
        primary = _held_item(self.inventory, self.primary_item_id, self.usable_hands)
        if len(self.contributor_item_ids) > 1 or self.primary_item_id in self.contributor_item_ids:
            raise ValueError('an Attack has one primary and at most one different contributor')
        if self.contributor_item_ids:
            contributor = _held_item(self.inventory, self.contributor_item_ids[0], self.usable_hands)
            _dual_pair((primary, contributor))

    @property
    def primary(self) -> WeaponUnitState | None:
        return None if self.primary_item_id is None else self.inventory.item(self.primary_item_id)

    @property
    def contributors(self) -> tuple[WeaponUnitState, ...]:
        return tuple(self.inventory.item(item_id) for item_id in self.contributor_item_ids)

    @property
    def kind(self) -> WeaponKind:
        return WeaponKind.UNARMED if self.primary is None else self.primary.kind

    @property
    def primary_profile(self) -> WeaponProfile:
        """The sole base-Damage/Skill source, independently of contributors."""
        return weapon_profile(self.kind)

    @property
    def skill(self) -> Skill:
        return self.primary_profile.skill

    @property
    def primary_grip(self) -> WeaponGrip | None:
        return None if self.primary is None else self.primary.grip

    @property
    def item_ids(self) -> tuple[str, ...]:
        return () if self.primary_item_id is None else (self.primary_item_id, *self.contributor_item_ids)

    @property
    def used_hands(self) -> tuple[WeaponGrip, ...]:
        return _ordered_hands(() if self.primary is None else (self.primary, *self.contributors))


def build_weapon_use(actor_id: str, inventory: WeaponInventoryState, primary_item_id: str | None,
        contributor_item_ids: tuple[str, ...] = (),
        usable_hands: tuple[WeaponGrip, ...] = _BOTH_HANDS) -> WeaponUse:
    return WeaponUse(actor_id, inventory, primary_item_id, contributor_item_ids, usable_hands)


@dataclass(frozen=True, slots=True)
class WeaponProtectionUse:
    actor_id: str
    inventory: WeaponInventoryState
    skill: Skill
    item_ids: tuple[str, ...] = ()
    shield_used: bool = False
    usable_hands: tuple[WeaponGrip, ...] = _BOTH_HANDS

    def __post_init__(self):
        _facts(self.actor_id, self.inventory, self.usable_hands)
        if type(self.skill) is not Skill:
            raise TypeError('weapon Protection requires its exact typed Skill')
        if self.skill not in (Skill.DEFENCE, Skill.MELEE):
            raise ValueError('this weapon source describes Defence or a Close-Shooting Melee counter')
        if type(self.shield_used) is not bool:
            raise TypeError('Shield use requires an exact bool')
        _item_ids(self.item_ids)
        if len(self.item_ids) > 2:
            raise ValueError('at most two physical weapons contribute to Protection')
        implements = tuple(_held_item(self.inventory, item_id, self.usable_hands) for item_id in self.item_ids)
        if len(implements) == 2:
            _dual_pair(implements)
        if self.shield_used and (self.inventory.shield_hand is None
                or self.inventory.shield_hand not in self.usable_hands):
            raise ValueError('a used Shield requires its actual occupied usable hand')
        if self.skill is Skill.DEFENCE:
            if not implements and not self.shield_used:
                raise ValueError('Defence requires a usable held weapon or actual Shield')
            if any(WeaponTrait.NO_DEFENCE in weapon_profile(item.kind).trait_codes for item in implements):
                raise ValueError('a NO_DEFENCE implement cannot supply the Defence Test')

    @property
    def implements(self) -> tuple[WeaponUnitState, ...]:
        return tuple(self.inventory.item(item_id) for item_id in self.item_ids)

    @property
    def used_hands(self) -> tuple[WeaponGrip, ...]:
        return _ordered_hands(self.implements, self.inventory.shield_hand if self.shield_used else None)


def build_weapon_protection_use(actor_id: str, inventory: WeaponInventoryState, skill: Skill,
        item_ids: tuple[str, ...] = (), shield_used: bool = False,
        usable_hands: tuple[WeaponGrip, ...] = _BOTH_HANDS) -> WeaponProtectionUse:
    return WeaponProtectionUse(actor_id, inventory, skill, item_ids, shield_used, usable_hands)
