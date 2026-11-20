"""Explicit scalar weapon Traits with actual item sources (PG93–96, GM82–84).

These helpers prepare modifiers; they do not execute attacks, spend stock,
apply Conditions or decide range eligibility. The Test owner still applies
Drained, caps and quality rules after combining all sources. Special impacts,
Wounds Table dice, charges and other item Abilities have their own owners.
"""
from __future__ import annotations

from dataclasses import dataclass,field,replace

from towr.domain.attack_models import DamageModifier,DamageProfile,ResilienceProfile
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.test_models import DiceModifier,Skill
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import AcquiredTalent,has_talent
from towr.domain.weapon_catalog import WeaponKind,weapon_printed_damage,weapon_profile,WeaponTrait
from towr.domain.weapon_inventory_models import WeaponGrip
from towr.domain.weapon_use_models import WeaponUse,WeaponProtectionUse


# Existing canonical sources stay identical across the PC/generated bridge.
AXE_ARMOUR_RULE_ID='RULE-EQUIPMENT-003:axe-armour'
WARHAMMER_STAGGERED_RULE_ID='RULE-EQUIPMENT-003:warhammer-staggered-target'
MORNING_STAR_STAGGERED_RULE_ID='RULE-EQUIPMENT-003:morning-star-staggered'
FLAIL_STAGGERED_RULE_ID='RULE-EQUIPMENT-003:flail-staggered'
GREATAXE_MELEE_RULE_ID='RULE-EQUIPMENT-003:greataxe-melee'
GREATHAMMER_MELEE_RULE_ID='RULE-EQUIPMENT-003:greathammer-melee'
HALBERD_ARMOUR_RULE_ID='RULE-EQUIPMENT-003:halberd-armour'
GREATAXE_ARMOUR_RULE_ID='RULE-EQUIPMENT-003:greataxe-armour'
GLAIVE_DEFENCE_RULE_ID='RULE-EQUIPMENT-003:glaive-defence'
GREATHAMMER_STAGGERED_RULE_ID='RULE-EQUIPMENT-003:greathammer-staggered-target'
GREATSWORD_MELEE_RULE_ID='RULE-EQUIPMENT-003:greatsword-melee'
GREATSWORD_DEFENCE_RULE_ID='RULE-EQUIPMENT-003:greatsword-defence'
FOOT_SPEAR_CHARGE_DEFENCE_RULE_ID='RULE-EQUIPMENT-003:foot-spear-charge-defence'
BILLHOOK_MOUNTED_RULE_ID='RULE-EQUIPMENT-003:billhook-mounted-target'
SWORD_DEFENCE_RULE_ID='RULE-EQUIPMENT-003:sword-defence'
SHORT_RANGE_SHOOTING_BONUS_RULE_ID='RULE-EQUIPMENT-004:short-range-shooting-bonus'
ARMOURED_TARGET_DAMAGE_BONUS_RULE_ID='RULE-EQUIPMENT-004:armoured-target-damage-bonus'

DAGGER_CONCEALMENT_RULE_ID='RULE-EQUIPMENT-003:dagger-concealment'
KNUCKLEDUSTERS_CONCEALMENT_RULE_ID='RULE-EQUIPMENT-003:knuckledusters-concealment'
STAFF_TERRAIN_RULE_ID='RULE-EQUIPMENT-003:staff-difficult-terrain'
PICKAXE_HARVEST_RULE_ID='RULE-EQUIPMENT-003:pickaxe-harvesting'
CAVALRY_SPEAR_CHARGE_RULE_ID='RULE-EQUIPMENT-003:cavalry-spear-mounted-charge'
LANCE_CHARGE_RULE_ID='RULE-EQUIPMENT-003:lance-mounted-charge'
LANCE_DAMAGE_RULE_ID='RULE-EQUIPMENT-003:lance-mounted-charge-damage'
THROWING_AXE_ARMOUR_RULE_ID='RULE-EQUIPMENT-005:throwing-axe-armour'
FRACASSE_STAGGERED_RULE_ID='RULE-MAGIC-ITEM-003:fracasse-staggered'
DUELLIST_DEFENCE_RULE_ID='RULE-MAGIC-ITEM-003:duellist-defence'
TRICKSTER_DEFENCE_RULE_ID='RULE-MAGIC-ITEM-003:trickster-defence'


