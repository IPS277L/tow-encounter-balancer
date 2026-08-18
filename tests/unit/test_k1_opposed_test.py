from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.test_models import (
    BasicOutcome,
    OpposedOutcome,
    OpposedSide,
    OpposedTestRequest,
    TestProfile,
    TestRequest,
    TieBreak,
)
from towr.rules.opposed_test import resolve_opposed_test


def opposed_request(*, tie_winner: OpposedSide = OpposedSide.INITIATOR) -> OpposedTestRequest:
    return OpposedTestRequest(
        id="contest",
        initiator=TestRequest(id="initiator", profile=TestProfile(2, 5)),
        opponent=TestRequest(id="opponent", profile=TestProfile(2, 5)),
        tie_break=TieBreak("RULE-TEST-006:context", tie_winner),
    )


class K1OpposedTestTests(unittest.TestCase):
    def test_side_with_more_successes_wins(self) -> None:
        result = resolve_opposed_test(
            opposed_request(),
            SequenceRandom([1, 2, 1, 10]),
        )

        self.assertIs(result.outcome, OpposedOutcome.INITIATOR_WINS)
        self.assertIs(result.winner, OpposedSide.INITIATOR)
        self.assertEqual(result.success_margin, 1)
        self.assertIs(result.consequence, BasicOutcome.MARGINAL_SUCCESS)
        self.assertFalse(result.tie_break_applied)

    def test_opponent_can_win_by_success_margin(self) -> None:
        result = resolve_opposed_test(
            opposed_request(),
            SequenceRandom([1, 10, 1, 2]),
        )

        self.assertIs(result.outcome, OpposedOutcome.OPPONENT_WINS)
        self.assertEqual(result.success_margin, 1)

    def test_nonzero_tie_uses_explicit_contextual_tie_break(self) -> None:
        result = resolve_opposed_test(
            opposed_request(tie_winner=OpposedSide.OPPONENT),
            SequenceRandom([1, 10, 2, 10]),
        )

        self.assertIs(result.outcome, OpposedOutcome.OPPONENT_WINS)
        self.assertIs(result.winner, OpposedSide.OPPONENT)
        self.assertTrue(result.tie_break_applied)
        self.assertEqual(result.tie_break_rule_id, "RULE-TEST-006:context")
        self.assertIs(result.consequence, BasicOutcome.MARGINAL_SUCCESS)

    def test_double_zero_means_both_fail_and_does_not_apply_tie_break(self) -> None:
        result = resolve_opposed_test(
            opposed_request(),
            SequenceRandom([10, 10, 10, 10]),
        )

        self.assertIs(result.outcome, OpposedOutcome.BOTH_FAIL)
        self.assertIsNone(result.winner)
        self.assertIsNone(result.consequence)
        self.assertFalse(result.tie_break_applied)
        self.assertIsNone(result.tie_break_rule_id)

    def test_margin_of_three_is_total_success_for_optional_consequences(self) -> None:
        request = OpposedTestRequest(
            id="wide-margin",
            initiator=TestRequest(id="initiator", profile=TestProfile(3, 5)),
            opponent=TestRequest(id="opponent", profile=TestProfile(1, 5)),
            tie_break=TieBreak("RULE-TEST-006:initiator", OpposedSide.INITIATOR),
        )

        result = resolve_opposed_test(
            request,
            SequenceRandom([1, 2, 3, 10]),
        )

        self.assertEqual(result.success_margin, 3)
        self.assertIs(result.consequence, BasicOutcome.TOTAL_SUCCESS)


if __name__ == "__main__":
    unittest.main()
