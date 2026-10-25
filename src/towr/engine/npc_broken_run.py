"""One deterministic free-move/Run transition; no Recover or end-turn."""
from towr.domain.action_execution_models import SkippedCastingTestAfterActionRequest
from towr.domain.npc_broken_run_models import NpcBrokenRunRequest, NpcBrokenRunResult
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.rules.casting_interruption_resolution import resolve_skipped_casting_test_after_action
from towr.rules.free_movement_resolution import resolve_free_movement
from towr.rules.run_action_execution import execute_run_action


def execute_npc_broken_run(request: NpcBrokenRunRequest) -> NpcBrokenRunResult:
    if not isinstance(request, NpcBrokenRunRequest):
        raise TypeError('request must be an NpcBrokenRunRequest')
    movement = resolve_free_movement(request.movement)
    run = execute_run_action(request.run_request)
    wizard = request.state.wizard
    interruption = None
    if request.actor_id == wizard.actor_id and wizard.magic_state.casting_lore_id is not None:
        interruption = resolve_skipped_casting_test_after_action(SkippedCastingTestAfterActionRequest(
            request.id + ':skipped-casting', wizard.actor_id, run.slot.execution,
            wizard.magic_state, wizard.caster.wizard_level, request.state.consumed_execution_ids,
        ))
    return NpcBrokenRunResult(request, movement, run, interruption)


def apply_npc_broken_run_result(state: NpcRosterCastingState, result: NpcBrokenRunResult) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState) or not isinstance(result, NpcBrokenRunResult):
        raise TypeError('Broken Run application requires typed state and result')
    if result.source.id in state.consumed_execution_ids:
        raise ValueError('Broken Run action was already consumed')
    if state != result.source.state:
        raise ValueError('Broken Run uses a stale complete source state')
    return result.state
