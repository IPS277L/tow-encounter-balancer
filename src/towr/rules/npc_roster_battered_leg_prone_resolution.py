"""One free self-stand, preserving the full Battered Leg owner and Test proof."""
from dataclasses import replace

from towr.domain.npc_roster_battered_leg_models import _owner
from towr.domain.npc_roster_battered_leg_prone_models import (
    NpcRosterBatteredLegProneStandRequest, NpcRosterBatteredLegProneStandResult,
)
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.rules.free_movement_resolution import resolve_free_move_prone_removal


def stand_npc_roster_battered_leg_prone(
    request: NpcRosterBatteredLegProneStandRequest,
) -> NpcRosterBatteredLegProneStandResult:
    if not isinstance(request, NpcRosterBatteredLegProneStandRequest):
        raise TypeError('Battered Leg self-stand requires its typed full request')
    replace(request)
    return NpcRosterBatteredLegProneStandResult(request, resolve_free_move_prone_removal(request.stand_request))


def apply_npc_roster_battered_leg_prone_stand(
    state: NpcRosterCastingState, result: NpcRosterBatteredLegProneStandResult,
) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState) or not isinstance(result, NpcRosterBatteredLegProneStandResult):
        raise TypeError('Battered Leg self-stand application requires typed owner and result')
    replace(result)
    _owner(state)
    if state != result.source.state:
        raise ValueError('Battered Leg self-stand belongs to another, stale or already consumed owner')
    return result.state
