"""Bound self-stand and scoped end-turn: no new action execution or RNG."""
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_prone_models import (
    NpcRosterProneStandRequest, NpcRosterProneStandResult,
    NpcRosterProneTurnEndRequest, NpcRosterProneTurnEndResult,
)
from towr.domain.turn_models import CombatTurnEndRequest
from towr.rules.free_movement_resolution import resolve_free_move_prone_removal
from towr.rules.turn_resolution import end_combat_turn


def stand_npc_roster_prone(request: NpcRosterProneStandRequest) -> NpcRosterProneStandResult:
    if not isinstance(request, NpcRosterProneStandRequest):
        raise TypeError('self-stand requires NpcRosterProneStandRequest')
    return NpcRosterProneStandResult(request, resolve_free_move_prone_removal(request.stand_request))


def apply_npc_roster_prone_stand(
    state: NpcRosterCastingState, result: NpcRosterProneStandResult,
) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState) or not isinstance(result, NpcRosterProneStandResult):
        raise TypeError('self-stand application requires typed full state and result')
    if state != result.source.state:
        raise ValueError('self-stand belongs to another, already applied or stale full source state')
    return result.state


def end_npc_roster_prone_turn(request: NpcRosterProneTurnEndRequest) -> NpcRosterProneTurnEndResult:
    if not isinstance(request, NpcRosterProneTurnEndRequest):
        raise TypeError('Prone turn end requires NpcRosterProneTurnEndRequest')
    return NpcRosterProneTurnEndResult(request, end_combat_turn(
        CombatTurnEndRequest(request.id, request.state.round_state, request.actor_id)))


def apply_npc_roster_prone_turn_end(
    state: NpcRosterCastingState, result: NpcRosterProneTurnEndResult,
) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState) or not isinstance(result, NpcRosterProneTurnEndResult):
        raise TypeError('Prone turn end application requires typed full state and result')
    if any(r.id == result.source.id or (r.actor_id, r.round_number) == (
            result.source.actor_id, result.source.state.round_state.round_number)
            for r in state.wound_turn_end_receipts):
        raise ValueError('Prone turn end was already consumed')
    if state != result.source.state:
        raise ValueError('Prone turn end belongs to another or stale full source state')
    return result.state
