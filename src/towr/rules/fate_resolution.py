from __future__ import annotations

from towr.domain.fate_models import (
    FATE_BURN_RULE_ID,
    FATE_LAST_STAND_RULE_ID,
    FATE_NEAR_MISS_RULE_ID,
    FATE_REFRESH_RULE_ID,
    FATE_SECOND_ACTION_RULE_ID,
    FATE_SESSION_RULE_ID,
    FATE_TACTICAL_RETREAT_RULE_ID,
    FATE_UNMITIGATED_SUCCESS_RULE_ID,
    FateBurnRequest,
    FateBurnResult,
    FateGloriousSpendRequest,
    FateGloriousSpendResult,
    FateRefreshRequest,
    FateRefreshResult,
    FateSecondActionSpendRequest,
    FateSecondActionSpendResult,
    FateTacticalRetreatSpendRequest,
    FateTacticalRetreatSpendResult,
    _expected_fate_burn,
    _expected_fate_glorious_spend,
    _expected_fate_refresh,
    _expected_fate_second_action_spend,
    _expected_fate_tactical_retreat_spend,
    _fate_spend_rule_ids,
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
        applied_rule_ids=_fate_spend_rule_ids(
            request.state,
            request.rule_id,
        ),
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
        applied_rule_ids=_fate_spend_rule_ids(
            request.state,
            *slot_result.applied_rule_ids,
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
        applied_rule_ids=_fate_spend_rule_ids(
            request.state,
            *retreat_result.applied_rule_ids,
        ),
    )


def refresh_fate(request: FateRefreshRequest) -> FateRefreshResult:
    """Restore the actor to their rating after a GM-approved mid-session break."""
    if request.rule_id != FATE_REFRESH_RULE_ID:
        raise ValueError("Fate refresh uses an unknown rule")
    refresh, state = _expected_fate_refresh(request)
    return FateRefreshResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        previous_state=request.state,
        state=state,
        refresh=refresh,
        applied_rule_ids=(FATE_SESSION_RULE_ID, request.rule_id),
    )


def burn_fate(request: FateBurnRequest) -> FateBurnResult:
    """Permanently reduce Fate and emit the selected typed effect request."""
    if request.rule_id not in {
        FATE_UNMITIGATED_SUCCESS_RULE_ID,
        FATE_NEAR_MISS_RULE_ID,
        FATE_LAST_STAND_RULE_ID,
    }:
        raise ValueError("Fate burn uses an unknown rule")
    burn, proof, state, effect_request = _expected_fate_burn(request)
    return FateBurnResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        previous_state=request.state,
        state=state,
        burn=burn,
        proof=proof,
        effect_request=effect_request,
        applied_rule_ids=(
            FATE_SESSION_RULE_ID,
            FATE_BURN_RULE_ID,
            request.rule_id,
        ),
    )
