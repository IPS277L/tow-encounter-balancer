from __future__ import annotations

from dataclasses import dataclass

from towr.domain.campaign_trapped_other_models import (
    CampaignTrappedOtherCost,
    CampaignTrappedOtherState,
)
from towr.domain.retreat_models import RUN_FOR_YOUR_LIVES_RULE_ID
from towr.domain.run_for_your_lives_trapped_models import (
    RunForYourLivesTrappedCostResult,
    TrappedEscapeCostKind,
    TrappedOtherCostApplicationRequest,
)


@dataclass(frozen=True, slots=True)
class RunForYourLivesTrappedOtherRequest:
    id: str
    source_cost: RunForYourLivesTrappedCostResult
    state: CampaignTrappedOtherState
    other_cost_id: str
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Trapped other request id")
        if not isinstance(self.source_cost, RunForYourLivesTrappedCostResult):
            raise TypeError(
                "source_cost must be a RunForYourLivesTrappedCostResult"
            )
        application = self.source_cost.application_request
        if (
            self.source_cost.decision.cost_kind is not TrappedEscapeCostKind.OTHER
            or self.source_cost.proof.cost_kind is not TrappedEscapeCostKind.OTHER
            or not isinstance(application, TrappedOtherCostApplicationRequest)
        ):
            raise ValueError("Trapped escape cost is not other")
        if not isinstance(self.state, CampaignTrappedOtherState):
            raise TypeError("state must be a CampaignTrappedOtherState")
        if self.state.campaign_id != application.campaign_id:
            raise ValueError("Trapped other state belongs to another campaign")
        if self.state.has_source_application(application.id):
            raise ValueError("Trapped other application was already consumed")
        _validate_non_empty_string(self.other_cost_id, "Trapped other cost id")
        if any(item.id == self.other_cost_id for item in self.state.costs):
            raise ValueError("Trapped other cost ID is already registered")
        _validate_non_empty_string(self.rule_id, "Trapped other rule_id")
        if self.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
            raise ValueError("Trapped other application uses an unknown rule")


@dataclass(frozen=True, slots=True)
class RunForYourLivesTrappedOtherResult:
    request_id: str
    rule_id: str
    source_request: RunForYourLivesTrappedOtherRequest
    cost: CampaignTrappedOtherCost
    previous_state: CampaignTrappedOtherState
    state: CampaignTrappedOtherState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Trapped other result request_id",
        )
        _validate_non_empty_string(self.rule_id, "Trapped other result rule_id")
        if not isinstance(
            self.source_request,
            RunForYourLivesTrappedOtherRequest,
        ):
            raise TypeError(
                "source_request must be a RunForYourLivesTrappedOtherRequest"
            )
        if not isinstance(self.cost, CampaignTrappedOtherCost):
            raise TypeError("cost must be a CampaignTrappedOtherCost")
        if not isinstance(self.previous_state, CampaignTrappedOtherState):
            raise TypeError("previous_state must be a CampaignTrappedOtherState")
        if not isinstance(self.state, CampaignTrappedOtherState):
            raise TypeError("state must be a CampaignTrappedOtherState")
        source = self.source_request
        expected_cost = _other_cost(source)
        expected_state = _state_after_registration(source, expected_cost)
        expected_rules = tuple(
            dict.fromkeys((*source.source_cost.applied_rule_ids, source.rule_id))
        )
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.cost != expected_cost
            or self.previous_state != source.state
            or self.state != expected_state
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Run For Your Lives Trapped other result is stale")


def _other_cost(
    request: RunForYourLivesTrappedOtherRequest,
) -> CampaignTrappedOtherCost:
    source = request.source_cost
    application = source.application_request
    assert isinstance(application, TrappedOtherCostApplicationRequest)
    specification = source.source_request.source_campaign.consequence.specification
    return CampaignTrappedOtherCost(
        id=request.other_cost_id,
        campaign_id=application.campaign_id,
        affected_actor_ids=application.affected_actor_ids,
        consequence_reference_ids=application.consequence_reference_ids,
        description_reference_id=specification.description_reference_id,
        source_application_id=application.id,
        source_proof_id=source.proof.id,
        source_consequence_id=source.proof.source_consequence_id,
        source_specification_id=source.proof.source_specification_id,
        source_decision_id=source.proof.decision_id,
        battle_id=application.battle_id,
        retreat_id=application.retreat_id,
        rule_id=request.rule_id,
    )


def _state_after_registration(
    request: RunForYourLivesTrappedOtherRequest,
    cost: CampaignTrappedOtherCost,
) -> CampaignTrappedOtherState:
    return CampaignTrappedOtherState(
        campaign_id=request.state.campaign_id,
        costs=(*request.state.costs, cost),
    )


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
