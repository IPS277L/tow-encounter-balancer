from __future__ import annotations

from towr.domain.help_models import (
    HELP_BONUS_RULE_ID,
    HelpActionExecutionRequest,
    HelpActionExecutionResult,
    HelpBonusApplicationRequest,
    HelpBonusApplicationResult,
    _expected_help_application,
    _expected_help_execution,
    _validate_help_action,
)
from towr.domain.test_models import TestResult
from towr.rules.dice import RandomSource
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


def execute_help_action(
    request: HelpActionExecutionRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> HelpActionExecutionResult:
    """Resolve one ally's Help Test and create its intended-Test bonus."""
    _validate_help_action(request)
    help_test_result = resolve_test(request.help_test, rng, decisions=decisions)
    return _complete_help_action(request, help_test_result)


def _complete_help_action(
    request: HelpActionExecutionRequest,
    help_test_result: TestResult,
) -> HelpActionExecutionResult:
    """Complete a validated Help action from its actual Test, without RNG."""
    return _expected_help_execution(request, help_test_result)


def apply_help_bonus(
    request: HelpBonusApplicationRequest,
) -> HelpBonusApplicationResult:
    """Apply one Help snapshot to the exact allied Test it names."""
    if request.rule_id != HELP_BONUS_RULE_ID:
        raise ValueError("Help application uses an unknown source rule")
    test, modifier = _expected_help_application(request)
    return HelpBonusApplicationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        test=test,
        modifier=modifier,
        applied_rule_ids=(request.rule_id, request.help.rule_id),
    )
