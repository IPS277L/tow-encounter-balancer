from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from towr.domain.npc_blunderbuss_models import NpcBlunderbussAttackExecutionRequest
from towr.rules.npc_blunderbuss_resolution import execute_npc_blunderbuss_attack, apply_npc_blunderbuss_attack
from towr.domain.npc_attack_selection_models import NpcAttackSelectionRequest
from towr.domain.npc_round_models import NpcRoundRequest, NpcRoundResult, NpcRoundStep
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatTurnEndRequest, CombatTurnStartRequest,
)
from towr.engine.npc_attack_controller import require_current_npc_attack_selection, select_npc_attack
from towr.rules.dice import RandomSource
from towr.rules.kernel import ResolutionDecisionProvider
from towr.rules.npc_roster_attack_execution import apply_npc_roster_attack_result, execute_npc_roster_attack
from towr.rules.turn_resolution import end_combat_turn, reserve_combat_action_slot, start_combat_turn


class NpcRoundCandidateProvider(Protocol):
    def get_candidates(self, context: NpcAttackSelectionRequest) -> NpcAttackSelectionRequest:
        """Return this exact fresh context with only its ordered candidates replaced."""
        ...


def run_npc_round(
    request: NpcRoundRequest, candidates: NpcRoundCandidateProvider, rng: RandomSource,
    *, decisions: ResolutionDecisionProvider | None = None,
) -> NpcRoundResult:
    """Run the remainder of one Minion round, or return a resumable explicit stop."""
    if not isinstance(request, NpcRoundRequest):
        raise TypeError("request must be an NpcRoundRequest")
    state, combat_round, pending = request.state, request.round_state, request.pending_follow_ups
    weapons = request.weapons
    steps: list[NpcRoundStep] = []
    # Each iteration closes at most one turn. There is no next-round/battle loop.
    for _ in range(len(combat_round.participants) + 1):
        if pending or combat_round.round_complete:
            return NpcRoundResult(request, tuple(steps))
        actor_id = request.next_actor(combat_round)
        if state.roster.participant(actor_id).state.injury.defeated:
            return NpcRoundResult(request, tuple(steps))
        prefix = request.actor_prefix(actor_id)
        if combat_round.active_turn is None:
            started = start_combat_turn(CombatTurnStartRequest(prefix + ":start", combat_round, actor_id))
            steps.append(started)
            combat_round = started.state
        if not combat_round.active_turn.action_slots:
            reserved = reserve_combat_action_slot(CombatActionSlotRequest(
                prefix + ":reserve", combat_round, actor_id, CombatActionDeclaration(CombatActionKind.ATTACK),
                ActionSlotGrant.STANDARD,
            ))
            steps.append(reserved)
            combat_round = reserved.state
        slot = combat_round.active_turn.action_slots[0]
        if not slot.executed:
            current = replace(request, state=state, round_state=combat_round, pending_follow_ups=pending, weapons=weapons)
            context = current.selection_context(state, combat_round)
            supplied = candidates.get_candidates(context)
            if not isinstance(supplied, NpcAttackSelectionRequest):
                raise TypeError("candidate provider must return an NpcAttackSelectionRequest")
            if replace(supplied, candidates=()) != context:
                raise ValueError("candidate provider changed the current roster/round/actor context")
            selected = select_npc_attack(supplied)
            steps.append(selected)
            if selected.execution_request is None:
                return NpcRoundResult(request, tuple(steps))
            executable = require_current_npc_attack_selection(selected, state, combat_round,
                pending_follow_ups=pending, round_context=current)
            if isinstance(executable, NpcBlunderbussAttackExecutionRequest):
                attack = execute_npc_blunderbuss_attack(executable, rng, decisions=decisions)
                current, _ = apply_npc_blunderbuss_attack(current, executable.weapon_state, attack)
                state, combat_round, pending, weapons = current.state, current.round_state, current.pending_follow_ups, current.weapons
            else:
                attack = execute_npc_roster_attack(executable, rng, decisions=decisions)
                state = apply_npc_roster_attack_result(state, attack)
                combat_round, pending = attack.execution.state, attack.pending_follow_ups
            steps.append(attack)
            if pending:
                return NpcRoundResult(request, tuple(steps))
        ended = end_combat_turn(CombatTurnEndRequest(prefix + ":end", combat_round, actor_id))
        steps.append(ended)
        combat_round = ended.state
    raise AssertionError("bounded NPC round failed to close or stop")
