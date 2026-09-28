from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum

from towr.domain.npc_round_request_models import NpcRoundRequest
from towr.domain.npc_round_weapon_models import NpcRoundWeaponState
from towr.domain.npc_blunderbuss_models import NpcBlunderbussAttackExecutionResult
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


NpcRoundStep = (CombatTurnStartResult | CombatActionSlotResult | NpcAttackSelectionResult
                | NpcRosterAttackExecutionResult | NpcBlunderbussAttackExecutionResult | CombatTurnEndResult)


@dataclass(frozen=True, slots=True)
class NpcRoundResult:
    source_request: NpcRoundRequest
    steps: tuple[NpcRoundStep, ...]
    _state: NpcRosterAttackState = field(init=False, repr=False)
    _round: CombatRoundState = field(init=False, repr=False)
    _pending: tuple[FollowUpRequest, ...] = field(init=False, repr=False)
    _outcome: NpcRoundOutcome = field(init=False, repr=False)
    _weapons: tuple[NpcRoundWeaponState, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcRoundRequest):
            raise TypeError("NPC round result requires its source request")
        steps = tuple(self.steps)
        if not all(isinstance(step, NpcRoundStep) for step in steps):
            raise TypeError("NPC round steps must contain typed transition results")
        if len(steps) > 5 * len(self.source_request.round_state.participants):
            raise ValueError("NPC round exceeds its bounded transition count")
        state, combat_round, pending, outcome, weapons = _validate_steps(self.source_request, steps)
        object.__setattr__(self, "steps", steps)
        object.__setattr__(self, "_state", state)
        object.__setattr__(self, "_round", combat_round)
        object.__setattr__(self, "_pending", pending)
        object.__setattr__(self, "_outcome", outcome)
        object.__setattr__(self, "_weapons", weapons)

    @property
    def weapons(self) -> tuple[NpcRoundWeaponState, ...]:
        return self._weapons

    @property
    def continuation(self) -> NpcRoundRequest:
        return replace(self.source_request, state=self.state, round_state=self.round_state,
                       pending_follow_ups=self.pending_follow_ups, weapons=self.weapons)

    @property
    def executed_attack_count(self) -> int:
        return sum(isinstance(step, (NpcRosterAttackExecutionResult, NpcBlunderbussAttackExecutionResult)) for step in self.steps)

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
    NpcRosterAttackState, CombatRoundState, tuple[FollowUpRequest, ...], NpcRoundOutcome, tuple[NpcRoundWeaponState, ...],
]:
    """Check provenance and state transfer, without executing Tests or rules again."""
    state, combat_round, pending = source.state, source.round_state, source.pending_follow_ups
    weapons = source.weapons
    selection = None
    for step in steps:
        actor_id = source.next_actor(combat_round)
        if pending or actor_id is None or (selection is not None and selection.execution_request is None):
            raise ValueError("round transitions continue after a required stop")
        if state.roster.participant(actor_id).state.injury.defeated:
            raise ValueError("defeated actor cannot progress a turn")
        prefix = source.actor_prefix(actor_id)
        turn = combat_round.active_turn
        if selection is not None and not isinstance(step, (NpcRosterAttackExecutionResult, NpcBlunderbussAttackExecutionResult)):
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
            if replace(step.source_request, candidates=()) != replace(source, weapons=weapons).selection_context(state, combat_round):
                raise ValueError("selection does not use the current roster/round context")
            selection = step
        elif isinstance(step, NpcBlunderbussAttackExecutionResult):
            if selection is None or step.source_request != selection.execution_request:
                raise ValueError("Blunderbuss execution does not match selected attack")
            current = replace(source, state=state, round_state=combat_round, pending_follow_ups=pending, weapons=weapons)
            if step.source_request.current != current:
                raise ValueError("Blunderbuss journal uses stale round/weapon context")
            continuation = step.continuation
            state, combat_round, pending, weapons = (continuation.state, continuation.round_state,
                                                    continuation.pending_follow_ups, continuation.weapons)
            selection = None
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
    return state, combat_round, pending, outcome, weapons
