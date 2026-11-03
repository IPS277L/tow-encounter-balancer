"""Standard Recover, then one skipped-Casting contribution when owed."""
from dataclasses import replace

from towr.domain.action_execution_models import SkippedCastingTestAfterActionRequest
from towr.domain.npc_roster_battered_leg_models import _owner
from towr.domain.npc_roster_battered_leg_recover_models import (
    NpcRosterBatteredLegRecoverRequest, NpcRosterBatteredLegRecoverResult,
)
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.rules.casting_interruption_resolution import resolve_skipped_casting_test_after_action
from towr.rules.dice import RandomSource
from towr.rules.recover_resolution import execute_recover_action


def execute_npc_roster_battered_leg_recover(request: NpcRosterBatteredLegRecoverRequest,
                                           rng: RandomSource) -> NpcRosterBatteredLegRecoverResult:
    if not isinstance(request, NpcRosterBatteredLegRecoverRequest):
        raise TypeError('Battered Leg Recover requires its typed full request')
    replace(request)
    recover = execute_recover_action(request.recover_request, rng)
    magic = recover.resolution.magic_state
    interruption = None
    if magic.casting_lore_id is not None:
        interruption = resolve_skipped_casting_test_after_action(SkippedCastingTestAfterActionRequest(
            request.id + ':skipped-casting', request.actor_id, recover.slot.execution, magic,
            request.state.wizard.caster.wizard_level, request.state.consumed_execution_ids))
    return NpcRosterBatteredLegRecoverResult(request, recover, interruption)


def apply_npc_roster_battered_leg_recover(state: NpcRosterCastingState,
                                        result: NpcRosterBatteredLegRecoverResult) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState) or not isinstance(result, NpcRosterBatteredLegRecoverResult):
        raise TypeError('Battered Leg Recover application requires typed full state and result')
    replace(result)
    _owner(state)
    if result.source.id in state.consumed_execution_ids:
        raise ValueError('Battered Leg Recover was already consumed')
    if state != result.source.state:
        raise ValueError('Battered Leg Recover belongs to another or stale complete owner')
    return result.state