def _boolean(value,label):
    if type(value) is not bool:
        raise TypeError(label+' requires an exact bool')


def _conditions(value,label):
    if type(value) is not ConditionState:
        raise TypeError(label+' requires its exact ConditionState')
    replace(value)


def _skill(value):
    if type(value) is not Skill:
        raise TypeError('weapon Test requires its exact actual Skill')


def _identifier(value):
    if type(value) is not str or not value.strip():
        raise TypeError('weapon contribution requires its exact nonempty item ID')


def weapon_kind_target_test_modifiers(kind:WeaponKind,skill:Skill,
        target_conditions:ConditionState|None=None,*,target_mounted:bool=False)->tuple[DiceModifier,...]:
    """Target-only Attack bonuses; no target means none, including on Help."""
    weapon_profile(kind);_skill(skill);_boolean(target_mounted,'actual mounted target')
    if target_conditions is not None:
        _conditions(target_conditions,'actual target Conditions')
    if target_conditions is None or skill is not Skill.MELEE:
        return ()
    if kind is WeaponKind.BILLHOOK and target_mounted:
        return (DiceModifier(BILLHOOK_MOUNTED_RULE_ID,1),)
    if kind is WeaponKind.WARHAMMER and target_conditions.has(Condition.STAGGERED):
        return (DiceModifier(WARHAMMER_STAGGERED_RULE_ID,1),)
    if kind is WeaponKind.GREATHAMMER and target_conditions.has(Condition.STAGGERED):
        return (DiceModifier(GREATHAMMER_STAGGERED_RULE_ID,1),)
    return ()


def weapon_kind_test_modifiers(kind:WeaponKind,skill:Skill,conditions:ConditionState,*,
        target_conditions:ConditionState|None=None,against_charge:bool=False,
        actor_mounted:bool=False,charging:bool=False,target_mounted:bool=False,
        target_range:RangedWeaponRange|None=None,concealing_weapon:bool=False,
        crossing_difficult_terrain:bool=False,harvesting_resources:bool=False)->tuple[DiceModifier,...]:
    """Raw item dice, independent of actor role and without changing a Test.

    Omitting target context retains the old own-Test/Help boundary. A caller
    can instead add weapon_kind_target_test_modifiers at its actual Attack.
    """
    weapon_profile(kind);_skill(skill);_conditions(conditions,'actor Conditions')
    for label,value in (('opposed Charge',against_charge),('actual mounted actor',actor_mounted),
            ('actual Charge',charging),('actual mounted target',target_mounted),
            ('concealing this weapon',concealing_weapon),('crossing Difficult Terrain',crossing_difficult_terrain),
            ('harvesting resources',harvesting_resources)):
        _boolean(value,label)
    if target_range is not None and type(target_range) is not RangedWeaponRange:
        raise TypeError('actual target Range requires its exact typed band or None')
    modifiers=[]
    staggered=conditions.has(Condition.STAGGERED)
    if skill is Skill.MELEE:
        if kind is WeaponKind.MORNING_STAR and staggered:
            modifiers.append(DiceModifier(MORNING_STAR_STAGGERED_RULE_ID,-1))
        elif kind is WeaponKind.MORNING_STAR_OF_FRACASSE and staggered:
            modifiers.append(DiceModifier(FRACASSE_STAGGERED_RULE_ID,-1))
        elif kind is WeaponKind.FLAIL and staggered:
            modifiers.append(DiceModifier(FLAIL_STAGGERED_RULE_ID,-2))
        elif kind is WeaponKind.GREATAXE:
            modifiers.append(DiceModifier(GREATAXE_MELEE_RULE_ID,-1))
        elif kind is WeaponKind.GREATSWORD:
            modifiers.append(DiceModifier(GREATSWORD_MELEE_RULE_ID,-1))
        elif kind is WeaponKind.GREATHAMMER:
            modifiers.append(DiceModifier(GREATHAMMER_MELEE_RULE_ID,-1))
        if actor_mounted and charging:
            if kind is WeaponKind.CAVALRY_SPEAR:
                modifiers.append(DiceModifier(CAVALRY_SPEAR_CHARGE_RULE_ID,1))
            elif kind is WeaponKind.LANCE:
                modifiers.append(DiceModifier(LANCE_CHARGE_RULE_ID,1))
    elif skill is Skill.DEFENCE:
        if kind is WeaponKind.FOOT_SPEAR and against_charge:
            modifiers.append(DiceModifier(FOOT_SPEAR_CHARGE_DEFENCE_RULE_ID,1))
        if not staggered:
            if kind is WeaponKind.SWORD:
                modifiers.append(DiceModifier(SWORD_DEFENCE_RULE_ID,1))
            elif kind is WeaponKind.GLAIVE:
                modifiers.append(DiceModifier(GLAIVE_DEFENCE_RULE_ID,1))
            elif kind is WeaponKind.GREATSWORD:
                modifiers.append(DiceModifier(GREATSWORD_DEFENCE_RULE_ID,1))
            elif kind is WeaponKind.DUELLIST_BLADES:
                modifiers.append(DiceModifier(DUELLIST_DEFENCE_RULE_ID,2))
            elif kind is WeaponKind.TRICKSTER_BLADE:
                modifiers.append(DiceModifier(TRICKSTER_DEFENCE_RULE_ID,1))
    elif skill is Skill.SHOOTING and target_range is RangedWeaponRange.SHORT:
        if kind is WeaponKind.SHORTBOW:
            modifiers.append(DiceModifier(SHORT_RANGE_SHOOTING_BONUS_RULE_ID,1))
        elif kind is WeaponKind.BLUNDERBUSS:
            modifiers.append(DiceModifier(SHORT_RANGE_SHOOTING_BONUS_RULE_ID,2))
    elif skill is Skill.STEALTH and concealing_weapon:
        if kind is WeaponKind.DAGGER:
            modifiers.append(DiceModifier(DAGGER_CONCEALMENT_RULE_ID,1))
        elif kind is WeaponKind.KNUCKLEDUSTERS:
            modifiers.append(DiceModifier(KNUCKLEDUSTERS_CONCEALMENT_RULE_ID,1))
    elif skill is Skill.ATHLETICS and kind is WeaponKind.STAFF and crossing_difficult_terrain:
        modifiers.append(DiceModifier(STAFF_TERRAIN_RULE_ID,1))
    elif skill is Skill.TOIL and kind is WeaponKind.PICKAXE and harvesting_resources:
        modifiers.append(DiceModifier(PICKAXE_HARVEST_RULE_ID,1))
    return (*modifiers,*weapon_kind_target_test_modifiers(kind,skill,target_conditions,
        target_mounted=target_mounted))


