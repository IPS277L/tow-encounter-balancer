from __future__ import annotations

from towr.domain.npc_nearby_defeat_models import NpcNearbyDefeatAcknowledgementRequest, NpcNearbyDefeatAcknowledgementResult
from towr.domain.npc_roster_attack_models import NpcRosterAttackState


def acknowledge_npc_nearby_defeat(request: NpcNearbyDefeatAcknowledgementRequest) -> NpcNearbyDefeatAcknowledgementResult:
    """Record one explicit secondary defeat decision without executing injury or RNG."""
    return NpcNearbyDefeatAcknowledgementResult(request)


def apply_npc_nearby_defeat(
    current: NpcRosterAttackState, result: NpcNearbyDefeatAcknowledgementResult,
) -> NpcRosterAttackState:
    if not isinstance(current, NpcRosterAttackState) or not isinstance(result, NpcNearbyDefeatAcknowledgementResult):
        raise TypeError("nearby defeat application requires typed current state and result")
    if result.source_request.key in current.acknowledged_nearby_defeats:
        raise ValueError("nearby defeat was already acknowledged")
    if current != result.source_request.current:
        raise ValueError("nearby defeat source differs from current roster/history")
    return result.state
