from __future__ import annotations

from towr.domain.aim_consumption_models import (
    RegisteredAimLossPreparedAttackExecutionRequest,
    RegisteredAimLossPreparedAttackExecutionResult,
    _validate_prepared_attack_loss_preflight,
    AimPreparedAttackLossConsumptionRequest,
    AimPreparedAttackLossConsumptionResult,
    RegisteredAimLossRangedAttackExecutionRequest,
    RegisteredAimLossRangedAttackExecutionResult,
    _validate_ranged_attack_loss_preflight,
    RegisteredAimLossLongChargeExecutionRequest,
    RegisteredAimLossLongChargeExecutionResult,
    _validate_long_charge_loss_preflight,
    RegisteredAimLossDifficultTerrainChargeExecutionRequest,
    RegisteredAimLossDifficultTerrainChargeExecutionResult,
    _validate_terrain_charge_loss_preflight,
    AimDifficultTerrainChargeLossConsumptionRequest,
    AimDifficultTerrainChargeLossConsumptionResult,
    AimLongChargeLossConsumptionRequest,
    AimLongChargeLossConsumptionResult,
    RegisteredAimLossChargeExecutionRequest,
    RegisteredAimLossChargeExecutionResult,
    _validate_charge_loss_preflight,
    AimChargeLossConsumptionRequest,
    AimChargeLossConsumptionResult,
    RegisteredAimLossAttackExecutionRequest,
    RegisteredAimLossAttackExecutionResult,
    _validate_attack_loss_preflight,
    _registered_loss_rule_ids,
    AimRangedAttackLossConsumptionRequest,
    AimRangedAttackLossConsumptionResult,
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
from towr.rules.charge_action_execution import execute_charge_action, execute_long_charge_action
from towr.domain.charge_models import DifficultTerrainChargeActionExecutionRequest
from towr.rules.charge_action_execution import execute_difficult_terrain_charge_action, _validate_difficult_terrain_charge_action
from towr.rules.difficult_terrain_resolution import resolve_difficult_terrain_traversal
from towr.rules.ranged_weapon_attack_resolution import execute_ranged_weapon_attack
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
    """Execute one different-target or same-target Melee/Brawn Attack with LOST Aim.

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


def execute_registered_aim_loss_long_charge(
    request: RegisteredAimLossLongChargeExecutionRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> RegisteredAimLossLongChargeExecutionResult:
    """Check Aim history before one Long Charge and register its sole completed result.

    Input snapshots are immutable; external RNG and decision effects are not undone.
    """
    if not isinstance(request, RegisteredAimLossLongChargeExecutionRequest):
        raise TypeError("request must be a RegisteredAimLossLongChargeExecutionRequest")
    _validate_long_charge_loss_preflight(request.state, request.follow_up, request.charge)
    execution = execute_long_charge_action(request.charge, rng, decisions=decisions)
    registration = consume_long_charge_lost_aim(AimLongChargeLossConsumptionRequest(
        f"{request.id}:registration", request.state, request.follow_up, execution,
    ))
    return RegisteredAimLossLongChargeExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        registration=registration,
        applied_rule_ids=_registered_loss_rule_ids(request, registration),
    )


def execute_registered_aim_loss_charge(
    request: RegisteredAimLossChargeExecutionRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> RegisteredAimLossChargeExecutionResult:
    """Check Aim history before one Charge and register its sole completed result.

    Input snapshots are immutable; external RNG and decision effects are not undone.
    """
    if not isinstance(request, RegisteredAimLossChargeExecutionRequest):
        raise TypeError("request must be a RegisteredAimLossChargeExecutionRequest")
    _validate_charge_loss_preflight(request.state, request.follow_up, request.charge)
    execution = execute_charge_action(request.charge, rng, decisions=decisions)
    registration = consume_charge_lost_aim(AimChargeLossConsumptionRequest(
        f"{request.id}:registration", request.state, request.follow_up, execution,
    ))
    return RegisteredAimLossChargeExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        registration=registration,
        applied_rule_ids=_registered_loss_rule_ids(request, registration),
    )


def execute_registered_aim_loss_difficult_terrain_charge(
    request: RegisteredAimLossDifficultTerrainChargeExecutionRequest, rng: RandomSource,
    *, decisions: ResolutionDecisionProvider | None = None,
) -> RegisteredAimLossDifficultTerrainChargeExecutionResult:
    """Check history and Charge eligibility before one terrain crossing and attack.

    Input snapshots remain immutable; external RNG/decision effects are not undone.
    """
    if not isinstance(request, RegisteredAimLossDifficultTerrainChargeExecutionRequest):
        raise TypeError("request must be a RegisteredAimLossDifficultTerrainChargeExecutionRequest")
    _validate_terrain_charge_loss_preflight(
        request.state, request.follow_up, request.action_id, request.charge, request.terrain,
    )
    _validate_difficult_terrain_charge_action(request.charge, request.charge.actor_conditions)
    traversal = resolve_difficult_terrain_traversal(request.terrain, rng, decisions=decisions)
    execution = execute_difficult_terrain_charge_action(DifficultTerrainChargeActionExecutionRequest(
        request.action_id, request.charge, traversal, request.charge.round_state, traversal.state,
    ), rng, decisions=decisions)
    registration = consume_difficult_terrain_charge_lost_aim(AimDifficultTerrainChargeLossConsumptionRequest(
        f"{request.id}:registration", request.state, request.follow_up, execution,
    ))
    return RegisteredAimLossDifficultTerrainChargeExecutionResult(
        request.id, request.rule_id, request, registration, _registered_loss_rule_ids(request, registration),
    )


def consume_difficult_terrain_charge_lost_aim(
    request: AimDifficultTerrainChargeLossConsumptionRequest,
) -> AimDifficultTerrainChargeLossConsumptionResult:
    """Register LOST from one completed terrain-aware Medium Melee/Brawn Charge.

    No traversal, movement, Athletics, attack or Condition is applied again. Caller retains
    the latest history and selects the actual next action after Aim.
    """
    if not isinstance(request, AimDifficultTerrainChargeLossConsumptionRequest):
        raise TypeError("request must be an AimDifficultTerrainChargeLossConsumptionRequest")
    return AimDifficultTerrainChargeLossConsumptionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        previous_state=request.state,
        state=_consumed_state(request),
        applied_rule_ids=_attack_loss_rule_ids(request),
    )


def consume_long_charge_lost_aim(request: AimLongChargeLossConsumptionRequest) -> AimLongChargeLossConsumptionResult:
    """Register LOST from Melee/Brawn Long Charge, including stopped-short outcomes.

    No movement, Athletics, attack or Condition is applied again. Caller retains
    the latest history and selects the actual next action after Aim.
    """
    if not isinstance(request, AimLongChargeLossConsumptionRequest):
        raise TypeError("request must be an AimLongChargeLossConsumptionRequest")
    return AimLongChargeLossConsumptionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        previous_state=request.state,
        state=_consumed_state(request),
        applied_rule_ids=_attack_loss_rule_ids(request),
    )


def consume_charge_lost_aim(request: AimChargeLossConsumptionRequest) -> AimChargeLossConsumptionResult:
    """Register LOST from one completed Medium Melee/Brawn Charge without executing it.

    Caller selects the next action and retains the latest history and Charge states.
    """
    if not isinstance(request, AimChargeLossConsumptionRequest):
        raise TypeError("request must be an AimChargeLossConsumptionRequest")
    return AimChargeLossConsumptionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        previous_state=request.state,
        state=_consumed_state(request),
        applied_rule_ids=_attack_loss_rule_ids(request),
    )


def execute_registered_aim_loss_prepared_attack(
    request: RegisteredAimLossPreparedAttackExecutionRequest,
    rng: RandomSource,
    *, decisions: ResolutionDecisionProvider | None = None,
) -> RegisteredAimLossPreparedAttackExecutionResult:
    """Check history before one direct prepared shot and register its LOST Aim.

    Input snapshots remain immutable; external RNG/decision effects are not undone.
    """
    if not isinstance(request, RegisteredAimLossPreparedAttackExecutionRequest):
        raise TypeError("request must be a RegisteredAimLossPreparedAttackExecutionRequest")
    _validate_prepared_attack_loss_preflight(request.state, request.follow_up, request.prepared_attack)
    execution = execute_prepared_ranged_weapon_attack(request.prepared_attack, rng, decisions=decisions)
    registration = consume_prepared_attack_lost_aim(AimPreparedAttackLossConsumptionRequest(
        f"{request.id}:registration", request.state, request.follow_up, execution,
    ))
    return RegisteredAimLossPreparedAttackExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        registration=registration,
        applied_rule_ids=_registered_loss_rule_ids(request, registration),
    )


def execute_registered_aim_loss_ranged_attack(
    request: RegisteredAimLossRangedAttackExecutionRequest,
    rng: RandomSource,
    *, decisions: ResolutionDecisionProvider | None = None,
) -> RegisteredAimLossRangedAttackExecutionResult:
    """Check history before one profile-aware shot and register its LOST Aim.

    Input snapshots remain immutable; external RNG/decision effects are not undone.
    """
    if not isinstance(request, RegisteredAimLossRangedAttackExecutionRequest):
        raise TypeError("request must be a RegisteredAimLossRangedAttackExecutionRequest")
    _validate_ranged_attack_loss_preflight(request.state, request.follow_up, request.ranged_attack)
    execution = execute_ranged_weapon_attack(request.ranged_attack, rng, decisions=decisions)
    registration = consume_ranged_attack_lost_aim(AimRangedAttackLossConsumptionRequest(
        f"{request.id}:registration", request.state, request.follow_up, execution,
    ))
    return RegisteredAimLossRangedAttackExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        registration=registration,
        applied_rule_ids=_registered_loss_rule_ids(request, registration),
    )


def consume_prepared_attack_lost_aim(
    request: AimPreparedAttackLossConsumptionRequest,
) -> AimPreparedAttackLossConsumptionResult:
    """Register LOST after one completed direct prepared shot at another target.

    Preserve preparation, profile, weapon/reload and sole Attack without re-execution.
    Caller retains the latest history and selects the actual next action.
    """
    if not isinstance(request, AimPreparedAttackLossConsumptionRequest):
        raise TypeError("request must be an AimPreparedAttackLossConsumptionRequest")
    return AimPreparedAttackLossConsumptionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        previous_state=request.state,
        state=_consumed_state(request),
        applied_rule_ids=_attack_loss_rule_ids(request),
    )


def consume_ranged_attack_lost_aim(
    request: AimRangedAttackLossConsumptionRequest,
) -> AimRangedAttackLossConsumptionResult:
    """Register LOST after one completed profile-aware shot at another target.

    Preserve the weapon/reload transition and sole Attack; do not execute or reload.
    Caller retains the latest history and selects the actual next action.
    """
    if not isinstance(request, AimRangedAttackLossConsumptionRequest):
        raise TypeError("request must be an AimRangedAttackLossConsumptionRequest")
    return AimRangedAttackLossConsumptionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        previous_state=request.state,
        state=_consumed_state(request),
        applied_rule_ids=_attack_loss_rule_ids(request),
    )


def consume_attack_lost_aim(request: AimAttackLossConsumptionRequest) -> AimAttackLossConsumptionResult:
    """Register LOST after a different-target or same-target Melee/Brawn Attack.

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
