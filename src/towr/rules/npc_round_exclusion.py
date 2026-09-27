from __future__ import annotations

from dataclasses import replace

from towr.domain.npc_round_exclusion_models import NpcRoundExclusionRequest, NpcRoundExclusionResult
from towr.domain.npc_round_models import NpcRoundRequest


def exclude_defeated_npc(request: NpcRoundExclusionRequest) -> NpcRoundExclusionResult:
    """Exclude one defeated Minion from remaining turns, without an action or RNG."""
    return NpcRoundExclusionResult(request)


def apply_npc_round_exclusion(current: NpcRoundRequest, result: NpcRoundExclusionResult) -> NpcRoundRequest:
    """Apply once to the exact roster/history/round/pending snapshot that was checked."""
    if not isinstance(current, NpcRoundRequest) or not isinstance(result, NpcRoundExclusionResult):
        raise TypeError("NPC exclusion application requires typed current request and result")
    if current != result.source_request.source:
        raise ValueError("NPC exclusion source differs from current roster/history/round/context")
    return replace(current, round_state=result.round_state)
