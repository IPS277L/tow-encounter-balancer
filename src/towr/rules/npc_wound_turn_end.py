"""Complete one admitted turn and expire its registered Stomach Blow effects."""
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest, NpcWoundTurnEndResult
from towr.domain.turn_models import CombatTurnEndRequest
from towr.rules.turn_resolution import end_combat_turn


def end_npc_wound_turn(request: NpcWoundTurnEndRequest) -> NpcWoundTurnEndResult:
    if not isinstance(request, NpcWoundTurnEndRequest):
        raise TypeError('turn end requires NpcWoundTurnEndRequest')
    return NpcWoundTurnEndResult(request, end_combat_turn(
        CombatTurnEndRequest(request.id, request.state.round_state, request.actor_id)))


def apply_npc_wound_turn_end_result(
    state: NpcRosterCastingState, result: NpcWoundTurnEndResult,
) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState) or not isinstance(result, NpcWoundTurnEndResult):
        raise TypeError('turn end application requires typed state and result')
    if any(r.id == result.source.id or (r.actor_id, r.round_number) == (
            result.source.actor_id, result.source.state.round_state.round_number)
           for r in state.wound_turn_end_receipts):
        raise ValueError('turn end was already consumed')
    if state != result.source.state:
        raise ValueError('turn end belongs to another or stale source state')
    return result.state
