from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum

from towr.domain.npc_attack_selection_models import NpcAttackSelectionRequest, NpcAttackSelectionResult
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult, NpcRosterAttackState
from towr.domain.resolution_models import FollowUpRequest, TargetInjuryPolicy
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlot,
    CombatActionSlotResult, CombatRoundState, CombatTurnEndResult, CombatTurnStartResult, CombatTurnState,
)


class NpcRoundOutcome(str, Enum):
    COMPLETE = "complete"
    PENDING_FOLLOW_UPS = "pending_follow_ups"
    SELECTION_BLOCKED = "selection_blocked"
    DEFEATED_ACTOR = "defeated_actor"


@dataclass(frozen=True, slots=True)
class NpcRoundRequest:
    id: str
    state: NpcRosterAttackState
    round_state: CombatRoundState
    actor_order: tuple[str, ...]
    pending_follow_ups: tuple[FollowUpRequest, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("NPC round request requires a non-empty string id")
        if not isinstance(self.state, NpcRosterAttackState) or not isinstance(self.round_state, CombatRoundState):
            raise TypeError("NPC round requires typed roster and round snapshots")
        order = tuple(self.actor_order)
        if not all(isinstance(actor, str) and actor.strip() for actor in order):
            raise ValueError("actor order requires non-empty string IDs")
        if len(set(order)) != len(order) or set(order) != {p.entity_id for p in self.round_state.participants}:
            raise ValueError("actor order must contain every round participant exactly once")
        for member in self.round_state.participants:
            participant = self.state.roster.participant(member.entity_id)
            if participant.turn_participant != member:
                raise ValueError("round participant side differs from roster")
            if participant.definition.injury_policy is not TargetInjuryPolicy.MINION:
                raise ValueError("NPC round currently supports Minion participants only")
        pending = tuple(self.pending_follow_ups)
        if not all(isinstance(item, FollowUpRequest) for item in pending):
            raise TypeError("pending follow-ups must be typed")
        turn = self.round_state.active_turn
        if turn is not None:
            if len(turn.action_slots) > 1 or any(
                slot.declaration != CombatActionDeclaration(CombatActionKind.ATTACK)
                or slot.grant is not ActionSlotGrant.STANDARD for slot in turn.action_slots
            ):
                raise ValueError("NPC round accepts only one standard Attack slot")
            if turn.action_slots and turn.action_slots[0].executed:
                receipt = turn.action_slots[0].execution
                if (receipt.id not in self.state.consumed_execution_ids
                        or receipt.executor_rule_id != "RULE-COMBAT-004:attack-action-execution"):
                    raise ValueError("executed Attack receipt requires matching consumed roster history")
        object.__setattr__(self, "actor_order", order)
        object.__setattr__(self, "pending_follow_ups", pending)

    def actor_prefix(self, actor_id: str) -> str:
        return f"{self.id}:round:{self.round_state.round_number}:actor:{actor_id}"

    def next_actor(self, round_state: CombatRoundState) -> str | None:
        if round_state.active_turn is not None:
            return round_state.active_turn.actor_id
        return next((actor for actor in self.actor_order
                     if actor not in round_state.completed_turn_entity_ids
                     and round_state.participant_for(actor).side is round_state.next_side), None)

    def selection_context(self, state: NpcRosterAttackState, round_state: CombatRoundState) -> NpcAttackSelectionRequest:
        actor_id = round_state.active_turn.actor_id
        return NpcAttackSelectionRequest(self.actor_prefix(actor_id) + ":selection", state, round_state,
                                        actor_id, 1, (), ())


NpcRoundStep = (CombatTurnStartResult | CombatActionSlotResult | NpcAttackSelectionResult
                | NpcRosterAttackExecutionResult | CombatTurnEndResult)


@dataclass(frozen=True, slots=True)
class NpcRoundResult:
    source_request: NpcRoundRequest
    steps: tuple[NpcRoundStep, ...]
    _state: NpcRosterAttackState = field(init=False, repr=False)
    _round: CombatRoundState = field(init=False, repr=False)
    _pending: tuple[FollowUpRequest, ...] = field(init=False, repr=False)
    _outcome: NpcRoundOutcome = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcRoundRequest):
            raise TypeError("NPC round result requires its source request")
        steps = tuple(self.steps)
        if not all(isinstance(step, NpcRoundStep) for step in steps):
            raise TypeError("NPC round steps must contain typed transition results")
        if len(steps) > 5 * len(self.source_request.round_state.participants):
            raise ValueError("NPC round exceeds its bounded transition count")
        state, combat_round, pending, outcome = _validate_steps(self.source_request, steps)
        object.__setattr__(self, "steps", steps)
        object.__setattr__(self, "_state", state)
        object.__setattr__(self, "_round", combat_round)
        object.__setattr__(self, "_pending", pending)
        object.__setattr__(self, "_outcome", outcome)

    @property
    def state(self) -> NpcRosterAttackState:
        return self._state

    @property
    def round_state(self) -> CombatRoundState:
        return self._round

    @property
    def pending_follow_ups(self) -> tuple[FollowUpRequest, ...]:
        return self._pending

    @property
    def outcome(self) -> NpcRoundOutcome:
        return self._outcome

    @property
    def blocked_selection(self) -> NpcAttackSelectionResult | None:
        if self.outcome is NpcRoundOutcome.SELECTION_BLOCKED:
            return self.steps[-1]
        return None


