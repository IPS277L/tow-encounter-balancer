from __future__ import annotations

import unittest

from tests.helpers import combatant
from towr.domain.combatants import CombatantState, Side
from towr.rules.damage import DamageOutcome, calculate_damage, resolve_damage
from towr.rules.health import HealthChange, apply_miss_stagger, apply_stagger, apply_wound


class DamageTests(unittest.TestCase):
    def test_damage_is_success_difference_plus_weapon(self) -> None:
        self.assertEqual(calculate_damage(3, 1, 4), 6)

    def test_damage_must_exceed_resilience_to_wound(self) -> None:
        self.assertIs(resolve_damage(6, 5), DamageOutcome.WOUND)
        self.assertIs(resolve_damage(5, 5), DamageOutcome.STAGGER)
        self.assertIs(resolve_damage(4, 5), DamageOutcome.STAGGER)


class HealthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = CombatantState(combatant("player", Side.PLAYERS))

    def test_second_ordinary_stagger_converts_to_wound(self) -> None:
        self.assertIs(apply_stagger(self.state), HealthChange.STAGGER)
        self.assertIs(apply_stagger(self.state), HealthChange.WOUND)
        self.assertEqual(self.state.wounds, 1)
        self.assertEqual(self.state.stagger, 0)

    def test_miss_stagger_does_not_accumulate(self) -> None:
        self.assertIs(apply_miss_stagger(self.state), HealthChange.STAGGER)
        self.assertIs(apply_miss_stagger(self.state), HealthChange.NONE)
        self.assertEqual(self.state.wounds, 0)
        self.assertEqual(self.state.stagger, 1)

    def test_direct_wound_resets_stagger(self) -> None:
        self.state.stagger = 1
        apply_wound(self.state)
        self.assertEqual(self.state.wounds, 1)
        self.assertEqual(self.state.stagger, 0)


if __name__ == "__main__":
    unittest.main()

