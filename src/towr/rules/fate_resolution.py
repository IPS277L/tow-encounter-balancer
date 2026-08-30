from __future__ import annotations

from towr.domain.fate_models import (
    FATE_SECOND_ACTION_RULE_ID,
    FATE_SESSION_RULE_ID,
    FATE_TACTICAL_RETREAT_RULE_ID,
    FateGloriousSpendRequest,
    FateGloriousSpendResult,
    FateSecondActionSpendRequest,
    FateSecondActionSpendResult,
    FateTacticalRetreatSpendRequest,
    FateTacticalRetreatSpendResult,
    _expected_fate_glorious_spend,
    _expected_fate_second_action_spend,
    _expected_fate_tactical_retreat_spend,
)
from towr.domain.test_models import FATE_GLORIOUS_RULE_ID
from towr.rules.retreat_resolution import secure_group_retreat
from towr.rules.turn_resolution import reserve_combat_action_slot


def spend_fate_for_glorious(
    request: FateGloriousSpendRequest,
) -> FateGloriousSpendResult:
    """Spend one session Fate before or after the initial roll."""
    if request.rule_id != FATE_GLORIOUS_RULE_ID:
        raise ValueError("Fate Glorious spend uses an unknown rule")
    spend, proof, state, test = _expected_fate_glorious_spend(request)
    return FateGloriousSpendResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        previous_state=request.state,
        state=state,
        spend=spend,
        proof=proof,
        test=test,
        applied_rule_ids=(FATE_SESSION_RULE_ID, request.rule_id),
    )


def spend_fate_for_second_action(
    request: FateSecondActionSpendRequest,
) -> FateSecondActionSpendResult:
    """Spend Fate and atomically reserve its bound second action slot."""
    if request.rule_id != FATE_SECOND_ACTION_RULE_ID:
        raise ValueError("Fate second action spend uses an unknown rule")
    spend, proof, state = _expected_fate_second_action_spend(request)
    slot_result = reserve_combat_action_slot(
        request.slot_request,
        fate_proof=proof,
    )
    return FateSecondActionSpendResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        previous_state=request.state,
        state=state,
        spend=spend,
        proof=proof,
        slot_result=slot_result,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    FATE_SESSION_RULE_ID,
                    *slot_result.applied_rule_ids,
                )
            )
        ),
    )


def spend_fate_for_tactical_retreat(
    request: FateTacticalRetreatSpendRequest,
) -> FateTacticalRetreatSpendResult:
    """Spend Fate and atomically bind the actor as the group rearguard."""
    if request.rule_id != FATE_TACTICAL_RETREAT_RULE_ID:
        raise ValueError("Fate Tactical Retreat spend uses an unknown rule")
    spend, proof, state = _expected_fate_tactical_retreat_spend(request)
    retreat_result = secure_group_retreat(
        request.retreat,
        fate_proof=proof,
    )
    return FateTacticalRetreatSpendResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        previous_state=request.state,
        state=state,
        spend=spend,
        proof=proof,
        retreat_result=retreat_result,
        applied_rule_ids=(
            FATE_SESSION_RULE_ID,
            *retreat_result.applied_rule_ids,
        ),
    )
