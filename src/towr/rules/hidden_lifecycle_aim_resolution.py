from __future__ import annotations

from towr.domain.hidden_lifecycle_aim_models import (
    HiddenLifecycleAimAttackExecutionRequest,
    HiddenLifecycleAimAttackExecutionResult,
    _lifecycle_aim_rule_ids,
    _validate_lifecycle_aim_attack,
)
from towr.domain.hidden_lifecycle_models import HiddenLifecycleApplicationRequest
from towr.rules.dice import RandomSource
from towr.rules.hidden_lifecycle_resolution import apply_hidden_lifecycle_result
from towr.rules.kernel import ResolutionDecisionProvider
from towr.rules.registered_hidden_aim_resolution import execute_registered_hidden_aim_attack


def execute_hidden_lifecycle_aim_attack(
    request: HiddenLifecycleAimAttackExecutionRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> HiddenLifecycleAimAttackExecutionResult:
    """Execute one hidden Aim shot and apply its registered result to lifecycle.

    Input snapshots are immutable; RNG and decision-provider effects are not undone.
    Caller retains the returned lifecycle and Aim histories.
    """
    if not isinstance(request, HiddenLifecycleAimAttackExecutionRequest):
        raise TypeError("request must be a HiddenLifecycleAimAttackExecutionRequest")
    _validate_lifecycle_aim_attack(request.state, request.attack)
    attack = execute_registered_hidden_aim_attack(request.attack, rng, decisions=decisions)
    lifecycle = apply_hidden_lifecycle_result(HiddenLifecycleApplicationRequest(
        f"{request.id}:hidden-lifecycle", request.state, attack.hidden_attack,
    ))
    return HiddenLifecycleAimAttackExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        attack=attack,
        lifecycle=lifecycle,
        applied_rule_ids=_lifecycle_aim_rule_ids(request, attack, lifecycle),
    )
