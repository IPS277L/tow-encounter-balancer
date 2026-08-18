from __future__ import annotations

import unittest

from tests.helpers import combatant
from towr.controllers.focused import FocusMostWounded
from towr.domain.combatants import CombatantState, Side


class TargetingTests(unittest.TestCase):
    def test_selects_most_wounded_and_keeps_roster_order_for_ties(self) -> None:
        actor = CombatantState(combatant("player", Side.PLAYERS))
        first = CombatantState(combatant("first", Side.MONSTERS), wounds=2)
        second = CombatantState(combatant("second", Side.MONSTERS), wounds=2)
        third = CombatantState(combatant("third", Side.MONSTERS), wounds=1)

        selected = FocusMostWounded().select(actor, [first, second, third])

        self.assertIs(selected, first)


if __name__ == "__main__":
    unittest.main()

