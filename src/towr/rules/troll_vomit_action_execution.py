from __future__ import annotations

from dataclasses import replace

from towr.domain.resolution_models import HazardResolutionRequest
from towr.domain.troll_vomit_models import (
    TROLL_VOMIT_ACTION_EXECUTION_RULE_ID,
    TrollVomitActionExecutionRequest,
    TrollVomitActionExecutionResult,
    _validate_troll_vomit_context,
)
from towr.domain.turn_models import ActionExecutionReceipt
from towr.rules.dice import RandomSource
from towr.rules.hazard_resolution import (
    resolve_hazard,
    resolve_hazard_exposure_application,
)
from towr.rules.injury_resolution import WoundDecisionProvider
from towr.rules.test_resolution import TestDecisionProvider, resolve_test
from towr.rules.troll_hazards import troll_vomit_hazard


def execute_troll_vomit_action(
    request: TrollVomitActionExecutionRequest,
    rng: RandomSource,
    *,
    test_decisions: TestDecisionProvider | None = None,
    wound_decisions: WoundDecisionProvider | None = None,
) -> TrollVomitActionExecutionResult:
    """Execute Troll Vomit as one Ability Improvise Hazard action."""
    if request.rule_id != TROLL_VOMIT_ACTION_EXECUTION_RULE_ID:
        raise ValueError("Troll Vomit request uses an unknown source rule")
    _validate_troll_vomit_context(request)
    turn = request.round_state.active_turn
    assert turn is not None
    slot = turn.action_slots[request.slot_index - 1]
    target = request.target

    exposure = troll_vomit_hazard(
        f"{request.id}:exposure",
        target.avoidance_test.id,
    )
    application = resolve_hazard_exposure_application(
        exposure,
        target.target_effect_immunities,
    )
    if application.blocked:
        raise ValueError("unclassified Troll Vomit cannot be immunity-blocked")
    avoidance_test = resolve_test(
        target.avoidance_test,
        rng,
        decisions=test_decisions,
    )
    hazard_request = HazardResolutionRequest(
        id=f"{request.id}:hazard",
        target_id=request.target.target_id,
        exposure=exposure,
        avoidance_test=avoidance_test,
        target_policy=target.target_policy,
        target_state=target.target_state,
        wound_dice_modifiers=target.wound_dice_modifiers,
        wound_negation_options=target.wound_negation_options,
        additional_profile_wounds=target.additional_profile_wounds,
    )
    hazard = resolve_hazard(
        hazard_request,
        rng,
        decisions=wound_decisions,
    )

    executed_slot = replace(
        slot,
        execution=ActionExecutionReceipt(
            id=request.id,
            executor_rule_id=request.rule_id,
            source_request_id=request.id,
            result_request_id=hazard.request_id,
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
    return TrollVomitActionExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        actor_id=request.actor_id,
        target_id=target.target_id,
        slot_index=request.slot_index,
        exposure=exposure,
        application=application,
        avoidance_test=avoidance_test,
        hazard_request=hazard_request,
        hazard=hazard,
        previous_target_state=target.target_state,
        target_state=hazard.state,
        previous_round_state=request.round_state,
        round_state=updated_round_state,
        slot=executed_slot,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    *application.applied_rule_ids,
                    *avoidance_test.trace.applied_rule_ids,
                    *hazard.applied_rule_ids,
                )
            )
        ),
    )
