from __future__ import annotations

from towr.domain.ranged_weapon_attack_preparation_models import (
    RangedWeaponAttackPreparationRequest,
    RangedWeaponAttackPreparationResult,
    _aim_follow_up_for,
    _applied_rule_ids,
    _execution_for,
    _profile_prepared_attack,
)
from towr.domain.ranged_weapon_profiles import ranged_weapon_combat_profile


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
