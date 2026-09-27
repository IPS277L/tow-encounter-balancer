from __future__ import annotations

from towr.domain.npc_blunderbuss_give_ground_models import (
    NpcBlunderbussGiveGroundConsumptionRequest, NpcBlunderbussGiveGroundConsumptionResult,
    NpcBlunderbussGiveGroundExecutionRequest, validate_blunderbuss_give_ground_context,
)
from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.spatial_models import SpatialBattleState
from towr.rules.spatial_resolution import resolve_give_ground


def execute_npc_blunderbuss_give_ground(
    request: NpcBlunderbussGiveGroundExecutionRequest,
) -> NpcBlunderbussGiveGroundConsumptionResult:
    """PG 1.4, Rules / Giving Ground, p119: one primary movement after secondary completion."""
    if not isinstance(request, NpcBlunderbussGiveGroundExecutionRequest):
        raise TypeError("Blunderbuss Give Ground execution requires its typed request")
    validate_blunderbuss_give_ground_context(request)
    movement = resolve_give_ground(request.movement)
    if movement.source_request != request.movement:
        raise ValueError("Blunderbuss Give Ground executor returned a different source request")
    return consume_npc_blunderbuss_give_ground(NpcBlunderbussGiveGroundConsumptionRequest(
        request.id, request.current, request.spatial_state, request.attack, request.completion, movement,
    ))


def consume_npc_blunderbuss_give_ground(
    request: NpcBlunderbussGiveGroundConsumptionRequest,
) -> NpcBlunderbussGiveGroundConsumptionResult:
    """Transfer completed Conditions/usage without repeating movement or injury."""
    return NpcBlunderbussGiveGroundConsumptionResult(request)


def apply_npc_blunderbuss_give_ground(
    current: NpcRoundRequest, spatial_state: SpatialBattleState, result: NpcBlunderbussGiveGroundConsumptionResult,
) -> tuple[NpcRoundRequest, SpatialBattleState]:
    if (not isinstance(current, NpcRoundRequest) or not isinstance(spatial_state, SpatialBattleState)
            or not isinstance(result, NpcBlunderbussGiveGroundConsumptionResult)):
        raise TypeError("Blunderbuss Give Ground application requires typed current snapshots and result")
    if result.source_request.attack.primary_attack.attack.request_id in current.state.consumed_give_ground_execution_ids:
        raise ValueError("Blunderbuss primary Give Ground was already consumed")
    if current != result.source_request.current or spatial_state != result.source_request.spatial_state:
        raise ValueError("Blunderbuss Give Ground source differs from current round/roster/history/pending/spatial")
    return result.continuation, result.spatial_state
