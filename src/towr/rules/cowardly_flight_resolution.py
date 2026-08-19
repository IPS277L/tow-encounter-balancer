from __future__ import annotations

from dataclasses import replace

from towr.domain.condition_models import (
    Condition,
    ConditionApplicationRequest,
    EffectApplicationRequest,
    EffectClassification,
)
from towr.domain.magic_models import (
    FormalSpellDefinition,
    SpellDuration,
    SpellRange,
    SpellTargetKind,
)
from towr.domain.resolution_models import (
    CowardlyFlightMovementFollowUp,
    CowardlyFlightRequest,
    CowardlyFlightResult,
    CowardlyFlightSpellEffectRequest,
    CowardlyFlightWillpowerBatchRequest,
    CowardlyFlightWillpowerBatchResult,
    CowardlyFlightWillpowerRequest,
    CowardlyFlightWillpowerResult,
    CowardlyFlightZoneBatchRequest,
    CowardlyFlightZoneBatchResult,
    GiveGroundRequest,
)
from towr.rules.condition_effect_resolution import (
    resolve_condition_application,
)
from towr.rules.dice import RandomSource
from towr.rules.effect_resolution import resolve_effect_application
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


COWARDLY_FLIGHT_RULE_ID = "RULE-MAGIC-001:curse-of-cowardly-flight"
COWARDLY_FLIGHT_SPELL_DEFINITION = FormalSpellDefinition(
    rule_id=COWARDLY_FLIGHT_RULE_ID,
    lore_id="lore:battle-magic",
    casting_value=3,
    target_kind=SpellTargetKind.ZONE,
    range=SpellRange.LONG,
    duration=SpellDuration.INSTANT,
)


def resolve_cowardly_flight_spell_effect(
    request: CowardlyFlightSpellEffectRequest,
) -> CowardlyFlightResult:
    """Adapt one prepared target effect to the spell-specific reducer."""
    source = request.source
    if source.spell_rule_id != COWARDLY_FLIGHT_RULE_ID:
        raise ValueError(
            "spell effect is not Curse of Cowardly Flight"
        )
    if source.rule_id != COWARDLY_FLIGHT_RULE_ID:
        raise ValueError("spell effect rule_id does not match its spell")

    return resolve_cowardly_flight(
        CowardlyFlightRequest(
            id=source.resolution_id,
            target_id=source.target_id,
            potency=source.potency,
            can_give_ground=request.can_give_ground,
            willpower_test=request.willpower_test,
            target_state=request.target_state,
            target_effect_immunities=request.target_effect_immunities,
            rule_id=COWARDLY_FLIGHT_RULE_ID,
        )
    )


def resolve_cowardly_flight_zone_batch(
    request: CowardlyFlightZoneBatchRequest,
) -> CowardlyFlightZoneBatchResult:
    source = request.source
    if source.spell_rule_id != COWARDLY_FLIGHT_RULE_ID:
        raise ValueError(
            "spell execution is not Curse of Cowardly Flight"
        )

    expected_effects = tuple(
        target.effect_request
        for target in source.targets
        if target.effect_request is not None
    )
    if expected_effects != source.follow_ups:
        raise ValueError(
            "spell execution follow-ups do not match its target results"
        )

    contexts_by_target = {
        context.source.target_id: context for context in request.contexts
    }
    expected_target_ids = tuple(
        effect.target_id for effect in source.follow_ups
    )
    if len(set(expected_target_ids)) != len(expected_target_ids):
        raise ValueError("spell-effect target IDs must be unique")
    if set(contexts_by_target) != set(expected_target_ids):
        raise ValueError(
            "contexts must match positive spell-effect targets exactly"
        )

    target_results: list[CowardlyFlightResult] = []
    for effect in source.follow_ups:
        context = contexts_by_target[effect.target_id]
        if context.source != effect:
            raise ValueError(
                "Cowardly Flight context source does not match spell effect"
            )
        target_results.append(resolve_cowardly_flight_spell_effect(context))

    return CowardlyFlightZoneBatchResult(
        request_id=request.id,
        source_execution_id=source.request_id,
        caster_id=source.caster_id,
        spell_rule_id=source.spell_rule_id,
        lore_id=source.lore_id,
        selected_zone_id=source.selected_target_id,
        targets=tuple(target_results),
        movement_follow_ups=tuple(
            CowardlyFlightMovementFollowUp(
                target_id=result.target_id,
                request=follow_up,
            )
            for result in target_results
            for follow_up in result.follow_ups
            if isinstance(follow_up, GiveGroundRequest)
        ),
        willpower_follow_ups=tuple(
            follow_up
            for result in target_results
            for follow_up in result.follow_ups
            if isinstance(follow_up, CowardlyFlightWillpowerRequest)
        ),
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    *source.applied_rule_ids,
                    request.rule_id,
                    *(
                        rule_id
                        for result in target_results
                        for rule_id in result.application.applied_rule_ids
                    ),
                )
            )
        ),
    )


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


