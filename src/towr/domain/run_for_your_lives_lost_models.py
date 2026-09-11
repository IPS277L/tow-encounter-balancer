from __future__ import annotations

from dataclasses import dataclass

from towr.domain.campaign_consequence_models import (
    RunForYourLivesCampaignApplicationResult,
)
from towr.domain.campaign_delay_models import (
    CampaignDelayConsequence,
    CampaignDelayState,
)
from towr.domain.retreat_models import (
    RUN_FOR_YOUR_LIVES_RULE_ID,
    RunForYourLivesOutcome,
)


@dataclass(frozen=True, slots=True)
class RunForYourLivesLostRequest:
    id: str
    source_campaign: RunForYourLivesCampaignApplicationResult
    state: CampaignDelayState
    delay_consequence_id: str
    unfamiliar_territory_reference_id: str
    intended_destination_reference_id: str
    return_delay_reference_id: str
    enemy_opportunity_reference_id: str
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Lost request id")
        if not isinstance(
            self.source_campaign,
            RunForYourLivesCampaignApplicationResult,
        ):
            raise TypeError(
                "source_campaign must be a "
                "RunForYourLivesCampaignApplicationResult"
            )
        consequence = self.source_campaign.consequence
        if consequence.outcome is not RunForYourLivesOutcome.LOST:
            raise ValueError("Run For Your Lives campaign outcome is not Lost")
        if not isinstance(self.state, CampaignDelayState):
            raise TypeError("state must be a CampaignDelayState")
        if self.state.campaign_id != consequence.campaign_id:
            raise ValueError("campaign delay state belongs to another campaign")
        if self.state.has_source_consequence(consequence.id):
            raise ValueError("Lost consequence was already consumed")
        _validate_non_empty_string(
            self.delay_consequence_id,
            "Lost delay_consequence_id",
        )
        if any(
            item.id == self.delay_consequence_id
            for item in self.state.consequences
        ):
            raise ValueError("campaign delay consequence ID is already registered")
        for value, name in (
            (
                self.unfamiliar_territory_reference_id,
                "Lost unfamiliar_territory_reference_id",
            ),
            (
                self.intended_destination_reference_id,
                "Lost intended_destination_reference_id",
            ),
            (self.return_delay_reference_id, "Lost return_delay_reference_id"),
            (
                self.enemy_opportunity_reference_id,
                "Lost enemy_opportunity_reference_id",
            ),
        ):
            _validate_non_empty_string(value, name)
        role_references = (
            self.unfamiliar_territory_reference_id,
            self.intended_destination_reference_id,
            self.return_delay_reference_id,
            self.enemy_opportunity_reference_id,
        )
        _validate_unique_values(role_references, "Lost role references")
        if (
            consequence.specification.concrete_consequence_reference_ids
            != role_references
        ):
            raise ValueError(
                "Lost role references must exactly match the registered "
                "consequence references"
            )
        _validate_non_empty_string(self.rule_id, "Lost rule_id")
        if self.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
            raise ValueError("Lost application uses an unknown rule")


@dataclass(frozen=True, slots=True)
class RunForYourLivesLostResult:
    request_id: str
    rule_id: str
    source_request: RunForYourLivesLostRequest
    consequence: CampaignDelayConsequence
    previous_state: CampaignDelayState
    state: CampaignDelayState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Lost result request_id")
        _validate_non_empty_string(self.rule_id, "Lost result rule_id")
        if not isinstance(self.source_request, RunForYourLivesLostRequest):
            raise TypeError("source_request must be a RunForYourLivesLostRequest")
        if not isinstance(self.consequence, CampaignDelayConsequence):
            raise TypeError("consequence must be a CampaignDelayConsequence")
        if not isinstance(self.previous_state, CampaignDelayState):
            raise TypeError("previous_state must be a CampaignDelayState")
        if not isinstance(self.state, CampaignDelayState):
            raise TypeError("state must be a CampaignDelayState")
        source = self.source_request
        expected_consequence = _delay_consequence(source)
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
            raise ValueError("Run For Your Lives Lost result is stale")


def _delay_consequence(
    request: RunForYourLivesLostRequest,
) -> CampaignDelayConsequence:
    consequence = request.source_campaign.consequence
    specification = consequence.specification
    return CampaignDelayConsequence(
        id=request.delay_consequence_id,
        campaign_id=consequence.campaign_id,
        unfamiliar_territory_reference_id=(
            request.unfamiliar_territory_reference_id
        ),
        intended_destination_reference_id=(
            request.intended_destination_reference_id
        ),
        return_delay_reference_id=request.return_delay_reference_id,
        enemy_opportunity_reference_id=request.enemy_opportunity_reference_id,
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
    request: RunForYourLivesLostRequest,
    consequence: CampaignDelayConsequence,
) -> CampaignDelayState:
    return CampaignDelayState(
        campaign_id=request.state.campaign_id,
        consequences=(*request.state.consequences, consequence),
    )


def _validate_unique_values(values: tuple[str, ...], name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
