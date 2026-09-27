from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.spatial_models import SpatialBattleState
from towr.domain.turn_models import CombatRoundAdvanceRequest, CombatRoundAdvanceResult, CombatRoundState, CombatTurnParticipant


@dataclass(frozen=True, slots=True)
class NpcRoundAdvanceRequest:
    id: str
    current: NpcRoundRequest
    spatial_state: SpatialBattleState
    next_round_participants: tuple[CombatTurnParticipant, ...]
    next_actor_order: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("NPC round advance requires a non-empty id")
        if not isinstance(self.current, NpcRoundRequest) or not isinstance(self.spatial_state, SpatialBattleState):
            raise TypeError("NPC round advance requires typed current snapshots")
        current = self.current
        if current.pending_follow_ups:
            raise ValueError("pending follow-ups must be resolved before advancing the round")
        if current.round_state.active_turn is not None or not current.round_state.round_complete:
            raise ValueError("NPC round must be complete without an active turn")
        if self.spatial_state.round_number != current.round_state.round_number:
            raise ValueError("combat and spatial rounds must match before advance")
        object.__setattr__(self, "next_round_participants", tuple(self.next_round_participants))
        object.__setattr__(self, "next_actor_order", tuple(self.next_actor_order))
        # Reuse the existing roster/side/Minion and exact actor-order checks without executing rules.
        replace(current, round_state=self.next_round_state, actor_order=self.next_actor_order)
        for member in self.next_round_participants:
            if current.state.roster.participant(member.entity_id).state.injury.defeated:
                raise ValueError("defeated Minion cannot enter the next round")
        for member in (*current.round_state.participants, *self.next_round_participants):
            if self.spatial_state.placement_for(member.entity_id).side_id != member.side.value:
                raise ValueError("spatial placement side differs from round participant")

    @property
    def next_round_state(self) -> CombatRoundState:
        return CombatRoundState(self.current.round_state.round_number + 1,
                                self.next_round_participants, self.current.round_state.side_order)

    @property
    def combat_request(self) -> CombatRoundAdvanceRequest:
        return CombatRoundAdvanceRequest(self.id, self.current.round_state, self.next_round_participants)


@dataclass(frozen=True, slots=True)
class NpcRoundAdvanceResult:
    source_request: NpcRoundAdvanceRequest
    combat: CombatRoundAdvanceResult
    spatial_state: SpatialBattleState

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcRoundAdvanceRequest):
            raise TypeError("NPC round advance result requires its typed source")
        if not isinstance(self.combat, CombatRoundAdvanceResult) or not isinstance(self.spatial_state, SpatialBattleState):
            raise TypeError("NPC round advance result requires typed transitions")
        source = self.source_request
        if (self.combat.request_id != source.id or self.combat.state != source.next_round_state
                or self.combat.applied_rule_ids != ("RULE-COMBAT-001:rounds-sides-turns",)):
            raise ValueError("combat round transition differs from source")
        expected = replace(source.spatial_state, round_number=source.spatial_state.round_number + 1,
                           gave_ground_entity_ids=(), free_move_used_entity_ids=(), difficult_terrain_tested_entity_ids=())
        if self.spatial_state != expected:
            raise ValueError("spatial round transition differs from source")

    @property
    def continuation(self) -> NpcRoundRequest:
        return replace(self.source_request.current, round_state=self.combat.state,
                       actor_order=self.source_request.next_actor_order)
