from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum

from towr.domain.injury_models import ProfileNpcType, ProfileStateChangeRequest
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult, NpcRosterAttackState
from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.resolution_models import FollowUpRequest
from towr.domain.turn_models import CombatRoundState


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


def validate_minion_defeat_context(
    state: NpcRosterAttackState, round_state: CombatRoundState,
    attack: NpcRosterAttackExecutionResult, decision: MinionDefeatDecision,
    pending_follow_ups: tuple[FollowUpRequest, ...],
) -> ProfileStateChangeRequest:
    """Shared M2/M8 provenance checks without a Minion-only round wrapper."""
    if not isinstance(state, NpcRosterAttackState) or not isinstance(round_state, CombatRoundState):
        raise TypeError("defeat context requires typed roster and round state")
    if not isinstance(attack, NpcRosterAttackExecutionResult):
        raise TypeError("defeat acknowledgement requires the full roster Attack result")
    if not isinstance(decision, MinionDefeatDecision):
        raise TypeError("defeat acknowledgement requires a typed decision")
    if not decision.gm_approved:
        raise ValueError("defeat disposition requires GM approval")
    execution = attack.execution
    if (decision.attacker_id != execution.actor_id
            or decision.target_id != execution.target_id):
        raise ValueError("defeat decision belongs to another attacker/target")
    if execution.request_id in state.acknowledged_defeat_execution_ids:
        raise ValueError("defeat execution was already acknowledged")
    if state != attack.state or round_state != execution.state:
        raise ValueError("defeat acknowledgement requires the exact post-Attack roster/history/round")
    changes = tuple(item for item in attack.pending_follow_ups if isinstance(item, ProfileStateChangeRequest))
    previous = attack.source_request.execution.kernel_request.target_state
    target = state.roster.participant(execution.target_id).state.injury
    expected = ProfileStateChangeRequest(ProfileNpcType.MINION, previous.wounds, target.wounds, True)
    if not target.defeated or previous.defeated or changes != (expected,):
        raise ValueError("Attack must produce exactly one Minion defeat ProfileStateChange")
    if pending_follow_ups.count(expected) != 1:
        raise ValueError("current queue requires exactly one matching defeat follow-up")
    # Other queued work may surround this item; never remove it implicitly.
    pending = iter(pending_follow_ups)
    for item in attack.pending_follow_ups:
        if not any(queued == item for queued in pending):
            raise ValueError("current queue omits or reorders source Attack follow-ups")
    return expected


def acknowledged_minion_defeat_state(state: NpcRosterAttackState, execution_id: str) -> NpcRosterAttackState:
    """Project an already validated acknowledgement without changing injury."""
    return replace(state, acknowledged_defeat_execution_ids=(
        *state.acknowledged_defeat_execution_ids, execution_id,
    ))


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
        validate_minion_defeat_context(self.current.state, self.current.round_state,
                                      self.attack, self.decision, self.current.pending_follow_ups)

    @property
    def follow_up(self) -> ProfileStateChangeRequest:
        return next(item for item in self.attack.pending_follow_ups if isinstance(item, ProfileStateChangeRequest))


@dataclass(frozen=True, slots=True)
class MinionDefeatAcknowledgementResult:
    source_request: MinionDefeatAcknowledgementRequest
    _continuation: NpcRoundRequest = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, MinionDefeatAcknowledgementRequest):
            raise TypeError("defeat acknowledgement result requires its typed source request")
        object.__setattr__(self, "_continuation", self._build_continuation())

    @property
    def continuation(self) -> NpcRoundRequest:
        return self._continuation

    def _build_continuation(self) -> NpcRoundRequest:
        """Project the validated immutable source once, without replaying defeat."""
        source = self.source_request
        current = source.current
        index = current.pending_follow_ups.index(source.follow_up)
        state = acknowledged_minion_defeat_state(current.state, source.attack.execution.request_id)
        return replace(current, state=state,
                       pending_follow_ups=current.pending_follow_ups[:index] + current.pending_follow_ups[index + 1:])

    @property
    def applied_rule_ids(self) -> tuple[str, ...]:
        return ("RULE-NPC-002",)
