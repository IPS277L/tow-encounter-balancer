from __future__ import annotations

from typing import Protocol, Sequence

from towr.domain.combatants import CombatantState


class TargetSelector(Protocol):
    def select(
        self,
        actor: CombatantState,
        candidates: Sequence[CombatantState],
    ) -> CombatantState: ...