def weapon_kind_damage_modifiers(kind:WeaponKind,target_resilience:ResilienceProfile,*,
        actor_mounted:bool=False,charging:bool=False)->tuple[DamageModifier,...]:
    """Printed extra Damage only; Meteoric protection is a later projection."""
    profile=weapon_profile(kind)
    if type(target_resilience) is not ResilienceProfile:
        raise TypeError('weapon Damage requires the actual target ResilienceProfile')
    replace(target_resilience)
    _boolean(actor_mounted,'actual mounted actor');_boolean(charging,'actual Charge')
    modifiers=[]
    if target_resilience.is_armoured:
        rule={WeaponKind.AXE:AXE_ARMOUR_RULE_ID,WeaponKind.THROWING_AXE:THROWING_AXE_ARMOUR_RULE_ID,
            WeaponKind.HALBERD:HALBERD_ARMOUR_RULE_ID,WeaponKind.GREATAXE:GREATAXE_ARMOUR_RULE_ID,
            WeaponKind.CROSSBOW:ARMOURED_TARGET_DAMAGE_BONUS_RULE_ID}.get(kind)
        if rule is not None:
            modifiers.append(DamageModifier(rule,1,armour_specific=True,magical_source=profile.magical))
    if kind is WeaponKind.LANCE and actor_mounted and charging:
        modifiers.append(DamageModifier(LANCE_DAMAGE_RULE_ID,1,magical_source=profile.magical))
    return tuple(modifiers)


@dataclass(frozen=True,slots=True)
class WeaponDiceContribution:
    item_id:str
    modifier:DiceModifier

    def __post_init__(self):
        _identifier(self.item_id)
        if type(self.modifier) is not DiceModifier:
            raise TypeError('weapon dice contribution requires its exact DiceModifier')
        replace(self.modifier)


