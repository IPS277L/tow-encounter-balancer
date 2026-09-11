from __future__ import annotations

from towr.domain.aim_ranged_weapon_attack_models import (
    AIM_RANGED_ATTACK_EXECUTION_RULE_ID,
    AimRangedWeaponAttackExecutionRequest,
    AimRangedWeaponAttackExecutionResult,
)
from towr.rules.dice import RandomSource
from towr.rules.kernel import ResolutionDecisionProvider
from towr.rules.ranged_weapon_attack_resolution import (
    execute_ranged_weapon_attack,
)


def execute_aim_ranged_weapon_attack(
    request: AimRangedWeaponAttackExecutionRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> AimRangedWeaponAttackExecutionResult:
    """Consume one applied Aim follow-up through one profile-aware Attack."""
    if request.rule_id != AIM_RANGED_ATTACK_EXECUTION_RULE_ID:
        raise ValueError("Aim ranged Attack uses an unknown source rule")
    ranged_attack = execute_ranged_weapon_attack(
        request.ranged_attack,
        rng,
        decisions=decisions,
    )
    follow_up_id = request.aim_follow_up.request_id
    return AimRangedWeaponAttackExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        ranged_attack=ranged_attack,
        previous_consumed_aim_follow_up_ids=(
            request.consumed_aim_follow_up_ids
        ),
        consumed_aim_follow_up_ids=(
            *request.consumed_aim_follow_up_ids,
            follow_up_id,
        ),
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    *request.aim_follow_up.applied_rule_ids,
                    *ranged_attack.applied_rule_ids,
                )
            )
        ),
    )
