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
from towr.domain.pc_mount_models import CombatMount
from towr.domain.ranged_weapon_profiles import (
    RangedWeaponHands, RangedWeaponRange, RangedWeaponId, ranged_weapon_combat_profile,
)
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatSide


class GeneratedWeapon(str, Enum):
    STAFF = 'staff'
    DAGGER = 'dagger'
    FOOT_SPEAR = 'foot_spear'
    POLEARM = 'polearm'
    AXE = 'axe'
    SWORD = 'sword'
    WARHAMMER = 'warhammer'
    MORNING_STAR = 'morning_star'
    PICKAXE = 'pickaxe'
    FLAIL = 'flail'
    BILLHOOK = 'billhook'
    HALBERD = 'halberd'
    GLAIVE = 'glaive'
    GREATAXE = 'greataxe'
    GREATSWORD = 'greatsword'
    GREATHAMMER = 'greathammer'
    PISTOL = 'pistol'
    REPEATER_PISTOL = 'repeater_pistol'
    REPEATER_HANDBOW = 'repeater_handbow'
    SHORTBOW = 'shortbow'
    WARBOW = 'warbow'
    LONGBOW = 'longbow'
    CROSSBOW = 'crossbow'
    HANDGUN = 'handgun'
    BLUNDERBUSS = 'blunderbuss'
    HOCHLAND_LONG_RIFLE = 'hochland_long_rifle'
    REPEATER_CROSSBOW = 'repeater_crossbow'
    REPEATER_HANDGUN = 'repeater_handgun'
    WEIGHTED_NET = 'weighted_net'


GENERATED_TWO_HANDED_RANGED_WEAPONS = (
    GeneratedWeapon.SHORTBOW, GeneratedWeapon.WARBOW, GeneratedWeapon.LONGBOW,
    GeneratedWeapon.CROSSBOW, GeneratedWeapon.HANDGUN, GeneratedWeapon.BLUNDERBUSS,
    GeneratedWeapon.HOCHLAND_LONG_RIFLE, GeneratedWeapon.REPEATER_CROSSBOW,
    GeneratedWeapon.REPEATER_HANDGUN,
)


GENERATED_RANGED_WEAPONS = (
    GeneratedWeapon.PISTOL, GeneratedWeapon.REPEATER_PISTOL, GeneratedWeapon.REPEATER_HANDBOW,
    *GENERATED_TWO_HANDED_RANGED_WEAPONS,
)


# Stationary Python callers retain their explicitly Close-capable proposal pool.
# A battlefield-enabled request opts into the full enum, rather than silently
# proposing an unusable two-handed shot in the old stationary scene.
GENERATED_CLOSE_WEAPONS = tuple(weapon for weapon in GeneratedWeapon
    if weapon not in GENERATED_TWO_HANDED_RANGED_WEAPONS)


GENERATED_VARIABLE_GRIP_WEAPONS = (
    GeneratedWeapon.FOOT_SPEAR, GeneratedWeapon.POLEARM,
)


def generated_weapon_grips(weapon: GeneratedWeapon) -> tuple[RangedWeaponHands | None, ...]:
    """Explicit alternative grips; fixed weapons have no separate grip fact."""
    if type(weapon) is not GeneratedWeapon:
        raise TypeError('generated weapon grip requires its typed identifier')
    return ((RangedWeaponHands.ONE_HANDED, RangedWeaponHands.TWO_HANDED)
        if weapon in GENERATED_VARIABLE_GRIP_WEAPONS else (None,))


