from __future__ import annotations

from dataclasses import dataclass, field

from towr.domain.retreat_models import (
    RUN_FOR_YOUR_LIVES_RULE_ID,
    RetreatCoverKind,
    RunForYourLivesCampaignConsequenceRequest,
    RunForYourLivesOutcome,
    classify_run_for_your_lives,
)


@dataclass(frozen=True, slots=True)
class RunForYourLivesConsequenceSpecification:
    """Stable GM-authored references for one typed table outcome."""

    id: str
    outcome: RunForYourLivesOutcome
    description_reference_id: str
    affected_subject_reference_ids: tuple[str, ...]
    concrete_consequence_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "campaign consequence specification id")
        if not isinstance(self.outcome, RunForYourLivesOutcome):
            raise TypeError("outcome must be a RunForYourLivesOutcome")
        _validate_non_empty_string(
            self.description_reference_id,
            "campaign consequence description_reference_id",
        )
        object.__setattr__(
            self,
            "affected_subject_reference_ids",
            _validate_unique_non_empty_ids(
                self.affected_subject_reference_ids,
                "campaign consequence affected subject reference ID",
            ),
        )
        object.__setattr__(
            self,
            "concrete_consequence_reference_ids",
            _validate_unique_non_empty_ids(
                self.concrete_consequence_reference_ids,
                "campaign consequence concrete consequence reference ID",
            ),
        )


@dataclass(frozen=True, slots=True)
class CampaignConsequenceRecord:
    """Registered consequence fact; specialized state mutation is still pending."""

    id: str
    campaign_id: str
    source_request_id: str
    battle_id: str
    retreat_id: str
    player_character_ids: tuple[str, ...]
    cover_kind: RetreatCoverKind
    cover_proof_id: str
    rearguard_actor_id: str | None
    failed_actor_ids: tuple[str, ...]
    complication_ids: tuple[str, ...]
    table_total: int
    outcome: RunForYourLivesOutcome
    specification: RunForYourLivesConsequenceSpecification
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        for value, name in (
            (self.id, "campaign consequence record id"),
            (self.campaign_id, "campaign id"),
            (self.source_request_id, "campaign consequence source_request_id"),
            (self.battle_id, "campaign consequence battle_id"),
            (self.retreat_id, "campaign consequence retreat_id"),
            (self.cover_proof_id, "campaign consequence cover_proof_id"),
            (self.rule_id, "campaign consequence rule_id"),
        ):
            _validate_non_empty_string(value, name)
        player_ids = _validate_unique_non_empty_ids(
            self.player_character_ids,
            "campaign consequence player character ID",
        )
        if not isinstance(self.cover_kind, RetreatCoverKind):
            raise TypeError("cover_kind must be a RetreatCoverKind")
        if self.cover_kind is RetreatCoverKind.FATE_REARGUARD:
            _validate_non_empty_string(
                self.rearguard_actor_id,
                "campaign consequence rearguard_actor_id",
            )
            if self.rearguard_actor_id not in player_ids:
                raise ValueError("campaign consequence rearguard is not a PC")
        elif self.rearguard_actor_id is not None:
            raise ValueError("alternative-price consequence has no rearguard actor")
        failed_ids = _validate_unique_ids(
            self.failed_actor_ids,
            "campaign consequence failed actor ID",
        )
        if any(actor_id not in player_ids for actor_id in failed_ids):
            raise ValueError("campaign consequence failed actor is not a PC")
        complication_ids = _validate_unique_ids(
            self.complication_ids,
            "campaign consequence Complication ID",
        )
        if not isinstance(self.table_total, int) or isinstance(
            self.table_total,
            bool,
        ):
            raise TypeError("campaign consequence table_total must be an integer")
        if self.table_total < 1:
            raise ValueError("campaign consequence table_total must be positive")
        if not isinstance(self.outcome, RunForYourLivesOutcome):
            raise TypeError("outcome must be a RunForYourLivesOutcome")
        if classify_run_for_your_lives(self.table_total) is not self.outcome:
            raise ValueError("campaign consequence outcome disagrees with table total")
        if not isinstance(
            self.specification,
            RunForYourLivesConsequenceSpecification,
        ):
            raise TypeError(
                "specification must be a RunForYourLivesConsequenceSpecification"
            )
        if self.specification.outcome is not self.outcome:
            raise ValueError("campaign consequence specification outcome disagrees")
        if self.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
            raise ValueError("campaign consequence uses an unknown rule")
        object.__setattr__(self, "player_character_ids", player_ids)
        object.__setattr__(self, "failed_actor_ids", failed_ids)
        object.__setattr__(self, "complication_ids", complication_ids)


@dataclass(frozen=True, slots=True)
class CampaignConsequenceState:
    """Narrow audit aggregate of registered campaign consequence facts."""

    campaign_id: str
    consequences: tuple[CampaignConsequenceRecord, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.campaign_id, "campaign id")
        consequences = tuple(self.consequences)
        if not all(
            isinstance(consequence, CampaignConsequenceRecord)
            for consequence in consequences
        ):
            raise TypeError(
                "consequences must contain CampaignConsequenceRecord values"
            )
        if any(
            consequence.campaign_id != self.campaign_id
            for consequence in consequences
        ):
            raise ValueError("all campaign consequences must belong to the campaign")
        _validate_unique_ids(
            tuple(consequence.id for consequence in consequences),
            "campaign consequence record ID",
        )
        _validate_unique_ids(
            tuple(consequence.source_request_id for consequence in consequences),
            "campaign consequence source request ID",
        )
        _validate_unique_ids(
            tuple(consequence.specification.id for consequence in consequences),
            "campaign consequence specification ID",
        )
        object.__setattr__(self, "consequences", consequences)

    def has_source_request(self, source_request_id: str) -> bool:
        _validate_non_empty_string(
            source_request_id,
            "campaign consequence source request id",
        )
        return any(
            consequence.source_request_id == source_request_id
            for consequence in self.consequences
        )


