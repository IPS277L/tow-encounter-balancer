from __future__ import annotations

from dataclasses import dataclass

from towr.domain.campaign_consequence_models import (
    RunForYourLivesCampaignApplicationResult,
)
from towr.domain.campaign_hunt_models import (
    CampaignHuntActivation,
    CampaignHuntState,
    CampaignHuntThreat,
)
from towr.domain.retreat_models import (
    RUN_FOR_YOUR_LIVES_RULE_ID,
    RunForYourLivesOutcome,
)


@dataclass(frozen=True, slots=True)
class RunForYourLivesHuntedRegistrationRequest:
    id: str
    source_campaign: RunForYourLivesCampaignApplicationResult
    state: CampaignHuntState
    threat_id: str
    pursuer_reference_id: str
    activation_trigger_reference_id: str
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Hunted registration request id")
        if not isinstance(
            self.source_campaign,
            RunForYourLivesCampaignApplicationResult,
        ):
            raise TypeError(
                "source_campaign must be a "
                "RunForYourLivesCampaignApplicationResult"
            )
        consequence = self.source_campaign.consequence
        if consequence.outcome is not RunForYourLivesOutcome.HUNTED:
            raise ValueError("Run For Your Lives campaign outcome is not Hunted")
        if not isinstance(self.state, CampaignHuntState):
            raise TypeError("state must be a CampaignHuntState")
        if self.state.campaign_id != consequence.campaign_id:
            raise ValueError("campaign hunt state belongs to another campaign")
        if self.state.has_source_consequence(consequence.id):
            raise ValueError("Hunted consequence was already consumed")
        _validate_non_empty_string(self.threat_id, "Hunted threat_id")
        if self.state.threat(self.threat_id) is not None:
            raise ValueError("campaign hunt threat ID is already registered")
        _validate_non_empty_string(
            self.pursuer_reference_id,
            "Hunted pursuer_reference_id",
        )
        _validate_non_empty_string(
            self.activation_trigger_reference_id,
            "Hunted activation_trigger_reference_id",
        )
        if self.pursuer_reference_id == self.activation_trigger_reference_id:
            raise ValueError(
                "Hunted pursuer and activation trigger references must be distinct"
            )
        expected_references = (
            self.pursuer_reference_id,
            self.activation_trigger_reference_id,
        )
        if (
            consequence.specification.concrete_consequence_reference_ids
            != expected_references
        ):
            raise ValueError(
                "Hunted role references must exactly match the registered "
                "consequence references"
            )
        _validate_rule_id(self.rule_id)


@dataclass(frozen=True, slots=True)
class RunForYourLivesHuntedRegistrationResult:
    request_id: str
    rule_id: str
    source_request: RunForYourLivesHuntedRegistrationRequest
    threat: CampaignHuntThreat
    previous_state: CampaignHuntState
    state: CampaignHuntState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Hunted registration result request_id",
        )
        _validate_rule_id(self.rule_id)
        if not isinstance(
            self.source_request,
            RunForYourLivesHuntedRegistrationRequest,
        ):
            raise TypeError(
                "source_request must be a "
                "RunForYourLivesHuntedRegistrationRequest"
            )
        if not isinstance(self.threat, CampaignHuntThreat):
            raise TypeError("threat must be a CampaignHuntThreat")
        if not isinstance(self.previous_state, CampaignHuntState):
            raise TypeError("previous_state must be a CampaignHuntState")
        if not isinstance(self.state, CampaignHuntState):
            raise TypeError("state must be a CampaignHuntState")
        source = self.source_request
        expected_threat = _hunt_threat(source)
        expected_state = _state_after_threat_registration(source, expected_threat)
        expected_rules = tuple(
            dict.fromkeys((*source.source_campaign.applied_rule_ids, source.rule_id))
        )
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.threat != expected_threat
            or self.previous_state != source.state
            or self.state != expected_state
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Run For Your Lives Hunted registration result is stale")


