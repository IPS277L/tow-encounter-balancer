"""Pure application of one existing Casting result; never rolls or casts."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from towr.domain.npc_crushed_rib_models import NpcCrushedRibContext
from towr.domain.condition_models import Condition
from towr.domain.npc_stationary_wound_models import NpcStationaryWoundContext
from towr.domain.npc_roster_casting_models import (
    NpcRosterCastingRequest, NpcRosterCastingResult, NpcRosterCastingState,
    NpcRosterCastingTargetContext,
)
from towr.domain.cowardly_flight_casting_models import (
    CowardlyFlightCastingFacts, CowardlyFlightCastingPolicy,
    CowardlyFlightCastingRequest, CowardlyFlightCastingTarget,
)


def prepare_npc_roster_casting(
    *, request_id: str, state: NpcRosterCastingState, selected_zone_id: str,
    targets: tuple[NpcRosterCastingTargetContext, ...],
    facts: CowardlyFlightCastingFacts, policy: CowardlyFlightCastingPolicy,
    stationary_wounds: NpcStationaryWoundContext | None = None,
    crushed_rib_context: NpcCrushedRibContext | None = None,
) -> NpcRosterCastingRequest:
    """Build a bound request from current injury and live projections, no RNG."""
    if not isinstance(state, NpcRosterCastingState):
        raise TypeError('state must be an NpcRosterCastingState')
    if state.pending_miscast_continuation is not None:
        raise ValueError('prepared Miscast blocks normal Casting')
    if state.pending_minion_attack is not None:
        raise ValueError('pending Minion attack blocks normal Casting')
    if state.pending_interruption is not None:
        raise ValueError('pending interruption Miscast blocks normal Casting')
    if state.pending_movement is not None:
        raise ValueError('pending movement blocks normal Casting')
    if state.pending_miscast is not None:
        raise ValueError('pending Miscast blocks normal Casting')
    if state.champion_attack is not None and state.champion_attack.pending is not None:
        raise ValueError('pending Champion attack blocks normal Casting')
    if not isinstance(targets, (tuple, list)) or not all(
        isinstance(t, NpcRosterCastingTargetContext) for t in targets
    ):
        raise TypeError('targets must be ordered Casting target contexts')
    casting = CowardlyFlightCastingRequest(
        request_id, state.wizard.caster, state.wizard.actor_id,
        state.casting_round_state, 1, state.wizard.magic_state,
        state.casting_spatial_state, selected_zone_id,
        tuple(CowardlyFlightCastingTarget(
            t.actor_id, t.willpower_profile, state.roster.participant(t.actor_id).state.injury,
            t.can_give_ground and not state.roster.participant(t.actor_id).state.injury.conditions.has(
                Condition.PRONE)) for t in targets), facts, policy,
    )
    if crushed_rib_context is not None:
        from towr.domain.npc_crushed_rib_models import NpcCrushedRibContext
        from towr.domain.crushed_rib_test_models import CrushedRibCastingPreparationRequest
        from towr.rules.crushed_rib_test_resolution import prepare_crushed_rib_casting
        if not isinstance(crushed_rib_context, NpcCrushedRibContext):
            raise TypeError('Casting requires typed Crushed Rib owner context')
        crushed_rib_context.validate_source(state, state.wizard.actor_id)
        if crushed_rib_context.consumption is None:
            preparation = prepare_crushed_rib_casting(CrushedRibCastingPreparationRequest(
                request_id + ':crushed-rib', state.wizard.actor_id,
                state.roster.participant(state.wizard.actor_id).state.injury, casting.casting_test_request))
            casting = replace(casting, crushed_rib_preparation=preparation)
    return NpcRosterCastingRequest(state, casting, stationary_wounds=stationary_wounds,
                                  crushed_rib_context=crushed_rib_context)


def apply_npc_roster_casting_result(
    state: NpcRosterCastingState,
    result: NpcRosterCastingResult,
) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState):
        raise TypeError("state must be an NpcRosterCastingState")
    if not isinstance(result, NpcRosterCastingResult):
        raise TypeError("result must be an NpcRosterCastingResult")
    replace(result)
    if result.source.crushed_rib_context is not None:
        result.source.crushed_rib_context.validate_source(state, state.wizard.actor_id)
    if result.casting.source.id in state.consumed_execution_ids:
        raise ValueError("Casting execution has already been consumed")
    if state != result.source.state:
        raise ValueError("Casting result belongs to another or stale source state")
    return result.state
