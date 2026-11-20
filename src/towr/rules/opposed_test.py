from __future__ import annotations

from towr.domain.test_models import (
    BasicOutcome,
    OpposedOutcome,
    OpposedSide,
    OpposedTestRequest,
    OpposedTestResult,
    TestResult,
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
    return complete_opposed_test(request,initiator,opponent)


def complete_opposed_test(request: OpposedTestRequest, initiator: TestResult,
        opponent: TestResult) -> OpposedTestResult:
    """Complete actual retained Tests without rerolls or invented successes."""
    from dataclasses import replace
    for actual,source in ((initiator,request.initiator),(opponent,request.opponent)):
        if type(actual) is not TestResult or actual.trace.request_id != source.id:
            raise ValueError('opposed completion requires its actual bound Test results')
        if actual.honour_bound is not None:
            replace(actual)
            if actual.honour_bound.activation.source_request.test != source:
                raise ValueError('Unmitigated opposed result replaced its actual prepared Test')
    first, second = initiator.honour_bound,opponent.honour_bound
    if first is not None and second is not None:
        raise ValueError('opposed Unmitigated outcomes require an explicitly resolved GM conflict')
    if first is not None or second is not None:
        winner = OpposedSide.INITIATOR if first is not None else OpposedSide.OPPONENT
        grant = first if first is not None else second
        return OpposedTestResult(request.id,initiator,opponent,_winner_outcome(winner),winner,
            grant.maximum_successes,BasicOutcome.TOTAL_SUCCESS,False,None)
    initiator_successes = initiator.effective_successes
    opponent_successes = opponent.effective_successes

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