@dataclass(frozen=True, slots=True)
class RunForYourLivesCampaignApplicationRequest:
    id: str
    source_consequence: RunForYourLivesCampaignConsequenceRequest
    campaign_state: CampaignConsequenceState
    consequence_id: str
    specification: RunForYourLivesConsequenceSpecification
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.id,
            "Run For Your Lives campaign application request id",
        )
        if not isinstance(
            self.source_consequence,
            RunForYourLivesCampaignConsequenceRequest,
        ):
            raise TypeError(
                "source_consequence must be a "
                "RunForYourLivesCampaignConsequenceRequest"
            )
        if not isinstance(self.campaign_state, CampaignConsequenceState):
            raise TypeError("campaign_state must be a CampaignConsequenceState")
        if self.campaign_state.has_source_request(self.source_consequence.id):
            raise ValueError("Run For Your Lives consequence was already registered")
        _validate_non_empty_string(
            self.consequence_id,
            "Run For Your Lives consequence_id",
        )
        if any(
            consequence.id == self.consequence_id
            for consequence in self.campaign_state.consequences
        ):
            raise ValueError("campaign consequence ID is already registered")
        if not isinstance(
            self.specification,
            RunForYourLivesConsequenceSpecification,
        ):
            raise TypeError(
                "specification must be a RunForYourLivesConsequenceSpecification"
            )
        if self.specification.outcome is not self.source_consequence.outcome:
            raise ValueError(
                "campaign consequence specification does not match table outcome"
            )
        if any(
            consequence.specification.id == self.specification.id
            for consequence in self.campaign_state.consequences
        ):
            raise ValueError("campaign consequence specification was already used")
        _validate_non_empty_string(
            self.rule_id,
            "Run For Your Lives campaign application rule_id",
        )
        if self.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
            raise ValueError("Run For Your Lives campaign application uses unknown rule")


@dataclass(frozen=True, slots=True)
class RunForYourLivesCampaignApplicationResult:
    request_id: str
    rule_id: str
    source_request: RunForYourLivesCampaignApplicationRequest
    consequence: CampaignConsequenceRecord
    previous_state: CampaignConsequenceState
    state: CampaignConsequenceState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Run For Your Lives campaign application result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "Run For Your Lives campaign application result rule_id",
        )
        if not isinstance(
            self.source_request,
            RunForYourLivesCampaignApplicationRequest,
        ):
            raise TypeError(
                "source_request must be a RunForYourLivesCampaignApplicationRequest"
            )
        if not isinstance(self.consequence, CampaignConsequenceRecord):
            raise TypeError("consequence must be a CampaignConsequenceRecord")
        if not isinstance(self.previous_state, CampaignConsequenceState):
            raise TypeError("previous_state must be a CampaignConsequenceState")
        if not isinstance(self.state, CampaignConsequenceState):
            raise TypeError("state must be a CampaignConsequenceState")
        source = self.source_request
        expected_consequence = _registered_consequence(source)
        expected_state = _state_after_registration(source, expected_consequence)
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.consequence != expected_consequence
            or self.previous_state != source.campaign_state
            or self.state != expected_state
            or self.applied_rule_ids != (source.rule_id,)
        ):
            raise ValueError(
                "Run For Your Lives campaign result has stale provenance"
            )


def _registered_consequence(
    request: RunForYourLivesCampaignApplicationRequest,
) -> CampaignConsequenceRecord:
    source = request.source_consequence
    return CampaignConsequenceRecord(
        id=request.consequence_id,
        campaign_id=request.campaign_state.campaign_id,
        source_request_id=source.id,
        battle_id=source.battle_id,
        retreat_id=source.retreat_id,
        player_character_ids=source.player_character_ids,
        cover_kind=source.cover_kind,
        cover_proof_id=source.cover_proof_id,
        rearguard_actor_id=source.rearguard_actor_id,
        failed_actor_ids=source.failed_actor_ids,
        complication_ids=source.complication_ids,
        table_total=source.table_total,
        outcome=source.outcome,
        specification=request.specification,
        rule_id=request.rule_id,
    )


def _state_after_registration(
    request: RunForYourLivesCampaignApplicationRequest,
    consequence: CampaignConsequenceRecord,
) -> CampaignConsequenceState:
    return CampaignConsequenceState(
        campaign_id=request.campaign_state.campaign_id,
        consequences=(*request.campaign_state.consequences, consequence),
    )


def _validate_unique_non_empty_ids(
    values: tuple[str, ...],
    name: str,
) -> tuple[str, ...]:
    ids = _validate_unique_ids(values, name)
    if not ids:
        raise ValueError(f"{name}s must not be empty")
    return ids


def _validate_unique_ids(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    ids = tuple(values)
    for value in ids:
        _validate_non_empty_string(value, name)
    if len(set(ids)) != len(ids):
        raise ValueError(f"{name}s must be unique")
    return ids


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
