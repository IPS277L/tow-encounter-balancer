"""Complete canonical NPC firearm sources and explicit scene confirmations."""
from dataclasses import dataclass, replace
from enum import Enum

from towr.domain.npc_roster_models import NpcDefinition
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.test_models import InlineProfile


PC_NPC_PISTOL_DEFINITION_IDS = (
    'pc-book-npc:empire_official_pistol',
    'pc-book-npc:imperial_ogre_pistol',
)


class PcNpcPistolReloadHandPolicy(str, Enum):
    TWO_AVAILABLE_HANDS = 'two_available_hands'


@dataclass(frozen=True, slots=True)
class PcNpcPistolPolicy:
    actor_id: str
    initially_loaded: bool
    has_blackpowder_lore: bool
    has_blackpowder_kit: bool
    ammunition_supply_confirmed: bool
    reload_hand_policy: PcNpcPistolReloadHandPolicy

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('NPC Pistol actor must be an exact nonempty string')
        for name in ('initially_loaded','has_blackpowder_lore','has_blackpowder_kit',
                'ammunition_supply_confirmed'):
            value = getattr(self,name)
            if type(value) is not bool:
                raise TypeError(f'NPC Pistol {name} must be an exact boolean')
            if not value:
                raise ValueError(f'NPC Pistol requires confirmed {name}')
        if type(self.reload_hand_policy) is not PcNpcPistolReloadHandPolicy:
            raise TypeError('NPC Pistol Reload requires its exact hand policy enum')


@dataclass(frozen=True, slots=True)
class PcNpcPistolProfile:
    weapon_id: RangedWeaponId
    dexterity_profile: InlineProfile
    strength: int

    def __post_init__(self):
        if type(self.weapon_id) is not RangedWeaponId or self.weapon_id not in (
                RangedWeaponId.PISTOL,RangedWeaponId.OGRE_PISTOL):
            raise TypeError('NPC Pistol profile requires its exact firearm kind')
        if type(self.dexterity_profile) is not InlineProfile:
            raise TypeError('NPC Pistol Dexterity requires an exact InlineProfile')
        replace(self.dexterity_profile)
        if type(self.strength) is not int:
            raise TypeError('NPC Pistol Strength must be an exact integer')
        if self.strength < 1:
            raise ValueError('NPC Pistol Strength must be positive')


def pc_npc_pistol_profile(definition: NpcDefinition) -> PcNpcPistolProfile:
    """Derive I/Default Reload dice only from the complete printed loadout."""
    if type(definition) is not NpcDefinition:
        raise TypeError('NPC Pistol requires an exact NpcDefinition')
    validate_pc_book_npc_definition(definition)
    if definition.id == PC_NPC_PISTOL_DEFINITION_IDS[0]:
        return PcNpcPistolProfile(RangedWeaponId.PISTOL,InlineProfile(3,3),3)
    if definition.id == PC_NPC_PISTOL_DEFINITION_IDS[1]:
        return PcNpcPistolProfile(RangedWeaponId.OGRE_PISTOL,InlineProfile(2,2),5)
    raise ValueError('NPC Pistol requires a canonical Official or Ogre firearm loadout')


def validate_pc_npc_pistol_policies(source) -> None:
    policies = source.npc_pistol_policies
    if type(policies) is not tuple:
        raise TypeError('NPC Pistol policies require an exact ordered tuple')
    for policy in policies:
        if type(policy) is not PcNpcPistolPolicy:
            raise TypeError('NPC Pistol policy must retain its exact type')
        replace(policy)
    expected = tuple(enemy.state.actor_id for enemy in source.enemies
        if enemy.definition.id in PC_NPC_PISTOL_DEFINITION_IDS)
    if tuple(policy.actor_id for policy in policies) != expected:
        raise ValueError('each canonical NPC Pistol requires exactly one policy in source order')
    for actor_id in expected:
        pc_npc_pistol_profile(source.enemy(actor_id).definition)
