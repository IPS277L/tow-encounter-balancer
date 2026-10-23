"""Apply an existing Champion attack while preserving bound magic/spatial."""
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult


def apply_npc_roster_champion_attack_result(
    state: NpcRosterCastingState, result: NpcRosterChampionAttackResult,
) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState) or not isinstance(result, NpcRosterChampionAttackResult):
        raise TypeError('handoff application requires typed state and result')
    if result.attack.execution.request_id in state.consumed_execution_ids:
        raise ValueError('action execution has already been consumed')
    if state != result.source.state:
        raise ValueError('Champion handoff belongs to another or stale source state')
    return result.state
