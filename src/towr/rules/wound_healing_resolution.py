from __future__ import annotations

from towr.domain.injury_models import HealingRequirement
from towr.domain.wound_healing_models import (
    CATCH_YOUR_BREATH_HEALING_RULE_ID,
    CatchYourBreathHealingRequest,
    CatchYourBreathHealingResult,
    expected_catch_your_breath_transition,
)
from towr.rules.wound_table import lookup_wound


def apply_catch_your_breath_healing(
    request: CatchYourBreathHealingRequest,
) -> CatchYourBreathHealingResult:
    """Heal all eligible Catch Your Breath Wounds after battle treatment."""
    if request.rule_id != CATCH_YOUR_BREATH_HEALING_RULE_ID:
        raise ValueError("Catch Your Breath uses an unknown source rule")
    eligible: list[int] = []
    for wound in request.injury_state.wounds:
        entry = lookup_wound(wound.table_total)
        if entry.id is not wound.entry_id:
            raise ValueError("Wound history conflicts with the Wound table")
        if (
            not wound.healed
            and entry.healing is HealingRequirement.CATCH_YOUR_BREATH
        ):
            eligible.append(wound.sequence)
    if request.wound_sequences != tuple(eligible):
        raise ValueError(
            "Catch Your Breath must heal every and only eligible Wound"
        )

    state, removed_effects, removed_conditions = (
        expected_catch_your_breath_transition(request)
    )
    return CatchYourBreathHealingResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        target_id=request.target_id,
        healed_wound_sequences=request.wound_sequences,
        previous_state=request.injury_state,
        state=state,
        removed_effects=removed_effects,
        removed_conditions=removed_conditions,
        previous_consumed_source_ids=request.consumed_source_ids,
        consumed_source_ids=(
            *request.consumed_source_ids,
            request.treatment.request_id,
        ),
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    *request.treatment.applied_rule_ids,
                )
            )
        ),
    )
