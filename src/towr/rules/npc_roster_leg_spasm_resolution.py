"""Explicit Leg Spasm self-stand; one existing K1 call, no RNG or action."""
from dataclasses import replace

from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandRequest, NpcRosterLegSpasmStandResult
from towr.rules.free_movement_resolution import resolve_free_move_prone_removal


def stand_npc_roster_leg_spasm(request: NpcRosterLegSpasmStandRequest) -> NpcRosterLegSpasmStandResult:
    if not isinstance(request, NpcRosterLegSpasmStandRequest):
        raise TypeError('Leg Spasm stand requires NpcRosterLegSpasmStandRequest')
    replace(request)  # Validate the complete source before executing the primitive.
    return NpcRosterLegSpasmStandResult(request, resolve_free_move_prone_removal(request.stand_request))


def apply_npc_roster_leg_spasm_stand(
    state: NpcRosterCastingState, result: NpcRosterLegSpasmStandResult,
) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState) or not isinstance(result, NpcRosterLegSpasmStandResult):
        raise TypeError('Leg Spasm application requires typed full state and result')
    if state != result.source.state:
        raise ValueError('Leg Spasm stand belongs to another, already applied or stale full source state')
    return result.state