def resolve_cowardly_flight_willpower_batch(
    request: CowardlyFlightWillpowerBatchRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> CowardlyFlightWillpowerBatchResult:
    """Gate Tests on completed movement and resolve them in target order."""
    source = request.source
    if source.spell_rule_id != COWARDLY_FLIGHT_RULE_ID:
        raise ValueError(
            "spell batch is not Curse of Cowardly Flight"
        )
    if request.rule_id != COWARDLY_FLIGHT_RULE_ID:
        raise ValueError("Willpower batch rule_id does not match the spell")

    expected_movements = tuple(
        CowardlyFlightMovementFollowUp(
            target_id=target.target_id,
            request=follow_up,
        )
        for target in source.targets
        for follow_up in target.follow_ups
        if isinstance(follow_up, GiveGroundRequest)
    )
    expected_willpower = tuple(
        follow_up
        for target in source.targets
        for follow_up in target.follow_ups
        if isinstance(follow_up, CowardlyFlightWillpowerRequest)
    )
    target_ids = tuple(target.target_id for target in source.targets)
    if len(set(target_ids)) != len(target_ids):
        raise ValueError("Zone target result IDs must be unique")
    willpower_ids = tuple(item.id for item in expected_willpower)
    if len(set(willpower_ids)) != len(willpower_ids):
        raise ValueError("Willpower follow-up IDs must be unique")
    if source.movement_follow_ups != expected_movements:
        raise ValueError(
            "movement follow-ups do not match Zone target results"
        )
    if source.willpower_follow_ups != expected_willpower:
        raise ValueError(
            "Willpower follow-ups do not match Zone target results"
        )

    expected_by_id = {
        item.request.resolution_id: item for item in expected_movements
    }
    if len(expected_by_id) != len(expected_movements):
        raise ValueError("movement follow-up IDs must be unique")
    completions_by_id = {
        item.source.request.resolution_id: item
        for item in request.movement_completions
    }
    if set(completions_by_id) != set(expected_by_id):
        raise ValueError(
            "movement completions must match movement follow-ups exactly"
        )
    for resolution_id, expected in expected_by_id.items():
        if completions_by_id[resolution_id].source != expected:
            raise ValueError(
                "movement completion does not match its movement follow-up"
            )

    results = tuple(
        resolve_cowardly_flight_willpower(
            follow_up,
            rng,
            decisions=decisions,
        )
        for follow_up in expected_willpower
    )
    completed_movements = tuple(
        completions_by_id[item.request.resolution_id]
        for item in expected_movements
    )
    return CowardlyFlightWillpowerBatchResult(
        request_id=request.id,
        source_batch_id=source.request_id,
        source_execution_id=source.source_execution_id,
        caster_id=source.caster_id,
        spell_rule_id=source.spell_rule_id,
        lore_id=source.lore_id,
        selected_zone_id=source.selected_zone_id,
        completed_movements=completed_movements,
        targets=results,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    *source.applied_rule_ids,
                    request.rule_id,
                    *(
                        rule_id
                        for result in results
                        for rule_id in result.applied_rule_ids
                    ),
                )
            )
        ),
    )
