from __future__ import annotations

from dataclasses import replace

from towr.domain.combat_surgeon_models import COMBAT_SURGEON_RULE_ID
from towr.domain.combat_surgeon_surgery_models import (
    COMBAT_SURGEON_BATTLE_SURGERY_RULE_ID,
    CombatSurgeonBattleSurgeryActionRequest,
    CombatSurgeonBattleSurgeryActionResult,
    _exacting_request,
    _expected_failure_risk,
    _expected_proof,
    _source_progress,
    _validate_battle_surgery_context,
)
from towr.domain.injury_models import HealingRequirement
from towr.domain.turn_models import ActionExecutionReceipt
from towr.rules.dice import RandomSource
from towr.rules.exacting_test_resolution import (
    resolve_exacting_test_contribution,
)
from towr.rules.test_resolution import TestDecisionProvider
from towr.rules.wound_table import lookup_wound


def execute_combat_surgeon_battle_surgery_action(
    request: CombatSurgeonBattleSurgeryActionRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> CombatSurgeonBattleSurgeryActionResult:
    """Spend one action on Combat Surgeon's Exacting battle surgery."""
    if request.rule_id != COMBAT_SURGEON_BATTLE_SURGERY_RULE_ID:
        raise ValueError("battle surgery uses an unknown source rule")
    _validate_battle_surgery_context(request)
    wound = request.injury_state.wounds[request.wound_sequence - 1]
    entry = lookup_wound(wound.table_total)
    if entry.id is not wound.entry_id:
        raise ValueError("Wound history conflicts with the Wound table")
    if entry.healing is not HealingRequirement.SURGERY_AND_RECOVERY:
        raise ValueError("battle surgery requires a surgery-and-recovery Wound")

    previous_progress = _source_progress(request)
    exacting = resolve_exacting_test_contribution(
        _exacting_request(request, previous_progress),
        rng,
        decisions=decisions,
    )
    progress = replace(previous_progress, exacting=exacting.progress)
    proof = _expected_proof(request, progress)
    failure_risk = _expected_failure_risk(request, exacting)

    turn = request.round_state.active_turn
    assert turn is not None
    slot = turn.action_slots[request.slot_index - 1]
    executed_slot = replace(
        slot,
        execution=ActionExecutionReceipt(
            id=request.id,
            executor_rule_id=request.rule_id,
            source_request_id=request.id,
            result_request_id=exacting.request_id,
            actor_id=request.surgeon_id,
            round_number=request.round_state.round_number,
            slot_index=slot.index,
            declaration=slot.declaration,
        ),
    )
    updated_slots = tuple(
        executed_slot if item.index == request.slot_index else item
        for item in turn.action_slots
    )
    round_state = replace(
        request.round_state,
        active_turn=replace(turn, action_slots=updated_slots),
    )
    return CombatSurgeonBattleSurgeryActionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        exacting=exacting,
        previous_progress=previous_progress,
        progress=progress,
        proof=proof,
        failure_risk=failure_risk,
        previous_state=request.injury_state,
        state=request.injury_state,
        previous_round_state=request.round_state,
        round_state=round_state,
        slot=executed_slot,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    COMBAT_SURGEON_RULE_ID,
                    *exacting.applied_rule_ids,
                    *((failure_risk.rule_id,) if failure_risk else ()),
                )
            )
        ),
    )
