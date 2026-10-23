"""Ordinary Minion -> Champion Attack, completion and pure roster application."""
from towr.domain.npc_champion_attack_models import (
    NpcChampionAttackRequest, NpcChampionAttackResult, NpcChampionAttackState,
)
from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleCompletionRequest
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.dice import RandomSource
from towr.rules.kernel import ResolutionDecisionProvider, apply_kernel_character_wound_completion
from towr.rules.wound_lifecycle_resolution import complete_character_wound_lifecycle


def execute_npc_champion_attack(
    request: NpcChampionAttackRequest, rng: RandomSource, *,
    decisions: ResolutionDecisionProvider | None = None,
) -> NpcChampionAttackResult:
    if not isinstance(request, NpcChampionAttackRequest):
        raise TypeError('request must be an NpcChampionAttackRequest')
    execution = execute_attack_action(request.execution, rng, decisions=decisions)
    resolution = execution.resolution
    completion = None
    if resolution.pending_character_wound is not None:
        completion = complete_character_wound_lifecycle(CharacterWoundLifecycleCompletionRequest(
            id=request.execution.id + ':complete-wound', roll=resolution.pending_character_wound,
            current_state=resolution.target_state, daily_wounds=request.state.daily_wounds,
            daily_registration_id=request.execution.id + ':daily-wound',
            consumed_roll_ids=request.state.consumed_wound_roll_ids,
        ))
        resolution = apply_kernel_character_wound_completion(resolution, completion)
    return NpcChampionAttackResult(request, execution, resolution, completion)


def apply_npc_champion_attack_result(
    state: NpcChampionAttackState, result: NpcChampionAttackResult,
) -> NpcChampionAttackState:
    if not isinstance(state, NpcChampionAttackState) or not isinstance(result, NpcChampionAttackResult):
        raise TypeError('Champion application requires typed state and result')
    if result.execution.request_id in state.consumed_execution_ids:
        raise ValueError('Champion attack execution was already consumed')
    if state != result.source.state:
        raise ValueError('Champion attack result belongs to another or stale source state')
    return result.state
