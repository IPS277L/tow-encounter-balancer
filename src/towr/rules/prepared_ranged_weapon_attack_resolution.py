from __future__ import annotations

from towr.domain.prepared_ranged_weapon_attack_models import (
    PreparedRangedWeaponAttackExecutionRequest,
    PreparedRangedWeaponAttackExecutionResult,
    _aim_request_for,
    _applied_rule_ids,
)
from towr.rules.aim_ranged_weapon_attack_resolution import execute_aim_ranged_weapon_attack
from towr.rules.dice import RandomSource
from towr.rules.kernel import ResolutionDecisionProvider
from towr.rules.ranged_weapon_attack_resolution import execute_ranged_weapon_attack


def execute_prepared_ranged_weapon_attack(
    request: PreparedRangedWeaponAttackExecutionRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> PreparedRangedWeaponAttackExecutionResult:
    """Execute one prepared shot, preserving profile trace and Aim consumption."""
    if not isinstance(request, PreparedRangedWeaponAttackExecutionRequest):
        raise TypeError("request must be a prepared ranged Attack request")
    if request.preparation.aim_follow_up is None:
        execution = execute_ranged_weapon_attack(
            request.preparation.execution, rng, decisions=decisions
        )
        consumed = request.consumed_aim_follow_up_ids
    else:
        execution = execute_aim_ranged_weapon_attack(
            _aim_request_for(request), rng, decisions=decisions
        )
        consumed = execution.consumed_aim_follow_up_ids
    return PreparedRangedWeaponAttackExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        execution=execution,
        previous_consumed_aim_follow_up_ids=request.consumed_aim_follow_up_ids,
        consumed_aim_follow_up_ids=consumed,
        applied_rule_ids=_applied_rule_ids(request, execution),
    )
