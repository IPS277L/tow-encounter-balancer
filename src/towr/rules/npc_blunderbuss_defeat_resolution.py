from __future__ import annotations

from towr.domain.npc_blunderbuss_defeat_models import (
    NpcBlunderbussDefeatAcknowledgementRequest, NpcBlunderbussDefeatAcknowledgementResult,
)
from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.spatial_models import SpatialBattleState


def acknowledge_npc_blunderbuss_defeat(
    request: NpcBlunderbussDefeatAcknowledgementRequest,
) -> NpcBlunderbussDefeatAcknowledgementResult:
    """GM Guide 1.1, Minions p91: record a primary disposition after secondary completion."""
    return NpcBlunderbussDefeatAcknowledgementResult(request)


def apply_npc_blunderbuss_defeat(
    current: NpcRoundRequest, spatial_state: SpatialBattleState, result: NpcBlunderbussDefeatAcknowledgementResult,
) -> tuple[NpcRoundRequest, SpatialBattleState]:
    if (not isinstance(current, NpcRoundRequest) or not isinstance(spatial_state, SpatialBattleState)
            or not isinstance(result, NpcBlunderbussDefeatAcknowledgementResult)):
        raise TypeError("Blunderbuss defeat application requires typed current snapshots and result")
    if result.source_request.attack.primary_attack.attack.request_id in current.state.acknowledged_defeat_execution_ids:
        raise ValueError("Blunderbuss primary defeat was already acknowledged")
    if current != result.source_request.current or spatial_state != result.source_request.spatial_state:
        raise ValueError("Blunderbuss defeat source differs from current round/roster/history/pending/spatial")
    return result.continuation, result.spatial_state
