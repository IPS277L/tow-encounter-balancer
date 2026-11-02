"""Apply an existing Champion attack while preserving bound magic/spatial."""
from dataclasses import replace
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult


def apply_npc_roster_champion_attack_result(
    state: NpcRosterCastingState, result: NpcRosterChampionAttackResult,
) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState) or not isinstance(result, NpcRosterChampionAttackResult):
        raise TypeError('handoff application requires typed state and result')
    if (result.source.crushed_rib_context is not None
            or result.source.attack.crushed_rib_preparation is not None
            or result.source.attack.crushed_rib_consumption is not None
            or result.attack.crushed_rib is not None):
        replace(result.source)
        if result.source.crushed_rib_context is not None:
            result.source.crushed_rib_context.validate_source(state, result.attack.execution.target_id)
        replace(result)
    if result.attack.execution.request_id in state.consumed_execution_ids:
        raise ValueError('action execution has already been consumed')
    if state != result.source.state:
        raise ValueError('Champion handoff belongs to another or stale source state')
    return result.state
