from __future__ import annotations

from dataclasses import dataclass

from towr.domain.campaign_consequence_models import (
    RunForYourLivesCampaignApplicationResult,
)
from towr.domain.campaign_debt_models import (
    CampaignDebtObligation,
    CampaignDebtState,
)
from towr.domain.retreat_models import (
    RUN_FOR_YOUR_LIVES_RULE_ID,
    RunForYourLivesOutcome,
)


@dataclass(frozen=True, slots=True)
class RunForYourLivesIndebtedRequest:
    id: str
    source_campaign: RunForYourLivesCampaignApplicationResult
    state: CampaignDebtState
    obligation_id: str
    creditor_reference_id: str
    debt_reference_id: str
    repayment_reference_id: str
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Indebted request id")
        if not isinstance(
            self.source_campaign,
            RunForYourLivesCampaignApplicationResult,
        ):
            raise TypeError(
                "source_campaign must be a "
                "RunForYourLivesCampaignApplicationResult"
            )
        consequence = self.source_campaign.consequence
        if consequence.outcome is not RunForYourLivesOutcome.INDEBTED:
            raise ValueError("Run For Your Lives campaign outcome is not Indebted")
        if not isinstance(self.state, CampaignDebtState):
            raise TypeError("state must be a CampaignDebtState")
        if self.state.campaign_id != consequence.campaign_id:
            raise ValueError("campaign debt state belongs to another campaign")
        if self.state.has_source_consequence(consequence.id):
            raise ValueError("Indebted consequence was already consumed")
        _validate_non_empty_string(self.obligation_id, "Indebted obligation_id")
        if any(item.id == self.obligation_id for item in self.state.obligations):
            raise ValueError("campaign debt obligation ID is already registered")
        for value, name in (
            (self.creditor_reference_id, "Indebted creditor_reference_id"),
            (self.debt_reference_id, "Indebted debt_reference_id"),
            (self.repayment_reference_id, "Indebted repayment_reference_id"),
        ):
            _validate_non_empty_string(value, name)
        role_references = (
            self.creditor_reference_id,
            self.debt_reference_id,
            self.repayment_reference_id,
        )
        _validate_unique_values(role_references, "Indebted role references")
        if (
            consequence.specification.concrete_consequence_reference_ids
            != role_references
        ):
            raise ValueError(
                "Indebted role references must exactly match the registered "
                "consequence references"
            )
        _validate_non_empty_string(self.rule_id, "Indebted rule_id")
        if self.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
            raise ValueError("Indebted application uses an unknown rule")


@dataclass(frozen=True, slots=True)
class RunForYourLivesIndebtedResult:
    request_id: str
    rule_id: str
    source_request: RunForYourLivesIndebtedRequest
    obligation: CampaignDebtObligation
    previous_state: CampaignDebtState
    state: CampaignDebtState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Indebted result request_id")
        _validate_non_empty_string(self.rule_id, "Indebted result rule_id")
        if not isinstance(self.source_request, RunForYourLivesIndebtedRequest):
            raise TypeError(
                "source_request must be a RunForYourLivesIndebtedRequest"
            )
        if not isinstance(self.obligation, CampaignDebtObligation):
            raise TypeError("obligation must be a CampaignDebtObligation")
        if not isinstance(self.previous_state, CampaignDebtState):
            raise TypeError("previous_state must be a CampaignDebtState")
        if not isinstance(self.state, CampaignDebtState):
            raise TypeError("state must be a CampaignDebtState")
        source = self.source_request
        expected_obligation = _debt_obligation(source)
        expected_state = _state_after_registration(source, expected_obligation)
        expected_rules = tuple(
            dict.fromkeys((*source.source_campaign.applied_rule_ids, source.rule_id))
        )
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.obligation != expected_obligation
            or self.previous_state != source.state
            or self.state != expected_state
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Run For Your Lives Indebted result is stale")


def _debt_obligation(
    request: RunForYourLivesIndebtedRequest,
) -> CampaignDebtObligation:
    consequence = request.source_campaign.consequence
    specification = consequence.specification
    return CampaignDebtObligation(
        id=request.obligation_id,
        campaign_id=consequence.campaign_id,
        creditor_reference_id=request.creditor_reference_id,
        debt_reference_id=request.debt_reference_id,
        repayment_reference_id=request.repayment_reference_id,
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
    request: RunForYourLivesIndebtedRequest,
    obligation: CampaignDebtObligation,
) -> CampaignDebtState:
    return CampaignDebtState(
        campaign_id=request.state.campaign_id,
        obligations=(*request.state.obligations, obligation),
    )


def _validate_unique_values(values: tuple[str, ...], name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
