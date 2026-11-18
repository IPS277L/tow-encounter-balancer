"""Composable authored Minions; derived values use PG93,97 and ordinary Tests.

This is an explicit supported component set, not a rule language. Drained is
an authored encounter permission, not an automatically acquired book talent.
"""
from dataclasses import dataclass, field, replace
from enum import Enum

from towr.domain.attack_models import ConditionOnHitSpec, DamageProfile, ResilienceProfile
from towr.domain.armour_models import (
    ArmourLoadout, BodyArmour, body_resilience_bonus, helmet_resilience_bonus,
    armour_is_worn, active_agilulf, armour_burden_sources,
    protects_against_mundane_armour_effects,
)
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_roster_models import NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile
from towr.domain.pc_mount_models import (
    CombatMount, RiderKind, mount_source_resilience_bonus, validate_mount_rider,
)
from towr.domain.ranged_weapon_profiles import (
    RangedWeaponHands, RangedWeaponRange, RangedWeaponId, ranged_weapon_combat_profile,
)
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatSide
from towr.domain.weapon_catalog import WeaponKind, weapon_profile, weapon_printed_damage
from towr.domain.weapon_capability_models import weapon_ranged_requirements
from towr.domain.weapon_inventory_models import (
    WeaponGrip, WeaponItemLocation, WeaponItemSource, WeaponInventoryState,
    initial_weapon_inventory, weapon_unit_id,
)


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
    # The same printed hands govern all roles. A real Reload still has to
    # free the Shield hand through its source-bound equipment owner.
    return weapon_profile(WeaponKind(weapon.value)).hands is RangedWeaponHands.ONE_HANDED


