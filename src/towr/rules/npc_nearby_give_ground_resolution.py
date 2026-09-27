from __future__ import annotations

from towr.domain.npc_nearby_give_ground_models import (
    NpcNearbyGiveGroundConsumptionRequest, NpcNearbyGiveGroundConsumptionResult,
    NpcNearbyGiveGroundExecutionRequest, validate_nearby_give_ground_context,
)
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.spatial_models import SpatialBattleState
from towr.rules.spatial_resolution import resolve_give_ground


def execute_npc_nearby_give_ground(request: NpcNearbyGiveGroundExecutionRequest) -> NpcNearbyGiveGroundConsumptionResult:
    """PG 1.4, Rules / Giving Ground, p119: execute one scoped secondary movement."""
    if not isinstance(request, NpcNearbyGiveGroundExecutionRequest):
        raise TypeError("nearby Give Ground execution requires its typed request")
    validate_nearby_give_ground_context(request)
    movement = resolve_give_ground(request.movement)
    if movement.source_request != request.movement:
        raise ValueError("nearby Give Ground executor returned a different source request")
    return consume_npc_nearby_give_ground(NpcNearbyGiveGroundConsumptionRequest(
        request.id, request.current, request.spatial_state, request.batch, request.target_id, movement, request.previous,
        request.continuation,
    ))


def consume_npc_nearby_give_ground(request: NpcNearbyGiveGroundConsumptionRequest) -> NpcNearbyGiveGroundConsumptionResult:
    """Transfer completed Conditions/usage without executing movement or injury again."""
    return NpcNearbyGiveGroundConsumptionResult(request)


def apply_npc_nearby_give_ground(
    current: NpcRosterAttackState, spatial_state: SpatialBattleState, result: NpcNearbyGiveGroundConsumptionResult,
) -> tuple[NpcRosterAttackState, SpatialBattleState]:
    if (not isinstance(current, NpcRosterAttackState) or not isinstance(spatial_state, SpatialBattleState)
            or not isinstance(result, NpcNearbyGiveGroundConsumptionResult)):
        raise TypeError("nearby Give Ground application requires typed current snapshots and result")
    if current != result.source_request.current or spatial_state != result.source_request.spatial_state:
        raise ValueError("nearby Give Ground source differs from current roster/history/spatial")
    return result.state, result.spatial_state
