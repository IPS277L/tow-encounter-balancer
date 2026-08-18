from __future__ import annotations

from dataclasses import replace

from towr.domain.condition_models import (
    Condition,
    ConditionApplicationRequest,
)
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.npc_effect_models import (
    TrollStupidityConditionRemovedRequest,
    TrollStupidityLeadershipRequest,
    TrollStupidityOutcome,
    TrollStupidityResult,
    TrollStupidityStartRequest,
    TrollStupidityState,
    TrollStupidityWoundRequest,
)
from towr.domain.test_models import DiceModifier
from towr.rules.condition_effect_resolution import (
    resolve_condition_application,
)


def troll_stupidity_test_modifiers(
    state: TrollStupidityState,
) -> tuple[DiceModifier, ...]:
    if not isinstance(state, TrollStupidityState):
        raise TypeError("state must be a TrollStupidityState")
    if state.suppressed_until_battle_end:
        return ()
    return (DiceModifier(state.rule_id, -1),)


def start_troll_stupidity(
    request: TrollStupidityStartRequest,
) -> TrollStupidityResult:
    if request.ability_state.suppressed_until_battle_end:
        return _unchanged_result(
            request.id,
            request.target_id,
            request.target_state,
            request.ability_state,
            TrollStupidityOutcome.ALREADY_SUPPRESSED,
        )
    application = resolve_condition_application(
        ConditionApplicationRequest(
            id=f"{request.id}:{request.target_id}:distracted",
            state=request.target_state.conditions,
            condition=Condition.DISTRACTED,
            source_rule_id=request.ability_state.rule_id,
        )
    )
    return TrollStupidityResult(
        request_id=request.id,
        target_id=request.target_id,
        state=replace(request.target_state, conditions=application.state),
        ability_state=request.ability_state,
        outcome=TrollStupidityOutcome.DISTRACTED_ACTIVE,
        condition_application=application,
        applied_rule_ids=application.applied_rule_ids,
    )


def resolve_troll_stupidity_after_wound(
    request: TrollStupidityWoundRequest,
) -> TrollStupidityResult:
    if request.ability_state.suppressed_until_battle_end:
        return _unchanged_result(
            request.id,
            request.target_id,
            request.wound.state,
            request.ability_state,
            TrollStupidityOutcome.ALREADY_SUPPRESSED,
        )
    if request.wound.wounds_inflicted < 1:
        raise ValueError(
            "Stupidity requires an actually inflicted profile Wound"
        )
    return _suppress(
        request.id,
        request.target_id,
        request.wound.state,
        request.ability_state,
        TrollStupidityOutcome.REMOVED_BY_WOUND,
    )


def resolve_troll_stupidity_after_leadership(
    request: TrollStupidityLeadershipRequest,
) -> TrollStupidityResult:
    if request.ability_state.suppressed_until_battle_end:
        return _unchanged_result(
            request.id,
            request.target_id,
            request.target_state,
            request.ability_state,
            TrollStupidityOutcome.ALREADY_SUPPRESSED,
        )
    if not request.leadership_test.succeeded:
        return _unchanged_result(
            request.id,
            request.target_id,
            request.target_state,
            request.ability_state,
            TrollStupidityOutcome.LEADERSHIP_FAILED,
        )
    return _suppress(
        request.id,
        request.target_id,
        request.target_state,
        request.ability_state,
        TrollStupidityOutcome.REMOVED_BY_LEADERSHIP,
    )


def resolve_troll_stupidity_after_condition_removal(
    request: TrollStupidityConditionRemovedRequest,
) -> TrollStupidityResult:
    if request.target_state.conditions.has(Condition.DISTRACTED):
        raise ValueError(
            "the external rule must remove Distracted before Stupidity resolves"
        )
    if request.ability_state.suppressed_until_battle_end:
        return _unchanged_result(
            request.id,
            request.target_id,
            request.target_state,
            request.ability_state,
            TrollStupidityOutcome.ALREADY_SUPPRESSED,
        )
    result = _suppress(
        request.id,
        request.target_id,
        request.target_state,
        request.ability_state,
        TrollStupidityOutcome.REMOVED_EXTERNALLY,
    )
    return replace(
        result,
        applied_rule_ids=(
            request.removal_rule_id,
            request.ability_state.rule_id,
        ),
    )


def _suppress(
    request_id: str,
    target_id: str,
    state: ProfileInjuryState,
    ability_state: TrollStupidityState,
    outcome: TrollStupidityOutcome,
) -> TrollStupidityResult:
    updated_ability = TrollStupidityState(
        rule_id=ability_state.rule_id,
        suppressed_until_battle_end=True,
    )
    return TrollStupidityResult(
        request_id=request_id,
        target_id=target_id,
        state=replace(
            state,
            conditions=state.conditions.without_condition(Condition.DISTRACTED),
        ),
        ability_state=updated_ability,
        outcome=outcome,
        condition_application=None,
        applied_rule_ids=(ability_state.rule_id,),
    )


def _unchanged_result(
    request_id: str,
    target_id: str,
    state: ProfileInjuryState,
    ability_state: TrollStupidityState,
    outcome: TrollStupidityOutcome,
) -> TrollStupidityResult:
    return TrollStupidityResult(
        request_id=request_id,
        target_id=target_id,
        state=state,
        ability_state=ability_state,
        outcome=outcome,
        condition_application=None,
        applied_rule_ids=(ability_state.rule_id,),
    )
