from __future__ import annotations

from towr.domain.npc_nearby_completion_models import NpcNearbyCompletionRequest, NpcNearbyCompletionResult
from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.spatial_models import SpatialBattleState


def complete_npc_nearby_consequences(request: NpcNearbyCompletionRequest) -> NpcNearbyCompletionResult:
    """Record completion of one full secondary chain without executing any rules again."""
    return NpcNearbyCompletionResult(request)


def apply_npc_nearby_completion(
    current: NpcRoundRequest, spatial_state: SpatialBattleState, result: NpcNearbyCompletionResult,
) -> tuple[NpcRoundRequest, SpatialBattleState]:
    if (not isinstance(current, NpcRoundRequest) or not isinstance(spatial_state, SpatialBattleState)
            or not isinstance(result, NpcNearbyCompletionResult)):
        raise TypeError("nearby completion application requires typed current snapshots and result")
    if result.source_request.source in current.state.completed_nearby_stagger_sources:
        raise ValueError("nearby effect was already completed")
    if current != result.source_request.current or spatial_state != result.source_request.spatial_state:
        raise ValueError("nearby completion source differs from current round/roster/history/pending/spatial")
    return result.continuation, result.spatial_state
