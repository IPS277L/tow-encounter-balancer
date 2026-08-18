from __future__ import annotations

from towr.domain.test_models import (
    BasicOutcome,
    OpposedOutcome,
    OpposedSide,
    OpposedTestRequest,
    OpposedTestResult,
)
from towr.rules.dice import RandomSource
from towr.rules.test_resolution import (
    TestDecisionProvider,
    classify_basic_outcome,
    resolve_test,
)


def resolve_opposed_test(
    request: OpposedTestRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> OpposedTestResult:
    initiator = resolve_test(request.initiator, rng, decisions=decisions)
    opponent = resolve_test(request.opponent, rng, decisions=decisions)
    initiator_successes = initiator.successes
    opponent_successes = opponent.successes

    if initiator_successes == 0 and opponent_successes == 0:
        return OpposedTestResult(
            request_id=request.id,
            initiator=initiator,
            opponent=opponent,
            outcome=OpposedOutcome.BOTH_FAIL,
            winner=None,
            success_margin=0,
            consequence=None,
            tie_break_applied=False,
            tie_break_rule_id=None,
        )

    if initiator_successes == opponent_successes:
        winner = request.tie_break.winner
        return OpposedTestResult(
            request_id=request.id,
            initiator=initiator,
            opponent=opponent,
            outcome=_winner_outcome(winner),
            winner=winner,
            success_margin=0,
            consequence=BasicOutcome.MARGINAL_SUCCESS,
            tie_break_applied=True,
            tie_break_rule_id=request.tie_break.rule_id,
        )

    if initiator_successes > opponent_successes:
        winner = OpposedSide.INITIATOR
    else:
        winner = OpposedSide.OPPONENT
    margin = abs(initiator_successes - opponent_successes)
    return OpposedTestResult(
        request_id=request.id,
        initiator=initiator,
        opponent=opponent,
        outcome=_winner_outcome(winner),
        winner=winner,
        success_margin=margin,
        consequence=classify_basic_outcome(margin),
        tie_break_applied=False,
        tie_break_rule_id=None,
    )


def _winner_outcome(winner: OpposedSide) -> OpposedOutcome:
    if winner is OpposedSide.INITIATOR:
        return OpposedOutcome.INITIATOR_WINS
    return OpposedOutcome.OPPONENT_WINS
