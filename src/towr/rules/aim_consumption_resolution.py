from __future__ import annotations

from towr.domain.aim_consumption_models import (
    RegisteredAimLossAttackExecutionRequest,
    RegisteredAimLossAttackExecutionResult,
    _validate_attack_loss_preflight,
    _registered_loss_rule_ids,
    AimAttackLossConsumptionRequest,
    AimAttackLossConsumptionResult,
    _attack_loss_rule_ids,
    RegisteredPreparedAimRangedAttackExecutionRequest,
    RegisteredPreparedAimRangedAttackExecutionResult,
    _validate_prepared_aim_attack_preflight,
    _registered_prepared_aim_rule_ids,
    RegisteredAimRangedAttackExecutionRequest,
    RegisteredAimRangedAttackExecutionResult,
    AimAttackConsumptionRequest,
    AimAttackConsumptionResult,
    AimLossConsumptionRequest,
    AimLossConsumptionResult,
    _consumed_state,
    _consumption_rule_ids,
    _attack_consumed_state,
    _attack_consumption_rule_ids,
    _validate_aim_attack_preflight,
    _registered_aim_rule_ids,
)
from towr.rules.aim_ranged_weapon_attack_resolution import execute_aim_ranged_weapon_attack
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.dice import RandomSource
from towr.rules.kernel import ResolutionDecisionProvider
from towr.rules.prepared_ranged_weapon_attack_resolution import execute_prepared_ranged_weapon_attack


def execute_registered_prepared_aim_ranged_attack(
    request: RegisteredPreparedAimRangedAttackExecutionRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> RegisteredPreparedAimRangedAttackExecutionResult:
    """Execute one prepared Aim shot and register its sole nested execution.

    Input snapshots are immutable; RNG and decision-provider effects are not undone.
    """
    if not isinstance(request, RegisteredPreparedAimRangedAttackExecutionRequest):
        raise TypeError("request must be a RegisteredPreparedAimRangedAttackExecutionRequest")
    _validate_prepared_aim_attack_preflight(request.state, request.attack)
    execution = execute_prepared_ranged_weapon_attack(request.attack, rng, decisions=decisions)
    registration = register_aim_ranged_attack(AimAttackConsumptionRequest(
        f"{request.id}:registration", request.state, execution.execution,
    ))
    return RegisteredPreparedAimRangedAttackExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        execution=execution,
        registration=registration,
        applied_rule_ids=_registered_prepared_aim_rule_ids(request, execution, registration),
    )


def execute_registered_aim_ranged_attack(
    request: RegisteredAimRangedAttackExecutionRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> RegisteredAimRangedAttackExecutionResult:
    """Check history before one execution and return its registered result.

    Input snapshots are immutable; RNG and decision-provider effects are not undone.
    """
    if not isinstance(request, RegisteredAimRangedAttackExecutionRequest):
        raise TypeError("request must be a RegisteredAimRangedAttackExecutionRequest")
    _validate_aim_attack_preflight(request.state, request.attack)
    execution = execute_aim_ranged_weapon_attack(request.attack, rng, decisions=decisions)
    registration = register_aim_ranged_attack(AimAttackConsumptionRequest(
        f"{request.id}:registration", request.state, execution,
    ))
    return RegisteredAimRangedAttackExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        registration=registration,
        applied_rule_ids=_registered_aim_rule_ids(request, registration),
    )


def register_aim_ranged_attack(request: AimAttackConsumptionRequest) -> AimAttackConsumptionResult:
    """Register one completed Aim-bound shot, preserving its sole execution.

    Caller retains the latest actor history; this consumer does not execute attacks.
    """
    if not isinstance(request, AimAttackConsumptionRequest):
        raise TypeError("request must be an AimAttackConsumptionRequest")
    return AimAttackConsumptionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        previous_state=request.state,
        state=_attack_consumed_state(request),
        applied_rule_ids=_attack_consumption_rule_ids(request),
    )


def execute_registered_aim_loss_attack(
    request: RegisteredAimLossAttackExecutionRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> RegisteredAimLossAttackExecutionResult:
    """Execute one different-target or same-target Melee Attack with LOST Aim.

    Input snapshots are immutable; RNG and decision-provider effects are not undone.
    """
    if not isinstance(request, RegisteredAimLossAttackExecutionRequest):
        raise TypeError("request must be a RegisteredAimLossAttackExecutionRequest")
    _validate_attack_loss_preflight(request.state, request.follow_up, request.attack)
    execution = execute_attack_action(request.attack, rng, decisions=decisions)
    registration = consume_attack_lost_aim(AimAttackLossConsumptionRequest(
        f"{request.id}:registration", request.state, request.follow_up, execution,
    ))
    return RegisteredAimLossAttackExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        registration=registration,
        applied_rule_ids=_registered_loss_rule_ids(request, registration),
    )


def consume_attack_lost_aim(request: AimAttackLossConsumptionRequest) -> AimAttackLossConsumptionResult:
    """Register LOST after a different-target or same-target Melee Attack.

    No Attack, Test or receipt is executed again. Caller retains the latest history
    and identifies the actual next action after Aim.
    """
    if not isinstance(request, AimAttackLossConsumptionRequest):
        raise TypeError("request must be an AimAttackLossConsumptionRequest")
    return AimAttackLossConsumptionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        previous_state=request.state,
        state=_consumed_state(request),
        applied_rule_ids=_attack_loss_rule_ids(request),
    )


def consume_lost_aim(request: AimLossConsumptionRequest) -> AimLossConsumptionResult:
    """Register completed non-Attack Aim loss without re-executing either action.

    Caller selects the next action and retains the latest actor history.
    """
    if not isinstance(request, AimLossConsumptionRequest):
        raise TypeError("request must be an AimLossConsumptionRequest")
    return AimLossConsumptionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        previous_state=request.state,
        state=_consumed_state(request),
        applied_rule_ids=_consumption_rule_ids(request),
    )
