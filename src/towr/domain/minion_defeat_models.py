from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from towr.domain.injury_models import ProfileNpcType, ProfileStateChangeRequest
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult
from towr.domain.npc_round_models import NpcRoundRequest


class NpcDefeatDisposition(str, Enum):
    KILLED = "killed"
    KNOCKED_OUT = "knocked_out"
    DISARMED_AND_SURRENDERED = "disarmed_and_surrendered"


@dataclass(frozen=True, slots=True)
class MinionDefeatDecision:
    attacker_id: str
    target_id: str
    disposition: NpcDefeatDisposition
    gm_approved: bool

    def __post_init__(self) -> None:
        for value in (self.attacker_id, self.target_id):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("defeat decision requires non-empty attacker/target IDs")
        if self.attacker_id == self.target_id:
            raise ValueError("defeat decision requires distinct attacker and target")
        if not isinstance(self.disposition, NpcDefeatDisposition):
            raise TypeError("defeat disposition must be typed")
        if not isinstance(self.gm_approved, bool):
            raise TypeError("GM approval must be a boolean")


@dataclass(frozen=True, slots=True)
class MinionDefeatAcknowledgementRequest:
    id: str
    current: NpcRoundRequest
    attack: NpcRosterAttackExecutionResult
    decision: MinionDefeatDecision

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("defeat acknowledgement requires a non-empty id")
        if not isinstance(self.current, NpcRoundRequest):
            raise TypeError("defeat acknowledgement requires a current NPC round request")
        if not isinstance(self.attack, NpcRosterAttackExecutionResult):
            raise TypeError("defeat acknowledgement requires the full roster Attack result")
        if not isinstance(self.decision, MinionDefeatDecision):
            raise TypeError("defeat acknowledgement requires a typed decision")
        if not self.decision.gm_approved:
            raise ValueError("defeat disposition requires GM approval")
        execution = self.attack.execution
        if (self.decision.attacker_id != execution.actor_id
                or self.decision.target_id != execution.target_id):
            raise ValueError("defeat decision belongs to another attacker/target")
        if execution.request_id in self.current.state.acknowledged_defeat_execution_ids:
            raise ValueError("defeat execution was already acknowledged")
        if self.current.state != self.attack.state or self.current.round_state != execution.state:
            raise ValueError("defeat acknowledgement requires the exact post-Attack roster/history/round")
        changes = tuple(item for item in self.attack.pending_follow_ups if isinstance(item, ProfileStateChangeRequest))
        previous = self.attack.source_request.execution.kernel_request.target_state
        target = self.current.state.roster.participant(execution.target_id).state.injury
        expected = ProfileStateChangeRequest(ProfileNpcType.MINION, previous.wounds, target.wounds, True)
        if not target.defeated or previous.defeated or changes != (expected,):
            raise ValueError("Attack must produce exactly one Minion defeat ProfileStateChange")
        if self.current.pending_follow_ups.count(expected) != 1:
            raise ValueError("current queue requires exactly one matching defeat follow-up")
        # Other queued work may surround this item; never remove it implicitly.
        pending = iter(self.current.pending_follow_ups)
        for item in self.attack.pending_follow_ups:
            if not any(queued == item for queued in pending):
                raise ValueError("current queue omits or reorders source Attack follow-ups")

    @property
    def follow_up(self) -> ProfileStateChangeRequest:
        return next(item for item in self.attack.pending_follow_ups if isinstance(item, ProfileStateChangeRequest))


@dataclass(frozen=True, slots=True)
class MinionDefeatAcknowledgementResult:
    source_request: MinionDefeatAcknowledgementRequest

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, MinionDefeatAcknowledgementRequest):
            raise TypeError("defeat acknowledgement result requires its typed source request")

    @property
    def continuation(self) -> NpcRoundRequest:
        source = self.source_request
        current = source.current
        index = current.pending_follow_ups.index(source.follow_up)
        state = replace(current.state, acknowledged_defeat_execution_ids=(
            *current.state.acknowledged_defeat_execution_ids, source.attack.execution.request_id,
        ))
        return replace(current, state=state,
                       pending_follow_ups=current.pending_follow_ups[:index] + current.pending_follow_ups[index + 1:])

    @property
    def applied_rule_ids(self) -> tuple[str, ...]:
        return ("RULE-NPC-002",)
