"""Selected weapon sources prepared for the existing K1 impact families.

This prepares the primary impact and item-sourced on-hit Conditions/Wounds
Table dice. Oil's nearby targets, Blast's whole Zone (also on MISS), finite
stock and later weapon Abilities must be completed by the encounter owner.
No successful primary resolution alone claims those follow-ups are complete.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.attack_models import (
    ConditionImpactSpec, ConditionOnHitSpec, DamageImpactSpec, HazardImpactSpec,
    ImpactSpec, ResilienceProfile,
)
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundDiceModifier
from towr.domain.test_models import Skill
from towr.domain.weapon_catalog import WeaponKind, WeaponTrait, weapon_profile
from towr.domain.weapon_effect_preparation import WeaponDamagePreparation, weapon_damage_preparation
from towr.domain.weapon_use_models import WeaponUse


UNARMED_IMPACT_RULE_ID = 'RULE-EQUIPMENT-003:unarmed-stagger'


def is_unarmed_impact(spec) -> bool:
    return type(spec) is ConditionImpactSpec and spec == ConditionImpactSpec(Condition.STAGGERED,UNARMED_IMPACT_RULE_ID)


ROCK_IMPACT_RULE_ID = 'RULE-EQUIPMENT-005:rock-stagger'
NET_IMPACT_RULE_ID = 'RULE-EQUIPMENT-005:weighted-net-burdened'
OIL_IMPACT_RULE_ID = 'RULE-EQUIPMENT-005:oil-flask-ablaze'
BLAST_IMPACT_RULE_ID = 'RULE-EQUIPMENT-005:blasting-charge-hazard'


def is_stagger_weapon_impact(spec) -> bool:
    return type(spec) is ConditionImpactSpec and spec.condition is Condition.STAGGERED and spec.rule_id in (
        UNARMED_IMPACT_RULE_ID,ROCK_IMPACT_RULE_ID)


def is_oil_impact(spec) -> bool:
    return type(spec) is ConditionImpactSpec and spec == ConditionImpactSpec(Condition.ABLAZE,OIL_IMPACT_RULE_ID)


def is_blast_impact(spec) -> bool:
    return type(spec) is HazardImpactSpec and spec == HazardImpactSpec(3,Skill.ENDURANCE,BLAST_IMPACT_RULE_ID)

SCARAB_DRAINED_RULE_ID = 'RULE-MAGIC-ITEM-003:scarab-hit-drained'
DRAGON_FIRE_RULE_ID = 'RULE-MAGIC-ITEM-003:dragon-fire-arrow'
JUSTICE_WOUND_DICE_RULE_ID = 'RULE-MAGIC-ITEM-003:justice-wounds-table'
HOCHLAND_WOUND_DICE_RULE_ID = 'RULE-EQUIPMENT-004:wounds-table-bonus'


@dataclass(frozen=True, slots=True)
class WeaponHitConditionSource:
    item_id: str
    effect: ConditionOnHitSpec

    def __post_init__(self):
        if type(self.item_id) is not str or not self.item_id.strip():
            raise TypeError('on-hit Condition requires its actual weapon unit ID')
        if type(self.effect) is not ConditionOnHitSpec:
            raise TypeError('on-hit Condition requires its exact typed effect')
        replace(self.effect)


@dataclass(frozen=True, slots=True)
class WeaponWoundDiceSource:
    item_id: str
    modifier: WoundDiceModifier

    def __post_init__(self):
        if type(self.item_id) is not str or not self.item_id.strip():
            raise TypeError('Wounds Table dice require their actual weapon unit ID')
        if type(self.modifier) is not WoundDiceModifier:
            raise TypeError('Wounds Table dice require their exact typed modifier')
        replace(self.modifier)


def _parts(damage, dragon_fire):
    if type(damage) is not WeaponDamagePreparation:
        raise TypeError('weapon impact requires its full typed Damage preparation')
    replace(damage)
    if type(dragon_fire) is not bool:
        raise TypeError('Dragon fire intent requires an exact bool')
    use = damage.use
    if dragon_fire and (use.kind is not WeaponKind.DRAGON_BOW or use.primary.dragon_arrow_used):
        raise ValueError('fire arrow requires this actual Dragon Bow with its activation unused')
    special = {
        WeaponKind.UNARMED: (Condition.STAGGERED, UNARMED_IMPACT_RULE_ID),
        WeaponKind.ROCK: (Condition.STAGGERED, ROCK_IMPACT_RULE_ID),
        WeaponKind.WEIGHTED_NET: (Condition.BURDENED, NET_IMPACT_RULE_ID),
        WeaponKind.OIL_FLASK: (Condition.ABLAZE, OIL_IMPACT_RULE_ID),
    }
    if use.kind in special:
        condition, rule = special[use.kind]
        impact = ConditionImpactSpec(condition, rule)
    elif use.kind is WeaponKind.BLASTING_CHARGE:
        impact = HazardImpactSpec(3, Skill.ENDURANCE, BLAST_IMPACT_RULE_ID)
    else:
        if damage.damage is None:
            raise ValueError('a weapon without Damage requires its explicit special impact owner')
        impact = DamageImpactSpec(damage.damage, damage.target_resilience,
            ignores_armour=damage.ignores_armour, damage_modifiers=damage.modifiers,
            magical_source=damage.magical_source)

    conditions, wounds = [], []
    for item_id in use.item_ids:
        profile = weapon_profile(use.inventory.item(item_id).kind)
        if WeaponTrait.HIT_DRAINED in profile.trait_codes:
            conditions.append(WeaponHitConditionSource(item_id,
                ConditionOnHitSpec(Condition.DRAINED, SCARAB_DRAINED_RULE_ID)))
        if dragon_fire and profile.kind is WeaponKind.DRAGON_BOW:
            conditions.append(WeaponHitConditionSource(item_id,
                ConditionOnHitSpec(Condition.ABLAZE, DRAGON_FIRE_RULE_ID)))
        if WeaponTrait.WOUNDS_TABLE_PLUS_ONE_DIE in profile.trait_codes:
            rule = (JUSTICE_WOUND_DICE_RULE_ID if profile.kind is WeaponKind.SWORD_OF_JUSTICE
                else HOCHLAND_WOUND_DICE_RULE_ID)
            wounds.append(WeaponWoundDiceSource(item_id, WoundDiceModifier(rule, 1)))
    return impact, tuple(conditions), tuple(wounds)


@dataclass(frozen=True, slots=True)
class WeaponImpactPreparation:
    damage: WeaponDamagePreparation
    dragon_fire: bool
    impact_spec: ImpactSpec
    hit_condition_sources: tuple[WeaponHitConditionSource, ...]
    wound_dice_sources: tuple[WeaponWoundDiceSource, ...]

    def __post_init__(self):
        expected = _parts(self.damage, self.dragon_fire)
        if (self.impact_spec, self.hit_condition_sources, self.wound_dice_sources) != expected:
            raise ValueError('weapon impact changed its actual item sources or canonical effects')
        if type(self.impact_spec) is not type(expected[0]):
            raise TypeError('weapon impact must retain its actual impact family')
        replace(self.impact_spec)
        for sources, kind in ((self.hit_condition_sources, WeaponHitConditionSource),
                (self.wound_dice_sources, WeaponWoundDiceSource)):
            if type(sources) is not tuple or any(type(source) is not kind for source in sources):
                raise TypeError('weapon impact requires exact typed source tuples')
            for source in sources:
                replace(source)

    @property
    def secondary_effects(self) -> tuple[ConditionOnHitSpec, ...]:
        # Two Scarab Knives retain two item sources, but do not apply the same
        # non-stacking Condition twice. Wound-derived charges belong elsewhere.
        return tuple(dict.fromkeys(source.effect for source in self.hit_condition_sources))

    @property
    def wound_dice_modifiers(self) -> tuple[WoundDiceModifier, ...]:
        totals = {}
        for source in self.wound_dice_sources:
            modifier = source.modifier
            totals[modifier.rule_id] = totals.get(modifier.rule_id, 0) + modifier.amount
        return tuple(WoundDiceModifier(rule, amount) for rule, amount in totals.items())

    @property
    def forbids_give_ground(self) -> bool:
        return any(WeaponTrait.FORBIDS_GIVE_GROUND in weapon_profile(
            self.damage.use.inventory.item(item_id).kind).trait_codes
            for item_id in self.damage.use.item_ids)

    @property
    def requires_oil_nearby_targets(self) -> bool:
        return self.damage.use.kind is WeaponKind.OIL_FLASK

    @property
    def requires_blast_zone_targets_even_on_miss(self) -> bool:
        return self.damage.use.kind is WeaponKind.BLASTING_CHARGE


def prepare_weapon_impact(use: WeaponUse, strength: int, target_resilience: ResilienceProfile, *,
        actor_mounted: bool = False, charging: bool = False,
        dragon_fire: bool = False) -> WeaponImpactPreparation:
    damage = weapon_damage_preparation(use, strength, target_resilience,
        actor_mounted=actor_mounted, charging=charging)
    impact, conditions, wounds = _parts(damage, dragon_fire)
    return WeaponImpactPreparation(damage, dragon_fire, impact, conditions, wounds)
