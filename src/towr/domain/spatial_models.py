from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ZoneConnection:
    """An undirected boundary that permits movement between two Zones."""

    first_zone_id: str
    second_zone_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.first_zone_id, "first_zone_id")
        _validate_non_empty_string(self.second_zone_id, "second_zone_id")
        if self.first_zone_id == self.second_zone_id:
            raise ValueError("a Zone cannot be connected to itself")

    @property
    def key(self) -> frozenset[str]:
        return frozenset((self.first_zone_id, self.second_zone_id))

    def connects(self, first_zone_id: str, second_zone_id: str) -> bool:
        return self.key == frozenset((first_zone_id, second_zone_id))


@dataclass(frozen=True, slots=True)
class ZoneGraph:
    zone_ids: tuple[str, ...]
    connections: tuple[ZoneConnection, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        zone_ids = tuple(self.zone_ids)
        if not zone_ids:
            raise ValueError("Zone graph must contain at least one Zone")
        for zone_id in zone_ids:
            _validate_non_empty_string(zone_id, "zone_id")
        if len(set(zone_ids)) != len(zone_ids):
            raise ValueError("Zone IDs must be unique")

        connections = tuple(self.connections)
        if not all(isinstance(item, ZoneConnection) for item in connections):
            raise TypeError("connections must contain ZoneConnection values")
        connection_keys = tuple(item.key for item in connections)
        if len(set(connection_keys)) != len(connection_keys):
            raise ValueError("Zone connections must be unique")
        known_zone_ids = set(zone_ids)
        for connection in connections:
            if not connection.key <= known_zone_ids:
                raise ValueError("Zone connection references an unknown Zone")

        object.__setattr__(self, "zone_ids", zone_ids)
        object.__setattr__(self, "connections", connections)

    def contains(self, zone_id: str) -> bool:
        return zone_id in self.zone_ids

    def are_adjacent(self, first_zone_id: str, second_zone_id: str) -> bool:
        return any(
            connection.connects(first_zone_id, second_zone_id)
            for connection in self.connections
        )

    def adjacent_zone_ids(self, zone_id: str) -> tuple[str, ...]:
        if zone_id not in self.zone_ids:
            raise ValueError("unknown Zone")
        adjacent: list[str] = []
        for connection in self.connections:
            if connection.first_zone_id == zone_id:
                adjacent.append(connection.second_zone_id)
            elif connection.second_zone_id == zone_id:
                adjacent.append(connection.first_zone_id)
        return tuple(adjacent)


@dataclass(frozen=True, slots=True)
class SpatialEntityPlacement:
    entity_id: str
    side_id: str
    zone_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.entity_id, "entity_id")
        _validate_non_empty_string(self.side_id, "side_id")
        _validate_non_empty_string(self.zone_id, "zone_id")


@dataclass(frozen=True, slots=True)
class SpatialBattleState:
    graph: ZoneGraph
    placements: tuple[SpatialEntityPlacement, ...]
    round_number: int = 1
    gave_ground_entity_ids: tuple[str, ...] = field(default_factory=tuple)
    free_move_used_entity_ids: tuple[str, ...] = field(default_factory=tuple)
    difficult_terrain_tested_entity_ids: tuple[str, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        if not isinstance(self.graph, ZoneGraph):
            raise TypeError("graph must be a ZoneGraph")
        placements = tuple(self.placements)
        if not all(
            isinstance(item, SpatialEntityPlacement) for item in placements
        ):
            raise TypeError(
                "placements must contain SpatialEntityPlacement values"
            )
        entity_ids = tuple(item.entity_id for item in placements)
        if len(set(entity_ids)) != len(entity_ids):
            raise ValueError("spatial entity IDs must be unique")
        if any(not self.graph.contains(item.zone_id) for item in placements):
            raise ValueError("placement references an unknown Zone")
        if not isinstance(self.round_number, int) or isinstance(
            self.round_number,
            bool,
        ):
            raise TypeError("round_number must be an integer")
        if self.round_number < 1:
            raise ValueError("round_number must be positive")

        gave_ground_entity_ids = tuple(self.gave_ground_entity_ids)
        for entity_id in gave_ground_entity_ids:
            _validate_non_empty_string(entity_id, "gave_ground entity_id")
        if len(set(gave_ground_entity_ids)) != len(gave_ground_entity_ids):
            raise ValueError("Give Ground entity IDs must be unique")
        if not set(gave_ground_entity_ids) <= set(entity_ids):
            raise ValueError("Give Ground state references an unknown entity")

        free_move_used_entity_ids = tuple(self.free_move_used_entity_ids)
        for entity_id in free_move_used_entity_ids:
            _validate_non_empty_string(entity_id, "free-move-used entity_id")
        if len(set(free_move_used_entity_ids)) != len(
            free_move_used_entity_ids
        ):
            raise ValueError("free movement entity IDs must be unique")
        if not set(free_move_used_entity_ids) <= set(entity_ids):
            raise ValueError("free movement state references an unknown entity")

        difficult_terrain_tested_entity_ids = tuple(
            self.difficult_terrain_tested_entity_ids
        )
        for entity_id in difficult_terrain_tested_entity_ids:
            _validate_non_empty_string(
                entity_id,
                "Difficult Terrain tested entity_id",
            )
        if len(set(difficult_terrain_tested_entity_ids)) != len(
            difficult_terrain_tested_entity_ids
        ):
            raise ValueError("Difficult Terrain tested entity IDs must be unique")
        if not set(difficult_terrain_tested_entity_ids) <= set(entity_ids):
            raise ValueError(
                "Difficult Terrain state references an unknown entity"
            )

        object.__setattr__(self, "placements", placements)
        object.__setattr__(
            self,
            "gave_ground_entity_ids",
            gave_ground_entity_ids,
        )
        object.__setattr__(
            self,
            "free_move_used_entity_ids",
            free_move_used_entity_ids,
        )
        object.__setattr__(
            self,
            "difficult_terrain_tested_entity_ids",
            difficult_terrain_tested_entity_ids,
        )

    def placement_for(self, entity_id: str) -> SpatialEntityPlacement:
        for placement in self.placements:
            if placement.entity_id == entity_id:
                return placement
        raise ValueError(f"unknown spatial entity: {entity_id}")

    def placements_in(self, zone_id: str) -> tuple[SpatialEntityPlacement, ...]:
        if not self.graph.contains(zone_id):
            raise ValueError("unknown Zone")
        return tuple(
            placement
            for placement in self.placements
            if placement.zone_id == zone_id
        )


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
