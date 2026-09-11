from __future__ import annotations

import inspect
import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.exacting_test_models import (
    EXACTING_TEST_RULE_ID,
    ExactingOpposedTestContribution,
    ExactingOpposedTestContributionRequest,
    ExactingOpposedTestContributionResult,
    ExactingTestContribution,
    ExactingTestContributionRequest,
    ExactingTestProgress,
)
from towr.domain.test_models import (
    OpposedSide,
    OpposedTestRequest,
    OpposedTestResult,
    TestProfile,
    TestRequest,
    TieBreak,
)
from towr.rules.exacting_test_resolution import (
    apply_exacting_opposed_test_contribution,
    resolve_exacting_test_contribution,
)
from towr.rules.opposed_test import resolve_opposed_test


def opposed_result(
    initiator_values: tuple[int, ...],
    opponent_values: tuple[int, ...],
    *,
    test_id: str = "contest:1",
    tie_winner: OpposedSide = OpposedSide.INITIATOR,
) -> tuple[OpposedTestRequest, OpposedTestResult]:
    request = OpposedTestRequest(
        id=test_id,
        initiator=TestRequest(
            id=f"{test_id}:initiator",
            profile=TestProfile(len(initiator_values), 5),
        ),
        opponent=TestRequest(
            id=f"{test_id}:opponent",
            profile=TestProfile(len(opponent_values), 5),
        ),
        tie_break=TieBreak(
            rule_id=f"RULE-TEST-006:{test_id}:context",
            winner=tie_winner,
        ),
    )
    result = resolve_opposed_test(
        request,
        SequenceRandom([*initiator_values, *opponent_values]),
    )
    return request, result


def contribution_request(
    test: OpposedTestRequest,
    result: OpposedTestResult,
    *,
    progress: ExactingTestProgress | None = None,
    contributor_side: OpposedSide = OpposedSide.INITIATOR,
    request_id: str = "exacting:attempt:1",
    rule_id: str = EXACTING_TEST_RULE_ID,
) -> ExactingOpposedTestContributionRequest:
    return ExactingOpposedTestContributionRequest(
        id=request_id,
        progress=progress or ExactingTestProgress("exacting:task:1", 8),
        contributor_id="hero",
        contributor_side=contributor_side,
        test=test,
        test_result=result,
        rule_id=rule_id,
    )


