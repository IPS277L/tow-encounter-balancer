from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from towr.engine.events import BattleEvent


class BattleOutcome(str, Enum):
    PLAYER_VICTORY = "player_victory"
    MONSTER_VICTORY = "monster_victory"
    DRAW = "draw"
    ROUND_LIMIT = "round_limit"


@dataclass(frozen=True, slots=True)
class CombatantResult:
    id: str
    wounds: int
    stagger: int
    survived: bool


@dataclass(frozen=True, slots=True)
class BattleResult:
    outcome: BattleOutcome
    rounds: int
    combatants: tuple[CombatantResult, ...]
    rules_version: str
    events: tuple[BattleEvent, ...] = ()

