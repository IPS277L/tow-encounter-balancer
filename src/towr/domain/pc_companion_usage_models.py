"""Retain the three actual spatial once-budgets while a mount is ridden.

Removing a detached mount's placement also removes its SpatialBattleState
usage IDs. Remount/retention owners preserve this typed snapshot so another
detach in the same round cannot manufacture fresh movement or reactions.
"""
from dataclasses import dataclass, replace

from towr.domain.pc_battlefield_models import PcBattlefieldState
from towr.domain.spatial_models import SpatialBattleState


def _actor(actor_id):
    if type(actor_id) is not str or not actor_id.strip():
        raise TypeError('companion spatial usage requires its exact actor identifier')


@dataclass(frozen=True, slots=True)
class PcMountCompanionSpatialUsage:
    actor_id: str
    round_number: int
    gave_ground: bool
    free_move_used: bool
    difficult_terrain_tested: bool

    def __post_init__(self):
        _actor(self.actor_id)
        if type(self.round_number) is not int:
            raise TypeError('companion spatial usage round must be an exact integer')
        if self.round_number < 1:
            raise ValueError('companion spatial usage round must be positive')
        for flag in (self.gave_ground, self.free_move_used, self.difficult_terrain_tested):
            if type(flag) is not bool:
                raise TypeError('companion spatial usage requires three exact boolean facts')


def _battlefield(battlefield, actor):
    _actor(actor)
    if type(battlefield) is not PcBattlefieldState:
        raise TypeError('companion spatial usage requires the exact actual battlefield')
    if type(battlefield.spatial) is not SpatialBattleState:
        raise TypeError('companion spatial usage requires the exact actual spatial state')
    # Constructors validate geometry, uniqueness and placement membership. A
    # cached list must not be silently normalized into a supposedly exact source.
    for ids in (battlefield.spatial.gave_ground_entity_ids,
            battlefield.spatial.free_move_used_entity_ids,
            battlefield.spatial.difficult_terrain_tested_entity_ids):
        if type(ids) is not tuple or any(type(identifier) is not str for identifier in ids):
            raise TypeError('companion spatial usage must retain exact ordered actor IDs')
    replace(battlefield)
    battlefield.spatial.placement_for(actor)


def capture_companion_usage(battlefield: PcBattlefieldState, actor: str) -> PcMountCompanionSpatialUsage:
    _battlefield(battlefield, actor)
    spatial = battlefield.spatial
    return PcMountCompanionSpatialUsage(actor, spatial.round_number,
        actor in spatial.gave_ground_entity_ids,
        actor in spatial.free_move_used_entity_ids,
        actor in spatial.difficult_terrain_tested_entity_ids)


def restore_companion_usage(battlefield: PcBattlefieldState, actor: str,
        usage: PcMountCompanionSpatialUsage) -> PcBattlefieldState:
    _battlefield(battlefield, actor)
    if type(usage) is not PcMountCompanionSpatialUsage:
        raise TypeError('companion spatial restoration requires its exact typed usage snapshot')
    replace(usage)
    if usage.actor_id != actor:
        raise ValueError('companion spatial usage belongs to another actual actor')
    spatial = battlefield.spatial
    if usage.round_number > spatial.round_number:
        raise ValueError('companion spatial usage cannot come from a future round')
    if usage.round_number < spatial.round_number:
        return battlefield

    def retained(ids, used):
        return (*ids, actor) if used and actor not in ids else ids

    restored = replace(spatial,
        gave_ground_entity_ids=retained(spatial.gave_ground_entity_ids, usage.gave_ground),
        free_move_used_entity_ids=retained(spatial.free_move_used_entity_ids, usage.free_move_used),
        difficult_terrain_tested_entity_ids=retained(spatial.difficult_terrain_tested_entity_ids,
            usage.difficult_terrain_tested))
    return battlefield if restored == spatial else replace(battlefield, spatial=restored)
