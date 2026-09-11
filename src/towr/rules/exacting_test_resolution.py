from __future__ import annotations

from towr.domain.exacting_test_models import (
    EXACTING_TEST_RULE_ID,
    ExactingOpposedTestContributionRequest,
    ExactingOpposedTestContributionResult,
    ExactingTestContributionRequest,
    ExactingTestContributionResult,
    ExactingTestProgress,
    _expected_contribution,
    _expected_opposed_contribution,
)
from towr.rules.dice import RandomSource
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


def resolve_exacting_test_contribution(
    request: ExactingTestContributionRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> ExactingTestContributionResult:
    """Add one Basic Test's non-negative successes to Exacting progress."""
    if request.rule_id != EXACTING_TEST_RULE_ID:
        raise ValueError("Exacting contribution uses an unknown source rule")
    result = resolve_test(request.test, rng, decisions=decisions)
    contribution = _expected_contribution(request, result)
    progress = ExactingTestProgress(
        id=request.progress.id,
        required_successes=request.progress.required_successes,
        contributions=(*request.progress.contributions, contribution),
        rule_id=request.progress.rule_id,
    )
    return ExactingTestContributionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        test_result=result,
        contribution=contribution,
        previous_progress=request.progress,
        progress=progress,
        applied_rule_ids=tuple(
            dict.fromkeys((request.rule_id, *result.trace.applied_rule_ids))
        ),
    )


def apply_exacting_opposed_test_contribution(
    request: ExactingOpposedTestContributionRequest,
) -> ExactingOpposedTestContributionResult:
    """Add one already-resolved Opposed Test contribution without rolling."""
    if request.rule_id != EXACTING_TEST_RULE_ID:
        raise ValueError("Exacting opposed contribution uses an unknown source rule")
    contribution = _expected_opposed_contribution(request)
    progress = ExactingTestProgress(
        id=request.progress.id,
        required_successes=request.progress.required_successes,
        contributions=(*request.progress.contributions, contribution),
        rule_id=request.progress.rule_id,
    )
    result = request.test_result
    tie_rules = (
        (result.tie_break_rule_id,)
        if result.tie_break_applied and result.tie_break_rule_id is not None
        else ()
    )
    return ExactingOpposedTestContributionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        test_result=result,
        contribution=contribution,
        previous_progress=request.progress,
        progress=progress,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    *result.initiator.trace.applied_rule_ids,
                    *result.opponent.trace.applied_rule_ids,
                    *tie_rules,
                )
            )
        ),
    )
