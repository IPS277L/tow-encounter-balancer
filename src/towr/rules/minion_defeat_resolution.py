from __future__ import annotations

from towr.domain.minion_defeat_models import MinionDefeatAcknowledgementRequest, MinionDefeatAcknowledgementResult
from towr.domain.npc_round_models import NpcRoundRequest


def acknowledge_minion_defeat(request: MinionDefeatAcknowledgementRequest) -> MinionDefeatAcknowledgementResult:
    """Record an explicit attacker/GM disposition; no new Wound, action or RNG."""
    return MinionDefeatAcknowledgementResult(request)


def apply_minion_defeat_acknowledgement(
    current: NpcRoundRequest, result: MinionDefeatAcknowledgementResult,
) -> NpcRoundRequest:
    """Consume only the bound pending defeat, against its exact current snapshot."""
    if not isinstance(current, NpcRoundRequest) or not isinstance(result, MinionDefeatAcknowledgementResult):
        raise TypeError("defeat application requires typed current request and result")
    if current != result.source_request.current:
        raise ValueError("defeat acknowledgement source differs from current roster/history/round/pending")
    return result.continuation
