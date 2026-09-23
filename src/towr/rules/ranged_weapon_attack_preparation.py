from __future__ import annotations

from towr.domain.aim_consumption_models import AimConsumptionState
from towr.domain.ranged_weapon_attack_preparation_models import (
    RangedWeaponAttackPreparationRequest,
    RangedWeaponAttackPreparationResult,
    _aim_follow_up_for,
    _applied_rule_ids,
    _execution_for,
    _profile_prepared_attack,
)
from towr.domain.ranged_weapon_profiles import ranged_weapon_combat_profile


def prepare_ranged_weapon_attack_with_aim_history(
    state: AimConsumptionState,
    request: RangedWeaponAttackPreparationRequest,
) -> RangedWeaponAttackPreparationResult:
    """Reject a consumed Aim source before preparing its bonus.

    Caller retains the latest history and forwards its follow-up IDs to execution.
    Preparation neither consumes a fresh Aim nor executes an Attack.
    """
    if not isinstance(state, AimConsumptionState):
        raise TypeError("state must be an AimConsumptionState")
    if not isinstance(request, RangedWeaponAttackPreparationRequest):
        raise TypeError("request must be a RangedWeaponAttackPreparationRequest")
    if state.actor_id != request.attack.actor_id:
        raise ValueError("Aim history belongs to another actor")
    if request.aim is not None and request.aim.request_id in state.consumed_aim_source_ids:
        raise ValueError("Aim source was already consumed")
    return prepare_ranged_weapon_attack(request)


def prepare_ranged_weapon_attack(
    request: RangedWeaponAttackPreparationRequest,
) -> RangedWeaponAttackPreparationResult:
    """Apply one weapon profile and optional Aim without executing the Attack."""
    profile = ranged_weapon_combat_profile(request.weapon_state.weapon_id)
    profile_attack = _profile_prepared_attack(request)
    aim_follow_up = _aim_follow_up_for(request, profile_attack)
    attack = (
        aim_follow_up.attack
        if aim_follow_up is not None
        else profile_attack
    )
    assert attack is not None
    execution = _execution_for(request, attack)
    return RangedWeaponAttackPreparationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        profile=profile,
        profile_attack=profile_attack,
        aim_follow_up=aim_follow_up,
        execution=execution,
        applied_rule_ids=_applied_rule_ids(request, profile, aim_follow_up),
    )
