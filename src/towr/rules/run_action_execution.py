from __future__ import annotations

from dataclasses import replace

from towr.domain.condition_models import (
    Condition,
    ConditionApplicationRequest,
)
from towr.domain.movement_models import (
    DifficultTerrainRunActionExecutionRequest,
    DifficultTerrainRunActionExecutionResult,
    MovementSpeed,
    RunAthleticsExtensionRequest,
    RunAthleticsExtensionResult,
    RunAthleticsOutcome,
    RunActionExecutionRequest,
    RunActionExecutionResult,
)
from towr.domain.spatial_models import SpatialEntityPlacement
from towr.domain.turn_models import (
    ActionExecutionReceipt,
    CombatActionKind,
    ManoeuvreKind,
)
from towr.rules.free_movement_resolution import SPEED_MOVEMENT_RULE_ID
from towr.rules.condition_effect_resolution import (
    resolve_condition_application,
)
from towr.rules.dice import RandomSource
from towr.rules.spatial_resolution import ZONE_GRAPH_RULE_ID
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


RUN_ACTION_EXECUTION_RULE_ID = "RULE-COMBAT-014:run-action-execution"
DIFFICULT_TERRAIN_RUN_ACTION_EXECUTION_RULE_ID = (
    "RULE-COMBAT-014:difficult-terrain-run-action-execution"
)
RUN_ATHLETICS_EXTENSION_RULE_ID = (
    "RULE-COMBAT-014:run-athletics-extension"
)


def execute_run_action(
    request: RunActionExecutionRequest,
) -> RunActionExecutionResult:
    """Move one extra Zone and complete one reserved Run action slot."""
    turn = request.round_state.active_turn
    assert turn is not None
    if request.slot_index > len(turn.action_slots):
        raise ValueError("the requested action slot has not been reserved")
    earlier_slots = turn.action_slots[: request.slot_index - 1]
    if any(not slot.executed for slot in earlier_slots):
        raise ValueError("earlier action slots must be executed first")

    slot = turn.action_slots[request.slot_index - 1]
    if (
        slot.declaration.kind is not CombatActionKind.MANOEUVRE
        or slot.declaration.manoeuvre is not ManoeuvreKind.RUN
    ):
        raise ValueError("only a Run Manoeuvre slot can use this executor")
    if slot.executed:
        raise ValueError("the Run action slot has already been executed")

    if request.speed is MovementSpeed.SLOW:
        raise ValueError("Slow creatures cannot Run")
    if request.actor_conditions.has(Condition.BURDENED):
        raise ValueError("Burdened creatures cannot use Manoeuvres")
    if request.actor_conditions.has(Condition.PRONE):
        raise ValueError("Prone creatures cannot leave their Zone")
    if request.actor_conditions.has(Condition.DEFENCELESS):
        raise ValueError("Defenceless creatures cannot move")
    if request.crosses_obstacle:
        raise ValueError("Run cannot cross a blocking obstacle")
    if request.crosses_difficult_terrain:
        raise ValueError(
            "Difficult Terrain requires its Athletics movement phase"
        )

    spatial_state = request.spatial_state
    actor = spatial_state.placement_for(request.actor_id)
    if not spatial_state.graph.contains(request.destination_zone_id):
        raise ValueError("Run destination references an unknown Zone")
    if not spatial_state.graph.are_adjacent(
        actor.zone_id,
        request.destination_zone_id,
    ):
        raise ValueError("Run must cross exactly one Zone boundary")
    for entity_id in request.path_entity_ids:
        crossed = spatial_state.placement_for(entity_id)
        if crossed.side_id != actor.side_id:
            raise ValueError("Run cannot pass through an enemy")

    updated_placements = tuple(
        SpatialEntityPlacement(
            entity_id=placement.entity_id,
            side_id=placement.side_id,
            zone_id=request.destination_zone_id,
        )
        if placement.entity_id == request.actor_id
        else placement
        for placement in spatial_state.placements
    )
    updated_spatial_state = replace(
        spatial_state,
        placements=updated_placements,
    )

    executed_slot = replace(
        slot,
        execution=ActionExecutionReceipt(
            id=request.id,
            executor_rule_id=RUN_ACTION_EXECUTION_RULE_ID,
            source_request_id=request.id,
            result_request_id=request.id,
        ),
    )
    updated_slots = tuple(
        executed_slot if item.index == request.slot_index else item
        for item in turn.action_slots
    )
    updated_turn = replace(turn, action_slots=updated_slots)
    updated_round_state = replace(
        request.round_state,
        active_turn=updated_turn,
    )

    return RunActionExecutionResult(
        request_id=request.id,
        actor_id=request.actor_id,
        slot_index=request.slot_index,
        speed=request.speed,
        origin_zone_id=actor.zone_id,
        destination_zone_id=request.destination_zone_id,
        previous_round_state=request.round_state,
        round_state=updated_round_state,
        previous_spatial_state=spatial_state,
        spatial_state=updated_spatial_state,
        slot=executed_slot,
        applied_rule_ids=(
            RUN_ACTION_EXECUTION_RULE_ID,
            SPEED_MOVEMENT_RULE_ID,
            ZONE_GRAPH_RULE_ID,
        ),
    )


