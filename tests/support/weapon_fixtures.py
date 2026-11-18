"""Concrete item sources for deterministic shared weapon preparation tests."""
from towr.domain.ranged_weapon_profiles import RangedWeaponHands
from towr.domain.weapon_catalog import WeaponKind, weapon_profile
from towr.domain.weapon_inventory_models import (
    WeaponGrip, WeaponItemLocation, WeaponItemSource, initial_weapon_inventory,
    weapon_reload_target,
)
from towr.domain.weapon_use_models import build_weapon_use


def weapon_use(kind, *, offhand=None):
    if kind is WeaponKind.UNARMED:
        return build_weapon_use('actor', initial_weapon_inventory('actor', ()), None)
    grip = (WeaponGrip.BOTH if weapon_profile(kind).hands is RangedWeaponHands.TWO_HANDED
        else WeaponGrip.LEFT)
    sources = []
    for identifier, selected, hand in (('primary', kind, grip), ('secondary', offhand, WeaponGrip.RIGHT)):
        if selected is None:
            continue
        sources.append(WeaponItemSource(identifier, selected, WeaponItemLocation.HELD, hand,
            initially_loaded=True if weapon_reload_target(selected) is not None else None,
            gm_fit_confirmed=True if selected is WeaponKind.OGRE_PISTOL else None))
    inventory = initial_weapon_inventory('actor', tuple(sources))
    return build_weapon_use('actor', inventory, inventory.items[0].id,
        contributor_item_ids=tuple(item.id for item in inventory.items[1:]))
