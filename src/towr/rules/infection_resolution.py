from __future__ import annotations

from dataclasses import replace

from towr.domain.infection_models import (
    DAILY_WOUND_REGISTRATION_RULE_ID,
    END_OF_DAY_INFECTION_RULE_ID,
    DailyWoundRegistrationRequest,
    DailyWoundRegistrationResult,
    EndOfDayInfectionRequest,
    EndOfDayInfectionResult,
    _infection_festering_wound,
    _registration_receipt,
)
from towr.rules.dice import RandomSource
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


def register_daily_wound(
    request: DailyWoundRegistrationRequest,
) -> DailyWoundRegistrationResult:
    """Register one accepted character Wound for its campaign day."""
    if request.rule_id != DAILY_WOUND_REGISTRATION_RULE_ID:
        raise ValueError("daily Wound registration uses an unknown rule")
    receipt = _registration_receipt(request)
    return DailyWoundRegistrationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        receipt=receipt,
        previous_state=request.state,
        state=replace(
            request.state,
            receipts=(*request.state.receipts, receipt),
        ),
        applied_rule_ids=tuple(
            dict.fromkeys(
                (request.rule_id, *request.source.applied_rule_ids)
            )
        ),
    )


def resolve_end_of_day_infection(
    request: EndOfDayInfectionRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> EndOfDayInfectionResult:
    """Resolve one mandatory Infection Test and close the tracked day."""
    if request.rule_id != END_OF_DAY_INFECTION_RULE_ID:
        raise ValueError("Infection uses an unknown rule")
    test_result = resolve_test(
        request.endurance_test,
        rng,
        decisions=decisions,
    )
    avoided_infection = (
        test_result.successes >= request.daily_wounds.wound_count
    )
    added = _infection_festering_wound(request, avoided_infection)
    festering_state = request.festering_wound_state
    if added is not None:
        festering_state = replace(
            festering_state,
            wounds=(*festering_state.wounds, added),
        )
    return EndOfDayInfectionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        test_result=test_result,
        wound_count=request.daily_wounds.wound_count,
        avoided_infection=avoided_infection,
        added_festering_wound=added,
        previous_daily_wounds=request.daily_wounds,
        daily_wounds=replace(
            request.daily_wounds,
            closed_by_infection_id=request.id,
        ),
        previous_festering_wound_state=request.festering_wound_state,
        festering_wound_state=festering_state,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    *test_result.trace.applied_rule_ids,
                    *((added.rule_id,) if added is not None else ()),
                )
            )
        ),
    )
