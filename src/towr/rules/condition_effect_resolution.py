from __future__ import annotations

from towr.domain.condition_models import (
    ConditionApplicationRequest,
    ConditionApplicationResult,
    EffectApplicationRequest,
)
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.resolution_models import (
    ConditionAfterGiveGroundRequest,
    ConditionAfterGiveGroundResult,
    TargetInjuryState,
)
from towr.rules.effect_resolution import resolve_effect_application


def resolve_condition_application(
    request: ConditionApplicationRequest,
) -> ConditionApplicationResult:
    was_already_present = request.state.has(request.condition)
    effect = resolve_effect_application(
        EffectApplicationRequest(
            id=request.id,
            source_rule_id=request.source_rule_id,
            classification=request.classification,
            immunities=request.immunities,
        )
    )
    if effect.blocked:
        return ConditionApplicationResult(
            request_id=request.id,
            state=request.state,
            condition=request.condition,
            was_already_present=was_already_present,
            blocked=True,
            source_rule_id=request.source_rule_id,
            blocked_by_rule_id=effect.blocked_by_rule_id,
            applied_rule_ids=effect.applied_rule_ids,
        )
    return ConditionApplicationResult(
        request_id=request.id,
        state=request.state.with_condition(request.condition),
        condition=request.condition,
        was_already_present=was_already_present,
        blocked=False,
        source_rule_id=request.source_rule_id,
        blocked_by_rule_id=None,
        applied_rule_ids=effect.applied_rule_ids,
    )


def resolve_condition_after_give_ground(
    request: ConditionAfterGiveGroundRequest,
    state: TargetInjuryState,
) -> ConditionAfterGiveGroundResult:
    if not isinstance(state, (CharacterInjuryState, ProfileInjuryState)):
        raise TypeError("state must be a TargetInjuryState")
    application = resolve_condition_application(
        ConditionApplicationRequest(
            id=(
                f"{request.resolution_id}:{request.rule_id}:"
                "after-give-ground-condition"
            ),
            state=state.conditions,
            condition=request.condition,
            source_rule_id=request.rule_id,
            classification=request.classification,
            immunities=request.target_effect_immunities,
        )
    )
    if isinstance(state, CharacterInjuryState):
        updated_state: TargetInjuryState = CharacterInjuryState(
            wounds=state.wounds,
            conditions=application.state,
            active_wound_effects=state.active_wound_effects,
            dead=state.dead,
        )
    else:
        updated_state = ProfileInjuryState(
            wounds=state.wounds,
            wound_limit=state.wound_limit,
            conditions=application.state,
            defeated=state.defeated,
        )
    return ConditionAfterGiveGroundResult(
        resolution_id=request.resolution_id,
        state=updated_state,
        application=application,
    )