@dataclass(frozen=True,slots=True)
class WeaponDamageContribution:
    item_id:str
    modifier:DamageModifier

    def __post_init__(self):
        _identifier(self.item_id)
        if type(self.modifier) is not DamageModifier:
            raise TypeError('weapon Damage contribution requires its exact DamageModifier')
        replace(self.modifier)


def _aggregate_dice(contributions):
    totals={}
    for contribution in contributions:
        modifier=contribution.modifier
        key=(modifier.rule_id,modifier.bypasses_pool_cap)
        totals[key]=totals.get(key,0)+modifier.amount
    return tuple(DiceModifier(rule,amount,bypass) for (rule,bypass),amount in totals.items() if amount)


def _aggregate_damage(contributions):
    totals={}
    for contribution in contributions:
        modifier=contribution.modifier
        key=(modifier.rule_id,modifier.armour_specific,modifier.magical_source)
        totals[key]=totals.get(key,0)+modifier.amount
    return tuple(DamageModifier(rule,amount,armour_specific=armour,magical_source=magical)
        for (rule,armour,magical),amount in totals.items() if amount)


def _use(use,*,damage=False):
    if type(use) not in ((WeaponUse,) if damage else (WeaponUse,WeaponProtectionUse)):
        raise TypeError('weapon preparation requires its exact committed use')
    replace(use)


def _test_items(use):
    return (() if use.primary is None else (use.primary,*use.contributors)) if type(use) is WeaponUse else use.implements


def _test_contributions(use,conditions,skill,*,talents=(),**context):
    mighty_blow=has_talent(talents,TalentId.MIGHTY_BLOW)
    own_context=dict(context)
    target_conditions=own_context.pop('target_conditions',None)
    contributions=[]
    for item in _test_items(use):
        # Keep the item's own penalties separate from actual target Traits.
        # The Talent does not cancel unrelated negative target/actor sources.
        own=weapon_kind_test_modifiers(item.kind,skill,conditions,**own_context)
        if mighty_blow and skill is Skill.MELEE and item.grip is WeaponGrip.BOTH:
            own=tuple(modifier for modifier in own if modifier.amount>0)
        target=weapon_kind_target_test_modifiers(item.kind,skill,target_conditions,
            target_mounted=context.get('target_mounted',False))
        contributions.extend(WeaponDiceContribution(item.id,modifier) for modifier in (*own,*target))
    return tuple(contributions)


@dataclass(frozen=True,slots=True)
class WeaponTestPreparation:
    use:WeaponUse|WeaponProtectionUse
    conditions:ConditionState
    skill:Skill
    contributions:tuple[WeaponDiceContribution,...]
    target_conditions:ConditionState|None=field(default=None,kw_only=True)
    against_charge:bool=field(default=False,kw_only=True)
    actor_mounted:bool=field(default=False,kw_only=True)
    charging:bool=field(default=False,kw_only=True)
    target_mounted:bool=field(default=False,kw_only=True)
    target_range:RangedWeaponRange|None=field(default=None,kw_only=True)
    concealing_weapon:bool=field(default=False,kw_only=True)
    crossing_difficult_terrain:bool=field(default=False,kw_only=True)
    harvesting_resources:bool=field(default=False,kw_only=True)
    talents:tuple[AcquiredTalent,...]=field(default=(),kw_only=True)

    def __post_init__(self):
        _use(self.use);_skill(self.skill);_conditions(self.conditions,'actor Conditions')
        if self.skill is not self.use.skill:
            raise ValueError('a prepared Test must retain its actual WeaponUse/WeaponProtectionUse Skill')
        if type(self.contributions) is not tuple or any(type(item) is not WeaponDiceContribution for item in self.contributions):
            raise TypeError('weapon dice sources require an exact contribution tuple')
        for item in self.contributions:
            replace(item)
        # Also validate contexts for Unarmed/Shield-only, which have no items.
        weapon_kind_test_modifiers(WeaponKind.UNARMED,self.skill,self.conditions,**self.context)
        if self.contributions!=_test_contributions(self.use,self.conditions,self.skill,
                talents=self.talents,**self.context):
            raise ValueError('weapon dice contributions differ from their actual selected items and Test')

    @property
    def context(self):
        return {name:getattr(self,name) for name in ('target_conditions','against_charge','actor_mounted',
            'charging','target_mounted','target_range','concealing_weapon','crossing_difficult_terrain','harvesting_resources')}

    @property
    def modifiers(self)->tuple[DiceModifier,...]:
        return _aggregate_dice(self.contributions)


