"""Finite scene facts for ADR-0037; no movement execution or route selection.

PG1.4 Rules / Zones and Range p114, Speed p115, Giving Ground p119,
Broken p122. Range and route assertions remain explicit caller facts.
"""
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, TypeVar

from towr.domain.movement_models import MovementSpeed
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.spatial_models import SpatialEntityPlacement, ZoneGraph


T = TypeVar('T')


def _ordered(values: tuple[T, ...], kind: type[T], label: str) -> tuple[T, ...]:
    if not isinstance(values, (tuple, list)) or not all(isinstance(v, kind) for v in values):
        raise TypeError(f'{label} requires ordered {kind.__name__} values')
    return tuple(values)


def _identifier(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError('magic scenario IDs must be strings')
    if not value.strip():
        raise ValueError('magic scenario IDs must not be blank')


def _ids(values: tuple[str, ...]) -> tuple[str, ...]:
    identifiers = _ordered(values, str, 'IDs')
    for value in identifiers:
        _identifier(value)
    if len(set(identifiers)) != len(identifiers):
        raise ValueError('magic scenario IDs must be unique')
    return identifiers


def _boolean(value: bool) -> None:
    if not isinstance(value, bool):
        raise TypeError('magic scene flags must be explicit booleans')


@dataclass(frozen=True, slots=True)
class NpcMagicSceneKey:
    placements: tuple[SpatialEntityPlacement, ...]
    live_actor_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        placements = _ordered(self.placements, SpatialEntityPlacement, 'placements')
        actors = tuple(p.entity_id for p in placements)
        if not actors or len(set(actors)) != len(actors):
            raise ValueError('scene key requires distinct full placements')
        live = _ids(self.live_actor_ids)
        if not set(live) <= set(actors):
            raise ValueError('scene key has an unknown live actor')
        object.__setattr__(self, 'placements', placements)
        object.__setattr__(self, 'live_actor_ids', live)


@dataclass(frozen=True, slots=True)
class NpcMagicPairRange:
    first_actor_id: str
    second_actor_id: str
    target_range: RangedWeaponRange
    first_range_approved_by_gm: bool
    second_range_approved_by_gm: bool

    def __post_init__(self) -> None:
        _ids((self.first_actor_id, self.second_actor_id))
        if not isinstance(self.target_range, RangedWeaponRange):
            raise TypeError('pair range must be a RangedWeaponRange')
        _boolean(self.first_range_approved_by_gm)
        _boolean(self.second_range_approved_by_gm)


@dataclass(frozen=True, slots=True)
class NpcMagicZoneRange:
    zone_id: str
    target_range: RangedWeaponRange

    def __post_init__(self) -> None:
        _identifier(self.zone_id)
        if not isinstance(self.target_range, RangedWeaponRange):
            raise TypeError('Zone range must be a RangedWeaponRange')
        if self.target_range is RangedWeaponRange.CLOSE:
            raise ValueError('Zone range uses Short for the caster Zone, not Close')


@dataclass(frozen=True, slots=True)
class NpcMagicRouteFacts:
    path_entity_ids: tuple[str, ...]
    crosses_obstacle: bool
    crosses_difficult_terrain: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, 'path_entity_ids', _ids(self.path_entity_ids))
        _boolean(self.crosses_obstacle)
        _boolean(self.crosses_difficult_terrain)


@dataclass(frozen=True, slots=True)
class NpcMagicGiveGroundPlan:
    actor_id: str
    can_leave_zone: bool
    destination_zone_id: str | None
    route: NpcMagicRouteFacts | None
    impossible_confirmed: bool

    def __post_init__(self) -> None:
        _identifier(self.actor_id)
        _boolean(self.can_leave_zone)
        _boolean(self.impossible_confirmed)
        if self.destination_zone_id is None:
            if self.route is not None or not self.impossible_confirmed:
                raise ValueError('missing Give Ground route requires explicit factual impossibility')
        else:
            _identifier(self.destination_zone_id)
            if not isinstance(self.route, NpcMagicRouteFacts):
                raise TypeError('Give Ground destination requires typed route facts')
            if not self.can_leave_zone or self.impossible_confirmed:
                raise ValueError('Give Ground route contradicts departure/impossibility facts')


class NpcMagicBrokenPlanKind(str, Enum):
    SAFE_RECOVER = 'safe_recover'
    FREE_MOVE_RECOVER = 'free_move_recover'
    FREE_MOVE_RUN = 'free_move_run'


