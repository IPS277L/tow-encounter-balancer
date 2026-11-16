"""Composable authored Minions; derived values use PG93,97 and ordinary Tests.

This is an explicit supported component set, not a rule language. Drained is
an authored encounter permission, not an automatically acquired book talent.
"""
from dataclasses import dataclass, field, replace
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
    AXE = 'axe'
    SWORD = 'sword'
    WARHAMMER = 'warhammer'
    MORNING_STAR = 'morning_star'


class GeneratedAbility(str, Enum):
    DRAINED_ON_HIT = 'drained_on_hit'


class GeneratedTalent(str, Enum):
    MAGIC_RESISTANCE = 'magic_resistance'
    DEFENSIVE_STANCE = 'defensive_stance'
    WILD_ATTACK = 'wild_attack'


def generated_talent_requirements_met(talent: GeneratedTalent, *, weapon_skill: int,
        strength: int) -> bool:
    if type(talent) is not GeneratedTalent:
        raise TypeError('generated Talent requires its typed supported identifier')
    if talent is GeneratedTalent.DEFENSIVE_STANCE:
        return weapon_skill >= 3
    if talent is GeneratedTalent.WILD_ATTACK:
        return strength >= 4
    return True


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
    defence: int = field(kw_only=True)
    shield: bool = field(kw_only=True)
    talents: tuple[GeneratedTalent, ...] = field(default=(),kw_only=True)

    def __post_init__(self):
        for name in ('weapon_skill', 'strength', 'toughness', 'agility'):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f'{name} must be a positive integer')
        for name in ('melee', 'defence', 'athletics'):
            value = getattr(self, name)
            if type(value) is not int or not 2 <= value <= 6:
                raise ValueError(f'{name} must be an integer in 2..6')
        if type(self.weapon) is not GeneratedWeapon or type(self.light_armour) is not bool:
            raise TypeError('equipment requires supported typed weapon and explicit armour bool')
        if type(self.shield) is not bool:
            raise TypeError('Shield requires an exact equipment bool')
        if (type(self.abilities) is not tuple or len(set(self.abilities)) != len(self.abilities)
                or any(type(a) is not GeneratedAbility for a in self.abilities)):
            raise TypeError('abilities must be unique supported typed components')
        if (type(self.talents) is not tuple
                or any(type(talent) is not GeneratedTalent for talent in self.talents)
                or len(set(self.talents)) != len(self.talents)):
            raise TypeError('Talents require unique supported typed single acquisitions')
        if any(not generated_talent_requirements_met(talent,weapon_skill=self.weapon_skill,
                strength=self.strength) for talent in self.talents):
            raise ValueError('generated Talent Requirements are not met')

    def participant(self, actor_id: str) -> NpcParticipantSnapshot:
        """Build fresh state; identity never selects a mechanic."""
        definition_id = 'generated:' + actor_id
        resilience, attack, protection = generated_npc_profiles(self)
        definition = NpcDefinition(definition_id, 'authored:generated-minion', TargetInjuryPolicy.MINION,
            1, resilience, (attack,), protection, generated_components=self)
        state = NpcParticipantState(actor_id, definition_id, CombatSide.OPPOSITION,
            ProfileInjuryState(0, 1), (attack.id,), resilience, True, self.shield)
        return NpcParticipantSnapshot(definition, state)


def generated_npc_profiles(npc: GeneratedNpc) -> tuple[
        ResilienceProfile,NpcAttackProfile,tuple[NpcProtectionProfile,...]]:
    """Derive the complete admitted combat source from facts, without identity."""
    if type(npc) is not GeneratedNpc:
        raise TypeError('generated components require the complete typed facts')
    replace(npc)
    resilience = ResilienceProfile(npc.toughness, int(npc.light_armour)+int(npc.shield))
    offset = -1 if npc.weapon is GeneratedWeapon.DAGGER else int(npc.weapon is GeneratedWeapon.MORNING_STAR)
    attack = NpcAttackProfile(
            'primary', 'RULE-EQUIPMENT-003:' + npc.weapon.value, Skill.MELEE,
            InlineProfile(npc.weapon_skill, npc.melee), DamageProfile(npc.strength+offset),
            RangedWeaponRange.CLOSE, RangedWeaponRange.CLOSE, RangedWeaponHands.ONE_HANDED,
            secondary_effects=tuple(ConditionOnHitSpec(Condition.DRAINED, 'authored:drained-on-hit')
                for ability in npc.abilities if ability is GeneratedAbility.DRAINED_ON_HIT))
    protection = (
        NpcProtectionProfile('RULE-COMBAT-006:generated-defence', Skill.DEFENCE,
            InlineProfile(npc.weapon_skill,npc.defence)),
        NpcProtectionProfile('RULE-COMBAT-006:generated-athletics', Skill.ATHLETICS,
            InlineProfile(npc.agility,npc.athletics)))
    return resilience, attack, protection


def validate_generated_definition(definition: NpcDefinition) -> None:
    """A label alone cannot grant components; rederive every numeric/profile fact."""
    npc = definition.generated_components
    if npc is None:
        if definition.source_rule_id == 'authored:generated-minion':
            raise ValueError('generated NPC source must retain its complete components')
        return
    resilience,attack,protection = generated_npc_profiles(npc)
    if (definition.source_rule_id != 'authored:generated-minion'
            or definition.injury_policy is not TargetInjuryPolicy.MINION
            or type(definition.wound_limit) is not int or definition.wound_limit != 1
            or definition.resilience != resilience or definition.attacks != (attack,)
            or definition.protection != protection):
        raise ValueError('NPC combat source differs from its complete generated components')
