from __future__ import annotations

from dataclasses import replace

from towr.domain.resolution_models import ZoneHazardResolutionRequest
from towr.domain.soporific_breath_models import (
    SOPORIFIC_BREATH_ACTION_EXECUTION_RULE_ID,
    SOPORIFIC_BREATH_RULE_ID,
    SoporificBreathActionExecutionRequest,
    SoporificBreathActionExecutionResult,
    _validate_soporific_breath_context,
)
from towr.domain.turn_models import ActionExecutionReceipt
from towr.rules.dice import RandomSource
from towr.rules.injury_resolution import WoundDecisionProvider
from towr.rules.soporific_breath import soporific_breath_hazard
from towr.rules.test_resolution import TestDecisionProvider
from towr.rules.zone_hazard_resolution import resolve_zone_hazard


def execute_soporific_breath_action(
    request: SoporificBreathActionExecutionRequest,
    rng: RandomSource,
    *,
    test_decisions: TestDecisionProvider | None = None,
    wound_decisions: WoundDecisionProvider | None = None,
) -> SoporificBreathActionExecutionResult:
    """Execute Soporific Breath against everyone in one selected Zone."""
    if request.rule_id != SOPORIFIC_BREATH_ACTION_EXECUTION_RULE_ID:
        raise ValueError("Soporific Breath request uses an unknown source rule")
    _validate_soporific_breath_context(request)
    turn = request.round_state.active_turn
    assert turn is not None
    slot = turn.action_slots[request.slot_index - 1]

    zone_hazard_request = ZoneHazardResolutionRequest(
        id=f"{request.id}:zone-resolution",
        source=soporific_breath_hazard(f"{request.id}:zone-hazard"),
        targets=request.targets,
    )
    zone_hazard = resolve_zone_hazard(
        zone_hazard_request,
        rng,
        test_decisions=test_decisions,
        wound_decisions=wound_decisions,
    )
    executed_slot = replace(
        slot,
        execution=ActionExecutionReceipt(
            id=request.id,
            executor_rule_id=request.rule_id,
            source_request_id=request.id,
            result_request_id=zone_hazard.request_id,
            actor_id=request.actor_id,
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
    return SoporificBreathActionExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        actor_id=request.actor_id,
        slot_index=request.slot_index,
        target_zone_id=request.target_zone_id,
        zone_hazard_request=zone_hazard_request,
        zone_hazard=zone_hazard,
        previous_round_state=request.round_state,
        round_state=updated_round_state,
        previous_spatial_state=request.spatial_state,
        spatial_state=request.spatial_state,
        slot=executed_slot,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    SOPORIFIC_BREATH_RULE_ID,
                    *zone_hazard.applied_rule_ids,
                    *(
                        rule_id
                        for result in zone_hazard.targets
                        if result.avoidance_test is not None
                        for rule_id in (
                            result.avoidance_test.trace.applied_rule_ids
                        )
                    ),
                )
            )
        ),
    )