@dataclass(frozen=True, slots=True)
class GeneratedRangedFacts:
    ballistic_skill: int
    shooting: int
    initiative: int | None
    dexterity: int | None
    ammunition_supply_confirmed: bool
    has_blackpowder_lore: bool | None
    has_blackpowder_kit: bool | None
    awareness: int | None = field(default=None,kw_only=True)

    def __post_init__(self):
        if type(self.ballistic_skill) is not int or self.ballistic_skill < 1:
            raise ValueError('ballistic_skill must be a positive exact integer')
        if type(self.shooting) is not int or not 2 <= self.shooting <= 6:
            raise ValueError('shooting must be an exact integer in 2..6')
        if self.initiative is not None and (type(self.initiative) is not int or self.initiative < 1):
            raise ValueError('initiative must be a positive exact integer or None')
        if self.dexterity is not None and (type(self.dexterity) is not int or not 2 <= self.dexterity <= 6):
            raise ValueError('dexterity must be an exact integer in 2..6 or None')
        if self.ammunition_supply_confirmed is not True:
            raise ValueError('generated Shooting requires confirmed ammunition supply')
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
    weapons: tuple[WeaponItemSource, ...]
    armour: ArmourLoadout
    abilities: tuple[GeneratedAbility, ...] = ()
    defence: int = field(kw_only=True)
    talents: tuple[GeneratedTalent, ...] = field(default=(),kw_only=True)
    ranged: GeneratedRangedFacts | None = field(default=None,kw_only=True)
    mount: CombatMount | None = field(default=None,kw_only=True)
    rider_kind: RiderKind | None = field(default=None,kw_only=True)
    agilulf_code_confirmed: bool | None = field(default=None,kw_only=True)
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
        if (type(self.weapons) is not tuple or not self.weapons
                or any(type(item) is not WeaponItemSource for item in self.weapons)):
            raise TypeError('generated equipment needs its complete ordered physical sources')
        for item in self.weapons:
            replace(item)
            if item.kind.value not in GeneratedWeapon._value2member_map_:
                raise ValueError('generated weapon item has no implemented encounter owner')
        if len({item.id for item in self.weapons}) != len(self.weapons):
            raise ValueError('generated initial weapon item IDs must be unique')
        if not any(item.initial_location is WeaponItemLocation.HELD for item in self.weapons):
            raise ValueError('generated equipment requires an initially held primary')
        has_net = any(item.kind is WeaponKind.WEIGHTED_NET for item in self.weapons)
        if has_net != (self.throwing is not None):
            raise ValueError('Throwing belongs to the complete inventory containing Weighted Nets')
        if self.ballistic_skill is not None and (type(self.ballistic_skill) is not int or self.ballistic_skill < 1):
            raise ValueError('Net Ballistic Skill must be an exact positive integer or None')
        if not has_net and self.ballistic_skill is not None:
            raise ValueError('a separate Throwing Ballistic Skill requires a Net inventory item')
        if type(self.armour) is not ArmourLoadout:
            raise TypeError('equipment requires its full typed ArmourLoadout')
        replace(self.armour)
        if self.armour.barding and self.mount is None:
            raise ValueError('Barding requires its actual compatible mount')
        if BodyArmour.AGILULF in self.armour.body:
            if self.agilulf_code_confirmed is not True:
                raise ValueError('Agilulf requires an explicit confirmed chivalric scene')
            if self.weapon in (*GENERATED_RANGED_WEAPONS,GeneratedWeapon.WEIGHTED_NET):
                raise ValueError('Agilulf prohibits an initial Shooting/Throwing Attack')
        elif self.agilulf_code_confirmed is not None:
            raise ValueError('chivalric confirmation belongs to actually worn Agilulf')
        validate_mount_rider(self.mount,self.rider_kind)
        requirements = weapon_ranged_requirements(tuple(item.kind for item in self.weapons))
        if requirements is None:
            if self.ranged is not None:
                raise ValueError('Shooting preparation requires an actual Shooting item')
        else:
            if type(self.ranged) is not GeneratedRangedFacts:
                raise TypeError('Shooting inventory requires its complete typed actor facts')
            replace(self.ranged)
            for name in ('has_blackpowder_lore','has_blackpowder_kit'):
                if getattr(self.ranged,name) is not (True if requirements.firearm else None):
                    raise ValueError('Blackpowder facts must match the whole firearm inventory')
            if requirements.exacting:
                if self.ranged.initiative is None or self.ranged.dexterity is None:
                    raise ValueError('Exacting inventory requires actual Initiative and Dexterity')
            elif self.ranged.dexterity is not None:
                raise ValueError('free-reload-only inventory has no Exacting Dexterity')
            if (any(GeneratedWeapon(item.kind.value) in GENERATED_TWO_HANDED_RANGED_WEAPONS
                    for item in self.weapons) and self.ranged.awareness is None):
                raise ValueError('two-handed generated Shooting requires actual Awareness for Aim')
            if self.ranged.awareness is not None and self.ranged.initiative is None:
                raise ValueError('actual NPC Aim requires Initiative with Awareness')
        if has_net:
            if self.ranged is None and self.ballistic_skill is None:
                raise ValueError('Net inventory requires its actual Ballistic Skill')
            if (self.ranged is not None and self.ballistic_skill is not None
                    and self.ballistic_skill != self.ranged.ballistic_skill):
                raise ValueError('Shooting and Throwing share the same Ballistic Skill')
        _initial_generated_inventory(self,'generated:source-validation')
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
        resilience, attacks, protection = generated_npc_profiles(self)
        definition = NpcDefinition(definition_id, 'authored:generated-minion', TargetInjuryPolicy.MINION,
            1, resilience, attacks, protection, generated_components=self)
        conditions=ConditionState(frozenset((Condition.BURDENED,))
            if armour_burden_sources(self.armour,self.strength) else frozenset())
        state = NpcParticipantState(actor_id, definition_id, CombatSide.OPPOSITION,
            ProfileInjuryState(0, 1,conditions), tuple(attack.id for attack in attacks), resilience, True, self.shield)
        return NpcParticipantSnapshot(definition, state)

    @property
    def weapon(self) -> GeneratedWeapon:
        """The initially selected item kind; runtime use belongs to the inventory."""
        primary = next(item for item in self.weapons
            if item.initial_location is WeaponItemLocation.HELD)
        return GeneratedWeapon(primary.kind.value)

    @property
    def weapon_grip(self) -> RangedWeaponHands | None:
        """Initial printed grip view, never a mutable combat selection."""
        primary = next(item for item in self.weapons
            if item.initial_location is WeaponItemLocation.HELD)
        if not weapon_profile(primary.kind).variable_grip:
            return None
        return (RangedWeaponHands.TWO_HANDED if primary.initial_grip is WeaponGrip.BOTH
            else RangedWeaponHands.ONE_HANDED)

    @property
    def shield(self) -> bool:
        """Held Shield presence is derived from its complete source item."""
        return self.armour.shield is not None


