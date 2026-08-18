"""Domain definitions independent from battle execution and adapters."""

from towr.domain.actions import AttackAction, InlineRollSource, StatRollSource
from towr.domain.combatants import CombatantDefinition, CombatantState, Side
from towr.domain.encounters import EncounterDefinition
from towr.domain.results import BattleOutcome, BattleResult
from towr.domain.stats import DicePool, StatBlock

__all__ = [
    "AttackAction",
    "BattleOutcome",
    "BattleResult",
    "CombatantDefinition",
    "CombatantState",
    "DicePool",
    "EncounterDefinition",
    "InlineRollSource",
    "Side",
    "StatBlock",
    "StatRollSource",
]