@dataclass(frozen=True, slots=True)
class NpcMagicBrokenPlan:
    actor_id: str
    kind: NpcMagicBrokenPlanKind
    free_move_zone_ids: tuple[str, ...]
    free_move_route: NpcMagicRouteFacts | None
    run_destination_zone_id: str | None
    run_route: NpcMagicRouteFacts | None
    fastest_route_confirmed: bool

    def __post_init__(self) -> None:
        _identifier(self.actor_id)
        if not isinstance(self.kind, NpcMagicBrokenPlanKind):
            raise TypeError('Broken plan kind must be typed')
        object.__setattr__(self, 'free_move_zone_ids', _ids(self.free_move_zone_ids))
        _boolean(self.fastest_route_confirmed)
        if not self.fastest_route_confirmed:
            raise ValueError('Broken plan requires fastest route confirmation')
        moving = self.kind is not NpcMagicBrokenPlanKind.SAFE_RECOVER
        if moving:
            if not self.free_move_zone_ids or not isinstance(self.free_move_route, NpcMagicRouteFacts):
                raise ValueError('moving Broken plan requires free movement and route facts')
        elif self.free_move_zone_ids or self.free_move_route is not None:
            raise ValueError('safe Recover does not spend free movement')
        if self.kind is NpcMagicBrokenPlanKind.FREE_MOVE_RUN:
            _identifier(self.run_destination_zone_id)
            if not isinstance(self.run_route, NpcMagicRouteFacts):
                raise TypeError('Run plan requires typed route facts')
        elif self.run_destination_zone_id is not None or self.run_route is not None:
            raise ValueError('Recover plan cannot contain Run')


@dataclass(frozen=True, slots=True)
class NpcMagicAttackDeparture:
    """Explicit ordinary-Attack target availability, not a Curse away-route."""
    actor_id: str
    can_leave_zone: bool

    def __post_init__(self) -> None:
        _identifier(self.actor_id)
        _boolean(self.can_leave_zone)


@dataclass(frozen=True, slots=True)
class NpcMagicSceneFrame:
    key: NpcMagicSceneKey
    pair_ranges: tuple[NpcMagicPairRange, ...]
    zone_ranges: tuple[NpcMagicZoneRange, ...]
    give_ground_plans: tuple[NpcMagicGiveGroundPlan, ...]
    broken_plans: tuple[NpcMagicBrokenPlan, ...]
    attack_departures: tuple[NpcMagicAttackDeparture, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.key, NpcMagicSceneKey):
            raise TypeError('scene frame requires a typed key')
        for name, kind in (('pair_ranges', NpcMagicPairRange), ('zone_ranges', NpcMagicZoneRange),
                           ('give_ground_plans', NpcMagicGiveGroundPlan), ('broken_plans', NpcMagicBrokenPlan)):
            object.__setattr__(self, name, _ordered(getattr(self, name), kind, name))
        object.__setattr__(self, 'attack_departures', _ordered(
            self.attack_departures, NpcMagicAttackDeparture, 'attack departures'))


def _distance(graph: ZoneGraph, origin: str, destination: str) -> int | None:
    """Compatibility check only; never returns or selects a movement route."""
    visited = {origin}
    queue = deque(((origin, 0),))
    while queue:
        current, distance = queue.popleft()
        if current == destination:
            return distance
        for adjacent in graph.adjacent_zone_ids(current):
            if adjacent not in visited:
                visited.add(adjacent)
                queue.append((adjacent, distance + 1))
    return None


def _range_matches(graph: ZoneGraph, origin: str, destination: str, value: RangedWeaponRange) -> None:
    distance = _distance(graph, origin, destination)
    expected = {RangedWeaponRange.CLOSE: 0, RangedWeaponRange.SHORT: 0,
                RangedWeaponRange.MEDIUM: 1, RangedWeaponRange.LONG: 2}
    if (value is RangedWeaponRange.EXTREME and distance is not None and distance < 3
            or value is not RangedWeaponRange.EXTREME and distance != expected[value]):
        raise ValueError('supplied range contradicts scene Zone geometry')