def generated_npc_combat_ratings(npc: GeneratedNpc) -> tuple[int,int,int]:
    """Current WS/Melee/Defence benefits without rewriting their source facts."""
    if type(npc) is not GeneratedNpc:
        raise TypeError('generated ratings require the complete typed facts')
    replace(npc)
    return ((5,5,5) if active_agilulf(npc.armour)
        else (npc.weapon_skill,npc.melee,npc.defence))


def _initial_generated_inventory(npc: GeneratedNpc, actor_id: str) -> WeaponInventoryState:
    primary = next(item for item in npc.weapons
        if item.initial_location is WeaponItemLocation.HELD)
    occupied = set()
    for item in npc.weapons:
        if item.initial_location is WeaponItemLocation.HELD:
            occupied.update((WeaponGrip.LEFT,WeaponGrip.RIGHT) if item.initial_grip is WeaponGrip.BOTH
                else (item.initial_grip,))
    shield_hand = None
    if npc.shield:
        shield_hand = next((hand for hand in (WeaponGrip.RIGHT,WeaponGrip.LEFT)
            if hand not in occupied),None)
        if shield_hand is None:
            raise ValueError('a held Shield requires its own free physical hand')
    return initial_weapon_inventory(actor_id,npc.weapons,
        active_item_id=weapon_unit_id(actor_id,primary.id,0),shield_hand=shield_hand)


def generated_initial_weapon_inventory(npc: GeneratedNpc, actor_id: str) -> WeaponInventoryState:
    """Expand complete physical sources once, with a source-derived Shield hand."""
    if type(npc) is not GeneratedNpc:
        raise TypeError('generated inventory requires its complete exact source')
    replace(npc)
    return _initial_generated_inventory(npc,actor_id)


def _generated_item_grips(item: WeaponItemSource) -> tuple[WeaponGrip,...]:
    profile = weapon_profile(item.kind)
    if profile.variable_grip:
        return (WeaponGrip.LEFT,WeaponGrip.RIGHT,WeaponGrip.BOTH)
    return ((WeaponGrip.BOTH,) if profile.hands is RangedWeaponHands.TWO_HANDED
        else (WeaponGrip.LEFT,WeaponGrip.RIGHT))


def generated_weapon_attack_id(item_id: str, grip: WeaponGrip) -> str:
    """Injective source identity; equal kinds remain distinct physical choices."""
    if type(item_id) is not str or not item_id.strip():
        raise TypeError('generated Attack requires its exact source item ID')
    if type(grip) is not WeaponGrip:
        raise TypeError('generated Attack requires its exact physical grip')
    return 'generated-weapon:'+str(len(item_id))+':'+item_id+':'+grip.value