def execute_difficult_terrain_run_action(
    request: DifficultTerrainRunActionExecutionRequest,
) -> DifficultTerrainRunActionExecutionResult:
    """Complete a reserved Run using one proven terrain crossing."""
    if request.rule_id != DIFFICULT_TERRAIN_RUN_ACTION_EXECUTION_RULE_ID:
        raise ValueError("terrain Run uses an unknown source rule")
    source = request.run_action
    traversal = request.terrain_traversal
    turn = request.round_state.active_turn
    assert turn is not None
    if source.slot_index > len(turn.action_slots):
        raise ValueError("the requested action slot has not been reserved")
    earlier_slots = turn.action_slots[: source.slot_index - 1]
    if any(not slot.executed for slot in earlier_slots):
        raise ValueError("earlier action slots must be executed first")
    slot = turn.action_slots[source.slot_index - 1]
    if (
        slot.declaration.kind is not CombatActionKind.MANOEUVRE
        or slot.declaration.manoeuvre is not ManoeuvreKind.RUN
    ):
        raise ValueError("only a Run Manoeuvre slot can use this executor")
    if slot.executed:
        raise ValueError("the Run action slot has already been executed")
    if source.speed is MovementSpeed.SLOW:
        raise ValueError("Slow creatures cannot Run")
    if source.actor_conditions.has(Condition.BURDENED):
        raise ValueError("Burdened creatures cannot use Manoeuvres")

    executed_slot = replace(
        slot,
        execution=ActionExecutionReceipt(
            id=request.id,
            executor_rule_id=request.rule_id,
            source_request_id=request.id,
            result_request_id=traversal.request_id,
        ),
    )
    updated_slots = tuple(
        executed_slot if item.index == source.slot_index else item
        for item in turn.action_slots
    )
    updated_round_state = replace(
        request.round_state,
        active_turn=replace(turn, action_slots=updated_slots),
    )
    return DifficultTerrainRunActionExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        run_action_request=source,
        terrain_traversal=traversal,
        actor_id=source.actor_id,
        slot_index=source.slot_index,
        speed=source.speed,
        origin_zone_id=traversal.origin_zone_id,
        destination_zone_id=traversal.destination_zone_id,
        previous_conditions=source.actor_conditions,
        conditions=traversal.conditions,
        previous_round_state=request.round_state,
        round_state=updated_round_state,
        previous_spatial_state=request.spatial_state,
        spatial_state=request.spatial_state,
        slot=executed_slot,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    RUN_ACTION_EXECUTION_RULE_ID,
                    SPEED_MOVEMENT_RULE_ID,
                    *traversal.applied_rule_ids,
                )
            )
        ),
    )


def resolve_run_athletics_extension(
    request: RunAthleticsExtensionRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> RunAthleticsExtensionResult:
    """Resolve the optional Athletics Test for Run's second extra Zone."""
    if request.rule_id != RUN_ATHLETICS_EXTENSION_RULE_ID:
        raise ValueError("Run Athletics request uses an unknown source rule")
    if (
        request.base_run.actor_id
        in request.base_run.spatial_state.difficult_terrain_tested_entity_ids
    ):
        raise ValueError(
            "Run Athletics is unavailable after a Difficult Terrain Test"
        )
    if request.actor_conditions.has(Condition.BURDENED):
        raise ValueError("Burdened creatures cannot continue a Run")
    if request.actor_conditions.has(Condition.PRONE):
        raise ValueError("Prone creatures cannot leave their Zone")
    if request.actor_conditions.has(Condition.DEFENCELESS):
        raise ValueError("Defenceless creatures cannot move")
    if request.crosses_obstacle:
        raise ValueError("Run extension cannot cross a blocking obstacle")
    if request.crosses_difficult_terrain:
        raise ValueError(
            "Run Athletics cannot also resolve Difficult Terrain"
        )

    spatial_state = request.base_run.spatial_state
    actor = spatial_state.placement_for(request.base_run.actor_id)
    if not spatial_state.graph.contains(request.destination_zone_id):
        raise ValueError("Run extension references an unknown Zone")
    if not spatial_state.graph.are_adjacent(
        actor.zone_id,
        request.destination_zone_id,
    ):
        raise ValueError("Run extension must target one adjacent Zone")
    for entity_id in request.path_entity_ids:
        crossed = spatial_state.placement_for(entity_id)
        if crossed.side_id != actor.side_id:
            raise ValueError("Run extension cannot pass through an enemy")

    test_result = resolve_test(
        request.athletics_test,
        rng,
        decisions=decisions,
    )
    if test_result.succeeded:
        outcome = RunAthleticsOutcome.MOVED_EXTRA_ZONE
        updated_placements = tuple(
            SpatialEntityPlacement(
                entity_id=placement.entity_id,
                side_id=placement.side_id,
                zone_id=request.destination_zone_id,
            )
            if placement.entity_id == request.base_run.actor_id
            else placement
            for placement in spatial_state.placements
        )
        updated_spatial_state = replace(
            spatial_state,
            placements=updated_placements,
        )
        stagger_application = None
        conditions = request.actor_conditions
    else:
        updated_spatial_state = spatial_state
        stagger_application = resolve_condition_application(
            ConditionApplicationRequest(
                id=f"{request.id}:staggered",
                state=request.actor_conditions,
                condition=Condition.STAGGERED,
                source_rule_id=request.rule_id,
            )
        )
        conditions = stagger_application.state
        outcome = (
            RunAthleticsOutcome.FAILED_ALREADY_STAGGERED
            if stagger_application.was_already_present
            else RunAthleticsOutcome.FAILED_STAGGERED
        )

    return RunAthleticsExtensionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        actor_id=request.base_run.actor_id,
        skill=request.skill,
        base_run=request.base_run,
        athletics_test_request=request.athletics_test,
        athletics_test_result=test_result,
        outcome=outcome,
        destination_zone_id=request.destination_zone_id,
        previous_conditions=request.actor_conditions,
        conditions=conditions,
        stagger_application=stagger_application,
        previous_spatial_state=spatial_state,
        spatial_state=updated_spatial_state,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    ZONE_GRAPH_RULE_ID,
                    *test_result.trace.applied_rule_ids,
                )
            )
        ),
    )
