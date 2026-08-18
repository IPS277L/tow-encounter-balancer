from __future__ import annotations

from dataclasses import replace

from towr.domain.condition_models import (
    Condition,
    ConditionApplicationRequest,
    EffectApplicationRequest,
    EffectClassification,
)
from towr.domain.resolution_models import (
    CowardlyFlightRequest,
    CowardlyFlightResult,
    CowardlyFlightWillpowerRequest,
    CowardlyFlightWillpowerResult,
    GiveGroundRequest,
)
from towr.rules.condition_effect_resolution import (
    resolve_condition_application,
)
from towr.rules.dice import RandomSource
from towr.rules.effect_resolution import resolve_effect_application
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


def resolve_cowardly_flight(
    request: CowardlyFlightRequest,
) -> CowardlyFlightResult:
    """Gate both spell consequences before movement or dice are resolved."""
    application = resolve_effect_application(
        EffectApplicationRequest(
            id=f"{request.id}:{request.target_id}:source",
            source_rule_id=request.rule_id,
            classification=EffectClassification.PSYCHOLOGICAL,
            immunities=request.target_effect_immunities,
        )
    )
    if application.blocked:
        return CowardlyFlightResult(
            request_id=request.id,
            target_id=request.target_id,
            application=application,
            follow_ups=(),
        )

    follow_ups: list[GiveGroundRequest | CowardlyFlightWillpowerRequest] = []
    if request.can_give_ground:
        follow_ups.append(
            GiveGroundRequest(
                resolution_id=f"{request.id}:{request.target_id}:give-ground",
                rule_id=request.rule_id,
            )
        )
    follow_ups.append(
        CowardlyFlightWillpowerRequest(
            id=f"{request.id}:{request.target_id}:willpower",
            target_id=request.target_id,
            potency=request.potency,
            test=request.willpower_test,
            target_state=request.target_state,
            source_application=application,
            rule_id=request.rule_id,
        )
    )
    return CowardlyFlightResult(
        request_id=request.id,
        target_id=request.target_id,
        application=application,
        follow_ups=tuple(follow_ups),
    )


def resolve_cowardly_flight_willpower(
    request: CowardlyFlightWillpowerRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> CowardlyFlightWillpowerResult:
    test = resolve_test(request.test, rng, decisions=decisions)
    resisted = test.successes >= request.potency
    if resisted:
        return CowardlyFlightWillpowerResult(
            request_id=request.id,
            target_id=request.target_id,
            test=test,
            resisted=True,
            state=request.target_state,
            condition_application=None,
            applied_rule_ids=(request.rule_id,),
        )

    condition_application = resolve_condition_application(
        ConditionApplicationRequest(
            id=f"{request.id}:broken",
            state=request.target_state.conditions,
            condition=Condition.BROKEN,
            source_rule_id=request.rule_id,
            classification=EffectClassification.PSYCHOLOGICAL,
        )
    )
    state = replace(
        request.target_state,
        conditions=condition_application.state,
    )
    return CowardlyFlightWillpowerResult(
        request_id=request.id,
        target_id=request.target_id,
        test=test,
        resisted=False,
        state=state,
        condition_application=condition_application,
        applied_rule_ids=condition_application.applied_rule_ids,
    )
