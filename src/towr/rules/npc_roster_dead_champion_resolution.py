"""Current-round death exclusion only; no Attack, Wound, turn end or RNG."""
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_dead_champion_models import (
    NpcRosterDeadChampionExclusionRequest, NpcRosterDeadChampionExclusionResult,
)


def exclude_npc_roster_dead_champion(
    request: NpcRosterDeadChampionExclusionRequest,
) -> NpcRosterDeadChampionExclusionResult:
    if not isinstance(request, NpcRosterDeadChampionExclusionRequest):
        raise TypeError('dead Champion exclusion requires NpcRosterDeadChampionExclusionRequest')
    return NpcRosterDeadChampionExclusionResult(request)


def apply_npc_roster_dead_champion_exclusion(
    state: NpcRosterCastingState, result: NpcRosterDeadChampionExclusionResult,
) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState) or not isinstance(result, NpcRosterDeadChampionExclusionResult):
        raise TypeError('dead Champion exclusion application requires typed full state and result')
    if state != result.source.state:
        raise ValueError('dead Champion exclusion belongs to another, already applied or stale full source state')
    return result.state
