from __future__ import annotations

from towr.domain.fate_models import (
    FATE_TACTICAL_RETREAT_RULE_ID,
    FateTacticalRetreatProof,
)
from towr.domain.retreat_models import (
    RETREAT_RULE_ID,
    GroupRetreatDeclaration,
    RetreatRearGuardResult,
)


def secure_group_retreat(
    request: GroupRetreatDeclaration,
    *,
    fate_proof: FateTacticalRetreatProof,
) -> RetreatRearGuardResult:
    """Bind a validated group Retreat to its Fate-funded rearguard."""
    if request.rule_id != RETREAT_RULE_ID:
        raise ValueError("group Retreat uses an unknown rule")
    if not isinstance(fate_proof, FateTacticalRetreatProof):
        raise TypeError("fate_proof must be a FateTacticalRetreatProof")
    if (
        fate_proof.rule_id != FATE_TACTICAL_RETREAT_RULE_ID
        or fate_proof.retreat_id != request.id
        or fate_proof.battle_id != request.battle_id
        or fate_proof.player_character_ids != request.player_character_ids
        or fate_proof.actor_id not in request.player_character_ids
    ):
        raise ValueError("Fate proof belongs to another group Retreat")
    return RetreatRearGuardResult(
        request_id=request.id,
        source_request=request,
        rearguard_actor_id=fate_proof.actor_id,
        fate_proof_id=fate_proof.id,
        source_spend_id=fate_proof.source_spend_id,
        covered_player_character_ids=request.player_character_ids,
        pursuit_decision_required=True,
        applied_rule_ids=(RETREAT_RULE_ID, fate_proof.rule_id),
    )
