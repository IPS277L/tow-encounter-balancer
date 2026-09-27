from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from towr.domain.npc_attack_selection_models import NpcAttackSelectionRequest
from towr.domain.npc_round_advance_models import NpcRoundAdvanceRequest
from towr.domain.npc_round_models import NpcRoundOutcome, NpcRoundRequest, NpcRoundResult
from towr.domain.npc_rounds_models import NpcRoundsRequest, NpcRoundsResult
from towr.domain.spatial_models import SpatialBattleState
from towr.engine.npc_round_coordinator import run_npc_round
from towr.rules.dice import RandomSource
from towr.rules.kernel import ResolutionDecisionProvider
from towr.rules.npc_round_advance import advance_npc_round, apply_npc_round_advance


class NpcRoundsCandidateProvider(Protocol):
    def get_candidates(
        self, context: NpcAttackSelectionRequest, spatial_state: SpatialBattleState,
    ) -> NpcAttackSelectionRequest:
        """Supply only candidates, using these current combat and spatial snapshots."""
        ...


class NpcNextRoundProvider(Protocol):
    def get_next_round(
        self, current: NpcRoundRequest, spatial_state: SpatialBattleState,
    ) -> NpcRoundAdvanceRequest:
        """Choose the next composition/order, binding the exact completed snapshots."""
        ...


@dataclass(frozen=True, slots=True)
class _RoundCandidates:
    provider: NpcRoundsCandidateProvider
    spatial_state: SpatialBattleState

    def get_candidates(self, context: NpcAttackSelectionRequest) -> NpcAttackSelectionRequest:
        return self.provider.get_candidates(context, self.spatial_state)


def run_npc_rounds(
    request: NpcRoundsRequest, candidates: NpcRoundsCandidateProvider,
    next_rounds: NpcNextRoundProvider, rng: RandomSource,
    *, decisions: ResolutionDecisionProvider | None = None,
) -> NpcRoundsResult:
    """Visit at most max_rounds, including the supplied current (possibly complete) round."""
    if not isinstance(request, NpcRoundsRequest):
        raise TypeError("NPC rounds runner requires its typed request")
    current, spatial = request.current, request.spatial_state
    rounds, advances = [], []
    for index in range(request.max_rounds):
        result = run_npc_round(current, _RoundCandidates(candidates, spatial), rng, decisions=decisions)
        if not isinstance(result, NpcRoundResult) or result.source_request != current:
            raise ValueError("round result differs from executed request")
        rounds.append(result)
        current = replace(current, state=result.state, round_state=result.round_state,
                          pending_follow_ups=result.pending_follow_ups)
        if result.outcome is not NpcRoundOutcome.COMPLETE or index + 1 == request.max_rounds:
            return NpcRoundsResult(request, tuple(rounds), tuple(advances))
        planned = next_rounds.get_next_round(current, spatial)
        if not isinstance(planned, NpcRoundAdvanceRequest):
            raise TypeError("next round provider must return an NpcRoundAdvanceRequest")
        if planned.current != current or planned.spatial_state != spatial:
            raise ValueError("next round provider changed the current snapshots")
        advanced = advance_npc_round(planned)
        if advanced.source_request != planned:
            raise ValueError("round advance differs from planned request")
        current, spatial = apply_npc_round_advance(current, spatial, advanced)
        advances.append(advanced)
    raise AssertionError("bounded NPC rounds failed to stop")
