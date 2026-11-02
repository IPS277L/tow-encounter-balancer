"""Ordinary Minion -> Champion Attack, completion and pure roster application."""
from dataclasses import replace

from towr.domain.npc_champion_attack_models import (
    NpcChampionAttackRequest, NpcChampionAttackResult, NpcChampionAttackState,
)
from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleCompletionRequest
from towr.rules.attack_action_execution import (
    execute_attack_action, _validate_attack_action_slot, _complete_attack_action,
)
from towr.rules.attack_resolution import resolve_attack
from towr.rules.crushed_rib_test_resolution import complete_crushed_rib_test
from towr.rules.dice import RandomSource
from towr.rules.kernel import (
    ResolutionDecisionProvider, apply_kernel_character_wound_completion,
    _resolve_kernel_attack_after_test,
)
from towr.rules.wound_lifecycle_resolution import complete_character_wound_lifecycle


def execute_npc_champion_attack(
    request: NpcChampionAttackRequest, rng: RandomSource, *,
    decisions: ResolutionDecisionProvider | None = None,
) -> NpcChampionAttackResult:
    if not isinstance(request, NpcChampionAttackRequest):
        raise TypeError('request must be an NpcChampionAttackRequest')
    crushed = None
    if request.crushed_rib_preparation is not None or request.crushed_rib_consumption is not None:
        # Re-admit the original transported source before any Attack RNG.
        replace(request)
    if request.crushed_rib_preparation is None:
        execution = execute_attack_action(request.execution, rng, decisions=decisions)
    else:
        _validate_attack_action_slot(request.execution)
        attack = resolve_attack(request.effective_attack, rng, decisions=decisions)
        crushed = complete_crushed_rib_test(request.crushed_rib_preparation, attack.defender_test)
        post_test = replace(request.execution.kernel_request, attack=request.effective_attack,
                            target_state=crushed.state)
        raw = _resolve_kernel_attack_after_test(post_test, attack, rng, decisions=decisions)
        execution = _complete_attack_action(request.execution, raw)
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
    return NpcChampionAttackResult(request, execution, resolution, completion, crushed_rib=crushed)


def apply_npc_champion_attack_result(
    state: NpcChampionAttackState, result: NpcChampionAttackResult,
) -> NpcChampionAttackState:
    if not isinstance(state, NpcChampionAttackState) or not isinstance(result, NpcChampionAttackResult):
        raise TypeError('Champion application requires typed state and result')
    if result.source.crushed_rib_preparation is not None or result.source.crushed_rib_consumption is not None:
        replace(result)
        # Validate current injury's strict source shape as well as full equality.
        from towr.domain.crushed_rib_test_models import _injury
        _injury(state.roster.participant(result.execution.target_id).state.injury,
                pending=result.source.crushed_rib_preparation is not None)
    if result.execution.request_id in state.consumed_execution_ids:
        raise ValueError('Champion attack execution was already consumed')
    if state != result.source.state:
        raise ValueError('Champion attack result belongs to another or stale source state')
    return result.state
