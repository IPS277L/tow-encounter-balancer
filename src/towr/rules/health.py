from __future__ import annotations

from enum import Enum

from towr.domain.combatants import CombatantState


class HealthChange(str, Enum):
    NONE = "none"
    STAGGER = "stagger"
    WOUND = "wound"


def apply_wound(target: CombatantState) -> HealthChange:
    target.wounds += 1
    target.stagger = 0
    return HealthChange.WOUND


def apply_stagger(target: CombatantState) -> HealthChange:
    """Apply ordinary accumulating stagger, converting the second point to a wound."""

    if target.stagger == 0:
        target.stagger = 1
        return HealthChange.STAGGER
    return apply_wound(target)


def apply_miss_stagger(attacker: CombatantState) -> HealthChange:
    """A miss can create, but never accumulate, attacker stagger."""

    if attacker.stagger == 0:
        attacker.stagger = 1
        return HealthChange.STAGGER
    return HealthChange.NONE

