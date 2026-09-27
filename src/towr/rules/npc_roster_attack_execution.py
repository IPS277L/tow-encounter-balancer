from __future__ import annotations

from towr.domain.npc_roster_attack_models import (
    NpcRosterAttackExecutionRequest, NpcRosterAttackExecutionResult,
    NpcRosterAttackState, validate_npc_roster_attack,
)
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.dice import RandomSource
from towr.rules.kernel import ResolutionDecisionProvider


def execute_npc_roster_attack(
    request: NpcRosterAttackExecutionRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> NpcRosterAttackExecutionResult:
    """Bind one prepared Minion attack to a roster and the existing reserved slot."""
    if not isinstance(request, NpcRosterAttackExecutionRequest):
        raise TypeError("request must be an NpcRosterAttackExecutionRequest")
    validate_npc_roster_attack(request)
    execution = execute_attack_action(request.execution, rng, decisions=decisions)
    return NpcRosterAttackExecutionResult(request, request.execution, execution)


def apply_npc_roster_attack_result(
    state: NpcRosterAttackState,
    result: NpcRosterAttackExecutionResult,
) -> NpcRosterAttackState:
    """Accept against the exact current snapshot; caller also keeps execution.state."""
    if not isinstance(state, NpcRosterAttackState):
        raise TypeError("state must be an NpcRosterAttackState")
    if not isinstance(result, NpcRosterAttackExecutionResult):
        raise TypeError("result must be an NpcRosterAttackExecutionResult")
    if result.execution.request_id in state.consumed_execution_ids:
        raise ValueError("NPC roster attack execution was already consumed")
    if state != result.source_request.state:
        raise ValueError("NPC roster attack result uses a stale source snapshot/history")
    return result.state
