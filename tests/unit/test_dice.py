from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.stats import DicePool
from towr.engine.rng import SeededRandom
from towr.rules.dice import roll_pool


class DicePoolTests(unittest.TestCase):
    def test_rejects_dice_outside_one_to_ten(self) -> None:
        with self.assertRaises(ValueError):
            DicePool(0, 5)
        with self.assertRaises(ValueError):
            DicePool(11, 5)

    def test_rejects_threshold_outside_d10(self) -> None:
        with self.assertRaises(ValueError):
            DicePool(2, 0)
        with self.assertRaises(ValueError):
            DicePool(2, 11)

    def test_counts_values_at_or_below_threshold(self) -> None:
        result = roll_pool(DicePool(4, 7), SequenceRandom([1, 7, 8, 10]))
        self.assertEqual(result.values, (1, 7, 8, 10))
        self.assertEqual(result.successes, 2)

    def test_single_die_succeeds_only_on_one(self) -> None:
        failure = roll_pool(DicePool(1, 10), SequenceRandom([2]))
        success = roll_pool(DicePool(1, 2), SequenceRandom([1]))
        self.assertEqual(failure.successes, 0)
        self.assertEqual(success.successes, 1)

    def test_seeded_rng_is_reproducible(self) -> None:
        first = [SeededRandom(123).randint(1, 10) for _ in range(3)]
        rng_a = SeededRandom(456)
        rng_b = SeededRandom(456)
        self.assertEqual(
            [rng_a.randint(1, 10) for _ in range(20)],
            [rng_b.randint(1, 10) for _ in range(20)],
        )
        self.assertEqual(len(first), 3)


if __name__ == "__main__":
    unittest.main()