def generated_weapon_allows_shield(weapon: GeneratedWeapon,
        weapon_grip: RangedWeaponHands | None = None) -> bool:
    """Equipment compatibility shared by explicit facts and proposal sampling."""
    if type(weapon) is not GeneratedWeapon:
        raise TypeError('generated weapon compatibility requires its typed identifier')
    if weapon_grip is not None and type(weapon_grip) is not RangedWeaponHands:
        raise TypeError('generated weapon grip requires exact weapon hands or None')
    if weapon_grip not in generated_weapon_grips(weapon):
        raise ValueError('variable weapons require their actual grip; fixed weapons forbid it')
    if weapon in GENERATED_VARIABLE_GRIP_WEAPONS:
        return weapon_grip is RangedWeaponHands.ONE_HANDED
    if weapon in GENERATED_RANGED_WEAPONS:
        # These generated shooters must keep their second hand free for Reload.
        return False
    from towr.domain.pc_melee_models import PcMeleeWeapon
    from towr.domain.pc_weapon_models import pc_weapon_requires_two_hands
    return not pc_weapon_requires_two_hands(PcMeleeWeapon(weapon.value))


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
    awareness: int | None = field(default=None,kw_only=True)

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
        if self.awareness is not None and (type(self.awareness) is not int
                or not 2 <= self.awareness <= 6):
            raise ValueError('Awareness must be an exact Skill rating in 2..6 or None')


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
    weapon_grip: RangedWeaponHands | None = field(default=None,kw_only=True)
    mount: CombatMount | None = field(default=None,kw_only=True)
    throwing: int | None = field(default=None,kw_only=True)
    brawn: int | None = field(default=None,kw_only=True)
    ballistic_skill: int | None = field(default=None,kw_only=True)

    def __post_init__(self):
        for name in ('weapon_skill', 'strength', 'toughness', 'agility'):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f'{name} must be a positive integer')
        for name in ('melee', 'defence', 'athletics'):
            value = getattr(self, name)
            if type(value) is not int or not 2 <= value <= 6:
                raise ValueError(f'{name} must be an integer in 2..6')
        for name in ('throwing','brawn'):
            value = getattr(self,name)
            if value is not None and (type(value) is not int or not 2 <= value <= 6):
                raise ValueError(f'{name} must be an exact Skill rating in 2..6 or None')
        if (self.weapon is GeneratedWeapon.WEIGHTED_NET) != (self.throwing is not None):
            raise ValueError('Weighted Net requires its explicit Throwing source; other generated weapons forbid it')
        if self.ballistic_skill is not None and (type(self.ballistic_skill) is not int or self.ballistic_skill < 1):
            raise ValueError('Net Ballistic Skill must be an exact positive integer or None')
        if (self.weapon is GeneratedWeapon.WEIGHTED_NET) != (self.ballistic_skill is not None):
            raise ValueError('Net requires its own explicit Ballistic Skill; other weapons keep their existing source')
        if self.weapon is GeneratedWeapon.WEIGHTED_NET and self.abilities:
            raise ValueError('primary Net Condition has no authored Damage secondary effects')
        if type(self.weapon) is not GeneratedWeapon or type(self.light_armour) is not bool:
            raise TypeError('equipment requires supported typed weapon and explicit armour bool')
        if type(self.shield) is not bool:
            raise TypeError('Shield requires an exact equipment bool')
        if self.mount is not None and type(self.mount) is not CombatMount:
            raise TypeError('Mount requires an exact supported component or None')
        allows_shield = generated_weapon_allows_shield(self.weapon,self.weapon_grip)
        if self.shield and not allows_shield:
            raise ValueError('generated weapon requires both hands or a free second hand, without Shield')
        if self.weapon in GENERATED_RANGED_WEAPONS:
            if type(self.ranged) is not GeneratedRangedFacts:
                raise TypeError('ranged weapon requires its complete typed ranged facts')
            replace(self.ranged)
            blackpowder=ranged_weapon_combat_profile(
                RangedWeaponId(self.weapon.value)).requires_blackpowder_lore
            if ((self.ranged.has_blackpowder_lore is not True or self.ranged.has_blackpowder_kit is not True)
                    if blackpowder else (self.ranged.has_blackpowder_lore is not None
                        or self.ranged.has_blackpowder_kit is not None)):
                raise ValueError('firearm requires Lore/Kit; other ranged weapons forbid Blackpowder facts')
            if self.weapon in GENERATED_TWO_HANDED_RANGED_WEAPONS and self.ranged.awareness is None:
                raise ValueError('two-handed generated Shooting requires its actual Awareness for Aim')
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
    # PG97 includes any Resilience bonus in "armoured", including Horse124.
    # This does not turn the mount into physically worn Casting armour.
    resilience = ResilienceProfile(npc.toughness,
        int(npc.light_armour)+int(npc.shield)+int(npc.mount is CombatMount.HORSE))
    secondary=tuple(ConditionOnHitSpec(Condition.DRAINED, 'authored:drained-on-hit')
        for ability in npc.abilities if ability is GeneratedAbility.DRAINED_ON_HIT)
    if npc.weapon is GeneratedWeapon.WEIGHTED_NET:
        from towr.domain.pc_weighted_net_models import weighted_net_profile
        attack = weighted_net_profile(npc.ballistic_skill,npc.throwing,npc.strength)
    elif npc.ranged is not None:
        weapon=ranged_weapon_combat_profile(RangedWeaponId(npc.weapon.value))
        attack=NpcAttackProfile('primary','RULE-EQUIPMENT-004:'+npc.weapon.value,Skill.SHOOTING,
            InlineProfile(npc.ranged.ballistic_skill,npc.ranged.shooting),DamageProfile(weapon.damage_value),
            weapon.optimum_range_min,weapon.optimum_range_max,weapon.hands,
            ignores_armour=weapon.ignores_armour,secondary_effects=secondary)
    else:
        from towr.domain.pc_melee_models import PcMeleeWeapon
        from towr.domain.pc_weapon_models import pc_weapon_damage, pc_weapon_requires_two_hands
        melee_weapon = PcMeleeWeapon(npc.weapon.value)
        if npc.weapon in GENERATED_VARIABLE_GRIP_WEAPONS:
            hands = npc.weapon_grip
            assert hands is not None
            damage = pc_weapon_damage(melee_weapon,npc.strength,
                two_handed=hands is RangedWeaponHands.TWO_HANDED)
            maximum_range = RangedWeaponRange.SHORT
        else:
            hands = (RangedWeaponHands.TWO_HANDED if pc_weapon_requires_two_hands(melee_weapon)
                else RangedWeaponHands.ONE_HANDED)
            damage = pc_weapon_damage(melee_weapon,npc.strength)
            maximum_range = RangedWeaponRange.CLOSE
        attack = NpcAttackProfile(
            'primary', 'RULE-EQUIPMENT-003:' + npc.weapon.value, Skill.MELEE,
            InlineProfile(npc.weapon_skill, npc.melee), damage,
            RangedWeaponRange.CLOSE, maximum_range, hands,
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
