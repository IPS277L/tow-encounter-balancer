"""Composable authored Minions; derived values use PG93,97 and ordinary Tests.

This is an explicit supported component set, not a rule language. Drained is
an authored encounter permission, not an automatically acquired book talent.
"""
from dataclasses import dataclass
from enum import Enum

from towr.domain.attack_models import ConditionOnHitSpec, DamageProfile, ResilienceProfile
from towr.domain.condition_models import Condition
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_roster_models import NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatSide


class GeneratedWeapon(str, Enum):
    STAFF = 'staff'
    DAGGER = 'dagger'


class GeneratedAbility(str, Enum):
    DRAINED_ON_HIT = 'drained_on_hit'


@dataclass(frozen=True, slots=True)
class GeneratedNpc:
    weapon_skill: int
    strength: int
    toughness: int
    agility: int
    melee: int
    athletics: int
    weapon: GeneratedWeapon
    light_armour: bool
    abilities: tuple[GeneratedAbility, ...] = ()

    def __post_init__(self):
        for name in ('weapon_skill', 'strength', 'toughness', 'agility'):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f'{name} must be a positive integer')
        for name in ('melee', 'athletics'):
            value = getattr(self, name)
            if type(value) is not int or not 2 <= value <= 6:
                raise ValueError(f'{name} must be an integer in 2..6')
        if type(self.weapon) is not GeneratedWeapon or type(self.light_armour) is not bool:
            raise TypeError('equipment requires supported typed weapon and explicit armour bool')
        if (type(self.abilities) is not tuple or len(set(self.abilities)) != len(self.abilities)
                or any(type(a) is not GeneratedAbility for a in self.abilities)):
            raise TypeError('abilities must be unique supported typed components')

    def participant(self, actor_id: str) -> NpcParticipantSnapshot:
        """Build fresh state; identity never selects a mechanic."""
        definition_id = 'generated:' + actor_id
        resilience = ResilienceProfile(self.toughness, int(self.light_armour))
        attack = NpcAttackProfile(
            'primary', 'RULE-EQUIPMENT-003:' + self.weapon.value, Skill.MELEE,
            InlineProfile(self.weapon_skill, self.melee),
            DamageProfile(self.strength - int(self.weapon is GeneratedWeapon.DAGGER)),
            RangedWeaponRange.CLOSE, RangedWeaponRange.CLOSE, RangedWeaponHands.ONE_HANDED,
            secondary_effects=tuple(ConditionOnHitSpec(Condition.DRAINED, 'authored:drained-on-hit')
                for ability in self.abilities if ability is GeneratedAbility.DRAINED_ON_HIT))
        definition = NpcDefinition(definition_id, 'authored:generated-minion', TargetInjuryPolicy.MINION,
            1, resilience, (attack,), (NpcProtectionProfile('RULE-COMBAT-006:protection',
                Skill.ATHLETICS, InlineProfile(self.agility, self.athletics)),))
        state = NpcParticipantState(actor_id, definition_id, CombatSide.OPPOSITION,
            ProfileInjuryState(0, 1), (attack.id,), resilience, True, False)
        return NpcParticipantSnapshot(definition, state)
