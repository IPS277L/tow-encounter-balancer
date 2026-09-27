from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.turn_models import CombatRoundState, CombatTurnState


@dataclass(frozen=True, slots=True)
class NpcRoundExclusionRequest:
    id: str
    source: NpcRoundRequest
    actor_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("NPC exclusion requires a non-empty string id")
        if not isinstance(self.source, NpcRoundRequest):
            raise TypeError("NPC exclusion requires a typed current round request")
        if not isinstance(self.actor_id, str) or not self.actor_id.strip():
            raise ValueError("NPC exclusion requires a non-empty actor id")
        if self.source.pending_follow_ups:
            raise ValueError("pending follow-ups must be resolved before exclusion")
        combat_round = self.source.round_state
        combat_round.participant_for(self.actor_id)
        if self.actor_id in combat_round.completed_turn_entity_ids:
            raise ValueError("completed turn cannot be replaced by exclusion")
        if self.actor_id in combat_round.excluded_turn_entity_ids:
            raise ValueError("participant is already excluded from this round")
        if not self.source.state.roster.participant(self.actor_id).state.injury.defeated:
            raise ValueError("only a defeated Minion may be excluded")


@dataclass(frozen=True, slots=True)
class NpcRoundExclusionResult:
    source_request: NpcRoundExclusionRequest

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcRoundExclusionRequest):
            raise TypeError("NPC exclusion result requires its typed source request")

    @property
    def interrupted_turn(self) -> CombatTurnState | None:
        turn = self.source_request.source.round_state.active_turn
        return turn if turn is not None and turn.actor_id == self.source_request.actor_id else None

    @property
    def round_state(self) -> CombatRoundState:
        source = self.source_request
        combat_round = source.source.round_state
        return replace(combat_round,
                       excluded_turn_entity_ids=(*combat_round.excluded_turn_entity_ids, source.actor_id),
                       active_turn=None if self.interrupted_turn is not None else combat_round.active_turn)

    @property
    def applied_rule_ids(self) -> tuple[str, ...]:
        return ("RULE-NPC-002", "RULE-COMBAT-001:rounds-sides-turns")
