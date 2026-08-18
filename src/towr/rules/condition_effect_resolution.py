from __future__ import annotations

from towr.domain.condition_models import (
    ConditionApplicationRequest,
    ConditionApplicationResult,
)
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.resolution_models import (
    ConditionAfterGiveGroundRequest,
    ConditionAfterGiveGroundResult,
    TargetInjuryState,
)


def resolve_condition_application(
    request: ConditionApplicationRequest,
) -> ConditionApplicationResult:
    was_already_present = request.state.has(request.condition)
    blocking_immunity = next(
        (
            immunity
            for immunity in request.immunities
            if immunity.classification is request.classification
        ),
        None,
    )
    if blocking_immunity is not None:
        return ConditionApplicationResult(
            request_id=request.id,
            state=request.state,
            condition=request.condition,
            was_already_present=was_already_present,
            blocked=True,
            source_rule_id=request.source_rule_id,
            blocked_by_rule_id=blocking_immunity.rule_id,
            applied_rule_ids=(blocking_immunity.rule_id,),
        )
    return ConditionApplicationResult(
        request_id=request.id,
        state=request.state.with_condition(request.condition),
        condition=request.condition,
        was_already_present=was_already_present,
        blocked=False,
        source_rule_id=request.source_rule_id,
        blocked_by_rule_id=None,
        applied_rule_ids=(request.source_rule_id,),
    )


def resolve_condition_after_give_ground(
    request: ConditionAfterGiveGroundRequest,
    state: TargetInjuryState,
) -> ConditionAfterGiveGroundResult:
    if not isinstance(state, (CharacterInjuryState, ProfileInjuryState)):
        raise TypeError("state must be a TargetInjuryState")
    was_already_present = state.conditions.has(request.condition)
    conditions = state.conditions.with_condition(request.condition)
    if isinstance(state, CharacterInjuryState):
        updated_state: TargetInjuryState = CharacterInjuryState(
            wounds=state.wounds,
            conditions=conditions,
            active_wound_effects=state.active_wound_effects,
            dead=state.dead,
        )
    else:
        updated_state = ProfileInjuryState(
            wounds=state.wounds,
            wound_limit=state.wound_limit,
            conditions=conditions,
            defeated=state.defeated,
        )
    return ConditionAfterGiveGroundResult(
        resolution_id=request.resolution_id,
        state=updated_state,
        condition=request.condition,
        was_already_present=was_already_present,
        applied_rule_ids=(request.rule_id,),
    )
