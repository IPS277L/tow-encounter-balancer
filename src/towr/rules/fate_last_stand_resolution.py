from __future__ import annotations

from towr.domain.fate_last_stand_models import (
    FATE_LAST_STAND_APPLICATION_RULE_ID,
    FateLastStandApplicationRequest,
    FateLastStandApplicationResult,
    FateLastStandResolutionStep,
    _last_stand_applied_rule_ids,
    _last_stand_effect,
    _last_stand_terminal_state,
    _qualifying_wound,
)


def apply_fate_last_stand(
    request: FateLastStandApplicationRequest,
) -> FateLastStandApplicationResult:
    """Close an accomplished Last Stand feat, then kill its actor."""
    if request.rule_id != FATE_LAST_STAND_APPLICATION_RULE_ID:
        raise ValueError("Last Stand application uses an unknown rule")
    effect = _last_stand_effect(request.burn)
    return FateLastStandApplicationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        session_id=request.session_id,
        actor_id=request.actor_id,
        battle_id=request.battle_id,
        fate_state=request.burn.state,
        previous_injury_state=request.injury_state,
        injury_state=_last_stand_terminal_state(request.injury_state),
        qualifying_wound=_qualifying_wound(
            request.injury_state,
            request.qualifying_wound_sequence,
        ),
        feat_id=effect.feat_id,
        final_scope_reference_id=request.final_scope_reference_id,
        affected_subject_ids=request.affected_subject_ids,
        accomplishment_reference_ids=request.accomplishment_reference_ids,
        feat_accomplished=request.feat_accomplished,
        fits_game_tone_confirmed=request.fits_game_tone_confirmed,
        within_actor_possibility_limits_confirmed=(
            request.within_actor_possibility_limits_confirmed
        ),
        desperate_battle_approval_id=effect.desperate_battle_approval_id,
        gm_adjustment_id=request.gm_adjustment_id,
        test_required=effect.test_required,
        actor_dies_after_feat=effect.actor_dies_after_feat,
        gm_may_adjust_scope=effect.gm_may_adjust_scope,
        resolution_steps=(
            FateLastStandResolutionStep.FEAT_ACCOMPLISHED,
            FateLastStandResolutionStep.ACTOR_DIED,
        ),
        previous_consumed_effect_ids=request.consumed_effect_ids,
        consumed_effect_ids=(
            *request.consumed_effect_ids,
            effect.id,
        ),
        applied_rule_ids=_last_stand_applied_rule_ids(request),
    )
