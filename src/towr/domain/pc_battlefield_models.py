"""Explicit spatial facts for the configured open encounter arena.

PG1.4 V114: equal Zones imply Short, not Close; Close is a separate relation
and may span the edge of adjacent Zones. The line graph below is one explicit
scenario layout, not a universal book geometry. These helpers do not execute
actions, spend movement or grant permission to move. Existing K1 owners remain
responsible for those rules and their source-bound receipts.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace
from itertools import combinations

from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.pc_companion_policy_models import DismountedMountPolicy
from towr.domain.pc_scene_feature_models import (PcZoneFeatures,PcVisibilityFact,validate_scene_feature_source)
from towr.domain.spatial_models import (
    SpatialBattleState,
    SpatialEntityPlacement,
    ZoneConnection,
    ZoneGraph,
)


_INITIAL_ZONE_OFFSETS = {
    RangedWeaponRange.CLOSE: 0,
    RangedWeaponRange.SHORT: 0,
    RangedWeaponRange.MEDIUM: 1,
    RangedWeaponRange.LONG: 2,
    RangedWeaponRange.EXTREME: 3,
}


def _identifier(value: str, name: str) -> None:
    if type(value) is not str:
        raise TypeError(f'{name} must be an exact string')
    if not value.strip():
        raise ValueError(f'{name} must not be empty')


def _identifiers(values: tuple[str, ...], name: str, *, nonempty: bool = False) -> None:
    if type(values) is not tuple:
        raise TypeError(f'{name} must be an ordered tuple')
    if nonempty and not values:
        raise ValueError(f'{name} must not be empty')
    for value in values:
        _identifier(value, name)
    if len(set(values)) != len(values):
        raise ValueError(f'{name} must contain unique IDs')


def _zone_distance(graph: ZoneGraph, first: str, second: str) -> int:
    if first == second:
        return 0
    visited = {first}
    pending = deque(((first, 0),))
    while pending:
        zone_id, distance = pending.popleft()
        for adjacent in graph.adjacent_zone_ids(zone_id):
            if adjacent in visited:
                continue
            if adjacent == second:
                return distance + 1
            visited.add(adjacent)
            pending.append((adjacent, distance + 1))
    raise ValueError('battlefield participants must share connected Zones')


def _close_key(first: str, second: str) -> tuple[str, str]:
    return (first, second) if first < second else (second, first)


@dataclass(frozen=True, slots=True)
class PcAirspaceSpec:
    fall_hazard_rating: int = 2
    open_sky_confirmed: bool = True

    def __post_init__(self):
        if type(self.fall_hazard_rating) is not int or self.fall_hazard_rating < 1:
            raise ValueError('airspace requires an exact positive GM fall Hazard rating')
        if type(self.open_sky_confirmed) is not bool:
            raise TypeError('open sky confirmation must be an exact bool')
        if self.open_sky_confirmed is not True:
            raise ValueError('airspace requires the explicit open sky confirmation')


@dataclass(frozen=True, slots=True)
class PcBattlefieldSpec:
    initial_range: RangedWeaponRange
    two_handed_max_range: RangedWeaponRange
    airspace: PcAirspaceSpec | None = field(default=None, kw_only=True)
    zone_features: tuple[PcZoneFeatures,...] = field(default=(),kw_only=True)
    visibility: tuple[PcVisibilityFact,...] = field(default=(),kw_only=True)
    darkness: bool = field(default=False,kw_only=True)
    enemy_zone_blocking: bool = field(default=False,kw_only=True)
    dismounted_mount_policy: DismountedMountPolicy = field(default=DismountedMountPolicy.WAIT_AND_RECOVER,kw_only=True)
    dismounted_mounts_are_combatants: bool = field(default=False,kw_only=True)

    def __post_init__(self) -> None:
        if type(self.enemy_zone_blocking) is not bool:
            raise TypeError('enemy_zone_blocking requires an exact GM boolean')
        if type(self.dismounted_mount_policy) is not DismountedMountPolicy:
            raise TypeError('dismounted mount policy requires its exact supported GM policy')
        if type(self.dismounted_mounts_are_combatants) is not bool:
            raise TypeError('dismounted mount combatant status requires an exact GM boolean')
        for name in ('initial_range', 'two_handed_max_range'):
            if type(getattr(self, name)) is not RangedWeaponRange:
                raise TypeError(f'{name} requires a typed Range')
        if self.two_handed_max_range is RangedWeaponRange.CLOSE:
            raise ValueError('two-handed shooting maximum must be Short or further')
        validate_scene_feature_source(self.zone_features,self.visibility,self.darkness,self.initial_range)
        if self.airspace is not None:
            if type(self.airspace) is not PcAirspaceSpec:
                raise TypeError('airspace requires its exact typed scene premise or None')
            replace(self.airspace)


@dataclass(frozen=True, slots=True)
class PcBattlefieldState:
    spatial: SpatialBattleState
    close_pairs: tuple[tuple[str, str], ...]
    air_to_ground: tuple[tuple[str, str], ...] = field(default=(), kw_only=True)

    def __post_init__(self) -> None:
        if type(self.spatial) is not SpatialBattleState:
            raise TypeError('battlefield requires a SpatialBattleState')
        # Keep the K1 placement/round/usage contract even for readmitted facts.
        replace(self.spatial)
        if type(self.air_to_ground) is not tuple:
            raise TypeError('airspace mapping must retain its source-ordered tuple')
        air_ids, ground_ids = [], []
        for pair in self.air_to_ground:
            if type(pair) is not tuple or len(pair) != 2:
                raise TypeError('airspace mapping requires exact air/ground Zone pairs')
            air, ground = pair
            _identifier(air, 'midair Zone'); _identifier(ground, 'ground Zone')
            if (not self.spatial.graph.contains(air) or not self.spatial.graph.contains(ground)
                    or not self.spatial.graph.are_adjacent(air, ground)):
                raise ValueError('each midair Zone must connect to its actual ground below')
            air_ids.append(air); ground_ids.append(ground)
        if (len(set(air_ids)) != len(air_ids) or len(set(ground_ids)) != len(ground_ids)
                or set(air_ids) & set(ground_ids)):
            raise ValueError('air/ground layers must be disjoint and map one-to-one')
        if type(self.close_pairs) is not tuple:
            raise TypeError('Close pairs must be a tuple')
        normalised = set()
        for pair in self.close_pairs:
            if type(pair) is not tuple or len(pair) != 2:
                raise TypeError('a Close pair must be a tuple of two actor IDs')
            first, second = pair
            _identifier(first, 'Close actor ID')
            _identifier(second, 'Close actor ID')
            if first == second:
                raise ValueError('a Close pair must name two different actors')
            first_placement = self.spatial.placement_for(first)
            second_placement = self.spatial.placement_for(second)
            key = _close_key(first, second)
            if key in normalised:
                raise ValueError('Close pairs must be unique unordered links')
            first_zone = first_placement.zone_id
            second_zone = second_placement.zone_id
            if first_zone != second_zone and not self.spatial.graph.are_adjacent(
                    first_zone, second_zone):
                raise ValueError('Close actors must share a Zone or adjacent Zone edges')
            normalised.add(key)
        object.__setattr__(self, 'close_pairs', tuple(sorted(normalised)))


def build_pc_battlefield(spec: PcBattlefieldSpec, party_ids: tuple[str, ...],
        enemy_ids: tuple[str, ...], arena_id: str) -> PcBattlefieldState:
    """Place two explicitly clustered sides in one configured open line arena.

    Party starts at index0 and the opposition at0/1/2/3, with three Zones of
    margin at both ends. Stable arena-prefixed Zone IDs bind the generated graph
    to its scenario source; actual actor IDs are preserved unchanged.
    """
    if type(spec) is not PcBattlefieldSpec:
        raise TypeError('battlefield requires a PcBattlefieldSpec')
    replace(spec)
    _identifiers(party_ids, 'party actor IDs', nonempty=True)
    _identifiers(enemy_ids, 'enemy actor IDs', nonempty=True)
    if set(party_ids) & set(enemy_ids):
        raise ValueError('party and enemy actor IDs must be disjoint')
    _identifier(arena_id, 'arena ID')
    offset = _INITIAL_ZONE_OFFSETS[spec.initial_range]
    zone_ids = tuple(f'{arena_id}:zone:{index}' for index in range(-3, offset + 4))
    ground_edges = tuple(ZoneConnection(first, second) for first, second in zip(zone_ids, zone_ids[1:]))
    air_ids = tuple(f'{arena_id}:air:{index}' for index in range(-3, offset + 4)) if spec.airspace else ()
    mapping = tuple(zip(air_ids, zone_ids)) if air_ids else ()
    graph = ZoneGraph((*zone_ids, *air_ids), (*ground_edges,
        *(ZoneConnection(air, ground) for air, ground in mapping),
        *(ZoneConnection(first, second) for first, second in zip(air_ids, air_ids[1:]))))
    placements = tuple(
        SpatialEntityPlacement(actor_id, 'players_and_allies', f'{arena_id}:zone:0')
        for actor_id in party_ids) + tuple(
        SpatialEntityPlacement(actor_id, 'opposition', f'{arena_id}:zone:{offset}')
        for actor_id in enemy_ids)
    groups = ((party_ids + enemy_ids,) if spec.initial_range is RangedWeaponRange.CLOSE
        else (party_ids, enemy_ids))
    close_pairs = tuple(pair for group in groups for pair in combinations(group, 2))
    return PcBattlefieldState(SpatialBattleState(graph, placements), close_pairs, air_to_ground=mapping)


def _state(value: PcBattlefieldState) -> None:
    if type(value) is not PcBattlefieldState:
        raise TypeError('battlefield requires a PcBattlefieldState')


def battlefield_is_midair(state: PcBattlefieldState, entity_or_zone: str, *, zone: bool = False) -> bool:
    """Query actual placement; an explicit Zone query avoids ID-name heuristics."""
    _state(state); _identifier(entity_or_zone, 'airspace query ID')
    if type(zone) is not bool:
        raise TypeError('airspace Zone-query selector must be an exact bool')
    if zone:
        zone_id = entity_or_zone
        if not state.spatial.graph.contains(zone_id):
            raise ValueError('airspace query requires an actual battlefield Zone')
    else:
        placement = next((item for item in state.spatial.placements if item.entity_id == entity_or_zone), None)
        if placement is not None:
            zone_id = placement.zone_id
        elif state.spatial.graph.contains(entity_or_zone):
            zone_id = entity_or_zone
        else:
            raise ValueError('airspace query requires an actual entity or Zone')
    return any(air == zone_id for air, _ in state.air_to_ground)


def battlefield_ground_below(state: PcBattlefieldState, zone_id: str) -> str:
    _state(state); _identifier(zone_id, 'falling source Zone')
    if not state.spatial.graph.contains(zone_id):
        raise ValueError('ground below requires an actual battlefield Zone')
    return next((ground for air, ground in state.air_to_ground if air == zone_id), zone_id)


def battlefield_range(state: PcBattlefieldState, first_id: str,
        second_id: str) -> RangedWeaponRange:
    """Read explicit Close first, then the graph distance; no transitive closure."""
    _state(state)
    _identifier(first_id, 'first actor ID')
    _identifier(second_id, 'second actor ID')
    first = state.spatial.placement_for(first_id)
    second = state.spatial.placement_for(second_id)
    if first_id == second_id or _close_key(first_id, second_id) in state.close_pairs:
        return RangedWeaponRange.CLOSE
    distance = _zone_distance(state.spatial.graph, first.zone_id, second.zone_id)
    if distance == 0:
        return RangedWeaponRange.SHORT
    if distance == 1:
        return RangedWeaponRange.MEDIUM
    if distance == 2:
        return RangedWeaponRange.LONG
    return RangedWeaponRange.EXTREME


def battlefield_nearby(state: PcBattlefieldState, actor_id: str,
        living_ids: tuple[str, ...]) -> tuple[str, ...]:
    """Return other living actors explicitly Close to the anchor, in caller order.

    The anchor may have just died: a hit's mandatory nearby effects still need
    the established position of that actor. This helper never invents liveness.
    """
    _state(state)
    _identifier(actor_id, 'nearby anchor ID')
    state.spatial.placement_for(actor_id)
    _identifiers(living_ids, 'living actor IDs')
    for living_id in living_ids:
        state.spatial.placement_for(living_id)
    return tuple(living_id for living_id in living_ids if living_id != actor_id
        and _close_key(actor_id, living_id) in state.close_pairs)


def with_actor_placement(state: PcBattlefieldState, actor_id: str, zone_id: str,
        *, close_to_ids: tuple[str, ...] = ()) -> PcBattlefieldState:
    """Project chosen facts only; clear this actor's old links and set explicit ones.

    Conditions, movement availability, path length and costs are deliberately
    absent. The action owner must obtain the actual K1 result and preserve its
    usage/proof before accepting this projection as a battle transition.
    """
    _state(state)
    _identifier(actor_id, 'moving actor ID')
    _identifier(zone_id, 'destination Zone ID')
    state.spatial.placement_for(actor_id)
    if not state.spatial.graph.contains(zone_id):
        raise ValueError('destination is not a battlefield Zone')
    _identifiers(close_to_ids, 'new Close actor IDs')
    if actor_id in close_to_ids:
        raise ValueError('an actor cannot be Close to itself through a pair')
    for other_id in close_to_ids:
        state.spatial.placement_for(other_id)
    placements = tuple(replace(item, zone_id=zone_id) if item.entity_id == actor_id
        else item for item in state.spatial.placements)
    close_pairs = tuple(pair for pair in state.close_pairs if actor_id not in pair) + tuple(
        (actor_id, other_id) for other_id in close_to_ids)
    return replace(state, spatial=replace(state.spatial, placements=placements), close_pairs=close_pairs)
