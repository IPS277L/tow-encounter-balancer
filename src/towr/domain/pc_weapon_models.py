"""Admitted PC/generated weapon bridge to shared PG/GM item preparation."""
from towr.domain.attack_models import DamageModifier, DamageProfile, ResilienceProfile
from towr.domain.condition_models import ConditionState
from towr.domain.pc_melee_models import PC_RANGED_WEAPONS, PcMeleeWeapon
from towr.domain.test_models import DiceModifier, Skill
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.weapon_catalog import WeaponKind, weapon_profile, weapon_printed_damage


from towr.domain.weapon_effect_preparation import (
    AXE_ARMOUR_RULE_ID, WARHAMMER_STAGGERED_RULE_ID,
    MORNING_STAR_STAGGERED_RULE_ID, FLAIL_STAGGERED_RULE_ID,
    GREATAXE_MELEE_RULE_ID, GREATHAMMER_MELEE_RULE_ID,
    HALBERD_ARMOUR_RULE_ID, GREATAXE_ARMOUR_RULE_ID, GLAIVE_DEFENCE_RULE_ID,
    GREATHAMMER_STAGGERED_RULE_ID, GREATSWORD_MELEE_RULE_ID,
    GREATSWORD_DEFENCE_RULE_ID, FOOT_SPEAR_CHARGE_DEFENCE_RULE_ID,
    BILLHOOK_MOUNTED_RULE_ID, weapon_kind_test_modifiers,
    weapon_kind_target_test_modifiers, weapon_kind_damage_modifiers,
)


def _weapon_kind(weapon: PcMeleeWeapon) -> WeaponKind:
    """Role admission remains explicit while printed facts have one source."""
    if type(weapon) is not PcMeleeWeapon:
        raise TypeError('PC weapon preparation requires its admitted typed weapon')
    return WeaponKind(weapon.value)


def pc_weapon_requires_two_hands(weapon: PcMeleeWeapon) -> bool:
    return weapon_profile(_weapon_kind(weapon)).hands is RangedWeaponHands.TWO_HANDED


def pc_weapon_allows_close_shooting(weapon: PcMeleeWeapon) -> bool:
    """PG94 permission belongs to the optimum range, independently of hands."""
    return (weapon in PC_RANGED_WEAPONS and
        weapon_profile(_weapon_kind(weapon)).optimum_range_min is RangedWeaponRange.CLOSE)


def pc_weapon_supports_variable_grip(weapon: PcMeleeWeapon) -> bool:
    return weapon_profile(_weapon_kind(weapon)).variable_grip


def pc_weapon_damage(weapon: PcMeleeWeapon, strength: int, *, two_handed: bool = False) -> DamageProfile:
    damage = weapon_printed_damage(_weapon_kind(weapon), strength=strength, two_handed=two_handed)
    if damage is None:
        raise ValueError('Weighted Net inflicts Burdened instead of a Damage profile')
    return DamageProfile(damage)


def pc_weapon_test_modifiers(weapon: PcMeleeWeapon, skill: Skill,
        conditions: ConditionState, *, against_charge: bool = False) -> tuple[DiceModifier, ...]:
    """Own Test/Help properties use the same implementation as actual item use."""
    return weapon_kind_test_modifiers(_weapon_kind(weapon), skill, conditions,
        against_charge=against_charge)


def pc_weapon_attack_modifiers(weapon: PcMeleeWeapon,
        target_conditions: ConditionState, *, target_mounted: bool = False) -> tuple[DiceModifier, ...]:
    """Target bonuses require the actual enemy; an unopposed Help has none."""
    return weapon_kind_target_test_modifiers(_weapon_kind(weapon), Skill.MELEE,
        target_conditions, target_mounted=target_mounted)


def pc_weapon_damage_modifiers(weapon: PcMeleeWeapon,
        target_resilience: ResilienceProfile) -> tuple[DamageModifier, ...]:
    return weapon_kind_damage_modifiers(_weapon_kind(weapon), target_resilience)
