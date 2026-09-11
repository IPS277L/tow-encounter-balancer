from __future__ import annotations

from dataclasses import dataclass

from towr.domain.campaign_consequence_models import (
    RunForYourLivesCampaignApplicationResult,
)
from towr.domain.campaign_reputation_models import (
    CampaignReputationConsequence,
    CampaignReputationState,
)
from towr.domain.retreat_models import (
    RUN_FOR_YOUR_LIVES_RULE_ID,
    RunForYourLivesOutcome,
)


@dataclass(frozen=True, slots=True)
class RunForYourLivesMockedRequest:
    id: str
    source_campaign: RunForYourLivesCampaignApplicationResult
    state: CampaignReputationState
    reputation_consequence_id: str
    witness_reference_ids: tuple[str, ...]
    gossip_incident_reference_id: str
    reputation_effect_reference_id: str
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Mocked request id")
        if not isinstance(
            self.source_campaign,
            RunForYourLivesCampaignApplicationResult,
        ):
            raise TypeError(
                "source_campaign must be a "
                "RunForYourLivesCampaignApplicationResult"
            )
        consequence = self.source_campaign.consequence
        if consequence.outcome is not RunForYourLivesOutcome.MOCKED:
            raise ValueError("Run For Your Lives campaign outcome is not Mocked")
        if not isinstance(self.state, CampaignReputationState):
            raise TypeError("state must be a CampaignReputationState")
        if self.state.campaign_id != consequence.campaign_id:
            raise ValueError("campaign reputation state belongs to another campaign")
        if self.state.has_source_consequence(consequence.id):
            raise ValueError("Mocked consequence was already consumed")
        _validate_non_empty_string(
            self.reputation_consequence_id,
            "Mocked reputation_consequence_id",
        )
        if any(
            item.id == self.reputation_consequence_id
            for item in self.state.consequences
        ):
            raise ValueError(
                "campaign reputation consequence ID is already registered"
            )
        witnesses = _validate_unique_non_empty_ids(
            self.witness_reference_ids,
            "Mocked witness reference ID",
        )
        _validate_non_empty_string(
            self.gossip_incident_reference_id,
            "Mocked gossip_incident_reference_id",
        )
        _validate_non_empty_string(
            self.reputation_effect_reference_id,
            "Mocked reputation_effect_reference_id",
        )
        role_references = (
            *witnesses,
            self.gossip_incident_reference_id,
            self.reputation_effect_reference_id,
        )
        _validate_unique_values(role_references, "Mocked role references")
        if (
            consequence.specification.concrete_consequence_reference_ids
            != role_references
        ):
            raise ValueError(
                "Mocked role references must exactly match the registered "
                "consequence references"
            )
        _validate_non_empty_string(self.rule_id, "Mocked rule_id")
        if self.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
            raise ValueError("Mocked application uses an unknown rule")
        object.__setattr__(self, "witness_reference_ids", witnesses)


@dataclass(frozen=True, slots=True)
class RunForYourLivesMockedResult:
    request_id: str
    rule_id: str
    source_request: RunForYourLivesMockedRequest
    consequence: CampaignReputationConsequence
    previous_state: CampaignReputationState
    state: CampaignReputationState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Mocked result request_id")
        _validate_non_empty_string(self.rule_id, "Mocked result rule_id")
        if not isinstance(self.source_request, RunForYourLivesMockedRequest):
            raise TypeError("source_request must be a RunForYourLivesMockedRequest")
        if not isinstance(self.consequence, CampaignReputationConsequence):
            raise TypeError(
                "consequence must be a CampaignReputationConsequence"
            )
        if not isinstance(self.previous_state, CampaignReputationState):
            raise TypeError("previous_state must be a CampaignReputationState")
        if not isinstance(self.state, CampaignReputationState):
            raise TypeError("state must be a CampaignReputationState")
        source = self.source_request
        expected_consequence = _reputation_consequence(source)
        expected_state = _state_after_registration(source, expected_consequence)
        expected_rules = tuple(
            dict.fromkeys((*source.source_campaign.applied_rule_ids, source.rule_id))
        )
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.consequence != expected_consequence
            or self.previous_state != source.state
            or self.state != expected_state
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Run For Your Lives Mocked result is stale")


def _reputation_consequence(
    request: RunForYourLivesMockedRequest,
) -> CampaignReputationConsequence:
    consequence = request.source_campaign.consequence
    specification = consequence.specification
    return CampaignReputationConsequence(
        id=request.reputation_consequence_id,
        campaign_id=consequence.campaign_id,
        witness_reference_ids=request.witness_reference_ids,
        gossip_incident_reference_id=request.gossip_incident_reference_id,
        reputation_effect_reference_id=request.reputation_effect_reference_id,
        description_reference_id=specification.description_reference_id,
        affected_subject_reference_ids=specification.affected_subject_reference_ids,
        source_application_id=request.source_campaign.request_id,
        source_consequence_id=consequence.id,
        source_specification_id=specification.id,
        battle_id=consequence.battle_id,
        retreat_id=consequence.retreat_id,
        rule_id=request.rule_id,
    )


def _state_after_registration(
    request: RunForYourLivesMockedRequest,
    consequence: CampaignReputationConsequence,
) -> CampaignReputationState:
    return CampaignReputationState(
        campaign_id=request.state.campaign_id,
        consequences=(*request.state.consequences, consequence),
    )


def _validate_unique_non_empty_ids(
    values: tuple[str, ...],
    name: str,
) -> tuple[str, ...]:
    ids = tuple(values)
    if not ids:
        raise ValueError(f"{name}s must not be empty")
    for value in ids:
        _validate_non_empty_string(value, name)
    _validate_unique_values(ids, f"{name}s")
    return ids


def _validate_unique_values(values: tuple[str, ...], name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
