from __future__ import annotations

from dataclasses import dataclass

from towr.domain.campaign_opportunity_models import (
    CampaignGoldenOpportunity,
    CampaignGoldenOpportunityState,
)
from towr.domain.retreat_models import (
    RETREAT_ALTERNATIVE_PRICE_RULE_ID,
    RetreatAlternativePrice,
    RetreatAlternativePriceResolutionResult,
    RetreatMisfortunePriceApplicationRequest,
)


@dataclass(frozen=True, slots=True)
class RetreatMisfortunePriceCampaignRequest:
    """Bind a selected misfortune price to explicit GM-authored campaign facts."""

    id: str
    source_price: RetreatAlternativePriceResolutionResult
    campaign_state: CampaignGoldenOpportunityState
    beneficiary_enemy_id: str
    golden_opportunity_id: str
    description_reference_id: str
    rule_id: str = RETREAT_ALTERNATIVE_PRICE_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.id,
            "Retreat misfortune price application request id",
        )
        if not isinstance(
            self.source_price,
            RetreatAlternativePriceResolutionResult,
        ):
            raise TypeError(
                "source_price must be a RetreatAlternativePriceResolutionResult"
            )
        application = self.source_price.application_request
        if (
            self.source_price.decision.price is not RetreatAlternativePrice.MISFORTUNE
            or self.source_price.proof.price
            is not RetreatAlternativePrice.MISFORTUNE
            or not isinstance(application, RetreatMisfortunePriceApplicationRequest)
        ):
            raise ValueError("Retreat price is not misfortune")
        if application.golden_opportunity_count != 1:
            raise ValueError("Retreat misfortune price must confer one opportunity")
        if not isinstance(self.campaign_state, CampaignGoldenOpportunityState):
            raise TypeError(
                "campaign_state must be a CampaignGoldenOpportunityState"
            )
        _validate_non_empty_string(
            self.beneficiary_enemy_id,
            "Retreat misfortune beneficiary_enemy_id",
        )
        if self.beneficiary_enemy_id not in application.beneficiary_enemy_ids:
            raise ValueError("Retreat misfortune beneficiary is not an eligible enemy")
        if self.campaign_state.has_source_application(application.id):
            raise ValueError("Retreat misfortune price application was already consumed")
        _validate_non_empty_string(
            self.golden_opportunity_id,
            "Retreat misfortune golden_opportunity_id",
        )
        if any(
            opportunity.id == self.golden_opportunity_id
            for opportunity in self.campaign_state.opportunities
        ):
            raise ValueError("golden opportunity ID is already registered")
        _validate_non_empty_string(
            self.description_reference_id,
            "Retreat misfortune description_reference_id",
        )
        _validate_non_empty_string(self.rule_id, "Retreat misfortune price rule_id")
        if self.rule_id != RETREAT_ALTERNATIVE_PRICE_RULE_ID:
            raise ValueError("Retreat misfortune price uses an unknown rule")


@dataclass(frozen=True, slots=True)
class RetreatMisfortunePriceApplicationResult:
    request_id: str
    rule_id: str
    source_request: RetreatMisfortunePriceCampaignRequest
    opportunity: CampaignGoldenOpportunity
    previous_state: CampaignGoldenOpportunityState
    state: CampaignGoldenOpportunityState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Retreat misfortune price result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "Retreat misfortune price result rule_id",
        )
        if not isinstance(
            self.source_request,
            RetreatMisfortunePriceCampaignRequest,
        ):
            raise TypeError(
                "source_request must be a RetreatMisfortunePriceCampaignRequest"
            )
        if not isinstance(self.opportunity, CampaignGoldenOpportunity):
            raise TypeError("opportunity must be a CampaignGoldenOpportunity")
        if not isinstance(self.previous_state, CampaignGoldenOpportunityState):
            raise TypeError("previous_state must be a CampaignGoldenOpportunityState")
        if not isinstance(self.state, CampaignGoldenOpportunityState):
            raise TypeError("state must be a CampaignGoldenOpportunityState")

        source = self.source_request
        expected_opportunity = _registered_opportunity(source)
        expected_state = _state_after_registration(source, expected_opportunity)
        expected_rules = _ordered_rule_ids(
            *source.source_price.applied_rule_ids,
            source.rule_id,
        )
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.opportunity != expected_opportunity
            or self.previous_state != source.campaign_state
            or self.state != expected_state
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Retreat misfortune price result has stale provenance")


def _registered_opportunity(
    request: RetreatMisfortunePriceCampaignRequest,
) -> CampaignGoldenOpportunity:
    application = request.source_price.application_request
    assert isinstance(application, RetreatMisfortunePriceApplicationRequest)
    return CampaignGoldenOpportunity(
        id=request.golden_opportunity_id,
        campaign_id=request.campaign_state.campaign_id,
        beneficiary_enemy_id=request.beneficiary_enemy_id,
        description_reference_id=request.description_reference_id,
        source_application_id=application.id,
        battle_id=application.battle_id,
        retreat_id=application.retreat_id,
        rule_id=request.rule_id,
    )


def _state_after_registration(
    request: RetreatMisfortunePriceCampaignRequest,
    opportunity: CampaignGoldenOpportunity,
) -> CampaignGoldenOpportunityState:
    return CampaignGoldenOpportunityState(
        campaign_id=request.campaign_state.campaign_id,
        opportunities=(*request.campaign_state.opportunities, opportunity),
    )


def _ordered_rule_ids(*rule_ids: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(rule_ids))


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
