"""A narrow Broken movement/Recover transition with existing K1 reducers."""
from towr.domain.action_execution_models import SkippedCastingTestAfterActionRequest
from towr.domain.npc_broken_recover_models import NpcBrokenRecoverRequest, NpcBrokenRecoverResult
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.rules.casting_interruption_resolution import resolve_skipped_casting_test_after_action
from towr.rules.dice import RandomSource
from towr.rules.free_movement_resolution import resolve_free_movement
from towr.rules.recover_resolution import execute_recover_action


def execute_npc_broken_recover(request: NpcBrokenRecoverRequest, rng: RandomSource) -> NpcBrokenRecoverResult:
    if not isinstance(request, NpcBrokenRecoverRequest):
        raise TypeError('request must be an NpcBrokenRecoverRequest')
    movement = None if request.movement is None else resolve_free_movement(request.movement)
    recover = execute_recover_action(request.recover_request, rng)
    wizard = request.state.wizard
    interruption = None
    if request.actor_id == wizard.actor_id and wizard.magic_state.casting_lore_id is not None:
        interruption = resolve_skipped_casting_test_after_action(SkippedCastingTestAfterActionRequest(
            request.id + ':skipped-casting', wizard.actor_id, recover.slot.execution,
            wizard.magic_state, wizard.caster.wizard_level, request.state.consumed_execution_ids,
        ))
    return NpcBrokenRecoverResult(request, movement, recover, interruption)


def apply_npc_broken_recover_result(state: NpcRosterCastingState, result: NpcBrokenRecoverResult) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState) or not isinstance(result, NpcBrokenRecoverResult):
        raise TypeError('Broken recovery application requires typed state and result')
    if result.source.id in state.consumed_execution_ids:
        raise ValueError('Broken recovery action was already consumed')
    if state != result.source.state:
        raise ValueError('Broken recovery uses a stale complete source state')
    return result.state
