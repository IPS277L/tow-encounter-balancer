from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.turn_models import CombatRoundState, CombatTurnState


def validate_minion_exclusion_context(
    state: NpcRosterAttackState, combat_round: CombatRoundState, actor_id: str,
) -> None:
    """Queue-independent checks shared by Minion-only M2 and full-owner M8."""
    if not isinstance(state, NpcRosterAttackState) or not isinstance(combat_round, CombatRoundState):
        raise TypeError('exclusion context requires typed roster and round state')
    combat_round.participant_for(actor_id)
    if actor_id in combat_round.completed_turn_entity_ids:
        raise ValueError("completed turn cannot be replaced by exclusion")
    if actor_id in combat_round.excluded_turn_entity_ids:
        raise ValueError("participant is already excluded from this round")
    actor = state.roster.participant(actor_id)
    if actor.definition.injury_policy is not TargetInjuryPolicy.MINION or not actor.state.injury.defeated:
        raise ValueError("only a defeated Minion may be excluded")


def excluded_minion_round(combat_round: CombatRoundState, actor_id: str) -> CombatRoundState:
    """Project a validated exclusion without an action or a completed turn."""
    turn = combat_round.active_turn
    return replace(combat_round, excluded_turn_entity_ids=(*combat_round.excluded_turn_entity_ids, actor_id),
                   active_turn=None if turn is not None and turn.actor_id == actor_id else turn)


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
        validate_minion_exclusion_context(self.source.state, self.source.round_state, self.actor_id)


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
        return excluded_minion_round(source.source.round_state, source.actor_id)

    @property
    def applied_rule_ids(self) -> tuple[str, ...]:
        return ("RULE-NPC-002", "RULE-COMBAT-001:rounds-sides-turns")