@dataclass(frozen=True, slots=True)
class RunForYourLivesHuntedActivationRequest:
    id: str
    state: CampaignHuntState
    threat_id: str
    activation_id: str
    activation_trigger_reference_id: str
    movement_event_reference_id: str
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Hunted activation request id")
        if not isinstance(self.state, CampaignHuntState):
            raise TypeError("state must be a CampaignHuntState")
        _validate_non_empty_string(self.threat_id, "Hunted activation threat_id")
        threat = self.state.threat(self.threat_id)
        if threat is None:
            raise ValueError("Hunted activation threat is not registered")
        if self.state.is_active(self.threat_id):
            raise ValueError("Hunted threat is already active")
        _validate_non_empty_string(self.activation_id, "Hunted activation_id")
        if any(item.id == self.activation_id for item in self.state.activations):
            raise ValueError("campaign hunt activation ID is already registered")
        _validate_non_empty_string(
            self.activation_trigger_reference_id,
            "Hunted activation_trigger_reference_id",
        )
        if self.activation_trigger_reference_id != threat.activation_trigger_reference_id:
            raise ValueError("Hunted activation does not match the registered trigger")
        _validate_non_empty_string(
            self.movement_event_reference_id,
            "Hunted movement_event_reference_id",
        )
        if (
            self.activation_trigger_reference_id
            == self.movement_event_reference_id
        ):
            raise ValueError(
                "Hunted trigger and movement event references must be distinct"
            )
        _validate_rule_id(self.rule_id)
        if self.rule_id != threat.rule_id:
            raise ValueError("Hunted activation uses another threat rule")


@dataclass(frozen=True, slots=True)
class RunForYourLivesHuntedActivationResult:
    request_id: str
    rule_id: str
    source_request: RunForYourLivesHuntedActivationRequest
    threat: CampaignHuntThreat
    activation: CampaignHuntActivation
    previous_state: CampaignHuntState
    state: CampaignHuntState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Hunted activation result request_id",
        )
        _validate_rule_id(self.rule_id)
        if not isinstance(
            self.source_request,
            RunForYourLivesHuntedActivationRequest,
        ):
            raise TypeError(
                "source_request must be a RunForYourLivesHuntedActivationRequest"
            )
        if not isinstance(self.threat, CampaignHuntThreat):
            raise TypeError("threat must be a CampaignHuntThreat")
        if not isinstance(self.activation, CampaignHuntActivation):
            raise TypeError("activation must be a CampaignHuntActivation")
        if not isinstance(self.previous_state, CampaignHuntState):
            raise TypeError("previous_state must be a CampaignHuntState")
        if not isinstance(self.state, CampaignHuntState):
            raise TypeError("state must be a CampaignHuntState")
        source = self.source_request
        expected_threat = source.state.threat(source.threat_id)
        assert expected_threat is not None
        expected_activation = _hunt_activation(source)
        expected_state = _state_after_activation(source, expected_activation)
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.threat != expected_threat
            or self.activation != expected_activation
            or self.previous_state != source.state
            or self.state != expected_state
            or self.applied_rule_ids != (source.rule_id,)
        ):
            raise ValueError("Run For Your Lives Hunted activation result is stale")


def _hunt_threat(
    request: RunForYourLivesHuntedRegistrationRequest,
) -> CampaignHuntThreat:
    consequence = request.source_campaign.consequence
    specification = consequence.specification
    return CampaignHuntThreat(
        id=request.threat_id,
        campaign_id=consequence.campaign_id,
        pursuer_reference_id=request.pursuer_reference_id,
        activation_trigger_reference_id=request.activation_trigger_reference_id,
        description_reference_id=specification.description_reference_id,
        affected_subject_reference_ids=specification.affected_subject_reference_ids,
        source_application_id=request.source_campaign.request_id,
        source_consequence_id=consequence.id,
        source_specification_id=specification.id,
        battle_id=consequence.battle_id,
        retreat_id=consequence.retreat_id,
        rule_id=request.rule_id,
    )


def _state_after_threat_registration(
    request: RunForYourLivesHuntedRegistrationRequest,
    threat: CampaignHuntThreat,
) -> CampaignHuntState:
    return CampaignHuntState(
        campaign_id=request.state.campaign_id,
        threats=(*request.state.threats, threat),
        activations=request.state.activations,
    )


def _hunt_activation(
    request: RunForYourLivesHuntedActivationRequest,
) -> CampaignHuntActivation:
    return CampaignHuntActivation(
        id=request.activation_id,
        campaign_id=request.state.campaign_id,
        threat_id=request.threat_id,
        activation_trigger_reference_id=request.activation_trigger_reference_id,
        movement_event_reference_id=request.movement_event_reference_id,
        rule_id=request.rule_id,
    )


def _state_after_activation(
    request: RunForYourLivesHuntedActivationRequest,
    activation: CampaignHuntActivation,
) -> CampaignHuntState:
    return CampaignHuntState(
        campaign_id=request.state.campaign_id,
        threats=request.state.threats,
        activations=(*request.state.activations, activation),
    )


def _validate_rule_id(rule_id: str) -> None:
    _validate_non_empty_string(rule_id, "Hunted rule_id")
    if rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
        raise ValueError("Hunted application uses an unknown rule")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
