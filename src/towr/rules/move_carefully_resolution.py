from __future__ import annotations

from dataclasses import replace

from towr.domain.condition_models import Condition
from towr.domain.movement_models import (
    MoveCarefullyActionExecutionRequest,
    MoveCarefullyActionExecutionResult,
    MoveCarefullySearchChoice,
    MovementSpeed,
)
from towr.domain.spatial_models import SpatialEntityPlacement
from towr.domain.turn_models import (
    ActionExecutionReceipt,
    CombatActionKind,
    ManoeuvreKind,
)
from towr.rules.dice import RandomSource
from towr.rules.free_movement_resolution import (
    FREE_MOVEMENT_RULE_ID,
    SPEED_MOVEMENT_RULE_ID,
)
from towr.rules.spatial_resolution import ZONE_GRAPH_RULE_ID
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


MOVE_CAREFULLY_ACTION_EXECUTION_RULE_ID = (
    "RULE-COMBAT-014:move-carefully-action-execution"
)


def execute_move_carefully_action(
    request: MoveCarefullyActionExecutionRequest,
    rng: RandomSource | None = None,
    *,
    decisions: TestDecisionProvider | None = None,
) -> MoveCarefullyActionExecutionResult:
    """Use free movement through Difficult Terrain and optionally search."""
    if request.rule_id != MOVE_CAREFULLY_ACTION_EXECUTION_RULE_ID:
        raise ValueError("Move Carefully request uses an unknown source rule")
    movement = request.free_movement
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
        or slot.declaration.manoeuvre
        is not ManoeuvreKind.MOVE_CAREFULLY
    ):
        raise ValueError("only Move Carefully can use this executor")
    if slot.executed:
        raise ValueError("the Move Carefully slot has already been executed")

    if movement.speed is MovementSpeed.SLOW:
        raise ValueError("Slow creatures cannot Move Carefully")
    if movement.actor_conditions.has(Condition.BURDENED):
        raise ValueError("Burdened creatures cannot use Manoeuvres")
    if movement.actor_conditions.has(Condition.PRONE):
        raise ValueError("Prone creatures cannot leave their Zone")
    if movement.actor_conditions.has(Condition.DEFENCELESS):
        raise ValueError("Defenceless creatures cannot move")
    state = request.spatial_state
    if movement.actor_id in state.free_move_used_entity_ids:
        raise ValueError("the actor's free movement was already used")
    if movement.crosses_obstacle:
        raise ValueError("Move Carefully cannot cross a blocking obstacle")
    if (
        request.search_choice is MoveCarefullySearchChoice.SEARCH
        and rng is None
    ):
        raise ValueError("Move Carefully search requires an RNG source")

    actor = state.placement_for(movement.actor_id)
    previous_zone_id = actor.zone_id
    for zone_id in movement.traversed_zone_ids:
        if not state.graph.contains(zone_id):
            raise ValueError("Move Carefully route references an unknown Zone")
        if not state.graph.are_adjacent(previous_zone_id, zone_id):
            raise ValueError("Move Carefully route must follow Zone links")
        previous_zone_id = zone_id
    for entity_id in movement.path_entity_ids:
        crossed = state.placement_for(entity_id)
        if crossed.side_id != actor.side_id:
            raise ValueError("Move Carefully cannot pass through an enemy")

    updated_placements = tuple(
        SpatialEntityPlacement(
            entity_id=placement.entity_id,
            side_id=placement.side_id,
            zone_id=movement.destination_zone_id,
        )
        if placement.entity_id == movement.actor_id
        else placement
        for placement in state.placements
    )
    updated_spatial_state = replace(
        state,
        placements=updated_placements,
        free_move_used_entity_ids=(
            *state.free_move_used_entity_ids,
            movement.actor_id,
        ),
    )

    awareness_result = None
    if request.search_choice is MoveCarefullySearchChoice.SEARCH:
        assert request.awareness_test is not None
        assert rng is not None
        awareness_result = resolve_test(
            request.awareness_test,
            rng,
            decisions=decisions,
        )
    receipt_result_id = (
        awareness_result.trace.request_id
        if awareness_result is not None
        else request.id
    )
    executed_slot = replace(
        slot,
        execution=ActionExecutionReceipt(
            id=request.id,
            executor_rule_id=request.rule_id,
            source_request_id=request.id,
            result_request_id=receipt_result_id,
            actor_id=movement.actor_id,
            round_number=request.round_state.round_number,
            slot_index=slot.index,
            declaration=slot.declaration,
        ),
    )
    updated_slots = tuple(
        executed_slot if item.index == request.slot_index else item
        for item in turn.action_slots
    )
    updated_round_state = replace(
        request.round_state,
        active_turn=replace(turn, action_slots=updated_slots),
    )

    return MoveCarefullyActionExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        actor_id=movement.actor_id,
        slot_index=request.slot_index,
        speed=movement.speed,
        origin_zone_id=actor.zone_id,
        traversed_zone_ids=movement.traversed_zone_ids,
        previous_conditions=movement.actor_conditions,
        conditions=movement.actor_conditions,
        search_choice=request.search_choice,
        search_skill=request.search_skill,
        awareness_test_request=request.awareness_test,
        awareness_test_result=awareness_result,
        previous_round_state=request.round_state,
        round_state=updated_round_state,
        previous_spatial_state=state,
        spatial_state=updated_spatial_state,
        slot=executed_slot,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    FREE_MOVEMENT_RULE_ID,
                    SPEED_MOVEMENT_RULE_ID,
                    ZONE_GRAPH_RULE_ID,
                    *(
                        awareness_result.trace.applied_rule_ids
                        if awareness_result is not None
                        else ()
                    ),
                )
            )
        ),
    )
