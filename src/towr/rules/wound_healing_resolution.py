from __future__ import annotations

from towr.domain.injury_models import CharacterInjuryState, HealingRequirement
from towr.domain.wound_healing_models import (
    CATCH_YOUR_BREATH_HEALING_RULE_ID,
    NIGHTS_RESPITE_HEALING_RULE_ID,
    REST_AND_RECOVERY_HEALING_RULE_ID,
    CatchYourBreathHealingRequest,
    CatchYourBreathHealingResult,
    NightsRespiteHealingRequest,
    NightsRespiteHealingResult,
    RestAndRecoveryHealingRequest,
    RestAndRecoveryHealingResult,
    _rest_and_recovery_surgery_rule_ids,
    _rest_and_recovery_surgery_source_id,
    expected_catch_your_breath_transition,
    expected_wound_healing_transition,
)
from towr.rules.wound_table import lookup_wound


def apply_catch_your_breath_healing(
    request: CatchYourBreathHealingRequest,
) -> CatchYourBreathHealingResult:
    """Heal all ready Catch Your Breath Wounds after immediate danger."""
    if request.rule_id != CATCH_YOUR_BREATH_HEALING_RULE_ID:
        raise ValueError("Catch Your Breath uses an unknown source rule")
    eligible = _eligible_wound_sequences(
        request.injury_state,
        HealingRequirement.CATCH_YOUR_BREATH,
    )
    if request.wound_sequences != eligible:
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
            request.opportunity.id,
        ),
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    request.opportunity.rule_id,
                    *(
                        request.opportunity.treatment.applied_rule_ids
                        if request.opportunity.treatment is not None
                        else ()
                    ),
                )
            )
        ),
    )


def apply_nights_respite_healing(
    request: NightsRespiteHealingRequest,
) -> NightsRespiteHealingResult:
    """Heal all ready Night's Respite Wounds after completed rest."""
    if request.rule_id != NIGHTS_RESPITE_HEALING_RULE_ID:
        raise ValueError("Night's Respite uses an unknown source rule")
    eligible = _eligible_wound_sequences(
        request.injury_state,
        HealingRequirement.NIGHTS_REST,
    )
    if request.wound_sequences != eligible:
        raise ValueError(
            "Night's Respite must heal every and only eligible Wound"
        )

    state, removed_effects, removed_conditions = (
        expected_wound_healing_transition(
            request.injury_state,
            request.wound_sequences,
            request.condition_source_snapshots,
        )
    )
    return NightsRespiteHealingResult(
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
            request.opportunity.id,
        ),
        applied_rule_ids=(
            request.rule_id,
            request.opportunity.rule_id,
        ),
    )


def apply_rest_and_recovery_healing(
    request: RestAndRecoveryHealingRequest,
) -> RestAndRecoveryHealingResult:
    """Heal one ready Wound after a successful recovery Endeavour."""
    if request.rule_id != REST_AND_RECOVERY_HEALING_RULE_ID:
        raise ValueError("Rest and Recovery uses an unknown healing rule")
    wound = request.injury_state.wounds[request.wound_sequence - 1]
    entry = lookup_wound(wound.table_total)
    if entry.id is not wound.entry_id:
        raise ValueError("Wound history conflicts with the Wound table")
    if entry.healing is HealingRequirement.REST_AND_RECOVERY:
        if request.surgery is not None:
            raise ValueError("ordinary recovery must not consume surgery proof")
        requirement = HealingRequirement.REST_AND_RECOVERY
    elif entry.healing is HealingRequirement.SURGERY_AND_RECOVERY:
        if request.surgery is None:
            raise ValueError("surgery-required recovery needs surgery proof")
        requirement = HealingRequirement.SURGERY_AND_RECOVERY
    else:
        raise ValueError("Rest and Recovery must select one eligible Wound")
    eligible = _eligible_wound_sequences(request.injury_state, requirement)
    if request.wound_sequence not in eligible:
        raise ValueError(
            "Rest and Recovery must select one eligible Wound"
        )

    state, removed_effects, removed_conditions = (
        expected_wound_healing_transition(
            request.injury_state,
            (request.wound_sequence,),
            request.condition_source_snapshots,
        )
    )
    return RestAndRecoveryHealingResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        target_id=request.target_id,
        healed_wound_sequence=request.wound_sequence,
        previous_state=request.injury_state,
        state=state,
        removed_effects=removed_effects,
        removed_conditions=removed_conditions,
        previous_consumed_source_ids=request.consumed_source_ids,
        consumed_source_ids=(
            *request.consumed_source_ids,
            *(
                (_rest_and_recovery_surgery_source_id(request.surgery),)
                if request.surgery
                else ()
            ),
            request.endeavour.request_id,
        ),
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    *(
                        _rest_and_recovery_surgery_rule_ids(request.surgery)
                        if request.surgery is not None
                        else ()
                    ),
                    *request.endeavour.applied_rule_ids,
                )
            )
        ),
    )


def _eligible_wound_sequences(
    state: CharacterInjuryState,
    requirement: HealingRequirement,
) -> tuple[int, ...]:
    eligible: list[int] = []
    for wound in state.wounds:
        entry = lookup_wound(wound.table_total)
        if entry.id is not wound.entry_id:
            raise ValueError("Wound history conflicts with the Wound table")
        if (
            not wound.healed
            and wound.treated
            and wound.effect_resolved
            and entry.healing is requirement
        ):
            eligible.append(wound.sequence)
    return tuple(eligible)
