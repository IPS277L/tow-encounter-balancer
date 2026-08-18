from __future__ import annotations

from enum import Enum


class DamageOutcome(str, Enum):
    WOUND = "wound"
    STAGGER = "stagger"


def calculate_damage(
    attacker_successes: int,
    defender_successes: int,
    weapon: int,
) -> int:
    if attacker_successes < defender_successes:
        raise ValueError("damage is only calculated for a successful attack")
    if weapon < 0:
        raise ValueError("weapon must not be negative")
    return attacker_successes - defender_successes + weapon


def resolve_damage(damage: int, resilience: int) -> DamageOutcome:
    if damage < 0 or resilience < 0:
        raise ValueError("damage and resilience must not be negative")
    return DamageOutcome.WOUND if damage > resilience else DamageOutcome.STAGGER

