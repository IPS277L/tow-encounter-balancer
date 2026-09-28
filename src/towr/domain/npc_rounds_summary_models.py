from __future__ import annotations

from dataclasses import dataclass

from towr.domain.condition_models import ConditionState
from towr.domain.npc_attack_selection_models import NpcAttackSelectionBlock
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult
from towr.domain.npc_round_models import NpcRoundOutcome
from towr.domain.npc_rounds_models import NpcRoundsOutcome, NpcRoundsResult
from towr.domain.turn_models import CombatSide


@dataclass(frozen=True, slots=True)
class NpcRoundsParticipantSummary:
    actor_id: str
    side: CombatSide
    wounds: int
    defeated: bool
    conditions: ConditionState

    def __post_init__(self) -> None:
        if not isinstance(self.actor_id, str) or not self.actor_id.strip():
            raise ValueError("participant summary requires an actor ID")
        if not isinstance(self.side, CombatSide) or not isinstance(self.conditions, ConditionState):
            raise TypeError("participant summary requires typed side and Conditions")
        if type(self.wounds) is not int or self.wounds < 0:
            raise ValueError("participant summary wounds must be a non-negative integer")
        if not isinstance(self.defeated, bool):
            raise TypeError("participant summary defeated must be a bool")


@dataclass(frozen=True, slots=True)
class NpcRoundsSummary:
    """Read-only projection of one validated runner result, not an encounter outcome."""

    source_result: NpcRoundsResult

    def __post_init__(self) -> None:
        if not isinstance(self.source_result, NpcRoundsResult):
            raise TypeError("NPC rounds summary requires an NpcRoundsResult")

    @property
    def outcome(self) -> NpcRoundsOutcome:
        return self.source_result.outcome

    @property
    def blocked_reason(self) -> NpcAttackSelectionBlock | None:
        selected = self.source_result.rounds[-1].blocked_selection
        return selected.blocked_reason if selected is not None else None

    @property
    def pending_follow_up_count(self) -> int:
        return len(self.source_result.rounds[-1].pending_follow_ups)

    @property
    def initial_round_number(self) -> int:
        return self.source_result.source_request.current.round_state.round_number

    @property
    def final_round_number(self) -> int:
        return self.source_result.rounds[-1].round_state.round_number

    @property
    def visited_round_count(self) -> int:
        return len(self.source_result.rounds)

    @property
    def newly_completed_round_count(self) -> int:
        return sum(result.outcome is NpcRoundOutcome.COMPLETE and not result.source_request.round_state.round_complete
                   for result in self.source_result.rounds)

    @property
    def executed_attack_count(self) -> int:
        return sum(result.executed_attack_count for result in self.source_result.rounds)

    @property
    def participants(self) -> tuple[NpcRoundsParticipantSummary, ...]:
        actor_ids = dict.fromkeys(member.entity_id for result in self.source_result.rounds
                                  for member in result.source_request.round_state.participants)
        roster = self.source_result.rounds[-1].state.roster
        records = []
        for actor_id in actor_ids:
            state = roster.participant(actor_id).state
            records.append(NpcRoundsParticipantSummary(actor_id, state.side, state.injury.wounds,
                                                       state.injury.defeated, state.injury.conditions))
        return tuple(records)