def weapon_test_modifiers(use:WeaponUse|WeaponProtectionUse,conditions:ConditionState,*,
        skill:Skill|None=None,target_conditions:ConditionState|None=None,against_charge:bool=False,
        actor_mounted:bool=False,charging:bool=False,target_mounted:bool=False,
        target_range:RangedWeaponRange|None=None,concealing_weapon:bool=False,
        crossing_difficult_terrain:bool=False,harvesting_resources:bool=False,
        talents:tuple[AcquiredTalent,...]=())->WeaponTestPreparation:
    """Prepare an actual Attack/Protection Skill, without utility stacking.

    Utility Tests use the low-level kind helper for their explicitly selected
    item; an Attack's two contributors do not silently contribute to them.
    """
    _use(use)
    actual=use.skill if skill is None else skill
    context=dict(target_conditions=target_conditions,against_charge=against_charge,actor_mounted=actor_mounted,
        charging=charging,target_mounted=target_mounted,target_range=target_range,concealing_weapon=concealing_weapon,
        crossing_difficult_terrain=crossing_difficult_terrain,harvesting_resources=harvesting_resources)
    return WeaponTestPreparation(use,conditions,actual,
        _test_contributions(use,conditions,actual,talents=talents,**context),talents=talents,**context)


def _damage_contributions(use,target_resilience,*,actor_mounted,charging):
    return tuple(WeaponDamageContribution(item.id,modifier) for item in _test_items(use)
        for modifier in weapon_kind_damage_modifiers(item.kind,target_resilience,
            actor_mounted=actor_mounted,charging=charging))


@dataclass(frozen=True,slots=True)
class WeaponDamagePreparation:
    use:WeaponUse
    strength:int
    target_resilience:ResilienceProfile
    contributions:tuple[WeaponDamageContribution,...]
    actor_mounted:bool=field(default=False,kw_only=True)
    charging:bool=field(default=False,kw_only=True)

    def __post_init__(self):
        _use(self.use,damage=True)
        if type(self.strength) is not int:
            raise TypeError('weapon Damage requires exact actual Strength')
        if self.strength<1:
            raise ValueError('weapon Damage requires positive actual Strength')
        # Validate even no-Damage/Unarmed contexts without manufacturing an item.
        weapon_kind_damage_modifiers(self.use.kind,self.target_resilience,
            actor_mounted=self.actor_mounted,charging=self.charging)
        weapon_printed_damage(self.use.kind,strength=self.strength,
            two_handed=self.use.primary_grip is WeaponGrip.BOTH)
        if type(self.contributions) is not tuple or any(type(item) is not WeaponDamageContribution for item in self.contributions):
            raise TypeError('weapon Damage sources require an exact contribution tuple')
        for item in self.contributions:
            replace(item)
        if self.contributions!=_damage_contributions(self.use,self.target_resilience,
                actor_mounted=self.actor_mounted,charging=self.charging):
            raise ValueError('weapon Damage contributions differ from their actual selected item sources')

    @property
    def damage(self)->DamageProfile|None:
        amount=weapon_printed_damage(self.use.kind,strength=self.strength,
            two_handed=self.use.primary_grip is WeaponGrip.BOTH)
        return None if amount is None else DamageProfile(amount)

    @property
    def modifiers(self)->tuple[DamageModifier,...]:
        return _aggregate_damage(self.contributions)

    @property
    def magical_source(self)->bool:
        return self.use.primary_profile.magical

    @property
    def ignores_armour(self)->bool:
        return WeaponTrait.IGNORES_ARMOUR in self.use.primary_profile.trait_codes


def weapon_damage_preparation(use:WeaponUse,strength:int,target_resilience:ResilienceProfile,*,
        actor_mounted:bool=False,charging:bool=False)->WeaponDamagePreparation:
    """One primary base plus independently sourced contributor Damage Traits."""
    _use(use,damage=True)
    return WeaponDamagePreparation(use,strength,target_resilience,
        _damage_contributions(use,target_resilience,actor_mounted=actor_mounted,charging=charging),
        actor_mounted=actor_mounted,charging=charging)
