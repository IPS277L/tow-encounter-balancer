"""One K1 start/slot or round/spatial advance; pure full-source application."""
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_turn_models import (
    NpcRosterTurnStartRequest, NpcRosterTurnStartResult, NpcRosterRoundAdvanceRequest, NpcRosterRoundAdvanceResult,
)
from towr.domain.turn_models import (
    ActionSlotGrant, CombatTurnStartRequest, CombatActionSlotRequest, CombatRoundAdvanceRequest,
)
from towr.rules.spatial_resolution import start_next_spatial_round
from towr.rules.turn_resolution import start_combat_turn, reserve_combat_action_slot, advance_combat_round


def start_npc_roster_turn(request: NpcRosterTurnStartRequest) -> NpcRosterTurnStartResult:
    if not isinstance(request, NpcRosterTurnStartRequest):
        raise TypeError('turn start requires NpcRosterTurnStartRequest')
    started = start_combat_turn(CombatTurnStartRequest(request.id + ':start', request.state.round_state, request.actor_id))
    slot = reserve_combat_action_slot(CombatActionSlotRequest(request.id + ':slot', started.state,
        request.actor_id, request.declaration, ActionSlotGrant.STANDARD))
    return NpcRosterTurnStartResult(request, started, slot)


def advance_npc_roster_round(request: NpcRosterRoundAdvanceRequest) -> NpcRosterRoundAdvanceResult:
    if not isinstance(request, NpcRosterRoundAdvanceRequest):
        raise TypeError('round advance requires NpcRosterRoundAdvanceRequest')
    combat = advance_combat_round(CombatRoundAdvanceRequest(request.id, request.state.round_state,
                                                           request.state.roster.turn_participants))
    spatial = start_next_spatial_round(request.state.spatial_state)
    return NpcRosterRoundAdvanceResult(request, combat, spatial)


def apply_npc_roster_turn_start_result(state: NpcRosterCastingState, result: NpcRosterTurnStartResult) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState) or not isinstance(result, NpcRosterTurnStartResult):
        raise TypeError('turn application requires typed current state and result')
    if state != result.source.state:
        raise ValueError('turn start belongs to another or stale full source state')
    return result.state


def apply_npc_roster_round_advance_result(state: NpcRosterCastingState, result: NpcRosterRoundAdvanceResult) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState) or not isinstance(result, NpcRosterRoundAdvanceResult):
        raise TypeError('advance application requires typed current state and result')
    if state != result.source.state:
        raise ValueError('round advance belongs to another or stale full source state')
    return result.state
