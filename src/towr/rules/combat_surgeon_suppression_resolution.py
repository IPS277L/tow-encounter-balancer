from __future__ import annotations

from dataclasses import replace

from towr.domain.combat_surgeon_suppression_models import (
    COMBAT_SURGEON_EFFECTIVE_EFFECTS_RULE_ID,
    COMBAT_SURGEON_SUPPRESSION_REGISTRATION_RULE_ID,
    CombatSurgeonEffectiveEffectsRequest,
    CombatSurgeonEffectiveEffectsResult,
    CombatSurgeonSuppressionRegistrationRequest,
    CombatSurgeonSuppressionRegistrationResult,
    _expected_effective_view,
)


def register_combat_surgeon_suppression(
    request: CombatSurgeonSuppressionRegistrationRequest,
) -> CombatSurgeonSuppressionRegistrationResult:
    """Register one successful Combat Surgeon suppression for a battle."""
    if request.rule_id != COMBAT_SURGEON_SUPPRESSION_REGISTRATION_RULE_ID:
        raise ValueError("suppression registration uses an unknown rule")
    suppression = request.source.suppression
    assert suppression is not None
    aggregate = replace(
        request.aggregate,
        suppressions=(*request.aggregate.suppressions, suppression),
    )
    return CombatSurgeonSuppressionRegistrationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        suppression=suppression,
        previous_aggregate=request.aggregate,
        aggregate=aggregate,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (request.rule_id, *request.source.applied_rule_ids)
            )
        ),
    )


def resolve_combat_surgeon_effective_effects(
    request: CombatSurgeonEffectiveEffectsRequest,
) -> CombatSurgeonEffectiveEffectsResult:
    """Return battle-effective effects without mutating canonical injury."""
    if request.rule_id != COMBAT_SURGEON_EFFECTIVE_EFFECTS_RULE_ID:
        raise ValueError("effective-effects view uses an unknown rule")
    (
        active_suppressions,
        suppressed_effects,
        effective_wound_effects,
        ignored_conditions,
        effective_conditions,
    ) = _expected_effective_view(request)
    return CombatSurgeonEffectiveEffectsResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        target_id=request.target_id,
        injury_state=request.injury_state,
        active_suppressions=active_suppressions,
        suppressed_effects=suppressed_effects,
        effective_wound_effects=effective_wound_effects,
        ignored_conditions=ignored_conditions,
        effective_conditions=effective_conditions,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    *(item.rule_id for item in active_suppressions),
                )
            )
        ),
    )
