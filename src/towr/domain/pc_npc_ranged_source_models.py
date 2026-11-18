"""Complete generated/canonical NPC ranged sources and scene confirmations."""
from dataclasses import dataclass, field, replace
from enum import Enum

from towr.domain.npc_roster_models import NpcDefinition
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.ranged_weapon_profiles import RangedWeaponId,RangedWeaponHands,ranged_weapon_combat_profile
from towr.domain.test_models import InlineProfile
from towr.domain.weapon_catalog import WeaponKind,WeaponGroup,weapon_profile
from towr.domain.weapon_inventory_models import WeaponItemSource,WeaponItemLocation,WeaponGrip,weapon_reload_target


PC_NPC_RANGED_DEFINITION_IDS = (
    'pc-book-npc:empire_official_pistol',
    'pc-book-npc:imperial_ogre_pistol',
)


class PcNpcRangedReloadHandPolicy(str, Enum):
    TWO_AVAILABLE_HANDS = 'two_available_hands'


@dataclass(frozen=True, slots=True)
class PcNpcRangedPolicy:
    actor_id: str
    has_blackpowder_lore: bool | None
    has_blackpowder_kit: bool | None
    ammunition_supply_confirmed: bool
    reload_hand_policy: PcNpcRangedReloadHandPolicy | None
    initial_weapon: WeaponItemSource | None = field(default=None,kw_only=True)

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('NPC ranged weapon actor must be an exact nonempty string')
        for name in ('ammunition_supply_confirmed',):
            value = getattr(self,name)
            if type(value) is not bool:
                raise TypeError(f'NPC ranged weapon {name} must be an exact boolean')
            if not value:
                raise ValueError(f'NPC ranged weapon requires confirmed {name}')
        for name in ('has_blackpowder_lore','has_blackpowder_kit'):
            value=getattr(self,name)
            if value is not None and value is not True:
                raise ValueError('NPC firearm permissions must be confirmed or absent for a non-firearm')
        if self.reload_hand_policy is not None and type(self.reload_hand_policy) is not PcNpcRangedReloadHandPolicy:
            raise TypeError('NPC ranged weapon Reload requires its exact hand policy enum')
        if self.initial_weapon is not None:
            if type(self.initial_weapon) is not WeaponItemSource:
                raise TypeError('canonical NPC weapon requires its complete item source')
            replace(self.initial_weapon)


@dataclass(frozen=True, slots=True)
class PcNpcRangedProfile:
    weapon_id: RangedWeaponId
    dexterity_profile: InlineProfile | None
    strength: int
    awareness_profile: InlineProfile | None = field(default=None,kw_only=True)

    def __post_init__(self):
        if type(self.weapon_id) is not RangedWeaponId or self.weapon_id not in (
                RangedWeaponId.PISTOL,RangedWeaponId.OGRE_PISTOL,
                RangedWeaponId.REPEATER_PISTOL,RangedWeaponId.REPEATER_HANDBOW,
                RangedWeaponId.SHORTBOW,RangedWeaponId.WARBOW,RangedWeaponId.LONGBOW,
                RangedWeaponId.CROSSBOW,RangedWeaponId.HANDGUN,RangedWeaponId.BLUNDERBUSS,
                RangedWeaponId.HOCHLAND_LONG_RIFLE,RangedWeaponId.REPEATER_CROSSBOW,
                RangedWeaponId.REPEATER_HANDGUN):
            raise TypeError('NPC ranged weapon profile requires its exact supported kind')
        if self.dexterity_profile is not None and type(self.dexterity_profile) is not InlineProfile:
            raise TypeError('NPC ranged weapon Dexterity requires an exact InlineProfile')
        if self.dexterity_profile is not None:
            replace(self.dexterity_profile)
        if weapon_reload_target(WeaponKind(self.weapon_id.value)) is not None and self.dexterity_profile is None:
            raise ValueError('an Exacting NPC weapon requires actual Dexterity')
        if self.awareness_profile is not None:
            if type(self.awareness_profile) is not InlineProfile:
                raise TypeError('NPC ranged Awareness requires an exact InlineProfile or None')
            replace(self.awareness_profile)
        if (ranged_weapon_combat_profile(self.weapon_id).hands is RangedWeaponHands.TWO_HANDED
                and self.awareness_profile is None):
            raise ValueError('two-handed NPC Shooting requires its actual Awareness for Aim')
        if type(self.strength) is not int:
            raise TypeError('NPC ranged weapon Strength must be an exact integer')
        if self.strength < 1:
            raise ValueError('NPC ranged weapon Strength must be positive')


