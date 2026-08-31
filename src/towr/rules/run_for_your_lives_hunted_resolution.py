from __future__ import annotations

from towr.domain.retreat_models import RUN_FOR_YOUR_LIVES_RULE_ID
from towr.domain.run_for_your_lives_hunted_models import (
    RunForYourLivesHuntedActivationRequest,
    RunForYourLivesHuntedActivationResult,
    RunForYourLivesHuntedRegistrationRequest,
    RunForYourLivesHuntedRegistrationResult,
    _hunt_activation,
    _hunt_threat,
    _state_after_activation,
    _state_after_threat_registration,
)


def register_run_for_your_lives_hunted(
    request: RunForYourLivesHuntedRegistrationRequest,
) -> RunForYourLivesHuntedRegistrationResult:
    """Register an inactive Hunted threat without starting a pursuit."""
    if request.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
        raise ValueError("Hunted application uses an unknown rule")
    threat = _hunt_threat(request)
    return RunForYourLivesHuntedRegistrationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        threat=threat,
        previous_state=request.state,
        state=_state_after_threat_registration(request, threat),
        applied_rule_ids=tuple(
            dict.fromkeys((*request.source_campaign.applied_rule_ids, request.rule_id))
        ),
    )


def activate_run_for_your_lives_hunted(
    request: RunForYourLivesHuntedActivationRequest,
) -> RunForYourLivesHuntedActivationResult:
    """Activate a registered threat from an explicit matching movement event."""
    if request.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
        raise ValueError("Hunted application uses an unknown rule")
    threat = request.state.threat(request.threat_id)
    assert threat is not None
    activation = _hunt_activation(request)
    return RunForYourLivesHuntedActivationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        threat=threat,
        activation=activation,
        previous_state=request.state,
        state=_state_after_activation(request, activation),
        applied_rule_ids=(request.rule_id,),
    )
