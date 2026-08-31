from __future__ import annotations

from dataclasses import dataclass

from towr.domain.campaign_consequence_models import (
    RunForYourLivesCampaignApplicationResult,
)
from towr.domain.campaign_enemy_readiness_models import (
    CampaignEnemyReadiness,
    CampaignEnemyReadinessActivation,
    CampaignEnemyReadinessState,
)
from towr.domain.retreat_models import (
    RUN_FOR_YOUR_LIVES_RULE_ID,
    RunForYourLivesOutcome,
)


@dataclass(frozen=True, slots=True)
class RunForYourLivesMarkedRegistrationRequest:
    id: str
    source_campaign: RunForYourLivesCampaignApplicationResult
    state: CampaignEnemyReadinessState
    readiness_id: str
    enemy_reference_id: str
    acquired_intelligence_reference_id: str
    next_action_trigger_reference_id: str
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Marked registration request id")
        if not isinstance(
            self.source_campaign,
            RunForYourLivesCampaignApplicationResult,
        ):
            raise TypeError(
                "source_campaign must be a "
                "RunForYourLivesCampaignApplicationResult"
            )
        consequence = self.source_campaign.consequence
        if consequence.outcome is not RunForYourLivesOutcome.MARKED:
            raise ValueError("Run For Your Lives campaign outcome is not Marked")
        if not isinstance(self.state, CampaignEnemyReadinessState):
            raise TypeError("state must be a CampaignEnemyReadinessState")
        if self.state.campaign_id != consequence.campaign_id:
            raise ValueError("enemy readiness state belongs to another campaign")
        if self.state.has_source_consequence(consequence.id):
            raise ValueError("Marked consequence was already consumed")
        _validate_non_empty_string(self.readiness_id, "Marked readiness_id")
        if self.state.readiness(self.readiness_id) is not None:
            raise ValueError("campaign enemy readiness ID is already registered")
        for value, name in (
            (self.enemy_reference_id, "Marked enemy_reference_id"),
            (
                self.acquired_intelligence_reference_id,
                "Marked acquired_intelligence_reference_id",
            ),
            (
                self.next_action_trigger_reference_id,
                "Marked next_action_trigger_reference_id",
            ),
        ):
            _validate_non_empty_string(value, name)
        role_references = (
            self.enemy_reference_id,
            self.acquired_intelligence_reference_id,
            self.next_action_trigger_reference_id,
        )
        _validate_unique_values(role_references, "Marked role references")
        if (
            consequence.specification.concrete_consequence_reference_ids
            != role_references
        ):
            raise ValueError(
                "Marked role references must exactly match the registered "
                "consequence references"
            )
        _validate_rule_id(self.rule_id)


@dataclass(frozen=True, slots=True)
class RunForYourLivesMarkedRegistrationResult:
    request_id: str
    rule_id: str
    source_request: RunForYourLivesMarkedRegistrationRequest
    readiness: CampaignEnemyReadiness
    previous_state: CampaignEnemyReadinessState
    state: CampaignEnemyReadinessState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Marked registration result request_id",
        )
        _validate_rule_id(self.rule_id)
        if not isinstance(
            self.source_request,
            RunForYourLivesMarkedRegistrationRequest,
        ):
            raise TypeError(
                "source_request must be a "
                "RunForYourLivesMarkedRegistrationRequest"
            )
        if not isinstance(self.readiness, CampaignEnemyReadiness):
            raise TypeError("readiness must be a CampaignEnemyReadiness")
        if not isinstance(self.previous_state, CampaignEnemyReadinessState):
            raise TypeError("previous_state must be a CampaignEnemyReadinessState")
        if not isinstance(self.state, CampaignEnemyReadinessState):
            raise TypeError("state must be a CampaignEnemyReadinessState")
        source = self.source_request
        expected_readiness = _enemy_readiness(source)
        expected_state = _state_after_readiness_registration(
            source,
            expected_readiness,
        )
        expected_rules = tuple(
            dict.fromkeys((*source.source_campaign.applied_rule_ids, source.rule_id))
        )
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.readiness != expected_readiness
            or self.previous_state != source.state
            or self.state != expected_state
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Run For Your Lives Marked registration result is stale")


