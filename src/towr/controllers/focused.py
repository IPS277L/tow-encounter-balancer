from __future__ import annotations

from typing import Sequence

from towr.domain.combatants import CombatantState


class FocusMostWounded:
    """Choose most wounds; preserve roster order for ties."""

    def select(
        self,
        actor: CombatantState,
        candidates: Sequence[CombatantState],
    ) -> CombatantState:
        del actor
        living = [candidate for candidate in candidates if candidate.is_alive]
        if not living:
            raise ValueError("cannot select a target from an empty living roster")
        return max(living, key=lambda candidate: candidate.wounds)

