from __future__ import annotations

from towr.domain.npc_round_advance_models import NpcRoundAdvanceRequest, NpcRoundAdvanceResult
from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.spatial_models import SpatialBattleState
from towr.rules.spatial_resolution import start_next_spatial_round
from towr.rules.turn_resolution import advance_combat_round


def advance_npc_round(request: NpcRoundAdvanceRequest) -> NpcRoundAdvanceResult:
    """Advance exactly one completed Minion round and its spatial usage together."""
    if not isinstance(request, NpcRoundAdvanceRequest):
        raise TypeError("NPC round advance requires its typed request")
    combat = advance_combat_round(request.combat_request)
    spatial = start_next_spatial_round(request.spatial_state)
    return NpcRoundAdvanceResult(request, combat, spatial)


def apply_npc_round_advance(
    current: NpcRoundRequest, spatial_state: SpatialBattleState, result: NpcRoundAdvanceResult,
) -> tuple[NpcRoundRequest, SpatialBattleState]:
    """Accept once against both exact source snapshots; preserve all roster histories."""
    if (not isinstance(current, NpcRoundRequest) or not isinstance(spatial_state, SpatialBattleState)
            or not isinstance(result, NpcRoundAdvanceResult)):
        raise TypeError("NPC round advance application requires typed snapshots and result")
    if current != result.source_request.current or spatial_state != result.source_request.spatial_state:
        raise ValueError("NPC round advance source differs from current roster/history/round/pending/spatial")
    return result.continuation, result.spatial_state
