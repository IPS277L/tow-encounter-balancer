from __future__ import annotations

from dataclasses import replace

from towr.domain.condition_models import (
    Condition,
    ConditionApplicationRequest,
)
from towr.domain.movement_models import (
    DifficultTerrainOutcome,
    DifficultTerrainTraversalRequest,
    DifficultTerrainTraversalResult,
)
from towr.domain.spatial_models import SpatialEntityPlacement
from towr.rules.condition_effect_resolution import (
    resolve_condition_application,
)
from towr.rules.dice import RandomSource
from towr.rules.spatial_resolution import ZONE_GRAPH_RULE_ID
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


DIFFICULT_TERRAIN_TRAVERSAL_RULE_ID = (
    "RULE-COMBAT-013:difficult-terrain-traversal"
)


def resolve_difficult_terrain_traversal(
    request: DifficultTerrainTraversalRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> DifficultTerrainTraversalResult:
    """Cross one Difficult Terrain boundary, then resolve its Athletics Test."""
    if request.rule_id != DIFFICULT_TERRAIN_TRAVERSAL_RULE_ID:
        raise ValueError("Difficult Terrain request uses an unknown source rule")
    if request.actor_conditions.has(Condition.PRONE):
        raise ValueError("Prone creatures cannot leave their Zone")
    if request.actor_conditions.has(Condition.DEFENCELESS):
        raise ValueError("Defenceless creatures cannot move")
    if request.crosses_obstacle:
        raise ValueError("Difficult Terrain cannot cross a blocking obstacle")

    state = request.state
    actor = state.placement_for(request.actor_id)
    if not state.graph.contains(request.destination_zone_id):
        raise ValueError("Difficult Terrain destination is unknown")
    if not state.graph.are_adjacent(
        actor.zone_id,
        request.destination_zone_id,
    ):
        raise ValueError("Difficult Terrain must cross one Zone boundary")
    for entity_id in request.path_entity_ids:
        crossed = state.placement_for(entity_id)
        if crossed.side_id != actor.side_id:
            raise ValueError("Difficult Terrain cannot pass through an enemy")

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
    usage = state.difficult_terrain_tested_entity_ids
    updated_usage = (
        usage if request.actor_id in usage else (*usage, request.actor_id)
    )
    updated_state = replace(
        state,
        placements=updated_placements,
        difficult_terrain_tested_entity_ids=updated_usage,
    )

    athletics_result = resolve_test(
        request.athletics_test,
        rng,
        decisions=decisions,
    )
    if athletics_result.succeeded:
        outcome = DifficultTerrainOutcome.CROSSED_SAFELY
        prone_application = None
        conditions = request.actor_conditions
    else:
        outcome = DifficultTerrainOutcome.CROSSED_AND_FELL_PRONE
        prone_application = resolve_condition_application(
            ConditionApplicationRequest(
                id=f"{request.id}:prone",
                state=request.actor_conditions,
                condition=Condition.PRONE,
                source_rule_id=request.rule_id,
            )
        )
        conditions = prone_application.state

    return DifficultTerrainTraversalResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        round_state=request.round_state,
        actor_id=request.actor_id,
        skill=request.skill,
        athletics_test_request=request.athletics_test,
        athletics_test_result=athletics_result,
        outcome=outcome,
        origin_zone_id=actor.zone_id,
        destination_zone_id=request.destination_zone_id,
        path_entity_ids=request.path_entity_ids,
        crosses_obstacle=request.crosses_obstacle,
        previous_conditions=request.actor_conditions,
        conditions=conditions,
        prone_application=prone_application,
        previous_state=state,
        state=updated_state,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    DIFFICULT_TERRAIN_TRAVERSAL_RULE_ID,
                    ZONE_GRAPH_RULE_ID,
                    *athletics_result.trace.applied_rule_ids,
                    *(
                        prone_application.applied_rule_ids
                        if prone_application is not None
                        else ()
                    ),
                )
            )
        ),
    )