def _generated_weapon_attack(npc: GeneratedNpc, item: WeaponItemSource,
        grip: WeaponGrip) -> NpcAttackProfile:
    identifier = generated_weapon_attack_id(item.id,grip)
    if grip not in _generated_item_grips(item):
        raise ValueError('generated Attack grip differs from its physical item')
    if item.kind is WeaponKind.WEIGHTED_NET:
        from towr.domain.pc_weighted_net_models import weighted_net_profile
        ballistic_skill = npc.ballistic_skill if npc.ballistic_skill is not None else npc.ranged.ballistic_skill
        return replace(weighted_net_profile(ballistic_skill,npc.throwing,npc.strength),id=identifier)
    secondary = tuple(ConditionOnHitSpec(Condition.DRAINED,'authored:drained-on-hit')
        for ability in npc.abilities if ability is GeneratedAbility.DRAINED_ON_HIT)
    if GeneratedWeapon(item.kind.value) in GENERATED_RANGED_WEAPONS:
        weapon = ranged_weapon_combat_profile(RangedWeaponId(item.kind.value))
        damage = weapon_printed_damage(item.kind,strength=npc.strength)
        assert damage is not None
        return NpcAttackProfile(identifier,'RULE-EQUIPMENT-004:'+item.kind.value,Skill.SHOOTING,
            InlineProfile(npc.ranged.ballistic_skill,npc.ranged.shooting),DamageProfile(damage),
            weapon.optimum_range_min,weapon.optimum_range_max,weapon.hands,
            ignores_armour=weapon.ignores_armour,secondary_effects=secondary)
    profile = weapon_profile(item.kind)
    hands = RangedWeaponHands.TWO_HANDED if grip is WeaponGrip.BOTH else RangedWeaponHands.ONE_HANDED
    damage = weapon_printed_damage(item.kind,strength=npc.strength,
        two_handed=hands is RangedWeaponHands.TWO_HANDED)
    assert damage is not None and profile.maximum_range is not None
    weapon_skill,melee,_ = generated_npc_combat_ratings(npc)
    return NpcAttackProfile(identifier,'RULE-EQUIPMENT-003:'+item.kind.value,Skill.MELEE,
        InlineProfile(weapon_skill,melee),DamageProfile(damage),RangedWeaponRange.CLOSE,
        profile.maximum_range,hands,secondary_effects=secondary)


def generated_weapon_attack_profile(npc: GeneratedNpc, item_id: str,
        grip: WeaponGrip) -> NpcAttackProfile:
    """Rederive one exact source-item/grip profile, not permission to use it.

    Runtime owners pass the actual unit's source_item_id and prove that unit's
    current location, grip, readiness and selected action separately.
    """
    if type(npc) is not GeneratedNpc:
        raise TypeError('generated Attack requires the complete typed facts')
    replace(npc)
    generated_weapon_attack_id(item_id,grip)
    item = next((item for item in npc.weapons if item.id == item_id),None)
    if item is None:
        raise ValueError('generated Attack source item does not belong to this definition')
    return _generated_weapon_attack(npc,item,grip)


def generated_npc_profiles(npc: GeneratedNpc) -> tuple[
        ResilienceProfile,tuple[NpcAttackProfile,...],tuple[NpcProtectionProfile,...]]:
    """Derive every physical item/grip choice without choosing a runtime use."""
    if type(npc) is not GeneratedNpc:
        raise TypeError('generated components require the complete typed facts')
    replace(npc)
    bonus = (body_resilience_bonus(npc.armour)+helmet_resilience_bonus(npc.armour)
        +int(npc.shield)+mount_source_resilience_bonus(npc.mount)+int(npc.armour.barding))
    resilience = ResilienceProfile(npc.toughness,bonus,
        armoured=True if armour_is_worn(npc.armour) and bonus == 0 else None,
        mundane_armour_ward=protects_against_mundane_armour_effects(npc.armour))
    weapon_skill,_,defence = generated_npc_combat_ratings(npc)
    attacks = tuple(_generated_weapon_attack(npc,item,grip)
        for item in npc.weapons for grip in _generated_item_grips(item))
    protection = (
        NpcProtectionProfile('RULE-COMBAT-006:generated-defence',Skill.DEFENCE,
            InlineProfile(weapon_skill,defence)),
        NpcProtectionProfile('RULE-COMBAT-006:generated-athletics',Skill.ATHLETICS,
            InlineProfile(npc.agility,npc.athletics)))
    return resilience,attacks,protection


def validate_generated_definition(definition: NpcDefinition) -> None:
    """A label alone cannot grant components; rederive every numeric/profile fact."""
    npc = definition.generated_components
    if npc is None:
        if definition.source_rule_id == 'authored:generated-minion':
            raise ValueError('generated NPC source must retain its complete components')
        return
    resilience,attacks,protection = generated_npc_profiles(npc)
    if (definition.source_rule_id != 'authored:generated-minion'
            or definition.injury_policy is not TargetInjuryPolicy.MINION
            or type(definition.wound_limit) is not int or definition.wound_limit != 1
            or definition.resilience != resilience or definition.attacks != attacks
            or definition.protection != protection):
        raise ValueError('NPC combat source differs from its complete generated components')