class K1ExactingOpposedTestResolutionTests(unittest.TestCase):
    def test_winning_side_adds_positive_success_difference(self) -> None:
        test, opposed = opposed_result((1, 2, 3), (1, 10))

        result = apply_exacting_opposed_test_contribution(
            contribution_request(test, opposed)
        )

        self.assertEqual(result.contribution.successes, 2)
        self.assertEqual(result.progress.accumulated_successes, 2)
        self.assertEqual(result.contribution.opposed_test_id, test.id)
        self.assertEqual(
            result.contribution.initiator_test_id,
            test.initiator.id,
        )
        self.assertEqual(
            result.contribution.opponent_test_id,
            test.opponent.id,
        )

    def test_opponent_can_be_the_contributing_side(self) -> None:
        test, opposed = opposed_result((1, 10), (1, 2, 3))

        result = apply_exacting_opposed_test_contribution(
            contribution_request(
                test,
                opposed,
                contributor_side=OpposedSide.OPPONENT,
            )
        )

        self.assertEqual(result.contribution.successes, 2)
        self.assertIs(
            result.contribution.contributor_side,
            OpposedSide.OPPONENT,
        )

    def test_winning_tie_adds_one_and_other_ties_add_zero(self) -> None:
        test, opposed = opposed_result(
            (1, 10),
            (2, 10),
            tie_winner=OpposedSide.INITIATOR,
        )
        winner = apply_exacting_opposed_test_contribution(
            contribution_request(test, opposed)
        )
        loser = apply_exacting_opposed_test_contribution(
            contribution_request(
                test,
                opposed,
                contributor_side=OpposedSide.OPPONENT,
                request_id="exacting:attempt:loser",
            )
        )
        failed_test, both_fail = opposed_result(
            (10,),
            (10,),
            test_id="contest:both-fail",
        )
        failed = apply_exacting_opposed_test_contribution(
            contribution_request(
                failed_test,
                both_fail,
                request_id="exacting:attempt:both-fail",
            )
        )

        self.assertEqual(winner.contribution.successes, 1)
        self.assertEqual(loser.contribution.successes, 0)
        self.assertEqual(failed.contribution.successes, 0)
        self.assertIn(opposed.tie_break_rule_id, winner.applied_rule_ids)

    def test_failure_preserves_existing_progress_and_trace(self) -> None:
        initial = ExactingTestProgress(
            "exacting:task:1",
            8,
            (
                ExactingTestContribution(
                    request_id="exacting:basic:1",
                    test_id="basic:test:1",
                    contributor_id="ally",
                    successes=3,
                ),
            ),
        )
        test, opposed = opposed_result((1, 10), (1, 2, 3))

        result = apply_exacting_opposed_test_contribution(
            contribution_request(test, opposed, progress=initial)
        )

        self.assertEqual(result.contribution.successes, 0)
        self.assertEqual(result.progress.accumulated_successes, 3)
        self.assertEqual(result.progress.contributions[0], initial.contributions[0])
        self.assertEqual(len(result.progress.contributions), 2)

    def test_mixed_contributions_preserve_overshoot_and_completion(self) -> None:
        initial = ExactingTestProgress(
            "exacting:task:1",
            4,
            (
                ExactingTestContribution(
                    request_id="exacting:basic:1",
                    test_id="basic:test:1",
                    contributor_id="ally",
                    successes=2,
                ),
            ),
        )
        test, opposed = opposed_result((1, 2, 3), (10,))

        result = apply_exacting_opposed_test_contribution(
            contribution_request(test, opposed, progress=initial)
        )

        self.assertEqual(result.progress.accumulated_successes, 5)
        self.assertTrue(result.progress.completed)
        self.assertIsInstance(
            result.progress.contributions[-1],
            ExactingOpposedTestContribution,
        )

    def test_basic_contribution_can_follow_an_opposed_contribution(self) -> None:
        test, opposed = opposed_result((1, 10), (10,))
        opposed_contribution = apply_exacting_opposed_test_contribution(
            contribution_request(test, opposed)
        )

        basic = resolve_exacting_test_contribution(
            ExactingTestContributionRequest(
                id="exacting:attempt:basic-after-opposed",
                progress=opposed_contribution.progress,
                contributor_id="ally",
                test=TestRequest(
                    "basic:test:after-opposed",
                    TestProfile(1, 5),
                ),
            ),
            SequenceRandom([1]),
        )

        self.assertEqual(basic.progress.accumulated_successes, 2)
        self.assertIsInstance(
            basic.progress.contributions[0],
            ExactingOpposedTestContribution,
        )
        self.assertIsInstance(
            basic.progress.contributions[1],
            ExactingTestContribution,
        )

    def test_replay_completed_progress_and_overlapping_test_ids_are_rejected(
        self,
    ) -> None:
        test, opposed = opposed_result((1, 2), (10,))
        first = apply_exacting_opposed_test_contribution(
            contribution_request(test, opposed)
        )

        with self.assertRaisesRegex(ValueError, "request was already consumed"):
            contribution_request(test, opposed, progress=first.progress)
        with self.assertRaisesRegex(ValueError, "Test was already consumed"):
            contribution_request(
                test,
                opposed,
                progress=first.progress,
                request_id="exacting:attempt:2",
            )

        completed = replace(first.progress, required_successes=2)
        next_test, next_result = opposed_result(
            (1,),
            (10,),
            test_id="contest:next",
        )
        with self.assertRaisesRegex(ValueError, "completed"):
            contribution_request(
                next_test,
                next_result,
                progress=completed,
                request_id="exacting:attempt:next",
            )

        wrapped = replace(test, id="contest:rewrapped")
        wrapped_result = replace(opposed, request_id=wrapped.id)
        with self.assertRaisesRegex(ValueError, "Test was already consumed"):
            contribution_request(
                wrapped,
                wrapped_result,
                progress=first.progress,
                request_id="exacting:attempt:rewrapped",
            )
        with self.assertRaisesRegex(ValueError, "Test was already consumed"):
            ExactingTestContributionRequest(
                id="exacting:attempt:reused-inner-basic",
                progress=first.progress,
                contributor_id="ally",
                test=TestRequest(test.initiator.id, TestProfile(1, 5)),
            )

    def test_foreign_or_internally_forged_opposed_result_is_rejected(self) -> None:
        test, opposed = opposed_result((1, 2), (10,))
        with self.assertRaisesRegex(ValueError, "belongs elsewhere"):
            contribution_request(
                test,
                replace(opposed, request_id="contest:foreign"),
            )
        with self.assertRaisesRegex(ValueError, "internally inconsistent"):
            contribution_request(
                test,
                replace(opposed, success_margin=9),
            )

    def test_result_is_closed_and_consumer_does_not_roll(self) -> None:
        test, opposed = opposed_result((1, 2), (10,))
        result = apply_exacting_opposed_test_contribution(
            contribution_request(test, opposed)
        )

        self.assertIsInstance(result, ExactingOpposedTestContributionResult)
        self.assertEqual(
            tuple(
                inspect.signature(
                    apply_exacting_opposed_test_contribution
                ).parameters
            ),
            ("request",),
        )
        with self.assertRaisesRegex(ValueError, "is stale"):
            replace(result, contribution=replace(result.contribution, successes=7))
        with self.assertRaisesRegex(ValueError, "unknown source rule"):
            wrong = contribution_request(
                test,
                opposed,
                progress=ExactingTestProgress(
                    "exacting:wrong",
                    8,
                    rule_id="RULE:wrong",
                ),
                rule_id="RULE:wrong",
            )
            apply_exacting_opposed_test_contribution(wrong)


if __name__ == "__main__":
    unittest.main()
