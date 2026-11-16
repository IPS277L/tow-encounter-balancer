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
from towr.domain.ranged_weapon_profiles import (
    RangedWeaponHands, RangedWeaponRange, RangedWeaponId, ranged_weapon_combat_profile,
)
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
    PISTOL = 'pistol'
    REPEATER_PISTOL = 'repeater_pistol'
    REPEATER_HANDBOW = 'repeater_handbow'


GENERATED_RANGED_WEAPONS = (
    GeneratedWeapon.PISTOL, GeneratedWeapon.REPEATER_PISTOL, GeneratedWeapon.REPEATER_HANDBOW,
)


@dataclass(frozen=True, slots=True)
class GeneratedRangedFacts:
    ballistic_skill: int
    shooting: int
    initiative: int
    dexterity: int
    initially_loaded: bool
    ammunition_supply_confirmed: bool
    has_blackpowder_lore: bool | None
    has_blackpowder_kit: bool | None

    def __post_init__(self):
        for name in ('ballistic_skill', 'initiative'):
            if type(getattr(self,name)) is not int or getattr(self,name) < 1:
                raise ValueError(f'{name} must be a positive integer')
        for name in ('shooting', 'dexterity'):
            if type(getattr(self,name)) is not int or not 2 <= getattr(self,name) <= 6:
                raise ValueError(f'{name} must be an integer in 2..6')
        for name in ('initially_loaded', 'ammunition_supply_confirmed'):
            if type(getattr(self,name)) is not bool or not getattr(self,name):
                raise ValueError(f'generated ranged source requires confirmed {name}')
        for name in ('has_blackpowder_lore', 'has_blackpowder_kit'):
            value=getattr(self,name)
            if value is not None and type(value) is not bool:
                raise TypeError(f'{name} must be an exact bool or None')


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
    ranged: GeneratedRangedFacts | None = field(default=None,kw_only=True)

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
        if self.weapon in GENERATED_RANGED_WEAPONS:
            if type(self.ranged) is not GeneratedRangedFacts:
                raise TypeError('ranged weapon requires its complete typed ranged facts')
            replace(self.ranged)
            if self.shield:
                raise ValueError('generated ranged weapon requires the second hand free, without Shield')
            blackpowder=self.weapon is not GeneratedWeapon.REPEATER_HANDBOW
            if ((self.ranged.has_blackpowder_lore is not True or self.ranged.has_blackpowder_kit is not True)
                    if blackpowder else (self.ranged.has_blackpowder_lore is not None
                        or self.ranged.has_blackpowder_kit is not None)):
                raise ValueError('firearm requires Lore/Kit; Handbow has no Blackpowder facts')
        elif self.ranged is not None:
            raise ValueError('melee generated source must not contain ranged facts')
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
    secondary=tuple(ConditionOnHitSpec(Condition.DRAINED, 'authored:drained-on-hit')
        for ability in npc.abilities if ability is GeneratedAbility.DRAINED_ON_HIT)
    if npc.ranged is not None:
        weapon=ranged_weapon_combat_profile(RangedWeaponId(npc.weapon.value))
        attack=NpcAttackProfile('primary','RULE-EQUIPMENT-004:'+npc.weapon.value,Skill.SHOOTING,
            InlineProfile(npc.ranged.ballistic_skill,npc.ranged.shooting),DamageProfile(weapon.damage_value),
            weapon.optimum_range_min,weapon.optimum_range_max,weapon.hands,
            ignores_armour=weapon.ignores_armour,secondary_effects=secondary)
    else:
        attack = NpcAttackProfile(
            'primary', 'RULE-EQUIPMENT-003:' + npc.weapon.value, Skill.MELEE,
            InlineProfile(npc.weapon_skill, npc.melee), DamageProfile(npc.strength+offset),
            RangedWeaponRange.CLOSE, RangedWeaponRange.CLOSE, RangedWeaponHands.ONE_HANDED,
            secondary_effects=secondary)
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
