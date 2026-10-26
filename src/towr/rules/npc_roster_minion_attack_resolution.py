"""One existing M2 execution, then exact-source pure application (ADR-0037)."""
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_minion_attack_models import NpcRosterMinionAttackRequest, NpcRosterMinionAttackResult
from towr.rules.dice import RandomSource
from towr.rules.kernel import ResolutionDecisionProvider
from towr.rules.npc_roster_attack_execution import execute_npc_roster_attack


def execute_npc_roster_minion_attack(
    request: NpcRosterMinionAttackRequest, rng: RandomSource,
    *, decisions: ResolutionDecisionProvider | None = None,
) -> NpcRosterMinionAttackResult:
    if not isinstance(request, NpcRosterMinionAttackRequest):
        raise TypeError('Minion execution requires NpcRosterMinionAttackRequest')
    return NpcRosterMinionAttackResult(request, execute_npc_roster_attack(request.attack, rng, decisions=decisions))


def apply_npc_roster_minion_attack_result(
    state: NpcRosterCastingState, result: NpcRosterMinionAttackResult,
) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState) or not isinstance(result, NpcRosterMinionAttackResult):
        raise TypeError('Minion handoff application requires typed state and result')
    if result.attack.execution.request_id in state.consumed_execution_ids:
        raise ValueError('action execution has already been consumed')
    if state != result.source.state:
        raise ValueError('Minion handoff belongs to another or stale source state')
    return result.state
