"""Concrete single-item sources for existing generated NPC fixtures."""
from towr.domain.generated_npc_models import GeneratedWeapon
from towr.domain.ranged_weapon_profiles import RangedWeaponHands
from towr.domain.weapon_catalog import WeaponKind, weapon_profile
from towr.domain.weapon_inventory_models import (
    WeaponGrip, WeaponItemLocation, WeaponItemSource, weapon_reload_target,
)


def initial_generated_weapons(kind, grip=None, *, initially_loaded=True, item_id='weapon',
        gm_fit_confirmed=None):
    """Declare the fixture's real item; never infer or repair malformed facts.

    ``grip`` is the former fixture's explicit variable-grip choice. Fixed
    weapons obtain their printed hand count, and all held 1H fixtures use LEFT.
    Readiness is supplied to each Exacting item, never to actor capabilities.
    """
    if type(kind) not in (GeneratedWeapon, WeaponKind):
        raise TypeError('fixture weapon requires its exact supported kind')
    kind = WeaponKind(kind.value)
    profile = weapon_profile(kind)
    if grip is not None and type(grip) is not RangedWeaponHands:
        raise TypeError('fixture grip requires its exact printed hands')
    if profile.variable_grip:
        if grip is None:
            raise ValueError('a variable-grip fixture must choose its actual hands')
        hands = grip
    else:
        if grip is not None:
            raise ValueError('a fixed weapon fixture has no variable-grip fact')
        hands = profile.hands
    target = weapon_reload_target(kind)
    if target is None and initially_loaded is not True and initially_loaded is not None:
        raise ValueError('this fixture item has no initial Shooting charge')
    actual = WeaponGrip.BOTH if hands is RangedWeaponHands.TWO_HANDED else WeaponGrip.LEFT
    return (WeaponItemSource(item_id, kind, WeaponItemLocation.HELD, actual,
        initially_loaded=initially_loaded if target is not None else None,
        gm_fit_confirmed=gm_fit_confirmed),)
