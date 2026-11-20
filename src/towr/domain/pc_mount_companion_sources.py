"""Canonical independent mount sources, PG1.4 V124 / GM1.1 VII135/175–176.

These facts belong to the animal, not its rider. Initial snapshots are created
once; remounting must retain the actual animal state rather than call this
factory again. Wound bands and species capabilities are source facts, not a
claim that a wounded animal can currently fly or that Skeletal behavior is set.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass, replace
from enum import Enum

from towr.domain.armour_models import ArmourLoadout
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.movement_models import MovementSpeed
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_roster_models import (
    NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile,
)
from towr.domain.pc_mount_models import CombatMount
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatSide


class MountCompanionWoundBand(str, Enum):
    NONE = 'none'
    DRAINED_1_2 = 'drained_1_2'
    GROUNDED_FROM_1 = 'grounded_from_1'


@dataclass(frozen=True, slots=True)
class MountCompanionCharacteristics:
    weapon_skill: int
    ballistic_skill: int
    strength: int
    toughness: int
    initiative: int
    agility: int
    reason: int
    fellowship: int

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) is not int:
                raise TypeError('mount Characteristics require exact integers')
            if value < (0 if field.name == 'ballistic_skill' else 1):
                raise ValueError('mount Characteristic is below its permitted source minimum')


@dataclass(frozen=True, slots=True)
class MountCompanionSkills:
    default: int = 1
    melee: int = 1
    defence: int = 1
    shooting: int = 1
    throwing: int = 1
    brawn: int = 1
    toil: int = 1
    survival: int = 1
    endurance: int = 1
    awareness: int = 1
    dexterity: int = 1
    athletics: int = 1
    stealth: int = 1
    willpower: int = 1
    recall: int = 1
    leadership: int = 1
    charm: int = 1

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) is not int:
                raise TypeError('mount Skills require exact integer ratings')
            if not 1 <= value <= 10:
                raise ValueError('mount Skill rating is outside the supported threshold range')


_CHARACTERISTIC_FOR_SKILL = {
    Skill.MELEE: 'weapon_skill', Skill.DEFENCE: 'weapon_skill',
    Skill.SHOOTING: 'ballistic_skill', Skill.THROWING: 'ballistic_skill',
    Skill.BRAWN: 'strength', Skill.TOIL: 'strength',
    Skill.SURVIVAL: 'toughness', Skill.ENDURANCE: 'toughness',
    Skill.AWARENESS: 'initiative', Skill.DEXTERITY: 'initiative',
    Skill.ATHLETICS: 'agility', Skill.STEALTH: 'agility',
    Skill.WILLPOWER: 'reason', Skill.RECALL: 'reason',
    Skill.LEADERSHIP: 'fellowship', Skill.CHARM: 'fellowship',
}


def _inputs(kind, barding):
    if type(kind) is not CombatMount:
        raise TypeError('mount companion requires its exact CombatMount source')
    if type(barding) is not bool:
        raise TypeError('mount companion Barding requires an exact boolean')


def _canonical(kind, barding):
    _inputs(kind, barding)
    if kind is CombatMount.DEMIGRYPH:
        page, name = 175, 'wicked_claws'
        characteristics = MountCompanionCharacteristics(4, 0, 5, 4, 4, 4, 2, 1)
        skills = MountCompanionSkills(melee=4, brawn=4, endurance=3, awareness=3,
            athletics=3, stealth=2, willpower=4)
        policy, limit, attack_dice, attack_skill, damage, protection_skill = TargetInjuryPolicy.BRUTE, 3, 4, 4, 5, 3
        band = MountCompanionWoundBand.DRAINED_1_2
    elif kind is CombatMount.PEGASUS:
        page, name = 176, 'hooves'
        characteristics = MountCompanionCharacteristics(3, 0, 4, 3, 4, 4, 2, 1)
        skills = MountCompanionSkills(melee=3, brawn=3, endurance=3, awareness=3, athletics=4, willpower=3)
        policy, limit, attack_dice, attack_skill, damage, protection_skill = TargetInjuryPolicy.BRUTE, 2, 3, 3, 3, 4
        band = MountCompanionWoundBand.GROUNDED_FROM_1
    else:
        page, name = 135, 'hooves'
        characteristics = MountCompanionCharacteristics(3, 0, 3, 3, 3, 4, 2, 1)
        skills = MountCompanionSkills(melee=3, brawn=4, endurance=3, awareness=3, athletics=4, willpower=3)
        policy, limit, attack_dice, attack_skill, damage, protection_skill = TargetInjuryPolicy.MINION, 1, 3, 3, 3, 4
        band = MountCompanionWoundBand.NONE
    source = f'BOOK-GM-GUIDE:1.1:p{page}:mount-companion:{kind.value}'
    attack = NpcAttackProfile(name, source+':'+name, Skill.MELEE,
        InlineProfile(attack_dice, attack_skill), DamageProfile(damage),
        RangedWeaponRange.CLOSE, RangedWeaponRange.CLOSE, None)
    protection = NpcProtectionProfile(source+':athletics', Skill.ATHLETICS, InlineProfile(4, protection_skill))
    armour = ArmourLoadout(barding=barding)
    definition = NpcDefinition(f'mount-companion:{kind.value}:{str(barding).lower()}', source,
        policy, limit, ResilienceProfile(characteristics.toughness, int(barding), armoured=barding),
        (attack,), (protection,))
    return (characteristics, skills, MovementSpeed.FAST, definition, armour,
        kind is CombatMount.PEGASUS, kind is CombatMount.DEMIGRYPH,
        kind is CombatMount.SKELETAL_STEED, band)


def _same_typed(actual, expected):
    if type(actual) is not type(expected):
        return False
    if is_dataclass(expected):
        return all(_same_typed(getattr(actual, field.name), getattr(expected, field.name))
            for field in fields(expected))
    if type(expected) is tuple:
        return len(actual) == len(expected) and all(_same_typed(a, b) for a, b in zip(actual, expected))
    return actual == expected


@dataclass(frozen=True, slots=True)
class MountCompanionProfile:
    kind: CombatMount
    characteristics: MountCompanionCharacteristics
    skills: MountCompanionSkills
    speed: MovementSpeed
    definition: NpcDefinition
    armour: ArmourLoadout
    can_fly: bool
    fearsome: bool
    undead: bool
    wound_band: MountCompanionWoundBand

    def __post_init__(self):
        if type(self.armour) is not ArmourLoadout:
            raise TypeError('mount companion requires its own exact armour source')
        replace(self.armour)
        _inputs(self.kind, self.armour.barding)
        for value, kind in ((self.characteristics, MountCompanionCharacteristics),
                (self.skills, MountCompanionSkills), (self.definition, NpcDefinition)):
            if type(value) is not kind:
                raise TypeError('mount companion requires exact immutable canonical profile types')
            replace(value)
        if type(self.speed) is not MovementSpeed or type(self.wound_band) is not MountCompanionWoundBand:
            raise TypeError('mount companion requires typed Speed and Wound band')
        if any(type(value) is not bool for value in (self.can_fly, self.fearsome, self.undead)):
            raise TypeError('mount species capabilities require exact booleans')
        actual = (self.characteristics, self.skills, self.speed, self.definition, self.armour,
            self.can_fly, self.fearsome, self.undead, self.wound_band)
        if not _same_typed(actual, _canonical(self.kind, self.armour.barding)):
            raise ValueError('mount companion differs from its complete canonical species/Barding source')

    @property
    def barding(self) -> bool:
        return self.armour.barding

    def skill_rating(self, skill: Skill) -> int:
        if type(skill) is not Skill:
            raise TypeError('mount Skill query requires its exact typed Skill')
        return getattr(self.skills, skill.value)

    def characteristic_for_skill(self, skill: Skill) -> int:
        if type(skill) is not Skill:
            raise TypeError('mount Characteristic query requires its exact typed Skill')
        # BS0 is truthful metadata. This method does not construct a Shooting
        # Test or silently replace an unavailable characteristic with one die.
        return getattr(self.characteristics, _CHARACTERISTIC_FOR_SKILL[skill])


def mount_companion_profile(kind: CombatMount, *, barding: bool = False) -> MountCompanionProfile:
    return MountCompanionProfile(kind, *_canonical(kind, barding))


def initial_mount_companion_snapshot(actor_id: str, side: CombatSide, kind: CombatMount, *,
        barding: bool = False) -> NpcParticipantSnapshot:
    if type(actor_id) is not str or not actor_id.strip():
        raise TypeError('mount companion requires its exact nonempty actor identifier')
    if type(side) is not CombatSide:
        raise TypeError('mount companion requires the actual typed encounter side')
    profile = mount_companion_profile(kind, barding=barding)
    definition = profile.definition
    return NpcParticipantSnapshot(definition, NpcParticipantState(actor_id, definition.id, side,
        ProfileInjuryState(0, definition.wound_limit), tuple(attack.id for attack in definition.attacks),
        definition.resilience, False, False))
