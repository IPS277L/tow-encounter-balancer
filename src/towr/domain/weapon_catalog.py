"""Printed weapon facts from PG1.4 IV92–96 and GM1.1 VI82–84/VII103.

This catalogue does not admit equipment to a scenario or execute its Traits.
Trait codes identify explicit future owners; they are not a rules language.
For Throwing, ``maximum_range=None`` means no *separate fixed* maximum: the
optimum band and actual Strength determine the legal range (PG96). For 2H
Shooting it means the GM supplies a reasonable maximum (PG94), not unlimited
range. Unarmed is an attack option, not a physical inventory item.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from towr.domain.ranged_weapon_profiles import (
    RangedWeaponDamageKind, RangedWeaponHands, RangedWeaponId, RangedWeaponRange,
    ranged_weapon_combat_profile,
)
from towr.domain.test_models import Skill


class WeaponKind(str, Enum):
    UNARMED = 'unarmed'
    KNUCKLEDUSTERS = 'knuckledusters'
    DAGGER = 'dagger'
    STAFF = 'staff'
    FOOT_SPEAR = 'foot_spear'
    CAVALRY_SPEAR = 'cavalry_spear'
    AXE = 'axe'
    PICKAXE = 'pickaxe'
    SWORD = 'sword'
    WARHAMMER = 'warhammer'
    MORNING_STAR = 'morning_star'
    POLEARM = 'polearm'
    FLAIL = 'flail'
    BILLHOOK = 'billhook'
    HALBERD = 'halberd'
    GLAIVE = 'glaive'
    GREATAXE = 'greataxe'
    GREATSWORD = 'greatsword'
    GREATHAMMER = 'greathammer'
    LANCE = 'lance'
    SLING = 'sling'
    SHORTBOW = 'shortbow'
    WARBOW = 'warbow'
    LONGBOW = 'longbow'
    CROSSBOW = 'crossbow'
    PISTOL = 'pistol'
    HANDGUN = 'handgun'
    BLUNDERBUSS = 'blunderbuss'
    HOCHLAND_LONG_RIFLE = 'hochland_long_rifle'
    REPEATER_HANDBOW = 'repeater_handbow'
    REPEATER_CROSSBOW = 'repeater_crossbow'
    REPEATER_PISTOL = 'repeater_pistol'
    REPEATER_HANDGUN = 'repeater_handgun'
    ROCK = 'rock'
    THROWING_SPEAR = 'throwing_spear'
    THROWING_AXE = 'throwing_axe'
    WEIGHTED_NET = 'weighted_net'
    THROWING_KNIVES = 'throwing_knives'
    OIL_FLASK = 'oil_flask'
    BLASTING_CHARGE = 'blasting_charge'
    DRAGON_BOW = 'dragon_bow'
    DUELLIST_BLADES = 'duellist_blades'
    GROTARGGS_HAMMER = 'grotarggs_hammer'
    HEADSMANS_AXE = 'headsmans_axe'
    MORNING_STAR_OF_FRACASSE = 'morning_star_of_fracasse'
    SCARAB_KNIFE = 'scarab_knife'
    TRICKSTER_BLADE = 'trickster_blade'
    UNWAVERING_SPEAR = 'unwavering_spear'
    SWORD_OF_JUSTICE = 'sword_of_justice'
    OGRE_PISTOL = 'ogre_pistol'


class WeaponGroup(str, Enum):
    MELEE = 'melee'
    SHOOTING = 'shooting'
    THROWING = 'throwing'


class WeaponDamageKind(str, Enum):
    NONE = 'none'
    FIXED = 'fixed'
    STRENGTH = 'strength'


class WeaponBook(str, Enum):
    PLAYER_GUIDE = 'player-guide:1.4'
    GAMEMASTER_GUIDE = 'gamemaster-guide:1.1'


class WeaponTrait(str, Enum):
    STAGGER_INSTEAD_OF_DAMAGE = 'stagger_instead_of_damage'
    NO_DEFENCE = 'no_defence'
    CONCEALMENT_STEALTH_PLUS_ONE = 'concealment_stealth_plus_one'
    DIFFICULT_TERRAIN_ATHLETICS_PLUS_ONE = 'difficult_terrain_athletics_plus_one'
    CHARGE_DEFENCE_PLUS_ONE = 'charge_defence_plus_one'
    FOOT_SPEAR_TWO_HANDED_DAMAGE_PLUS_ONE = 'foot_spear_two_handed_damage_plus_one'
    MOUNTED_CHARGE_MELEE_PLUS_ONE = 'mounted_charge_melee_plus_one'
    ARMOURED_TARGET_DAMAGE_PLUS_ONE = 'armoured_target_damage_plus_one'
    RESOURCE_HARVEST_TOIL_PLUS_ONE = 'resource_harvest_toil_plus_one'
    READY_DEFENCE_PLUS_ONE_DIE = 'ready_defence_plus_one_die'
    STAGGERED_TARGET_MELEE_PLUS_ONE = 'staggered_target_melee_plus_one'
    STAGGERED_MELEE_MINUS_ONE = 'staggered_melee_minus_one'
    POLEARM_TWO_HANDED_DAMAGE_PLUS_TWO = 'polearm_two_handed_damage_plus_two'
    STAGGERED_MELEE_MINUS_TWO = 'staggered_melee_minus_two'
    MOUNTED_TARGET_MELEE_PLUS_ONE = 'mounted_target_melee_plus_one'
    MELEE_MINUS_ONE = 'melee_minus_one'
    # PG93 omits the d here; the existing engine's user-approved +1d reading
    # remains its own explicit decision, rather than changing the printed row.
    GREATSWORD_PRINTED_READY_DEFENCE_PLUS_ONE = 'greatsword_printed_ready_defence_plus_one'
    MOUNTED_CHARGE_DAMAGE_PLUS_ONE = 'mounted_charge_damage_plus_one'
    SHORT_SHOOTING_PLUS_ONE = 'short_shooting_plus_one'
    SHORT_SHOOTING_PLUS_TWO = 'short_shooting_plus_two'
    IGNORES_ARMOUR = 'ignores_armour'
    RELOAD_TWO_SUCCESSES = 'reload_two_successes'
    RELOAD_THREE_SUCCESSES = 'reload_three_successes'
    RELOAD_FOUR_SUCCESSES = 'reload_four_successes'
    RELOAD_FIVE_AFTER_BONUS = 'reload_five_after_bonus'
    RELOAD_THREE_AFTER_BONUS = 'reload_three_after_bonus'
    OPTIONAL_SHOOTING_PLUS_ONE = 'optional_shooting_plus_one'
    OPTIONAL_SHOOTING_PLUS_TWO = 'optional_shooting_plus_two'
    OPTIONAL_SHOOTING_PLUS_THREE = 'optional_shooting_plus_three'
    BLACKPOWDER_LORE_REQUIRED = 'blackpowder_lore_required'
    HIT_NEARBY_STAGGER = 'hit_nearby_stagger'
    AIM_REQUIRED = 'aim_required'
    WOUNDS_TABLE_PLUS_ONE_DIE = 'wounds_table_plus_one_die'
    NO_DIRECT_WOUND = 'no_direct_wound'
    BURDENED_INSTEAD_OF_DAMAGE = 'burdened_instead_of_damage'
    KNIVES_FOR_WHOLE_BATTLE = 'knives_for_whole_battle'
    HIT_TARGET_AND_NEARBY_ABLAZE = 'hit_target_and_nearby_ablaze'
    HAZARD_THREE_IN_TARGET_ZONE_OR_OWN_ON_MISS = 'hazard_three_in_target_zone_or_own_on_miss'
    NO_ATTACK_DIE_PENALTIES_OR_GRIM = 'no_attack_die_penalties_or_grim'
    CANNOT_ATTACK_UNSEEN_TARGET = 'cannot_attack_unseen_target'
    ONCE_PER_BATTLE_HIT_ABLAZE = 'once_per_battle_hit_ablaze'
    READY_DEFENCE_PLUS_TWO_DICE = 'ready_defence_plus_two_dice'
    SECOND_ATTACK_ACTION = 'second_attack_action'
    OPTIONAL_GRIM_AND_GLORIOUS_PAIR = 'optional_grim_and_glorious_pair'
    HIGHER_GROUND_GLORIOUS = 'higher_ground_glorious'
    HIGHER_GROUND_MISS_STUCK = 'higher_ground_miss_stuck'
    STUCK_RETRIEVAL_BRAWN_MINUS_TWO = 'stuck_retrieval_brawn_minus_two'
    PRONE_GRIM_WOUND_DECAPITATION = 'prone_grim_wound_decapitation'
    HIT_DISARMS_MAGIC_WEAPON = 'hit_disarms_magic_weapon'
    HIT_DRAINED = 'hit_drained'
    WOUNDS_CHARGE_BLADE = 'wounds_charge_blade'
    THREE_CHARGES_HEAL_WOUND = 'three_charges_heal_wound'
    CHARGES_EXPIRE_AT_SUNSET = 'charges_expire_at_sunset'
    APPEARANCE_AS_COMMON_TRAPPING = 'appearance_as_common_trapping'
    FORBIDS_GIVE_GROUND = 'forbids_give_ground'
    GIVEN_GROUND_THIS_ROUND_GLORIOUS = 'given_ground_this_round_glorious'
    BROKEN_REGROWS_NEXT_DOWNTIME_UNLESS_BURNED = 'broken_regrows_next_downtime_unless_burned'
    CHAMPION_OR_PC_SINGLE_COMBAT_GLORIOUS = 'champion_or_pc_single_combat_glorious'


MAGIC_WEAPON_KINDS = frozenset((WeaponKind.DRAGON_BOW, WeaponKind.DUELLIST_BLADES,
    WeaponKind.GROTARGGS_HAMMER, WeaponKind.HEADSMANS_AXE, WeaponKind.MORNING_STAR_OF_FRACASSE,
    WeaponKind.SCARAB_KNIFE, WeaponKind.TRICKSTER_BLADE, WeaponKind.UNWAVERING_SPEAR,
    WeaponKind.SWORD_OF_JUSTICE))
_VARIABLE_GRIP = frozenset((WeaponKind.FOOT_SPEAR, WeaponKind.POLEARM))
_RANGE_RANK = {band: index for index, band in enumerate(RangedWeaponRange)}


@dataclass(frozen=True, slots=True)
class WeaponProfile:
    """One printed row; Strength damage_value is an offset, not fixed Damage.

    Throwing maximum_range=None has no independent fixed limit. Its legal
    maximum still follows the printed optimum band and the PG96 Strength rule.
    """
    kind: WeaponKind
    group: WeaponGroup
    skill: Skill
    hands: RangedWeaponHands | None
    physical: bool
    damage_kind: WeaponDamageKind
    damage_value: int | None
    maximum_range: RangedWeaponRange | None
    optimum_range_min: RangedWeaponRange | None
    optimum_range_max: RangedWeaponRange | None
    variable_grip: bool
    magical: bool
    dual_wield_allowed: bool
    trait_codes: tuple[WeaponTrait, ...]
    source_book: WeaponBook
    source_chapter: str
    source_page: int

    def __post_init__(self):
        for name, cls in (('kind', WeaponKind), ('group', WeaponGroup), ('skill', Skill),
                ('damage_kind', WeaponDamageKind), ('source_book', WeaponBook)):
            if type(getattr(self, name)) is not cls:
                raise TypeError(name+' requires its exact typed catalogue value')
        for name in ('physical', 'variable_grip', 'magical', 'dual_wield_allowed'):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name+' requires an exact bool')
        if self.hands is not None and type(self.hands) is not RangedWeaponHands:
            raise TypeError('printed hands must be exact 1H/2H or None')
        if (self.hands is None) != (self.kind in (WeaponKind.UNARMED, WeaponKind.ROCK)):
            raise ValueError('only Unarmed and Rock have no printed hand count')
        if self.physical is not (self.kind is not WeaponKind.UNARMED):
            raise ValueError('Unarmed is the sole non-physical attack option')
        if self.magical is not (self.kind in MAGIC_WEAPON_KINDS):
            raise ValueError('only the nine stated GM magic weapons have magical source')
        if self.variable_grip is not (self.kind in _VARIABLE_GRIP):
            raise ValueError('variable grip belongs to Foot Spear and Polearm')
        dual = (self.group is WeaponGroup.MELEE and self.hands is RangedWeaponHands.ONE_HANDED
            and self.kind not in (WeaponKind.MORNING_STAR, WeaponKind.LANCE))
        if self.dual_wield_allowed is not dual:
            raise ValueError('dual wield follows the actual printed melee hand count and exclusions')
        expected_skill = (Skill.BRAWN if self.kind in (WeaponKind.UNARMED, WeaponKind.KNUCKLEDUSTERS)
            else {WeaponGroup.MELEE: Skill.MELEE, WeaponGroup.SHOOTING: Skill.SHOOTING,
                WeaponGroup.THROWING: Skill.THROWING}[self.group])
        if self.skill is not expected_skill:
            raise ValueError('weapon group and printed attack Skill disagree')
        if self.damage_kind is WeaponDamageKind.NONE:
            if self.damage_value is not None:
                raise ValueError('a non-Damage attack has no numeric Damage')
        elif type(self.damage_value) is not int:
            raise TypeError('Damage requires an exact fixed value or Strength offset')
        elif self.damage_kind is WeaponDamageKind.FIXED and self.damage_value < 1:
            raise ValueError('printed fixed Damage must be positive')
        for band in (self.maximum_range, self.optimum_range_min, self.optimum_range_max):
            if band is not None and type(band) is not RangedWeaponRange:
                raise TypeError('weapon ranges require exact typed bands or None')
        if self.group is WeaponGroup.MELEE:
            if self.maximum_range is None or self.optimum_range_min is not None or self.optimum_range_max is not None:
                raise ValueError('melee has a printed maximum, without an optimum band')
        else:
            if (self.optimum_range_min is None or self.optimum_range_max is None
                    or _RANGE_RANK[self.optimum_range_min] > _RANGE_RANK[self.optimum_range_max]):
                raise ValueError('Shooting and Throwing require an ordered optimum band')
            if self.maximum_range is not None and _RANGE_RANK[self.maximum_range] < _RANGE_RANK[self.optimum_range_max]:
                raise ValueError('fixed maximum cannot precede optimum range')
            if self.group is WeaponGroup.THROWING and self.maximum_range is not None:
                raise ValueError('Throwing derives its maximum from optimum and actual Strength')
        if (type(self.trait_codes) is not tuple or any(type(trait) is not WeaponTrait for trait in self.trait_codes)
                or len(set(self.trait_codes)) != len(self.trait_codes)):
            raise TypeError('weapon Traits require a unique exact typed tuple')
        if type(self.source_chapter) is not str or self.source_chapter not in ('IV', 'VI', 'VII'):
            raise ValueError('weapon source requires its actual book chapter')
        if type(self.source_page) is not int or self.source_page < 1:
            raise ValueError('weapon source page must be an exact positive integer')


def _melee(kind, offset, *, hands=RangedWeaponHands.ONE_HANDED, traits=(),
        maximum=RangedWeaponRange.CLOSE, magical=False, page=93):
    return WeaponProfile(kind, WeaponGroup.MELEE,
        Skill.BRAWN if kind in (WeaponKind.UNARMED, WeaponKind.KNUCKLEDUSTERS) else Skill.MELEE,
        hands, kind is not WeaponKind.UNARMED,
        WeaponDamageKind.NONE if offset is None else WeaponDamageKind.STRENGTH, offset,
        maximum, None, None, kind in _VARIABLE_GRIP, magical,
        hands is RangedWeaponHands.ONE_HANDED and kind not in (WeaponKind.MORNING_STAR, WeaponKind.LANCE),
        traits, WeaponBook.GAMEMASTER_GUIDE if magical else WeaponBook.PLAYER_GUIDE,
        'VI' if magical else 'IV', page)


def _shooting(kind, *, traits=()):
    # Reuse the existing printed ranged facts, including Sling's S Damage and
    # Ogre Pistol's distinct Close–Medium optimum; no current enum is expanded.
    source = ranged_weapon_combat_profile(RangedWeaponId(kind.value))
    strength = source.damage_kind is RangedWeaponDamageKind.STRENGTH
    ogre = kind is WeaponKind.OGRE_PISTOL
    return WeaponProfile(kind, WeaponGroup.SHOOTING, Skill.SHOOTING, source.hands, True,
        WeaponDamageKind.STRENGTH if strength else WeaponDamageKind.FIXED,
        0 if strength else source.damage_value, source.maximum_range,
        source.optimum_range_min, source.optimum_range_max, False, False, False, traits,
        WeaponBook.GAMEMASTER_GUIDE if ogre else WeaponBook.PLAYER_GUIDE,
        'VII' if ogre else 'IV', 103 if ogre else 95)


def _throwing(kind, offset, minimum, maximum, *, hands=RangedWeaponHands.ONE_HANDED, traits=()):
    return WeaponProfile(kind, WeaponGroup.THROWING, Skill.THROWING, hands, True,
        WeaponDamageKind.NONE if offset is None else WeaponDamageKind.STRENGTH, offset,
        None, minimum, maximum, False, False, False, traits, WeaponBook.PLAYER_GUIDE, 'IV', 96)


_W, _T, _R, _H = WeaponKind, WeaponTrait, RangedWeaponRange, RangedWeaponHands
WEAPON_PROFILES: tuple[WeaponProfile, ...] = (
    _melee(_W.UNARMED, None, hands=None, traits=(_T.STAGGER_INSTEAD_OF_DAMAGE, _T.NO_DEFENCE)),
    _melee(_W.KNUCKLEDUSTERS, -1, traits=(_T.CONCEALMENT_STEALTH_PLUS_ONE, _T.NO_DEFENCE)),
    _melee(_W.DAGGER, -1, traits=(_T.CONCEALMENT_STEALTH_PLUS_ONE,)),
    _melee(_W.STAFF, 0, traits=(_T.DIFFICULT_TERRAIN_ATHLETICS_PLUS_ONE,)),
    _melee(_W.FOOT_SPEAR, 0, maximum=_R.SHORT, traits=(_T.CHARGE_DEFENCE_PLUS_ONE, _T.FOOT_SPEAR_TWO_HANDED_DAMAGE_PLUS_ONE)),
    _melee(_W.CAVALRY_SPEAR, 0, maximum=_R.SHORT, traits=(_T.MOUNTED_CHARGE_MELEE_PLUS_ONE,)),
    _melee(_W.AXE, 0, traits=(_T.ARMOURED_TARGET_DAMAGE_PLUS_ONE,)),
    _melee(_W.PICKAXE, 1, hands=_H.TWO_HANDED, traits=(_T.RESOURCE_HARVEST_TOIL_PLUS_ONE,)),
    _melee(_W.SWORD, 0, traits=(_T.READY_DEFENCE_PLUS_ONE_DIE,)),
    _melee(_W.WARHAMMER, 0, traits=(_T.STAGGERED_TARGET_MELEE_PLUS_ONE,)),
    _melee(_W.MORNING_STAR, 1, traits=(_T.STAGGERED_MELEE_MINUS_ONE,)),
    _melee(_W.POLEARM, 0, maximum=_R.SHORT, traits=(_T.POLEARM_TWO_HANDED_DAMAGE_PLUS_TWO,)),
    _melee(_W.FLAIL, 3, hands=_H.TWO_HANDED, traits=(_T.STAGGERED_MELEE_MINUS_TWO,)),
    _melee(_W.BILLHOOK, 2, hands=_H.TWO_HANDED, traits=(_T.MOUNTED_TARGET_MELEE_PLUS_ONE,)),
    _melee(_W.HALBERD, 2, hands=_H.TWO_HANDED, traits=(_T.ARMOURED_TARGET_DAMAGE_PLUS_ONE,)),
    _melee(_W.GLAIVE, 2, hands=_H.TWO_HANDED, traits=(_T.READY_DEFENCE_PLUS_ONE_DIE,)),
    _melee(_W.GREATAXE, 3, hands=_H.TWO_HANDED, traits=(_T.MELEE_MINUS_ONE, _T.ARMOURED_TARGET_DAMAGE_PLUS_ONE)),
    _melee(_W.GREATSWORD, 3, hands=_H.TWO_HANDED, traits=(_T.MELEE_MINUS_ONE, _T.GREATSWORD_PRINTED_READY_DEFENCE_PLUS_ONE)),
    _melee(_W.GREATHAMMER, 3, hands=_H.TWO_HANDED, traits=(_T.MELEE_MINUS_ONE, _T.STAGGERED_TARGET_MELEE_PLUS_ONE)),
    _melee(_W.LANCE, 1, traits=(_T.MOUNTED_CHARGE_MELEE_PLUS_ONE, _T.MOUNTED_CHARGE_DAMAGE_PLUS_ONE)),
    _shooting(_W.SLING),
    _shooting(_W.SHORTBOW, traits=(_T.SHORT_SHOOTING_PLUS_ONE,)),
    _shooting(_W.WARBOW),
    _shooting(_W.LONGBOW),
    _shooting(_W.CROSSBOW, traits=(_T.ARMOURED_TARGET_DAMAGE_PLUS_ONE, _T.RELOAD_TWO_SUCCESSES)),
    _shooting(_W.PISTOL, traits=(_T.IGNORES_ARMOUR, _T.RELOAD_THREE_SUCCESSES, _T.BLACKPOWDER_LORE_REQUIRED)),
    _shooting(_W.HANDGUN, traits=(_T.IGNORES_ARMOUR, _T.RELOAD_THREE_SUCCESSES, _T.BLACKPOWDER_LORE_REQUIRED)),
    _shooting(_W.BLUNDERBUSS, traits=(_T.SHORT_SHOOTING_PLUS_TWO, _T.HIT_NEARBY_STAGGER, _T.RELOAD_THREE_SUCCESSES, _T.BLACKPOWDER_LORE_REQUIRED)),
    _shooting(_W.HOCHLAND_LONG_RIFLE, traits=(_T.AIM_REQUIRED, _T.IGNORES_ARMOUR, _T.WOUNDS_TABLE_PLUS_ONE_DIE, _T.RELOAD_FOUR_SUCCESSES, _T.BLACKPOWDER_LORE_REQUIRED)),
    _shooting(_W.REPEATER_HANDBOW, traits=(_T.OPTIONAL_SHOOTING_PLUS_ONE, _T.RELOAD_THREE_AFTER_BONUS)),
    _shooting(_W.REPEATER_CROSSBOW, traits=(_T.OPTIONAL_SHOOTING_PLUS_ONE, _T.RELOAD_THREE_AFTER_BONUS)),
    _shooting(_W.REPEATER_PISTOL, traits=(_T.IGNORES_ARMOUR, _T.OPTIONAL_SHOOTING_PLUS_TWO, _T.RELOAD_THREE_AFTER_BONUS, _T.BLACKPOWDER_LORE_REQUIRED)),
    _shooting(_W.REPEATER_HANDGUN, traits=(_T.IGNORES_ARMOUR, _T.OPTIONAL_SHOOTING_PLUS_THREE, _T.RELOAD_FIVE_AFTER_BONUS, _T.BLACKPOWDER_LORE_REQUIRED)),
    _throwing(_W.ROCK, None, _R.SHORT, _R.MEDIUM, hands=None, traits=(_T.NO_DIRECT_WOUND,)),
    _throwing(_W.THROWING_SPEAR, 0, _R.CLOSE, _R.MEDIUM),
    _throwing(_W.THROWING_AXE, 1, _R.SHORT, _R.SHORT, traits=(_T.ARMOURED_TARGET_DAMAGE_PLUS_ONE,)),
    _throwing(_W.WEIGHTED_NET, None, _R.CLOSE, _R.SHORT, hands=_H.TWO_HANDED, traits=(_T.BURDENED_INSTEAD_OF_DAMAGE,)),
    _throwing(_W.THROWING_KNIVES, 0, _R.SHORT, _R.SHORT, traits=(_T.KNIVES_FOR_WHOLE_BATTLE,)),
    _throwing(_W.OIL_FLASK, None, _R.SHORT, _R.MEDIUM, traits=(_T.HIT_TARGET_AND_NEARBY_ABLAZE,)),
    _throwing(_W.BLASTING_CHARGE, None, _R.SHORT, _R.MEDIUM, traits=(_T.HAZARD_THREE_IN_TARGET_ZONE_OR_OWN_ON_MISS,)),
    WeaponProfile(_W.DRAGON_BOW, WeaponGroup.SHOOTING, Skill.SHOOTING, _H.TWO_HANDED, True,
        WeaponDamageKind.FIXED, 6, None, _R.MEDIUM, _R.EXTREME, False, True, False,
        (_T.NO_ATTACK_DIE_PENALTIES_OR_GRIM, _T.CANNOT_ATTACK_UNSEEN_TARGET, _T.ONCE_PER_BATTLE_HIT_ABLAZE), WeaponBook.GAMEMASTER_GUIDE, 'VI', 82),
    _melee(_W.DUELLIST_BLADES, 2, hands=_H.TWO_HANDED, magical=True, page=83,
        traits=(_T.READY_DEFENCE_PLUS_TWO_DICE, _T.SECOND_ATTACK_ACTION, _T.OPTIONAL_GRIM_AND_GLORIOUS_PAIR)),
    _melee(_W.GROTARGGS_HAMMER, 3, hands=_H.TWO_HANDED, magical=True, page=83,
        traits=(_T.HIGHER_GROUND_GLORIOUS, _T.HIGHER_GROUND_MISS_STUCK, _T.STUCK_RETRIEVAL_BRAWN_MINUS_TWO)),
    _melee(_W.HEADSMANS_AXE, 3, hands=_H.TWO_HANDED, magical=True, page=83,
        traits=(_T.PRONE_GRIM_WOUND_DECAPITATION,)),
    _melee(_W.MORNING_STAR_OF_FRACASSE, 3, magical=True, page=83,
        traits=(_T.STAGGERED_MELEE_MINUS_ONE, _T.HIT_DISARMS_MAGIC_WEAPON)),
    _melee(_W.SCARAB_KNIFE, 1, magical=True, page=84,
        traits=(_T.HIT_DRAINED, _T.WOUNDS_CHARGE_BLADE, _T.THREE_CHARGES_HEAL_WOUND, _T.CHARGES_EXPIRE_AT_SUNSET)),
    _melee(_W.TRICKSTER_BLADE, 1, magical=True, page=84,
        traits=(_T.READY_DEFENCE_PLUS_ONE_DIE, _T.APPEARANCE_AS_COMMON_TRAPPING)),
    _melee(_W.UNWAVERING_SPEAR, 1, hands=_H.TWO_HANDED, maximum=_R.SHORT, magical=True, page=84,
        traits=(_T.FORBIDS_GIVE_GROUND, _T.GIVEN_GROUND_THIS_ROUND_GLORIOUS, _T.BROKEN_REGROWS_NEXT_DOWNTIME_UNLESS_BURNED)),
    _melee(_W.SWORD_OF_JUSTICE, 1, magical=True, page=84,
        traits=(_T.WOUNDS_TABLE_PLUS_ONE_DIE, _T.CHAMPION_OR_PC_SINGLE_COMBAT_GLORIOUS)),
    _shooting(_W.OGRE_PISTOL, traits=(_T.IGNORES_ARMOUR, _T.RELOAD_THREE_SUCCESSES, _T.BLACKPOWDER_LORE_REQUIRED)),
)
_PROFILE_BY_KIND = MappingProxyType({profile.kind: profile for profile in WEAPON_PROFILES})
if len(_PROFILE_BY_KIND) != len(WEAPON_PROFILES) or set(_PROFILE_BY_KIND) != set(WeaponKind):
    raise RuntimeError('weapon catalogue must contain exactly one row for each WeaponKind')


def weapon_profile(kind: WeaponKind) -> WeaponProfile:
    if type(kind) is not WeaponKind:
        raise TypeError('weapon lookup requires its exact WeaponKind')
    return _PROFILE_BY_KIND[kind]


def weapon_is_physical(kind: WeaponKind) -> bool:
    return weapon_profile(kind).physical


def weapon_is_magical(kind: WeaponKind) -> bool:
    return weapon_profile(kind).magical


def weapon_printed_damage(kind: WeaponKind, *, strength: int | None = None,
        two_handed: bool = False) -> int | None:
    """Read printed base Damage only; no margins, buffs or target effects."""
    profile = weapon_profile(kind)
    if type(two_handed) is not bool:
        raise TypeError('printed damage grip context must be an exact bool')
    if strength is not None and (type(strength) is not int or strength < 1):
        raise ValueError('Strength must be an exact positive integer when supplied')
    if two_handed and profile.hands is not RangedWeaponHands.TWO_HANDED and not profile.variable_grip:
        raise ValueError('this weapon has no printed two-handed grip')
    if profile.damage_kind is WeaponDamageKind.NONE:
        return None
    if profile.damage_kind is WeaponDamageKind.FIXED:
        return profile.damage_value
    if strength is None:
        raise ValueError('Strength-based Damage requires actual Strength')
    bonus = (1 if kind is WeaponKind.FOOT_SPEAR else 2) if two_handed and profile.variable_grip else 0
    return strength + profile.damage_value + bonus
