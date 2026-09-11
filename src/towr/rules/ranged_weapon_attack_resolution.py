from __future__ import annotations

from towr.domain.ranged_weapon_attack_models import (
    RangedWeaponAttackExecutionRequest,
    RangedWeaponAttackExecutionResult,
    ReloadableRangedAttackExecutionRequest,
    ReloadableRangedAttackExecutionResult,
    _as_reloadable_request,
    _spent_weapon_state,
)
from towr.domain.reload_models import FreeReloadWeaponState
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.dice import RandomSource
from towr.rules.kernel import ResolutionDecisionProvider


def execute_reloadable_ranged_attack(
    request: ReloadableRangedAttackExecutionRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> ReloadableRangedAttackExecutionResult:
    """Fire one loaded weapon and apply its profile's reload trigger."""
    attack = execute_attack_action(
        request.attack,
        rng,
        decisions=decisions,
    )
    return ReloadableRangedAttackExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        attack=attack,
        previous_weapon_state=request.weapon_state,
        weapon_state=_spent_weapon_state(request),
        applied_rule_ids=tuple(
            dict.fromkeys((request.rule_id, *attack.applied_rule_ids))
        ),
    )


def execute_ranged_weapon_attack(
    request: RangedWeaponAttackExecutionRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> RangedWeaponAttackExecutionResult:
    """Execute one profile-aware Shooting Attack without duplicate receipts."""
    if isinstance(request.weapon_state, FreeReloadWeaponState):
        attack = execute_attack_action(
            request.attack,
            rng,
            decisions=decisions,
        )
        weapon_state = request.weapon_state
    else:
        reloadable = execute_reloadable_ranged_attack(
            _as_reloadable_request(request),
            rng,
            decisions=decisions,
        )
        attack = reloadable.attack
        weapon_state = reloadable.weapon_state

    return RangedWeaponAttackExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        attack=attack,
        previous_weapon_state=request.weapon_state,
        weapon_state=weapon_state,
        applied_rule_ids=tuple(
            dict.fromkeys((request.rule_id, *attack.applied_rule_ids))
        ),
    )
