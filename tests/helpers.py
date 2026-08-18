from __future__ import annotations

from collections.abc import Iterable

from towr.domain.actions import AttackAction, StatRollSource
from towr.domain.combatants import CombatantDefinition, Side
from towr.domain.stats import DicePool, StatBlock


class SequenceRandom:
    def __init__(self, values: Iterable[int]) -> None:
        self._values = iter(values)

    def randint(self, start: int, end: int) -> int:
        value = next(self._values)
        if not start <= value <= end:
            raise AssertionError(f"scripted value {value} is outside {start}..{end}")
        return value


def combatant(
    identifier: str,
    side: Side,
    *,
    ws: DicePool = DicePool(2, 5),
    defense: DicePool = DicePool(2, 5),
    resilience: int = 5,
    wound_limit: int = 5,
    actions: tuple[AttackAction, ...] | None = None,
) -> CombatantDefinition:
    selected_actions = actions
    if selected_actions is None:
        selected_actions = (
            AttackAction(
                id="basic_attack",
                roll_source=StatRollSource("WS"),
                weapon=0,
            ),
        )
    return CombatantDefinition(
        id=identifier,
        side=side,
        stats=StatBlock(
            rolls={"WS": ws, "DEF": defense},
            values={"RES": resilience},
        ),
        wound_limit=wound_limit,
        actions=selected_actions,
    )

