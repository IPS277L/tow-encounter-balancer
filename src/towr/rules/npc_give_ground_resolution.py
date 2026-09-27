from __future__ import annotations

from towr.domain.npc_give_ground_models import (
    NpcGiveGroundConsumptionRequest, NpcGiveGroundConsumptionResult, NpcGiveGroundExecutionRequest,
    validate_npc_give_ground_context,
)
from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.spatial_models import SpatialBattleState
from towr.rules.spatial_resolution import resolve_give_ground


def execute_npc_give_ground(request: NpcGiveGroundExecutionRequest) -> NpcGiveGroundConsumptionResult:
    """Validate current context, execute one movement and register its result once."""
    if not isinstance(request, NpcGiveGroundExecutionRequest):
        raise TypeError("NPC Give Ground execution requires its typed request")
    validate_npc_give_ground_context(request)
    movement = resolve_give_ground(request.movement)
    if movement.source_request != request.movement:
        raise ValueError("Give Ground executor returned a different source request")
    return consume_npc_give_ground(NpcGiveGroundConsumptionRequest(
        request.id, request.current, request.spatial_state, request.attack, movement,
    ))


def consume_npc_give_ground(request: NpcGiveGroundConsumptionRequest) -> NpcGiveGroundConsumptionResult:
    """Transfer a completed movement's Conditions and consume its pending item once."""
    return NpcGiveGroundConsumptionResult(request)


def apply_npc_give_ground(
    current: NpcRoundRequest, spatial_state: SpatialBattleState, result: NpcGiveGroundConsumptionResult,
) -> tuple[NpcRoundRequest, SpatialBattleState]:
    """Return both snapshots only against the exact current source; do not move again."""
    if (not isinstance(current, NpcRoundRequest) or not isinstance(spatial_state, SpatialBattleState)
            or not isinstance(result, NpcGiveGroundConsumptionResult)):
        raise TypeError("NPC Give Ground application requires typed current snapshots and result")
    if current != result.source_request.current or spatial_state != result.source_request.spatial_state:
        raise ValueError("NPC Give Ground source differs from current roster/history/round/pending/spatial")
    return result.continuation, result.spatial_state
