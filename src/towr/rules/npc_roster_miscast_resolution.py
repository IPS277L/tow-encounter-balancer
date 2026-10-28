"""Declined Miscast preparation and one table roll; no effect or Pool cleanup."""
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_miscast_models import (
    NpcRosterMiscastPreparationRequest, NpcRosterMiscastPreparationResult,
    NpcRosterMiscastRollRequest, NpcRosterMiscastRollResult,
)
from towr.rules.dice import RandomSource
from towr.rules.miscast_resolution import prepare_miscast, resolve_miscast_roll


def prepare_npc_roster_miscast(request: NpcRosterMiscastPreparationRequest) -> NpcRosterMiscastPreparationResult:
    if not isinstance(request, NpcRosterMiscastPreparationRequest):
        raise TypeError('Miscast preparation requires NpcRosterMiscastPreparationRequest')
    return NpcRosterMiscastPreparationResult(request, prepare_miscast(request.preparation_request))


def apply_npc_roster_miscast_preparation(
    state: NpcRosterCastingState, result: NpcRosterMiscastPreparationResult,
) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState) or not isinstance(result, NpcRosterMiscastPreparationResult):
        raise TypeError('Miscast preparation application requires typed full state and result')
    if state != result.source.state:
        raise ValueError('Miscast preparation belongs to another, already applied or stale full source state')
    return result.state


def roll_npc_roster_miscast(request: NpcRosterMiscastRollRequest, rng: RandomSource) -> NpcRosterMiscastRollResult:
    if not isinstance(request, NpcRosterMiscastRollRequest):
        raise TypeError('Miscast roll requires NpcRosterMiscastRollRequest')
    return NpcRosterMiscastRollResult(
        request, resolve_miscast_roll(request.roll_request, request.state.wizard.magic_state, rng))


def apply_npc_roster_miscast_roll(
    state: NpcRosterCastingState, result: NpcRosterMiscastRollResult,
) -> NpcRosterCastingState:
    if not isinstance(state, NpcRosterCastingState) or not isinstance(result, NpcRosterMiscastRollResult):
        raise TypeError('Miscast roll application requires typed full state and result')
    if state != result.source.state:
        raise ValueError('Miscast roll belongs to another, already applied or stale full source state')
    return result.state
