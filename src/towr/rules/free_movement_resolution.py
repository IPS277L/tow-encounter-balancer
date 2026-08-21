from __future__ import annotations

from dataclasses import replace

from towr.domain.condition_models import Condition
from towr.domain.movement_models import (
    DifficultTerrainFreeMovementRequest,
    DifficultTerrainFreeMovementResult,
    FreeMovementRequest,
    FreeMovementResult,
    FreeMoveProneRemovalRequest,
    FreeMoveProneRemovalResult,
    ProneRemovalTargetKind,
)
from towr.domain.spatial_models import SpatialEntityPlacement
from towr.rules.spatial_resolution import ZONE_GRAPH_RULE_ID


SPEED_MOVEMENT_RULE_ID = "RULE-COMBAT-012:speed"
FREE_MOVEMENT_RULE_ID = "RULE-COMBAT-014:free-movement"
DIFFICULT_TERRAIN_FREE_MOVEMENT_RULE_ID = (
    "RULE-COMBAT-014:difficult-terrain-free-movement"
)
FREE_MOVE_PRONE_REMOVAL_RULE_ID = (
    "RULE-COMBAT-014:free-move-prone-removal"
)


def resolve_free_move_prone_removal(
    request: FreeMoveProneRemovalRequest,
) -> FreeMoveProneRemovalResult:
    """Spend free movement to remove Prone from self or a nearby ally."""
    state = request.state
    if request.actor_id in state.free_move_used_entity_ids:
        raise ValueError("an actor may only use free movement once per turn")
    if request.actor_has_enemy_in_close_range:
        raise ValueError("an enemy in Close Range prevents Prone removal")
    if (
        request.target_kind is ProneRemovalTargetKind.ALLY
        and not request.target_in_close_range
    ):
        raise ValueError("Prone removal ally must be in Close Range")
    if not request.target_conditions.has(Condition.PRONE):
        raise ValueError("Prone removal requires a Prone target")

    updated_state = replace(
        state,
        free_move_used_entity_ids=(
            *state.free_move_used_entity_ids,
            request.actor_id,
        ),
    )
    return FreeMoveProneRemovalResult(
        request_id=request.id,
        rule_id=request.rule_id,
        round_state=request.round_state,
        actor_id=request.actor_id,
        target_kind=request.target_kind,
        target_id=request.target_id,
        target_in_close_range=request.target_in_close_range,
        actor_has_enemy_in_close_range=(
            request.actor_has_enemy_in_close_range
        ),
        previous_target_conditions=request.target_conditions,
        target_conditions=request.target_conditions.without_condition(
            Condition.PRONE
        ),
        previous_state=state,
        state=updated_state,
        applied_rule_ids=tuple(
            dict.fromkeys((request.rule_id, FREE_MOVEMENT_RULE_ID))
        ),
    )


def resolve_free_movement(request: FreeMovementRequest) -> FreeMovementResult:
    """Move the active actor along one legal incidental free-move route."""
    state = request.state
    actor = state.placement_for(request.actor_id)
    if request.actor_id in state.free_move_used_entity_ids:
        raise ValueError("an actor may only use free movement once per turn")
    if request.actor_conditions.has(Condition.PRONE):
        raise ValueError("a Prone actor cannot leave their Zone")
    if request.actor_conditions.has(Condition.DEFENCELESS):
        raise ValueError("a Defenceless actor cannot move")
    if request.crosses_obstacle:
        raise ValueError("free movement cannot cross a blocking obstacle")
    if request.crosses_difficult_terrain:
        raise ValueError(
            "Difficult Terrain requires its Athletics movement phase"
        )

    previous_zone_id = actor.zone_id
    for zone_id in request.traversed_zone_ids:
        if not state.graph.contains(zone_id):
            raise ValueError("free movement route references an unknown Zone")
        if not state.graph.are_adjacent(previous_zone_id, zone_id):
            raise ValueError("free movement route must follow Zone links")
        previous_zone_id = zone_id

    for entity_id in request.path_entity_ids:
        crossed = state.placement_for(entity_id)
        if crossed.side_id != actor.side_id:
            raise ValueError("free movement cannot pass through an enemy")

    updated_placements = tuple(
        SpatialEntityPlacement(
            entity_id=placement.entity_id,
            side_id=placement.side_id,
            zone_id=request.destination_zone_id,
        )
        if placement.entity_id == request.actor_id
        else placement
        for placement in state.placements
    )
    updated_state = replace(
        state,
        placements=updated_placements,
        free_move_used_entity_ids=(
            *state.free_move_used_entity_ids,
            request.actor_id,
        ),
    )
    return FreeMovementResult(
        request_id=request.id,
        rule_id=request.rule_id,
        round_state=request.round_state,
        actor_id=request.actor_id,
        speed=request.speed,
        origin_zone_id=actor.zone_id,
        traversed_zone_ids=request.traversed_zone_ids,
        previous_state=state,
        state=updated_state,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    SPEED_MOVEMENT_RULE_ID,
                    ZONE_GRAPH_RULE_ID,
                )
            )
        ),
    )


def resolve_difficult_terrain_free_movement(
    request: DifficultTerrainFreeMovementRequest,
) -> DifficultTerrainFreeMovementResult:
    """Consume one proven terrain crossing as the actor's free movement."""
    if request.rule_id != DIFFICULT_TERRAIN_FREE_MOVEMENT_RULE_ID:
        raise ValueError(
            "Difficult Terrain free movement uses an unknown source rule"
        )
    source = request.free_movement
    traversal = request.terrain_traversal
    if source.actor_id in request.state.free_move_used_entity_ids:
        raise ValueError("an actor may only use free movement once per turn")

    updated_state = replace(
        request.state,
        free_move_used_entity_ids=(
            *request.state.free_move_used_entity_ids,
            source.actor_id,
        ),
    )
    return DifficultTerrainFreeMovementResult(
        request_id=request.id,
        rule_id=request.rule_id,
        free_movement_request=source,
        terrain_traversal=traversal,
        round_state=source.round_state,
        actor_id=source.actor_id,
        speed=source.speed,
        origin_zone_id=traversal.origin_zone_id,
        destination_zone_id=traversal.destination_zone_id,
        previous_conditions=source.actor_conditions,
        conditions=traversal.conditions,
        previous_state=request.state,
        state=updated_state,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    FREE_MOVEMENT_RULE_ID,
                    SPEED_MOVEMENT_RULE_ID,
                    *traversal.applied_rule_ids,
                )
            )
        ),
    )
