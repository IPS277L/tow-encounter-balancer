from __future__ import annotations

from dataclasses import dataclass

from towr.domain.combatants import CombatantDefinition, Side


@dataclass(frozen=True, slots=True)
class EncounterDefinition:
    players: tuple[CombatantDefinition, ...]
    monsters: tuple[CombatantDefinition, ...]

    def __post_init__(self) -> None:
        if not self.players or not self.monsters:
            raise ValueError("an encounter needs at least one combatant on each side")
        if any(combatant.side is not Side.PLAYERS for combatant in self.players):
            raise ValueError("all players must belong to the player side")
        if any(combatant.side is not Side.MONSTERS for combatant in self.monsters):
            raise ValueError("all monsters must belong to the monster side")
        ids = [combatant.id for combatant in (*self.players, *self.monsters)]
        if len(ids) != len(set(ids)):
            raise ValueError("combatant ids must be unique within an encounter")