def _validate_steps(source: NpcRoundRequest, steps: tuple[NpcRoundStep, ...]) -> tuple[
    NpcRosterAttackState, CombatRoundState, tuple[FollowUpRequest, ...], NpcRoundOutcome,
]:
    """Check provenance and state transfer, without executing Tests or rules again."""
    state, combat_round, pending = source.state, source.round_state, source.pending_follow_ups
    selection = None
    for step in steps:
        actor_id = source.next_actor(combat_round)
        if pending or actor_id is None or (selection is not None and selection.execution_request is None):
            raise ValueError("round transitions continue after a required stop")
        if state.roster.participant(actor_id).state.injury.defeated:
            raise ValueError("defeated actor cannot progress a turn")
        prefix = source.actor_prefix(actor_id)
        turn = combat_round.active_turn
        if selection is not None and not isinstance(step, NpcRosterAttackExecutionResult):
            raise ValueError("selected attack must be the next transition")
        if isinstance(step, CombatTurnStartResult):
            expected_turn = CombatTurnState(actor_id, combat_round.participant_for(actor_id).side)
            if (turn is not None or step.request_id != prefix + ":start" or step.turn != expected_turn
                    or step.state != replace(combat_round, active_turn=expected_turn)):
                raise ValueError("turn start differs from source/order")
            combat_round = step.state
        elif isinstance(step, CombatActionSlotResult):
            slot = CombatActionSlot(1, CombatActionDeclaration(CombatActionKind.ATTACK), ActionSlotGrant.STANDARD)
            if (turn is None or turn.action_slots or step.request_id != prefix + ":reserve" or step.slot != slot
                    or step.state != replace(combat_round, active_turn=replace(turn, action_slots=(slot,)))):
                raise ValueError("slot reservation differs from active turn")
            combat_round = step.state
        elif isinstance(step, NpcAttackSelectionResult):
            if turn is None or len(turn.action_slots) != 1 or turn.action_slots[0].executed:
                raise ValueError("selection requires one unexecuted Attack slot")
            if replace(step.source_request, candidates=()) != source.selection_context(state, combat_round):
                raise ValueError("selection does not use the current roster/round context")
            selection = step
        elif isinstance(step, NpcRosterAttackExecutionResult):
            if selection is None or step.source_request != selection.execution_request:
                raise ValueError("execution does not match selected attack")
            state, combat_round, pending = step.state, step.execution.state, step.pending_follow_ups
            selection = None
        elif isinstance(step, CombatTurnEndResult):
            if (turn is None or not turn.action_slots or not turn.action_slots[0].executed
                    or turn.action_slots[0].execution.id not in state.consumed_execution_ids):
                raise ValueError("turn end requires an Attack already applied to roster")
            expected = replace(combat_round, active_turn=None,
                               completed_turn_entity_ids=(*combat_round.completed_turn_entity_ids, actor_id))
            if (step.request_id != prefix + ":end" or step.completed_turn != turn or step.state != expected
                    or step.next_side is not expected.next_side or step.round_complete != expected.round_complete):
                raise ValueError("turn end differs from source/receipt")
            combat_round = step.state
    if pending:
        outcome = NpcRoundOutcome.PENDING_FOLLOW_UPS
    elif combat_round.round_complete:
        outcome = NpcRoundOutcome.COMPLETE
    elif state.roster.participant(source.next_actor(combat_round)).state.injury.defeated:
        outcome = NpcRoundOutcome.DEFEATED_ACTOR
    elif selection is not None and selection.execution_request is None:
        outcome = NpcRoundOutcome.SELECTION_BLOCKED
    else:
        raise ValueError("round result stops before completion or an explicit blocking outcome")
    return state, combat_round, pending, outcome
