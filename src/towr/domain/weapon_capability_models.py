"""Actor preparation required by the whole physical inventory, PG94–96.

Readiness belongs to units. These facts describe only the shared Skills and
preparation an actor needs to use every supplied Shooting implement.
"""
from dataclasses import dataclass

from towr.domain.weapon_catalog import WeaponKind,WeaponGroup,WeaponTrait,weapon_profile
from towr.domain.weapon_inventory_models import weapon_reload_target


@dataclass(frozen=True,slots=True)
class RangedInventoryRequirements:
    weapon_kinds: tuple[WeaponKind,...]

    def __post_init__(self):
        if type(self.weapon_kinds) is not tuple or not self.weapon_kinds:
            raise TypeError('Shooting requirements need their actual ordered weapon kinds')
        if any(type(kind) is not WeaponKind or weapon_profile(kind).group is not WeaponGroup.SHOOTING
                for kind in self.weapon_kinds):
            raise ValueError('Shooting requirements contain a non-Shooting or untyped weapon')

    @property
    def exacting(self):
        return any(weapon_reload_target(kind) is not None for kind in self.weapon_kinds)

    def _has(self,*traits):
        return any(set(traits).intersection(weapon_profile(kind).trait_codes) for kind in self.weapon_kinds)

    @property
    def firearm(self):
        return self._has(WeaponTrait.BLACKPOWDER_LORE_REQUIRED)

    @property
    def repeater(self):
        return self._has(WeaponTrait.RELOAD_THREE_AFTER_BONUS,WeaponTrait.RELOAD_FIVE_AFTER_BONUS)

    @property
    def requires_aim(self):
        return self._has(WeaponTrait.AIM_REQUIRED)


def weapon_ranged_requirements(kinds: tuple[WeaponKind,...]) -> RangedInventoryRequirements | None:
    if type(kinds) is not tuple or any(type(kind) is not WeaponKind for kind in kinds):
        raise TypeError('inventory requirements need an exact tuple of typed weapon kinds')
    shooting=tuple(kind for kind in kinds if weapon_profile(kind).group is WeaponGroup.SHOOTING)
    return RangedInventoryRequirements(shooting) if shooting else None
