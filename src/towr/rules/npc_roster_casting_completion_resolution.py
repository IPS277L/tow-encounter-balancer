"""Apply one source-bound Curse completion without movement, Tests or RNG."""
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_casting_completion_models import NpcRosterCastingCompletionResult


def apply_npc_roster_casting_completion(
    state: NpcRosterCastingState, result: NpcRosterCastingCompletionResult,
) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState):
        raise TypeError("state must be an NpcRosterCastingState")
    if not isinstance(result, NpcRosterCastingCompletionResult):
        raise TypeError("result must be an NpcRosterCastingCompletionResult")
    if state.pending_movement is None:
        raise ValueError("movement completion was already consumed or is not pending")
    if state != result.source.state:
        raise ValueError("roster completion belongs to another or stale source state")
    return result.state
