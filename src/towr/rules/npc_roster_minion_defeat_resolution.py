"""Close one bound ordinary Minion defeat; no Attack, turn end or RNG."""
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_minion_defeat_models import NpcRosterMinionDefeatRequest, NpcRosterMinionDefeatResult


def acknowledge_npc_roster_minion_defeat(request: NpcRosterMinionDefeatRequest) -> NpcRosterMinionDefeatResult:
    if not isinstance(request, NpcRosterMinionDefeatRequest):
        raise TypeError('defeat acknowledgement requires NpcRosterMinionDefeatRequest')
    return NpcRosterMinionDefeatResult(request)


def apply_npc_roster_minion_defeat_result(
    state: NpcRosterCastingState, result: NpcRosterMinionDefeatResult,
) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState) or not isinstance(result, NpcRosterMinionDefeatResult):
        raise TypeError('defeat application requires typed full state and result')
    identifier = result.source.state.pending_minion_attack.execution.request_id
    if state.minion_attack is not None and identifier in state.minion_attack.acknowledged_defeat_execution_ids:
        raise ValueError('Minion defeat execution was already acknowledged')
    if state != result.source.state:
        raise ValueError('defeat acknowledgement belongs to another or stale full source state')
    return result.state
