from __future__ import annotations

from dataclasses import dataclass

from towr.domain.campaign_conflict_models import (
    CampaignConflictOpportunity,
    CampaignConflictOpportunityState,
)
from towr.domain.campaign_consequence_models import (
    RunForYourLivesCampaignApplicationResult,
)
from towr.domain.retreat_models import (
    RUN_FOR_YOUR_LIVES_RULE_ID,
    RunForYourLivesOutcome,
)


@dataclass(frozen=True, slots=True)
class RunForYourLivesSurroundedRequest:
    id: str
    source_campaign: RunForYourLivesCampaignApplicationResult
    state: CampaignConflictOpportunityState
    opportunity_id: str
    opposition_reference_id: str
    encounter_setup_reference_id: str
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Surrounded request id")
        if not isinstance(
            self.source_campaign,
            RunForYourLivesCampaignApplicationResult,
        ):
            raise TypeError(
                "source_campaign must be a "
                "RunForYourLivesCampaignApplicationResult"
            )
        consequence = self.source_campaign.consequence
        if consequence.outcome is not RunForYourLivesOutcome.SURROUNDED:
            raise ValueError("Run For Your Lives campaign outcome is not Surrounded")
        if not isinstance(self.state, CampaignConflictOpportunityState):
            raise TypeError("state must be a CampaignConflictOpportunityState")
        if self.state.campaign_id != consequence.campaign_id:
            raise ValueError("conflict opportunity state belongs to another campaign")
        if self.state.has_source_consequence(consequence.id):
            raise ValueError("Surrounded consequence was already consumed")
        _validate_non_empty_string(self.opportunity_id, "Surrounded opportunity_id")
        if any(item.id == self.opportunity_id for item in self.state.opportunities):
            raise ValueError("conflict opportunity ID is already registered")
        _validate_non_empty_string(
            self.opposition_reference_id,
            "Surrounded opposition_reference_id",
        )
        _validate_non_empty_string(
            self.encounter_setup_reference_id,
            "Surrounded encounter_setup_reference_id",
        )
        if self.opposition_reference_id == self.encounter_setup_reference_id:
            raise ValueError(
                "Surrounded opposition and encounter setup references must be distinct"
            )
        expected_references = (
            self.opposition_reference_id,
            self.encounter_setup_reference_id,
        )
        if (
            consequence.specification.concrete_consequence_reference_ids
            != expected_references
        ):
            raise ValueError(
                "Surrounded role references must exactly match the registered "
                "consequence references"
            )
        _validate_non_empty_string(self.rule_id, "Surrounded rule_id")
        if self.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
            raise ValueError("Surrounded application uses an unknown rule")


@dataclass(frozen=True, slots=True)
class RunForYourLivesSurroundedResult:
    request_id: str
    rule_id: str
    source_request: RunForYourLivesSurroundedRequest
    opportunity: CampaignConflictOpportunity
    previous_state: CampaignConflictOpportunityState
    state: CampaignConflictOpportunityState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Surrounded result request_id")
        _validate_non_empty_string(self.rule_id, "Surrounded result rule_id")
        if not isinstance(self.source_request, RunForYourLivesSurroundedRequest):
            raise TypeError(
                "source_request must be a RunForYourLivesSurroundedRequest"
            )
        if not isinstance(self.opportunity, CampaignConflictOpportunity):
            raise TypeError("opportunity must be a CampaignConflictOpportunity")
        if not isinstance(self.previous_state, CampaignConflictOpportunityState):
            raise TypeError("previous_state must be a CampaignConflictOpportunityState")
        if not isinstance(self.state, CampaignConflictOpportunityState):
            raise TypeError("state must be a CampaignConflictOpportunityState")
        source = self.source_request
        expected_opportunity = _conflict_opportunity(source)
        expected_state = _state_after_registration(source, expected_opportunity)
        expected_rules = tuple(
            dict.fromkeys((*source.source_campaign.applied_rule_ids, source.rule_id))
        )
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.opportunity != expected_opportunity
            or self.previous_state != source.state
            or self.state != expected_state
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Run For Your Lives Surrounded result is stale")


def _conflict_opportunity(
    request: RunForYourLivesSurroundedRequest,
) -> CampaignConflictOpportunity:
    consequence = request.source_campaign.consequence
    specification = consequence.specification
    return CampaignConflictOpportunity(
        id=request.opportunity_id,
        campaign_id=consequence.campaign_id,
        opposition_reference_id=request.opposition_reference_id,
        encounter_setup_reference_id=request.encounter_setup_reference_id,
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
    request: RunForYourLivesSurroundedRequest,
    opportunity: CampaignConflictOpportunity,
) -> CampaignConflictOpportunityState:
    return CampaignConflictOpportunityState(
        campaign_id=request.state.campaign_id,
        opportunities=(*request.state.opportunities, opportunity),
    )


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
