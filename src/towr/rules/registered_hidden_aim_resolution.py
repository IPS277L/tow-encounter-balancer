from __future__ import annotations

from towr.domain.aim_consumption_models import AimAttackConsumptionRequest
from towr.domain.aim_ranged_weapon_attack_models import AimRangedWeaponAttackExecutionResult
from towr.domain.prepared_hidden_ranged_attack_models import PreparedHiddenRangedAttackExecutionResult
from towr.domain.registered_hidden_aim_models import (
    RegisteredHiddenAimAttackExecutionRequest,
    RegisteredHiddenAimAttackExecutionResult,
    _registered_hidden_aim_rule_ids,
    _validate_registered_hidden_aim_preflight,
)
from towr.rules.aim_consumption_resolution import register_aim_ranged_attack
from towr.rules.dice import RandomSource
from towr.rules.hiding_position_resolution import execute_registered_hidden_attack
from towr.rules.kernel import ResolutionDecisionProvider


def execute_registered_hidden_aim_attack(
    request: RegisteredHiddenAimAttackExecutionRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> RegisteredHiddenAimAttackExecutionResult:
    """Execute one prepared hidden Aim shot and return both registrations.

    Input snapshots are immutable; RNG and decision-provider effects are not undone.
    Caller retains the current Aim, hiding-position and opportunity histories.
    """
    if not isinstance(request, RegisteredHiddenAimAttackExecutionRequest):
        raise TypeError("request must be a RegisteredHiddenAimAttackExecutionRequest")
    _validate_registered_hidden_aim_preflight(request.aim_state, request.attack)
    hidden_attack = execute_registered_hidden_attack(request.attack, rng, decisions=decisions)
    execution = hidden_attack.execution
    if not isinstance(execution, PreparedHiddenRangedAttackExecutionResult):
        raise TypeError("hidden executor must return a prepared execution")
    aim_execution = execution.prepared_attack.execution
    if not isinstance(aim_execution, AimRangedWeaponAttackExecutionResult):
        raise TypeError("prepared executor must return an Aim execution")
    aim_registration = register_aim_ranged_attack(AimAttackConsumptionRequest(
        f"{request.id}:aim-registration", request.aim_state, aim_execution,
    ))
    return RegisteredHiddenAimAttackExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        hidden_attack=hidden_attack,
        aim_registration=aim_registration,
        applied_rule_ids=_registered_hidden_aim_rule_ids(request, hidden_attack, aim_registration),
    )
