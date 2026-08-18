from __future__ import annotations

from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.resolution_models import (
    ConditionAfterGiveGroundRequest,
    ConditionAfterGiveGroundResult,
    TargetInjuryState,
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
