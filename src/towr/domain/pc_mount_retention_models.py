"""Back in the Saddle retains the actual dismounted body (PG1.4 III73/V124).

Retention is an immediate consequence of a real dismount, before a rider's
subsequent fall. In particular an airborne Pegasus does not teleport to the
ground with its falling rider. This receipt gives no action or current turn.
"""
from towr.domain.injury_models import injury_is_defeated
from dataclasses import dataclass, replace

from towr.domain.pc_battlefield_models import PcBattlefieldState, _close_key
from towr.domain.pc_companion_models import PcMountCompanionState
from towr.domain.pc_mount_models import PcDismountProof
from towr.domain.talent_actor_models import actor_acquired_talents
from towr.domain.talent_back_in_saddle_models import BackInSaddleSource
from towr.domain.talent_catalog import TalentId


def actor_back_in_saddle_source(state, rider):
    row = next((row for row in state.companions if row.rider_id == rider), None)
    if row is None:
        return None
    talent = next((entry for entry in actor_acquired_talents(state, rider)
        if entry.id is TalentId.BACK_IN_THE_SADDLE), None)
    return None if talent is None else BackInSaddleSource(rider, row.snapshot.state.actor_id, talent)


def _retained_battlefield(previous, rider, companion, stored_usage):
    if type(previous) is not PcBattlefieldState:
        raise TypeError('retained mount requires its actual typed battlefield')
    replace(previous)
    if companion in tuple(row.entity_id for row in previous.spatial.placements):
        raise ValueError('retained mount already has a separate physical placement')
    origin = previous.spatial.placement_for(rider)
    neighbours = [rider]
    for first, second in previous.close_pairs:
        if rider in (first, second):
            neighbours.append(second if first == rider else first)
    placement = replace(origin, entity_id=companion)
    battlefield = replace(previous,
        spatial=replace(previous.spatial, placements=(*previous.spatial.placements, placement)),
        close_pairs=(*previous.close_pairs, *(_close_key(companion, other) for other in neighbours)))
    from towr.domain.pc_companion_usage_models import restore_companion_usage
    return battlefield if stored_usage is None else restore_companion_usage(battlefield, companion, stored_usage)


@dataclass(frozen=True, slots=True)
class PcMountRetentionProof:
    source_dismount: PcDismountProof
    source: BackInSaddleSource
    history_index: int
    round_number: int
    previous: PcMountCompanionState
    state: PcMountCompanionState
    previous_battlefield: PcBattlefieldState
    battlefield: PcBattlefieldState

    def __post_init__(self):
        if type(self.source_dismount) is not PcDismountProof or type(self.source) is not BackInSaddleSource:
            raise TypeError('retention requires its exact dismount and acquired Talent sources')
        replace(self.source_dismount); replace(self.source)
        if type(self.history_index) is not int or self.history_index != self.source_dismount.history_index + 1:
            raise ValueError('retention must immediately follow its actual dismount')
        if type(self.round_number) is not int or self.round_number < 1:
            raise ValueError('retention requires its actual positive combat round')
        if type(self.previous) is not PcMountCompanionState or type(self.state) is not PcMountCompanionState:
            raise TypeError('retention requires exact physical mount body states')
        replace(self.previous); replace(self.state)
        if (self.source.actor_id != self.source_dismount.actor_id
                or self.previous.rider_id != self.source.actor_id
                or self.source.mount_id != self.previous.snapshot.state.actor_id
                or self.previous.retained_since_round is not None
                or injury_is_defeated(self.previous.snapshot.state.injury)):
            raise ValueError('retention source does not own an available living detached mount')
        if self.state != replace(self.previous, retained_since_round=self.round_number):
            raise ValueError('retention may not heal, replace or re-equip the mount')
        expected = _retained_battlefield(self.previous_battlefield, self.source.actor_id, self.source.mount_id,
            self.previous.stored_spatial_usage)
        if type(self.battlefield) is not PcBattlefieldState or self.battlefield != expected:
            raise ValueError('retention changed the actual physical dismount origin or Close links')


def expected_pc_mount_retention(state):
    if not state.history or type(state.history[-1]) is not PcDismountProof:
        return None
    dismount = state.history[-1]
    source = actor_back_in_saddle_source(state, dismount.actor_id)
    if source is None:
        return None
    from towr.domain.pc_actor_models import pc_actor_injury
    from towr.domain.injury_models import CharacterInjuryState
    injury = pc_actor_injury(state, source.actor_id)
    if ((type(injury) is CharacterInjuryState and injury.dead)
            or (type(injury) is not CharacterInjuryState and injury.defeated)):
        return None
    row = next(row for row in state.companions if row.rider_id == source.actor_id)
    if injury_is_defeated(row.snapshot.state.injury):
        return None
    current = state.round_state.round_number
    return PcMountRetentionProof(dismount, source, len(state.history), current, row,
        replace(row, retained_since_round=current), state.battlefield,
        _retained_battlefield(state.battlefield, source.actor_id, source.mount_id, row.stored_spatial_usage))


def project_pc_mount_retention(state, proof):
    if type(proof) is not PcMountRetentionProof:
        raise TypeError('retention requires its exact typed receipt')
    replace(proof)
    if proof != expected_pc_mount_retention(state):
        raise ValueError('retention differs from its actual source-bound dismount prefix')
    return dict(companions=tuple(proof.state if row.rider_id == proof.source.actor_id else row
        for row in state.companions), battlefield=proof.battlefield)
