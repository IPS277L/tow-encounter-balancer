from __future__ import annotations

from dataclasses import dataclass

from towr.domain.campaign_consequence_models import (
    RunForYourLivesCampaignApplicationResult,
)
from towr.domain.campaign_intelligence_models import (
    CampaignIntelligenceExposure,
    CampaignIntelligenceState,
)
from towr.domain.retreat_models import (
    RUN_FOR_YOUR_LIVES_RULE_ID,
    RunForYourLivesOutcome,
)


@dataclass(frozen=True, slots=True)
class RunForYourLivesExposedRequest:
    id: str
    source_campaign: RunForYourLivesCampaignApplicationResult
    state: CampaignIntelligenceState
    exposure_id: str
    enemy_reference_id: str
    home_reference_id: str
    shelter_reference_ids: tuple[str, ...]
    weakness_reference_id: str
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Exposed request id")
        if not isinstance(
            self.source_campaign,
            RunForYourLivesCampaignApplicationResult,
        ):
            raise TypeError(
                "source_campaign must be a "
                "RunForYourLivesCampaignApplicationResult"
            )
        consequence = self.source_campaign.consequence
        if consequence.outcome is not RunForYourLivesOutcome.EXPOSED:
            raise ValueError("Run For Your Lives campaign outcome is not Exposed")
        if not isinstance(self.state, CampaignIntelligenceState):
            raise TypeError("state must be a CampaignIntelligenceState")
        if self.state.campaign_id != consequence.campaign_id:
            raise ValueError("campaign intelligence state belongs to another campaign")
        if self.state.has_source_consequence(consequence.id):
            raise ValueError("Exposed consequence was already consumed")
        _validate_non_empty_string(self.exposure_id, "Exposed exposure_id")
        if any(item.id == self.exposure_id for item in self.state.exposures):
            raise ValueError("campaign intelligence exposure ID is already registered")
        _validate_non_empty_string(
            self.enemy_reference_id,
            "Exposed enemy_reference_id",
        )
        _validate_non_empty_string(
            self.home_reference_id,
            "Exposed home_reference_id",
        )
        shelters = _validate_unique_non_empty_ids(
            self.shelter_reference_ids,
            "Exposed shelter reference ID",
        )
        _validate_non_empty_string(
            self.weakness_reference_id,
            "Exposed weakness_reference_id",
        )
        role_references = (
            self.enemy_reference_id,
            self.home_reference_id,
            *shelters,
            self.weakness_reference_id,
        )
        _validate_unique_values(role_references, "Exposed role references")
        if (
            consequence.specification.concrete_consequence_reference_ids
            != role_references
        ):
            raise ValueError(
                "Exposed role references must exactly match the registered "
                "consequence references"
            )
        _validate_non_empty_string(self.rule_id, "Exposed rule_id")
        if self.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
            raise ValueError("Exposed application uses an unknown rule")
        object.__setattr__(self, "shelter_reference_ids", shelters)


@dataclass(frozen=True, slots=True)
class RunForYourLivesExposedResult:
    request_id: str
    rule_id: str
    source_request: RunForYourLivesExposedRequest
    exposure: CampaignIntelligenceExposure
    previous_state: CampaignIntelligenceState
    state: CampaignIntelligenceState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Exposed result request_id")
        _validate_non_empty_string(self.rule_id, "Exposed result rule_id")
        if not isinstance(self.source_request, RunForYourLivesExposedRequest):
            raise TypeError("source_request must be a RunForYourLivesExposedRequest")
        if not isinstance(self.exposure, CampaignIntelligenceExposure):
            raise TypeError("exposure must be a CampaignIntelligenceExposure")
        if not isinstance(self.previous_state, CampaignIntelligenceState):
            raise TypeError("previous_state must be a CampaignIntelligenceState")
        if not isinstance(self.state, CampaignIntelligenceState):
            raise TypeError("state must be a CampaignIntelligenceState")
        source = self.source_request
        expected_exposure = _intelligence_exposure(source)
        expected_state = _state_after_registration(source, expected_exposure)
        expected_rules = tuple(
            dict.fromkeys((*source.source_campaign.applied_rule_ids, source.rule_id))
        )
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.exposure != expected_exposure
            or self.previous_state != source.state
            or self.state != expected_state
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Run For Your Lives Exposed result is stale")


def _intelligence_exposure(
    request: RunForYourLivesExposedRequest,
) -> CampaignIntelligenceExposure:
    consequence = request.source_campaign.consequence
    specification = consequence.specification
    return CampaignIntelligenceExposure(
        id=request.exposure_id,
        campaign_id=consequence.campaign_id,
        enemy_reference_id=request.enemy_reference_id,
        home_reference_id=request.home_reference_id,
        shelter_reference_ids=request.shelter_reference_ids,
        weakness_reference_id=request.weakness_reference_id,
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
    request: RunForYourLivesExposedRequest,
    exposure: CampaignIntelligenceExposure,
) -> CampaignIntelligenceState:
    return CampaignIntelligenceState(
        campaign_id=request.state.campaign_id,
        exposures=(*request.state.exposures, exposure),
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