def validate_magic_scene_frame(
    frame: NpcMagicSceneFrame, initial: NpcRosterCastingState, speeds: Mapping[str, MovementSpeed],
) -> None:
    """Bind supplied facts to definitions/graph; authorize no current action."""
    roster, spatial = initial.roster, initial.spatial_state
    ids = tuple(p.state.actor_id for p in roster.participants)
    placements = frame.key.placements
    if tuple(p.entity_id for p in placements) != tuple(p.entity_id for p in spatial.placements):
        raise ValueError('frame must retain full ordered placements including archives')
    live = set(frame.key.live_actor_ids)
    if frame.key.live_actor_ids != tuple(i for i in ids if i in live):
        raise ValueError('frame live IDs must retain roster order')
    for placement in placements:
        if (placement.side_id != roster.participant(placement.entity_id).state.side.value
                or not spatial.graph.contains(placement.zone_id)):
            raise ValueError('frame placement differs from roster side/graph')
    zones = {p.entity_id: p.zone_id for p in placements}
    departures = tuple(p.actor_id for p in frame.attack_departures)
    if len(set(departures)) != len(departures) or not set(departures) <= live:
        raise ValueError('attack departures must name distinct live actors')
    if any(p.can_leave_zone and not spatial.graph.adjacent_zone_ids(zones[p.actor_id]) for p in frame.attack_departures):
        raise ValueError('can_leave_zone requires an adjacent Zone')
    sides = {p.state.actor_id: p.state.side for p in roster.participants}
    expected = {frozenset((a, b)) for a in live for b in live if sides[a] is not sides[b]}
    actual = []
    for pair in frame.pair_ranges:
        a, b = pair.first_actor_id, pair.second_actor_id
        key = frozenset((a, b))
        if key not in expected:
            raise ValueError('frame pair must name live hostile actors')
        actual.append(key)
        _range_matches(spatial.graph, zones[a], zones[b], pair.target_range)
        for actor, approval in ((a, pair.first_range_approved_by_gm), (b, pair.second_range_approved_by_gm)):
            if approval:
                attacks = roster.participant(actor).definition.attacks
                if (not attacks or pair.target_range is RangedWeaponRange.EXTREME
                        or attacks[0].hands is not RangedWeaponHands.TWO_HANDED
                        or tuple(RangedWeaponRange).index(pair.target_range)
                        <= tuple(RangedWeaponRange).index(attacks[0].range_max)):
                    raise ValueError('GM range approval is not applicable to this directed pair')
    if len(set(actual)) != len(actual) or set(actual) != expected:
        raise ValueError('frame requires each live hostile pair exactly once')
    if tuple(z.zone_id for z in frame.zone_ranges) != spatial.graph.zone_ids:
        raise ValueError('frame requires every Zone range in graph order')
    wizard = initial.wizard.actor_id
    zone_ranges = {z.zone_id: z.target_range for z in frame.zone_ranges}
    for zone in frame.zone_ranges:
        _range_matches(spatial.graph, zones[wizard], zone.zone_id, zone.target_range)
    for pair in frame.pair_ranges:
        if wizard in (pair.first_actor_id, pair.second_actor_id):
            other = pair.second_actor_id if pair.first_actor_id == wizard else pair.first_actor_id
            value = RangedWeaponRange.SHORT if pair.target_range is RangedWeaponRange.CLOSE else pair.target_range
            if value is not zone_ranges[zones[other]]:
                raise ValueError('pair range contradicts caster-to-Zone range')

    targets = tuple(i for i in ids if i in live and sides[i] is not sides[wizard]) if wizard in live else ()
    if tuple(p.actor_id for p in frame.give_ground_plans) != targets:
        raise ValueError('frame requires one Give Ground fact per live Curse target in roster order')

    def route(actor: str, facts: NpcMagicRouteFacts) -> None:
        if facts.crosses_obstacle or facts.crosses_difficult_terrain:
            raise ValueError('scene excludes obstacle/terrain routes')
        if any(i not in live or i == actor or sides[i] is not sides[actor] for i in facts.path_entity_ids):
            raise ValueError('route crosses self, unknown, archived or enemy actors')

    def unsafe(actor: str, zone: str) -> bool:
        return any(zones[i] == zone and sides[i] is not sides[actor] for i in live)

    for plan in frame.give_ground_plans:
        if plan.destination_zone_id is not None:
            origin, destination = zones[plan.actor_id], plan.destination_zone_id
            if not spatial.graph.are_adjacent(origin, destination):
                raise ValueError('Give Ground destination must be adjacent')
            before, after = _distance(spatial.graph, zones[wizard], origin), _distance(spatial.graph, zones[wizard], destination)
            if before is None or after is None or after <= before:
                raise ValueError('Give Ground route must move away from the Wizard')
            route(plan.actor_id, plan.route)
    plan_ids = tuple(p.actor_id for p in frame.broken_plans)
    if len(set(plan_ids)) != len(plan_ids) or not set(plan_ids) <= live:
        raise ValueError('Broken plans must name distinct live actors')
    for plan in frame.broken_plans:
        origin = zones[plan.actor_id]
        if plan.kind is NpcMagicBrokenPlanKind.SAFE_RECOVER:
            if unsafe(plan.actor_id, origin):
                raise ValueError('safe Recover requires a Zone without live enemies')
            continue
        if not unsafe(plan.actor_id, origin):
            raise ValueError('already safe Broken actor must Recover without movement')
        speed = speeds[plan.actor_id]
        if len(plan.free_move_zone_ids) > speed.free_move_zone_limit:
            raise ValueError('Broken plan exceeds the supplied Speed free movement')
        route(plan.actor_id, plan.free_move_route)
        previous = origin
        for zone in plan.free_move_zone_ids:
            if not spatial.graph.are_adjacent(previous, zone) or zone == origin:
                raise ValueError('Broken free movement must follow a non-repeating adjacent path')
            previous = zone
        if plan.kind is NpcMagicBrokenPlanKind.FREE_MOVE_RECOVER:
            if unsafe(plan.actor_id, previous) or any(not unsafe(plan.actor_id, z) for z in plan.free_move_zone_ids[:-1]):
                raise ValueError('Recover route must stop at its first safe Zone')
        else:
            if speed is MovementSpeed.SLOW or len(plan.free_move_zone_ids) != speed.free_move_zone_limit:
                raise ValueError('Run requires full Normal/Fast free movement')
            if (not all(unsafe(plan.actor_id, z) for z in plan.free_move_zone_ids)
                    or not spatial.graph.are_adjacent(previous, plan.run_destination_zone_id)
                    or unsafe(plan.actor_id, plan.run_destination_zone_id)):
                raise ValueError('Run must leave an unsafe free route for one adjacent safe Zone')
            route(plan.actor_id, plan.run_route)
