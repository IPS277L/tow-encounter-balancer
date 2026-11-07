from __future__ import annotations

from towr.domain.reload_models import (
    RELOAD_RULE_ID,
    ReloadActionExecutionRequest,
    ReloadActionExecutionResult,
    _complete_reload_action,
    _exacting_request,
    _validate_reload_action_context,
)
from towr.rules.dice import RandomSource
from towr.rules.exacting_test_resolution import (
    resolve_exacting_test_contribution,
)
from towr.rules.test_resolution import TestDecisionProvider


def execute_reload_action(
    request: ReloadActionExecutionRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> ReloadActionExecutionResult:
    """Spend one action and make one Dexterity Test toward reloading."""
    if request.rule_id != RELOAD_RULE_ID:
        raise ValueError("reload action uses an unknown source rule")
    _validate_reload_action_context(request)
    exacting = resolve_exacting_test_contribution(
        _exacting_request(request),
        rng,
        decisions=decisions,
    )
    return _complete_reload_action(request, exacting)
