from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from towr.domain.npc_round_advance_models import NpcRoundAdvanceResult
from towr.domain.npc_round_models import NpcRoundOutcome, NpcRoundRequest, NpcRoundResult
from towr.domain.spatial_models import SpatialBattleState


class NpcRoundsOutcome(str, Enum):
    ROUND_LIMIT = "round_limit"
    PENDING_FOLLOW_UPS = "pending_follow_ups"
    SELECTION_BLOCKED = "selection_blocked"
    DEFEATED_ACTOR = "defeated_actor"


@dataclass(frozen=True, slots=True)
class NpcRoundsRequest:
    current: NpcRoundRequest
    spatial_state: SpatialBattleState
    max_rounds: int

    def __post_init__(self) -> None:
        if not isinstance(self.current, NpcRoundRequest) or not isinstance(self.spatial_state, SpatialBattleState):
            raise TypeError("NPC rounds require typed current snapshots")
        if type(self.max_rounds) is not int or self.max_rounds < 1:
            raise ValueError("max_rounds must be a positive integer including the current round")
        if self.current.round_state.round_number != self.spatial_state.round_number:
            raise ValueError("combat and spatial rounds must match")
        for member in self.current.round_state.participants:
            if self.spatial_state.placement_for(member.entity_id).side_id != member.side.value:
                raise ValueError("spatial placement side differs from round participant")


@dataclass(frozen=True, slots=True)
class NpcRoundsResult:
    source_request: NpcRoundsRequest
    rounds: tuple[NpcRoundResult, ...]
    advances: tuple[NpcRoundAdvanceResult, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcRoundsRequest):
            raise TypeError("NPC rounds result requires its typed source")
        rounds, advances = tuple(self.rounds), tuple(self.advances)
        if (not all(isinstance(item, NpcRoundResult) for item in rounds)
                or not all(isinstance(item, NpcRoundAdvanceResult) for item in advances)):
            raise TypeError("NPC rounds journal requires typed round and advance results")
        if not 1 <= len(rounds) <= self.source_request.max_rounds or len(advances) != len(rounds) - 1:
            raise ValueError("NPC rounds journal exceeds limit or has missing/extra transitions")
        current, spatial = self.source_request.current, self.source_request.spatial_state
        for index, result in enumerate(rounds):
            if result.source_request != current:
                raise ValueError("round result differs from current source")
            current = replace(current, state=result.state, round_state=result.round_state,
                              pending_follow_ups=result.pending_follow_ups)
            if index < len(advances):
                advance = advances[index]
                if result.outcome is not NpcRoundOutcome.COMPLETE:
                    raise ValueError("NPC rounds cannot advance after a blocking outcome")
                if advance.source_request.current != current or advance.source_request.spatial_state != spatial:
                    raise ValueError("round advance differs from current source snapshots")
                current, spatial = advance.continuation, advance.spatial_state
        if rounds[-1].outcome is NpcRoundOutcome.COMPLETE and len(rounds) != self.source_request.max_rounds:
            raise ValueError("NPC rounds stopped before limit without a blocking outcome")
        object.__setattr__(self, "rounds", rounds)
        object.__setattr__(self, "advances", advances)

    @property
    def current(self) -> NpcRoundRequest:
        last = self.rounds[-1]
        return replace(last.source_request, state=last.state, round_state=last.round_state,
                       pending_follow_ups=last.pending_follow_ups)

    @property
    def spatial_state(self) -> SpatialBattleState:
        return self.advances[-1].spatial_state if self.advances else self.source_request.spatial_state

    @property
    def completed_rounds(self) -> tuple[NpcRoundResult, ...]:
        return tuple(item for item in self.rounds if item.outcome is NpcRoundOutcome.COMPLETE)

    @property
    def outcome(self) -> NpcRoundsOutcome:
        last = self.rounds[-1].outcome
        return NpcRoundsOutcome.ROUND_LIMIT if last is NpcRoundOutcome.COMPLETE else NpcRoundsOutcome(last.value)
