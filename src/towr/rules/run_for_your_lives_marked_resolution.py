from __future__ import annotations

from towr.domain.retreat_models import RUN_FOR_YOUR_LIVES_RULE_ID
from towr.domain.run_for_your_lives_marked_models import (
    RunForYourLivesMarkedActivationRequest,
    RunForYourLivesMarkedActivationResult,
    RunForYourLivesMarkedRegistrationRequest,
    RunForYourLivesMarkedRegistrationResult,
    _enemy_readiness,
    _readiness_activation,
    _state_after_activation,
    _state_after_readiness_registration,
)


def register_run_for_your_lives_marked(
    request: RunForYourLivesMarkedRegistrationRequest,
) -> RunForYourLivesMarkedRegistrationResult:
    """Register enemy preparedness without assigning its mechanical effect."""
    if request.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
        raise ValueError("Marked application uses an unknown rule")
    readiness = _enemy_readiness(request)
    return RunForYourLivesMarkedRegistrationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        readiness=readiness,
        previous_state=request.state,
        state=_state_after_readiness_registration(request, readiness),
        applied_rule_ids=tuple(
            dict.fromkeys((*request.source_campaign.applied_rule_ids, request.rule_id))
        ),
    )


def activate_run_for_your_lives_marked(
    request: RunForYourLivesMarkedActivationRequest,
) -> RunForYourLivesMarkedActivationResult:
    """Record the first explicit matching action against the prepared enemy."""
    if request.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
        raise ValueError("Marked application uses an unknown rule")
    readiness = request.state.readiness(request.readiness_id)
    assert readiness is not None
    activation = _readiness_activation(request)
    return RunForYourLivesMarkedActivationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        readiness=readiness,
        activation=activation,
        previous_state=request.state,
        state=_state_after_activation(request, activation),
        applied_rule_ids=(request.rule_id,),
    )
