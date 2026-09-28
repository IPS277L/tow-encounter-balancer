from dataclasses import dataclass

from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.reload_models import ReloadableWeaponState


@dataclass(frozen=True, slots=True)
class NpcRoundWeaponState:
    actor_id: str
    attack_profile_id: str
    weapon_state: ReloadableWeaponState

    def __post_init__(self) -> None:
        for value in (self.actor_id, self.attack_profile_id):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("round weapon requires actor/profile IDs")
        if not isinstance(self.weapon_state, ReloadableWeaponState):
            raise TypeError("round weapon requires typed reload state")
        if self.weapon_state.weapon_id is not RangedWeaponId.BLUNDERBUSS:
            raise ValueError("round weapon currently supports Blunderbuss only")


@dataclass(frozen=True, slots=True)
class NpcBlunderbussCandidateContext:
    weapon_instance_id: str
    next_reload_cycle_id: str
    has_blackpowder_lore: bool
    attacker_strength: int

    def __post_init__(self) -> None:
        for value in (self.weapon_instance_id, self.next_reload_cycle_id):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Blunderbuss candidate requires weapon/reload IDs")
        if not isinstance(self.has_blackpowder_lore, bool):
            raise TypeError("Blunderbuss Lore must be explicit")
        if type(self.attacker_strength) is not int or self.attacker_strength < 1:
            raise ValueError("Blunderbuss candidate requires positive Strength")
