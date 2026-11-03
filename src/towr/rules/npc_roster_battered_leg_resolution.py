"""One manual Endurance follow-up in the full M8 owner (ADR-0060)."""
from dataclasses import replace

from towr.domain.npc_roster_battered_leg_models import (
    NpcRosterBatteredLegRequest, NpcRosterBatteredLegResult, _owner,
)
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.rules.battered_leg_resolution import execute_battered_leg_endurance_test
from towr.rules.dice import RandomSource


def execute_npc_roster_battered_leg(request: NpcRosterBatteredLegRequest,
                                    rng: RandomSource) -> NpcRosterBatteredLegResult:
    if not isinstance(request, NpcRosterBatteredLegRequest):
        raise TypeError('Battered Leg requires its full owner request')
    replace(request)
    return NpcRosterBatteredLegResult(request, execute_battered_leg_endurance_test(request.k1_request, rng))


def apply_npc_roster_battered_leg(state: NpcRosterCastingState,
                                result: NpcRosterBatteredLegResult) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState) or not isinstance(result, NpcRosterBatteredLegResult):
        raise TypeError('Battered Leg application requires typed full source and result')
    replace(result)
    _owner(state)
    if state != result.source.state:
        raise ValueError('Battered Leg result belongs to another, stale or already consumed owner')
    return result.state
