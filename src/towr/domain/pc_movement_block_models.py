"""Actual enemy path IDs under the explicit narrow-passage scene premise.

PG114 leaves physical within-Zone possibilities to the GM. Occupancy is not a
universal blocker. This source is active only when enemy_zone_blocking is true.
"""
from towr.domain.pc_battlefield_models import battlefield_range
from towr.domain.ranged_weapon_profiles import RangedWeaponRange


def pc_enemy_path_blockers(state,actor,path,*,battlefield=None):
    source=state.source.battlefield
    if source is None or not source.enemy_zone_blocking:return ()
    from towr.domain.pc_actor_models import pc_actor_side, pc_opponent_ids
    pc_actor_side(state, actor)
    if type(path) is not tuple or any(type(zone) is not str or not zone.strip() for zone in path):
        raise TypeError('enemy path blockers require the actual ordered Zone route')
    current=state.battlefield if battlefield is None else battlefield
    if not path:return ()  # No claimed within-Zone microscopic route.
    origin=current.spatial.placement_for(actor).zone_id
    previous=origin
    for zone in path:
        if not current.spatial.graph.contains(zone) or not current.spatial.graph.are_adjacent(previous,zone):
            raise ValueError('enemy path blockers cannot invent route geometry')
        previous=zone
    enemies=pc_opponent_ids(state, actor)
    intermediates=set(path[:-1])
    return tuple(enemy for enemy in enemies
        if battlefield_range(current,actor,enemy) is RangedWeaponRange.CLOSE
        or current.spatial.placement_for(enemy).zone_id in intermediates)
