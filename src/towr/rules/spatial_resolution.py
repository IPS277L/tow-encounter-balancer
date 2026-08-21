from __future__ import annotations

from dataclasses import replace

from towr.domain.condition_models import (
    Condition,
    ConditionApplicationRequest,
)
from towr.domain.resolution_models import (
    GiveGroundResolutionRequest,
    GiveGroundResolutionResult,
)
from towr.domain.spatial_models import (
    SpatialBattleState,
    SpatialEntityPlacement,
    ZoneGraph,
)
from towr.rules.condition_effect_resolution import (
    resolve_condition_application,
)


ZONE_GRAPH_RULE_ID = "RULE-COMBAT-011:zones-and-ranges"
GIVE_GROUND_MOVEMENT_RULE_ID = "RULE-COMBAT-015:give-ground"


def resolve_give_ground(
    request: GiveGroundResolutionRequest,
) -> GiveGroundResolutionResult:
    """Apply one already chosen legal Give Ground destination."""
    state = request.state
    mover = state.placement_for(request.mover_id)
    if not state.graph.contains(request.destination_zone_id):
        raise ValueError("Give Ground destination is not in the Zone graph")
    if not state.graph.are_adjacent(
        mover.zone_id,
        request.destination_zone_id,
    ):
        raise ValueError("Give Ground destination must be an adjacent Zone")
    if request.mover_id in state.gave_ground_entity_ids:
        raise ValueError("an entity may only Give Ground once per round")
    if request.mover_conditions.has(Condition.PRONE):
        raise ValueError("a Prone entity cannot Give Ground")
    if request.mover_conditions.has(Condition.DEFENCELESS):
        raise ValueError("a Defenceless entity cannot move")
    if request.crosses_obstacle:
        raise ValueError("Give Ground cannot cross an obstacle")
    if request.crosses_difficult_terrain:
        raise ValueError("Give Ground cannot cross Difficult Terrain")

    for entity_id in request.path_entity_ids:
        crossed = state.placement_for(entity_id)
        if crossed.side_id != mover.side_id:
            raise ValueError("Give Ground cannot move through an enemy")

    if request.away_from_entity_id is not None:
        pursuer = state.placement_for(request.away_from_entity_id)
        origin_distance = _zone_distance(
            state.graph,
            pursuer.zone_id,
            mover.zone_id,
        )
        destination_distance = _zone_distance(
            state.graph,
            pursuer.zone_id,
            request.destination_zone_id,
        )
        if origin_distance is None or destination_distance is None:
            raise ValueError("mover and pursuer must share a connected Zone graph")
        if destination_distance <= origin_distance:
            raise ValueError("Give Ground must move away from the attacker")

    updated_placements = tuple(
        SpatialEntityPlacement(
            entity_id=placement.entity_id,
            side_id=placement.side_id,
            zone_id=request.destination_zone_id,
        )
        if placement.entity_id == request.mover_id
        else placement
        for placement in state.placements
    )
    updated_state = replace(
        state,
        placements=updated_placements,
        gave_ground_entity_ids=(
            *state.gave_ground_entity_ids,
            request.mover_id,
        ),
    )

    entered_enemy_zone = any(
        placement.entity_id != request.mover_id
        and placement.side_id != mover.side_id
        for placement in state.placements_in(request.destination_zone_id)
    )
    condition_application = None
    conditions = request.mover_conditions
    if entered_enemy_zone:
        condition_application = resolve_condition_application(
            ConditionApplicationRequest(
                id=(
                    f"{request.source.resolution_id}:{request.mover_id}:"
                    "enemy-zone-broken"
                ),
                state=request.mover_conditions,
                condition=Condition.BROKEN,
                source_rule_id=GIVE_GROUND_MOVEMENT_RULE_ID,
            )
        )
        conditions = condition_application.state

    return GiveGroundResolutionResult(
        source=request.source,
        mover_id=request.mover_id,
        origin_zone_id=mover.zone_id,
        destination_zone_id=request.destination_zone_id,
        previous_state=state,
        state=updated_state,
        conditions=conditions,
        condition_application=condition_application,
        entered_enemy_zone=entered_enemy_zone,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.source.rule_id,
                    ZONE_GRAPH_RULE_ID,
                    GIVE_GROUND_MOVEMENT_RULE_ID,
                    *(
                        condition_application.applied_rule_ids
                        if condition_application is not None
                        else ()
                    ),
                )
            )
        ),
    )


def start_next_spatial_round(state: SpatialBattleState) -> SpatialBattleState:
    """Advance the round-scoped movement state without choosing turn order."""
    if not isinstance(state, SpatialBattleState):
        raise TypeError("state must be a SpatialBattleState")
    return replace(
        state,
        round_number=state.round_number + 1,
        gave_ground_entity_ids=(),
        free_move_used_entity_ids=(),
    )


def _zone_distance(
    graph: ZoneGraph,
    origin_zone_id: str,
    destination_zone_id: str,
) -> int | None:
    if origin_zone_id == destination_zone_id:
        return 0
    visited = {origin_zone_id}
    frontier = [(origin_zone_id, 0)]
    while frontier:
        zone_id, distance = frontier.pop(0)
        for adjacent_zone_id in graph.adjacent_zone_ids(zone_id):
            if adjacent_zone_id in visited:
                continue
            if adjacent_zone_id == destination_zone_id:
                return distance + 1
            visited.add(adjacent_zone_id)
            frontier.append((adjacent_zone_id, distance + 1))
    return None
