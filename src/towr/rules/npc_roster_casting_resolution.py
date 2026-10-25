"""Pure application of one existing Casting result; never rolls or casts."""
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
) -> NpcRosterCastingRequest:
    """Build a bound request from current injury and live projections, no RNG."""
    if not isinstance(state, NpcRosterCastingState):
        raise TypeError('state must be an NpcRosterCastingState')
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
            t.can_give_ground) for t in targets), facts, policy,
    )
    return NpcRosterCastingRequest(state, casting)


def apply_npc_roster_casting_result(
    state: NpcRosterCastingState,
    result: NpcRosterCastingResult,
) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState):
        raise TypeError("state must be an NpcRosterCastingState")
    if not isinstance(result, NpcRosterCastingResult):
        raise TypeError("result must be an NpcRosterCastingResult")
    if result.casting.source.id in state.consumed_execution_ids:
        raise ValueError("Casting execution has already been consumed")
    if state != result.source.state:
        raise ValueError("Casting result belongs to another or stale source state")
    return result.state
