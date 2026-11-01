"""One K1 self-stand and exact-source application for ADR-0052; no RNG."""
from dataclasses import replace

from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_repeated_leg_spasm_models import (
    NpcRosterRepeatedLegSpasmStandRequest, NpcRosterRepeatedLegSpasmStandResult, _owner,
)
from towr.rules.free_movement_resolution import resolve_free_move_prone_removal


def stand_npc_roster_repeated_leg_spasm(
    request: NpcRosterRepeatedLegSpasmStandRequest,
) -> NpcRosterRepeatedLegSpasmStandResult:
    if not isinstance(request, NpcRosterRepeatedLegSpasmStandRequest):
        raise TypeError('repeated stand requires NpcRosterRepeatedLegSpasmStandRequest')
    replace(request)
    return NpcRosterRepeatedLegSpasmStandResult(request, resolve_free_move_prone_removal(request.stand_request))


def apply_npc_roster_repeated_leg_spasm_stand(
    state: NpcRosterCastingState, result: NpcRosterRepeatedLegSpasmStandResult,
) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState) or not isinstance(result, NpcRosterRepeatedLegSpasmStandResult):
        raise TypeError('repeated stand application requires typed state and result')
    _owner(state)
    replace(result)
    if state != result.source.state:
        raise ValueError('repeated stand belongs to another, already applied or stale full source')
    return result.state
