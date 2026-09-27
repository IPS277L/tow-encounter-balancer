from towr.domain.npc_attack_preparation_models import (
    NpcAttackPreparationRequest, NpcAttackPreparationResult, NpcProtectedAttackPreparationResult,
    _expected_npc_attack, _validate_protection_pair,
)
from towr.domain.protection_models import ProtectionPreparationRequest
from towr.rules.protection_preparation import prepare_protection


def prepare_npc_attack(request: NpcAttackPreparationRequest) -> NpcAttackPreparationResult:
    """Prepare one available numeric Melee/Shooting profile without RNG or AI."""
    if not isinstance(request, NpcAttackPreparationRequest):
        raise TypeError("request must be a NpcAttackPreparationRequest")
    profile, attack, rules = _expected_npc_attack(request)
    return NpcAttackPreparationResult(
        request.id, request, request.snapshot, request.target_id, profile, attack, rules,
    )


def prepare_npc_attack_protection(
    npc_attack: NpcAttackPreparationResult, protection: ProtectionPreparationRequest,
) -> NpcProtectedAttackPreparationResult:
    """Bind a single Protection preparation to the exact NPC attack and target."""
    _validate_protection_pair(npc_attack, protection)
    prepared = prepare_protection(protection)
    return NpcProtectedAttackPreparationResult(
        npc_attack, prepared,
        tuple(dict.fromkeys((*npc_attack.applied_rule_ids, *prepared.applied_rule_ids))),
    )
