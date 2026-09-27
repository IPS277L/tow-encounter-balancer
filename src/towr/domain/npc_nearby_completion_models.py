from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.npc_nearby_consequence_models import NpcNearbyConsequenceChain
from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.resolution_models import NearbyTargetsStaggerRequest
from towr.domain.spatial_models import SpatialBattleState


@dataclass(frozen=True, slots=True)
class NpcNearbyCompletionRequest:
    id: str
    current: NpcRoundRequest
    spatial_state: SpatialBattleState
    chain: NpcNearbyConsequenceChain

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("nearby completion requires an ID")
        if not isinstance(self.current, NpcRoundRequest) or not isinstance(self.spatial_state, SpatialBattleState):
            raise TypeError("nearby completion requires typed round and spatial snapshots")
        if not isinstance(self.chain, NpcNearbyConsequenceChain):
            raise TypeError("nearby completion requires a typed full consequence chain")
        if self.source in self.current.state.completed_nearby_stagger_sources:
            raise ValueError("nearby effect was already completed")
        if self.chain.pending_targets:
            raise ValueError("nearby completion requires all secondary pending to be resolved")
        primary = self.chain.batch.source_request.primary_attack.attack
        if self.current.state != self.chain.state or self.current.round_state != primary.state:
            raise ValueError("nearby completion requires exact chain roster/history and post-primary round")
        if self.spatial_state != self.chain.spatial_state:
            raise ValueError("nearby completion requires the exact chain spatial snapshot")
        if self.current.pending_follow_ups.count(self.source) != 1:
            raise ValueError("nearby completion requires exactly one matching primary trigger")
        pending = iter(self.current.pending_follow_ups)
        for item in primary.resolution.follow_ups:
            if not any(queued == item for queued in pending):
                raise ValueError("nearby completion queue omits or reorders primary follow-ups")

    @property
    def source(self) -> NearbyTargetsStaggerRequest:
        return self.chain.batch.source_request.resolution.source


@dataclass(frozen=True, slots=True)
class NpcNearbyCompletionResult:
    source_request: NpcNearbyCompletionRequest

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcNearbyCompletionRequest):
            raise TypeError("nearby completion result requires its typed source request")

    @property
    def continuation(self) -> NpcRoundRequest:
        source = self.source_request
        current = source.current
        state = replace(current.state, completed_nearby_stagger_sources=(
            *current.state.completed_nearby_stagger_sources, source.source,
        ))
        index = current.pending_follow_ups.index(source.source)
        return replace(current, state=state,
                       pending_follow_ups=current.pending_follow_ups[:index] + current.pending_follow_ups[index + 1:])

    @property
    def spatial_state(self) -> SpatialBattleState:
        return self.source_request.spatial_state

    @property
    def applied_rule_ids(self) -> tuple[str, ...]:
        return (self.source_request.source.rule_id,)
