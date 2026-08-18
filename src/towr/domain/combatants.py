from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from towr.domain.actions import AttackAction
from towr.domain.stats import StatBlock


class Side(str, Enum):
    PLAYERS = "players"
    MONSTERS = "monsters"


@dataclass(frozen=True, slots=True)
class CombatantDefinition:
    id: str
    side: Side
    stats: StatBlock
    wound_limit: int
    actions: tuple[AttackAction, ...]

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("combatant id must not be empty")
        if self.wound_limit < 1:
            raise ValueError("wound_limit must be positive")
        self.stats.roll("DEF")
        resilience = self.stats.value("RES")
        if resilience < 0:
            raise ValueError("RES must not be negative")


@dataclass(slots=True)
class CombatantState:
    definition: CombatantDefinition
    wounds: int = 0
    stagger: int = 0

    @property
    def is_alive(self) -> bool:
        return self.wounds < self.definition.wound_limit

