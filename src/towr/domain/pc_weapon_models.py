"""Explicit preparation for the admitted Close PC weapons (PG 92–93)."""
from towr.domain.attack_models import DamageModifier, DamageProfile, ResilienceProfile
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.test_models import DiceModifier, Skill


AXE_ARMOUR_RULE_ID = 'RULE-EQUIPMENT-003:axe-armour'
WARHAMMER_STAGGERED_RULE_ID = 'RULE-EQUIPMENT-003:warhammer-staggered-target'
MORNING_STAR_STAGGERED_RULE_ID = 'RULE-EQUIPMENT-003:morning-star-staggered'
FLAIL_STAGGERED_RULE_ID = 'RULE-EQUIPMENT-003:flail-staggered'
GREATAXE_MELEE_RULE_ID = 'RULE-EQUIPMENT-003:greataxe-melee'
GREATHAMMER_MELEE_RULE_ID = 'RULE-EQUIPMENT-003:greathammer-melee'
HALBERD_ARMOUR_RULE_ID = 'RULE-EQUIPMENT-003:halberd-armour'
GREATAXE_ARMOUR_RULE_ID = 'RULE-EQUIPMENT-003:greataxe-armour'
GLAIVE_DEFENCE_RULE_ID = 'RULE-EQUIPMENT-003:glaive-defence'
GREATHAMMER_STAGGERED_RULE_ID = 'RULE-EQUIPMENT-003:greathammer-staggered-target'


def pc_weapon_requires_two_hands(weapon: PcMeleeWeapon) -> bool:
    return weapon in (PcMeleeWeapon.PICKAXE, PcMeleeWeapon.FLAIL, PcMeleeWeapon.BILLHOOK,
        PcMeleeWeapon.HALBERD, PcMeleeWeapon.GLAIVE, PcMeleeWeapon.GREATAXE, PcMeleeWeapon.GREATHAMMER)


def pc_weapon_damage(weapon: PcMeleeWeapon, strength: int) -> DamageProfile:
    if weapon is PcMeleeWeapon.PISTOL:
        from towr.domain.ranged_weapon_profiles import RangedWeaponId,ranged_weapon_combat_profile
        return DamageProfile(ranged_weapon_combat_profile(RangedWeaponId.PISTOL).damage_value)
    if weapon is PcMeleeWeapon.DAGGER:
        offset = -1
    elif weapon in (PcMeleeWeapon.MORNING_STAR, PcMeleeWeapon.PICKAXE):
        offset = 1
    elif weapon in (PcMeleeWeapon.BILLHOOK, PcMeleeWeapon.HALBERD, PcMeleeWeapon.GLAIVE):
        offset = 2
    elif weapon in (PcMeleeWeapon.FLAIL, PcMeleeWeapon.GREATAXE, PcMeleeWeapon.GREATHAMMER):
        offset = 3
    else:
        offset = 0
    return DamageProfile(strength + offset)


def pc_weapon_test_modifiers(weapon: PcMeleeWeapon, skill: Skill,
        conditions: ConditionState) -> tuple[DiceModifier, ...]:
    """Actor traits apply to the actual Test, including an unopposed Help Test."""
    if skill is Skill.MELEE and weapon is PcMeleeWeapon.MORNING_STAR and conditions.has(Condition.STAGGERED):
        return (DiceModifier(MORNING_STAR_STAGGERED_RULE_ID, -1),)
    if skill is Skill.MELEE and weapon is PcMeleeWeapon.FLAIL and conditions.has(Condition.STAGGERED):
        return (DiceModifier(FLAIL_STAGGERED_RULE_ID, -2),)
    if skill is Skill.MELEE and weapon is PcMeleeWeapon.GREATAXE:
        return (DiceModifier(GREATAXE_MELEE_RULE_ID, -1),)
    if skill is Skill.MELEE and weapon is PcMeleeWeapon.GREATHAMMER:
        return (DiceModifier(GREATHAMMER_MELEE_RULE_ID, -1),)
    if skill is Skill.DEFENCE and weapon is PcMeleeWeapon.SWORD and not conditions.has(Condition.STAGGERED):
        return (DiceModifier('RULE-EQUIPMENT-003:sword-defence', 1),)
    if skill is Skill.DEFENCE and weapon is PcMeleeWeapon.GLAIVE and not conditions.has(Condition.STAGGERED):
        return (DiceModifier(GLAIVE_DEFENCE_RULE_ID, 1),)
    return ()


def pc_weapon_attack_modifiers(weapon: PcMeleeWeapon,
        target_conditions: ConditionState) -> tuple[DiceModifier, ...]:
    """This target trait belongs only to Attack; Help has no enemy target."""
    if weapon is PcMeleeWeapon.WARHAMMER and target_conditions.has(Condition.STAGGERED):
        return (DiceModifier(WARHAMMER_STAGGERED_RULE_ID, 1),)
    if weapon is PcMeleeWeapon.GREATHAMMER and target_conditions.has(Condition.STAGGERED):
        return (DiceModifier(GREATHAMMER_STAGGERED_RULE_ID, 1),)
    return ()


def pc_weapon_damage_modifiers(weapon: PcMeleeWeapon,
        target_resilience: ResilienceProfile) -> tuple[DamageModifier, ...]:
    if weapon is PcMeleeWeapon.AXE and target_resilience.is_armoured:
        return (DamageModifier(AXE_ARMOUR_RULE_ID, 1),)
    if weapon is PcMeleeWeapon.HALBERD and target_resilience.is_armoured:
        return (DamageModifier(HALBERD_ARMOUR_RULE_ID, 1),)
    if weapon is PcMeleeWeapon.GREATAXE and target_resilience.is_armoured:
        return (DamageModifier(GREATAXE_ARMOUR_RULE_ID, 1),)
    return ()
