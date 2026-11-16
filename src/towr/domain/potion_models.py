"""Potion inventory facts and immediate, source-preserving Wound healing.

GM1.1 VI89–90 defines the consumables. Recover, hand use, inventory spending
and the encounter's timely-application premise belong to the calling owner.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from towr.domain.condition_models import Condition
from towr.domain.injury_models import CharacterInjuryState, WoundConditionEffect

HEALING_POTION_RULE_ID = 'RULE-MAGIC-ITEM-007:healing-potion'
ENHANCEMENT_POTION_RULE_ID = 'RULE-MAGIC-ITEM-007:enhancement-potion'


class ConsumableKind(str, Enum):
    HEALING = 'healing_potion'
    ENHANCEMENT = 'enhancement_potion'


@dataclass(frozen=True, slots=True)
class ConsumableItem:
    id: str
    kind: ConsumableKind
    quantity: int
    characteristic: str | None

    def __post_init__(self) -> None:
        if type(self.id) is not str or not self.id.strip():
            raise ValueError('inventory item needs a nonempty instance ID')
        if type(self.kind) is not ConsumableKind:
            raise TypeError('consumable kind must be typed')
        if type(self.quantity) is not int or self.quantity < 1:
            raise ValueError('consumable quantity must be a positive integer')
        characteristics = ('weapon_skill', 'ballistic_skill', 'strength', 'toughness',
                           'initiative', 'agility', 'reason', 'fellowship')
        if self.kind is ConsumableKind.ENHANCEMENT:
            if self.characteristic not in characteristics:
                raise ValueError('Enhancement Potion must name its Characteristic')
        elif self.characteristic is not None:
            raise ValueError('Healing Potion cannot carry a Characteristic')


def heal_potion_wound(
    injury: CharacterInjuryState,
    wound_sequence: int,
    other_condition_sources: frozenset[Condition] = frozenset(),
) -> CharacterInjuryState:
    """Heal one resolved, living PC Wound without erasing independent causes.

    Unlike ordinary rest, GM90's timely Healing Potion ends every corresponding
    effect, including permanent injury. It does not resurrect a dead character.
    External conditions must be identified by the encounter owner; other active
    Wound causes are retained directly from the supplied injury state.
    """
    if type(injury) is not CharacterInjuryState:
        raise TypeError('Healing Potion requires a typed character injury state')
    replace(injury)
    if type(wound_sequence) is not int or not 1 <= wound_sequence <= len(injury.wounds):
        raise ValueError('Healing Potion requires an existing positive Wound sequence')
    if (type(other_condition_sources) is not frozenset
            or any(type(condition) is not Condition for condition in other_condition_sources)):
        raise TypeError('external Condition sources must be a frozenset of typed Conditions')
    wound = injury.wounds[wound_sequence - 1]
    replace(wound)
    if injury.dead:
        raise ValueError('Healing Potion cannot resurrect a dead character')
    if wound.healed or not wound.effect_resolved or wound.table_total >= 24:
        raise ValueError('Healing Potion requires an unhealed resolved Wound in rows 1–23')

    removed = tuple(effect for effect in injury.active_wound_effects
                    if effect.wound_sequence == wound_sequence)
    remaining = tuple(effect for effect in injury.active_wound_effects
                      if effect.wound_sequence != wound_sequence)
    retained_conditions = other_condition_sources | frozenset(
        effect.condition for effect in remaining if isinstance(effect, WoundConditionEffect)
    )
    conditions = injury.conditions
    for effect in removed:
        if isinstance(effect, WoundConditionEffect) and effect.condition not in retained_conditions:
            conditions = conditions.without_condition(effect.condition)
    return replace(
        injury,
        wounds=tuple(replace(item, treated=True, healed=True)
                     if item.sequence == wound_sequence else item for item in injury.wounds),
        conditions=conditions,
        active_wound_effects=remaining,
    )