def pc_npc_ranged_profile(definition: NpcDefinition,weapon_kind: WeaponKind | None = None) -> PcNpcRangedProfile:
    """Derive Reload only from full generated facts or the complete printed loadout."""
    if type(definition) is not NpcDefinition:
        raise TypeError('NPC ranged weapon requires an exact NpcDefinition')
    if definition.generated_components is not None:
        from towr.domain.generated_npc_models import validate_generated_definition
        validate_generated_definition(definition)
        npc=definition.generated_components
        if npc.ranged is None:
            raise ValueError('generated ranged capability requires its full source facts')
        facts=npc.ranged
        shooting=tuple(item.kind for item in npc.weapons if weapon_profile(item.kind).group is WeaponGroup.SHOOTING)
        kind=shooting[0] if weapon_kind is None else weapon_kind
        if type(kind) is not WeaponKind or kind not in shooting:
            raise ValueError('NPC Shooting profile requires a real source inventory item')
        return PcNpcRangedProfile(RangedWeaponId(kind.value),
            InlineProfile(facts.initiative,facts.dexterity) if facts.dexterity is not None else None,npc.strength,
            awareness_profile=(InlineProfile(facts.initiative,facts.awareness)
                if facts.awareness is not None else None))
    validate_pc_book_npc_definition(definition)
    if weapon_kind is not None and (type(weapon_kind) is not WeaponKind
            or weapon_kind.value not in ('pistol','ogre_pistol')):
        raise ValueError('canonical Shooting kind differs from its complete source')
    if definition.id == PC_NPC_RANGED_DEFINITION_IDS[0]:
        if weapon_kind not in (None,WeaponKind.PISTOL):raise ValueError('Official requires its Pistol')
        return PcNpcRangedProfile(RangedWeaponId.PISTOL,InlineProfile(3,3),3)
    if definition.id == PC_NPC_RANGED_DEFINITION_IDS[1]:
        if weapon_kind not in (None,WeaponKind.OGRE_PISTOL):raise ValueError('Ogre requires its Ogre Pistol')
        return PcNpcRangedProfile(RangedWeaponId.OGRE_PISTOL,InlineProfile(2,2),5)
    raise ValueError('NPC ranged weapon requires a canonical Official or Ogre firearm loadout')


def pc_npc_ranged_policy_for_generated(npc,actor_id: str) -> PcNpcRangedPolicy:
    from towr.domain.generated_npc_models import GeneratedNpc
    if type(npc) is not GeneratedNpc:
        raise TypeError('ranged policy requires complete generated NPC facts')
    replace(npc)
    if npc.ranged is None:
        raise ValueError('melee source cannot acquire a ranged policy')
    facts=npc.ranged
    from towr.domain.weapon_capability_models import weapon_ranged_requirements
    requirements=weapon_ranged_requirements(tuple(item.kind for item in npc.weapons))
    return PcNpcRangedPolicy(actor_id,facts.has_blackpowder_lore,
        facts.has_blackpowder_kit,facts.ammunition_supply_confirmed,
        PcNpcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS if requirements.exacting else None)


def validate_pc_npc_ranged_policies(source) -> None:
    policies = source.npc_ranged_policies
    if type(policies) is not tuple:
        raise TypeError('NPC ranged weapon policies require an exact ordered tuple')
    for policy in policies:
        if type(policy) is not PcNpcRangedPolicy:
            raise TypeError('NPC ranged weapon policy must retain its exact type')
        replace(policy)
    expected = tuple(enemy.state.actor_id for enemy in source.enemies
        if enemy.definition.id in PC_NPC_RANGED_DEFINITION_IDS
        or (enemy.definition.generated_components is not None
            and enemy.definition.generated_components.ranged is not None))
    if tuple(policy.actor_id for policy in policies) != expected:
        raise ValueError('each NPC ranged weapon requires exactly one policy in source order')
    for actor_id in expected:
        definition=source.enemy(actor_id).definition
        profile=pc_npc_ranged_profile(definition)
        policy=next(item for item in policies if item.actor_id==actor_id)
        if definition.generated_components is not None:
            if policy!=pc_npc_ranged_policy_for_generated(definition.generated_components,actor_id):
                raise ValueError('NPC ranged policy differs from its complete generated source')
        elif policy.has_blackpowder_lore is not True or policy.has_blackpowder_kit is not True:
            raise ValueError('canonical firearms require confirmed Blackpowder Lore and Kit')
        else:
            item=policy.initial_weapon
            if (type(item) is not WeaponItemSource or item.id!='weapon'
                    or item.kind.value!=profile.weapon_id.value or item.quantity!=1
                    or item.initial_location is not WeaponItemLocation.HELD
                    or item.initial_grip is not WeaponGrip.LEFT
                    or policy.reload_hand_policy is not PcNpcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS):
                raise ValueError('canonical firearms require their actual initial physical item')
