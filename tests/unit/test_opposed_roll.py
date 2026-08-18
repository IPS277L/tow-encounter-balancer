from __future__ import annotations

import unittest

from towr.rules.opposed_roll import OpposedOutcome, resolve_opposed


class OpposedRollTests(unittest.TestCase):
    def test_attacker_wins_with_more_successes(self) -> None:
        self.assertIs(resolve_opposed(3, 2), OpposedOutcome.ATTACKER_WINS)

    def test_nonzero_tie_favors_attacker(self) -> None:
        self.assertIs(resolve_opposed(2, 2), OpposedOutcome.ATTACKER_WINS)

    def test_defender_wins_with_more_successes(self) -> None:
        self.assertIs(resolve_opposed(1, 2), OpposedOutcome.DEFENDER_WINS)

    def test_double_zero_is_special(self) -> None:
        self.assertIs(resolve_opposed(0, 0), OpposedOutcome.DOUBLE_ZERO)


if __name__ == "__main__":
    unittest.main()