@dataclass(frozen=True, slots=True)
class RunForYourLivesMarkedActivationRequest:
    id: str
    state: CampaignEnemyReadinessState
    readiness_id: str
    activation_id: str
    enemy_reference_id: str
    next_action_trigger_reference_id: str
    action_event_reference_id: str
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Marked activation request id")
        if not isinstance(self.state, CampaignEnemyReadinessState):
            raise TypeError("state must be a CampaignEnemyReadinessState")
        _validate_non_empty_string(
            self.readiness_id,
            "Marked activation readiness_id",
        )
        readiness = self.state.readiness(self.readiness_id)
        if readiness is None:
            raise ValueError("Marked readiness is not registered")
        if self.state.is_activated(self.readiness_id):
            raise ValueError("Marked readiness is already activated")
        _validate_non_empty_string(self.activation_id, "Marked activation_id")
        if any(item.id == self.activation_id for item in self.state.activations):
            raise ValueError(
                "campaign enemy readiness activation ID is already registered"
            )
        _validate_non_empty_string(
            self.enemy_reference_id,
            "Marked activation enemy_reference_id",
        )
        if self.enemy_reference_id != readiness.enemy_reference_id:
            raise ValueError("Marked activation does not match the registered enemy")
        _validate_non_empty_string(
            self.next_action_trigger_reference_id,
            "Marked activation next_action_trigger_reference_id",
        )
        if (
            self.next_action_trigger_reference_id
            != readiness.next_action_trigger_reference_id
        ):
            raise ValueError("Marked activation does not match the registered trigger")
        _validate_non_empty_string(
            self.action_event_reference_id,
            "Marked action_event_reference_id",
        )
        if (
            self.next_action_trigger_reference_id
            == self.action_event_reference_id
        ):
            raise ValueError(
                "Marked trigger and action event references must be distinct"
            )
        _validate_rule_id(self.rule_id)
        if self.rule_id != readiness.rule_id:
            raise ValueError("Marked activation uses another readiness rule")


@dataclass(frozen=True, slots=True)
class RunForYourLivesMarkedActivationResult:
    request_id: str
    rule_id: str
    source_request: RunForYourLivesMarkedActivationRequest
    readiness: CampaignEnemyReadiness
    activation: CampaignEnemyReadinessActivation
    previous_state: CampaignEnemyReadinessState
    state: CampaignEnemyReadinessState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Marked activation result request_id",
        )
        _validate_rule_id(self.rule_id)
        if not isinstance(
            self.source_request,
            RunForYourLivesMarkedActivationRequest,
        ):
            raise TypeError(
                "source_request must be a RunForYourLivesMarkedActivationRequest"
            )
        if not isinstance(self.readiness, CampaignEnemyReadiness):
            raise TypeError("readiness must be a CampaignEnemyReadiness")
        if not isinstance(self.activation, CampaignEnemyReadinessActivation):
            raise TypeError(
                "activation must be a CampaignEnemyReadinessActivation"
            )
        if not isinstance(self.previous_state, CampaignEnemyReadinessState):
            raise TypeError("previous_state must be a CampaignEnemyReadinessState")
        if not isinstance(self.state, CampaignEnemyReadinessState):
            raise TypeError("state must be a CampaignEnemyReadinessState")
        source = self.source_request
        expected_readiness = source.state.readiness(source.readiness_id)
        assert expected_readiness is not None
        expected_activation = _readiness_activation(source)
        expected_state = _state_after_activation(source, expected_activation)
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.readiness != expected_readiness
            or self.activation != expected_activation
            or self.previous_state != source.state
            or self.state != expected_state
            or self.applied_rule_ids != (source.rule_id,)
        ):
            raise ValueError("Run For Your Lives Marked activation result is stale")


def _enemy_readiness(
    request: RunForYourLivesMarkedRegistrationRequest,
) -> CampaignEnemyReadiness:
    consequence = request.source_campaign.consequence
    specification = consequence.specification
    return CampaignEnemyReadiness(
        id=request.readiness_id,
        campaign_id=consequence.campaign_id,
        enemy_reference_id=request.enemy_reference_id,
        acquired_intelligence_reference_id=request.acquired_intelligence_reference_id,
        next_action_trigger_reference_id=request.next_action_trigger_reference_id,
        description_reference_id=specification.description_reference_id,
        affected_subject_reference_ids=specification.affected_subject_reference_ids,
        source_application_id=request.source_campaign.request_id,
        source_consequence_id=consequence.id,
        source_specification_id=specification.id,
        battle_id=consequence.battle_id,
        retreat_id=consequence.retreat_id,
        rule_id=request.rule_id,
    )


def _state_after_readiness_registration(
    request: RunForYourLivesMarkedRegistrationRequest,
    readiness: CampaignEnemyReadiness,
) -> CampaignEnemyReadinessState:
    return CampaignEnemyReadinessState(
        campaign_id=request.state.campaign_id,
        readiness_records=(*request.state.readiness_records, readiness),
        activations=request.state.activations,
    )


def _readiness_activation(
    request: RunForYourLivesMarkedActivationRequest,
) -> CampaignEnemyReadinessActivation:
    return CampaignEnemyReadinessActivation(
        id=request.activation_id,
        campaign_id=request.state.campaign_id,
        readiness_id=request.readiness_id,
        enemy_reference_id=request.enemy_reference_id,
        next_action_trigger_reference_id=request.next_action_trigger_reference_id,
        action_event_reference_id=request.action_event_reference_id,
        rule_id=request.rule_id,
    )


def _state_after_activation(
    request: RunForYourLivesMarkedActivationRequest,
    activation: CampaignEnemyReadinessActivation,
) -> CampaignEnemyReadinessState:
    return CampaignEnemyReadinessState(
        campaign_id=request.state.campaign_id,
        readiness_records=request.state.readiness_records,
        activations=(*request.state.activations, activation),
    )


def _validate_rule_id(rule_id: str) -> None:
    _validate_non_empty_string(rule_id, "Marked rule_id")
    if rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
        raise ValueError("Marked application uses an unknown rule")


def _validate_unique_values(values: tuple[str, ...], name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
