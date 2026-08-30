from __future__ import annotations

from towr.domain.fate_unmitigated_success_models import (
    FATE_UNMITIGATED_SUCCESS_APPLICATION_RULE_ID,
    FateUnmitigatedSuccessApplicationRequest,
    FateUnmitigatedSuccessApplicationResult,
    _classify_basic_outcome,
    _unmitigated_success_applied_rule_ids,
    _unmitigated_success_effect,
)


def apply_fate_unmitigated_success(
    request: FateUnmitigatedSuccessApplicationRequest,
) -> FateUnmitigatedSuccessApplicationResult:
    """Consume the effect without rerolling or rewriting its exact Test."""
    if request.rule_id != FATE_UNMITIGATED_SUCCESS_APPLICATION_RULE_ID:
        raise ValueError("Unmitigated Success application uses an unknown rule")
    effect = _unmitigated_success_effect(request.burn)
    return FateUnmitigatedSuccessApplicationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        session_id=request.session_id,
        actor_id=request.actor_id,
        fate_state=request.burn.state,
        test_result=request.test_result,
        ordinary_outcome=_classify_basic_outcome(request.test_result.successes),
        outcome=effect.minimum_outcome,
        outcome_reference_id=request.outcome_reference_id,
        gm_scope_agreement_id=effect.gm_scope_agreement_id,
        usual_outcome_superseded=effect.usual_outcome_superseded,
        realistically_possible_outcome_confirmed=(
            request.realistically_possible_outcome_confirmed
        ),
        is_attack=request.is_attack,
        killed_enemy_ids=request.killed_enemy_ids,
        wounds_inflicted=request.wounds_inflicted,
        previous_consumed_effect_ids=request.consumed_effect_ids,
        consumed_effect_ids=(*request.consumed_effect_ids, effect.id),
        applied_rule_ids=_unmitigated_success_applied_rule_ids(request),
    )
