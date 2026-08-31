from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from towr.domain.campaign_consequence_models import (
    RunForYourLivesCampaignApplicationResult,
)
from towr.domain.injury_models import DecisionOwner
from towr.domain.retreat_models import (
    RUN_FOR_YOUR_LIVES_RULE_ID,
    RetreatCoverKind,
    RunForYourLivesOutcome,
)


class TrappedEscapeCostKind(str, Enum):
    WOUNDS = "wounds"
    CAPTURE = "capture"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class TrappedEscapeCostDecision:
    id: str
    cost_kind: TrappedEscapeCostKind
    affected_actor_ids: tuple[str, ...]
    consequence_reference_ids: tuple[str, ...]
    decision_owner: DecisionOwner = DecisionOwner.GM

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Trapped cost decision id")
        if not isinstance(self.cost_kind, TrappedEscapeCostKind):
            raise TypeError("cost_kind must be a TrappedEscapeCostKind")
        object.__setattr__(
            self,
            "affected_actor_ids",
            _validate_unique_non_empty_ids(
                self.affected_actor_ids,
                "Trapped affected actor ID",
            ),
        )
        object.__setattr__(
            self,
            "consequence_reference_ids",
            _validate_unique_non_empty_ids(
                self.consequence_reference_ids,
                "Trapped consequence reference ID",
            ),
        )
        if self.decision_owner is not DecisionOwner.GM:
            raise ValueError("the GM decides the Trapped escape cost")


@dataclass(frozen=True, slots=True)
class RunForYourLivesTrappedCostRequest:
    id: str
    source_campaign: RunForYourLivesCampaignApplicationResult
    consumed_consequence_ids: tuple[str, ...] = field(default_factory=tuple)
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Trapped cost request id")
        if not isinstance(
            self.source_campaign,
            RunForYourLivesCampaignApplicationResult,
        ):
            raise TypeError(
                "source_campaign must be a "
                "RunForYourLivesCampaignApplicationResult"
            )
        if (
            self.source_campaign.consequence.outcome
            is not RunForYourLivesOutcome.TRAPPED
        ):
            raise ValueError("Run For Your Lives campaign outcome is not Trapped")
        consumed = _validate_unique_ids(
            self.consumed_consequence_ids,
            "consumed Run For Your Lives consequence ID",
        )
        if self.source_campaign.consequence.id in consumed:
            raise ValueError("Run For Your Lives Trapped consequence was already consumed")
        _validate_non_empty_string(self.rule_id, "Trapped cost rule_id")
        if self.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
            raise ValueError("Run For Your Lives Trapped cost uses an unknown rule")
        object.__setattr__(self, "consumed_consequence_ids", consumed)


@dataclass(frozen=True, slots=True)
class TrappedEscapeCostProof:
    id: str
    source_request_id: str
    source_consequence_id: str
    source_specification_id: str
    decision_id: str
    campaign_id: str
    battle_id: str
    retreat_id: str
    player_character_ids: tuple[str, ...]
    cover_kind: RetreatCoverKind
    cover_proof_id: str
    rearguard_actor_id: str | None
    cost_kind: TrappedEscapeCostKind
    affected_actor_ids: tuple[str, ...]
    consequence_reference_ids: tuple[str, ...]
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        for value, name in (
            (self.id, "Trapped cost proof id"),
            (self.source_request_id, "Trapped cost proof source_request_id"),
            (self.source_consequence_id, "Trapped cost proof source_consequence_id"),
            (
                self.source_specification_id,
                "Trapped cost proof source_specification_id",
            ),
            (self.decision_id, "Trapped cost proof decision_id"),
            (self.campaign_id, "Trapped cost proof campaign_id"),
            (self.battle_id, "Trapped cost proof battle_id"),
            (self.retreat_id, "Trapped cost proof retreat_id"),
            (self.cover_proof_id, "Trapped cost proof cover_proof_id"),
            (self.rule_id, "Trapped cost proof rule_id"),
        ):
            _validate_non_empty_string(value, name)
        player_ids = _validate_unique_non_empty_ids(
            self.player_character_ids,
            "Trapped cost proof player character ID",
        )
        if not isinstance(self.cover_kind, RetreatCoverKind):
            raise TypeError("cover_kind must be a RetreatCoverKind")
        if self.cover_kind is RetreatCoverKind.FATE_REARGUARD:
            _validate_non_empty_string(
                self.rearguard_actor_id,
                "Trapped cost proof rearguard_actor_id",
            )
            if self.rearguard_actor_id not in player_ids:
                raise ValueError("Trapped cost proof rearguard is not a PC")
        elif self.rearguard_actor_id is not None:
            raise ValueError("alternative-price Trapped proof has no rearguard")
        if not isinstance(self.cost_kind, TrappedEscapeCostKind):
            raise TypeError("cost_kind must be a TrappedEscapeCostKind")
        affected = _validate_unique_non_empty_ids(
            self.affected_actor_ids,
            "Trapped cost proof affected actor ID",
        )
        if tuple(actor_id for actor_id in player_ids if actor_id in affected) != affected:
            raise ValueError("Trapped affected actors must follow the player group order")
        references = _validate_unique_non_empty_ids(
            self.consequence_reference_ids,
            "Trapped cost proof consequence reference ID",
        )
        if self.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
            raise ValueError("Trapped cost proof uses an unknown rule")
        object.__setattr__(self, "player_character_ids", player_ids)
        object.__setattr__(self, "affected_actor_ids", affected)
        object.__setattr__(self, "consequence_reference_ids", references)


@dataclass(frozen=True, slots=True)
class TrappedWoundCostApplicationRequest:
    id: str
    source_proof_id: str
    campaign_id: str
    battle_id: str
    retreat_id: str
    affected_actor_ids: tuple[str, ...]
    consequence_reference_ids: tuple[str, ...]
    decision_owner: DecisionOwner = DecisionOwner.GM
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        _validate_application_request(self, "Wound")


@dataclass(frozen=True, slots=True)
class TrappedCaptureCostApplicationRequest:
    id: str
    source_proof_id: str
    campaign_id: str
    battle_id: str
    retreat_id: str
    affected_actor_ids: tuple[str, ...]
    consequence_reference_ids: tuple[str, ...]
    decision_owner: DecisionOwner = DecisionOwner.GM
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        _validate_application_request(self, "capture")


@dataclass(frozen=True, slots=True)
class TrappedOtherCostApplicationRequest:
    id: str
    source_proof_id: str
    campaign_id: str
    battle_id: str
    retreat_id: str
    affected_actor_ids: tuple[str, ...]
    consequence_reference_ids: tuple[str, ...]
    decision_owner: DecisionOwner = DecisionOwner.GM
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        _validate_application_request(self, "other")


TrappedEscapeCostApplicationRequest = (
    TrappedWoundCostApplicationRequest
    | TrappedCaptureCostApplicationRequest
    | TrappedOtherCostApplicationRequest
)


@dataclass(frozen=True, slots=True)
class RunForYourLivesTrappedCostResult:
    request_id: str
    rule_id: str
    source_request: RunForYourLivesTrappedCostRequest
    decision: TrappedEscapeCostDecision
    proof: TrappedEscapeCostProof
    application_request: TrappedEscapeCostApplicationRequest
    previous_consumed_consequence_ids: tuple[str, ...]
    consumed_consequence_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Trapped cost result request_id")
        _validate_non_empty_string(self.rule_id, "Trapped cost result rule_id")
        if not isinstance(self.source_request, RunForYourLivesTrappedCostRequest):
            raise TypeError("source_request must be a RunForYourLivesTrappedCostRequest")
        if not isinstance(self.decision, TrappedEscapeCostDecision):
            raise TypeError("decision must be a TrappedEscapeCostDecision")
        if not isinstance(self.proof, TrappedEscapeCostProof):
            raise TypeError("proof must be a TrappedEscapeCostProof")
        if not isinstance(
            self.application_request,
            (
                TrappedWoundCostApplicationRequest,
                TrappedCaptureCostApplicationRequest,
                TrappedOtherCostApplicationRequest,
            ),
        ):
            raise TypeError("application_request must be a Trapped cost request")
        source = self.source_request
        _validate_decision_for_request(source, self.decision)
        expected_proof = _trapped_cost_proof(source, self.decision)
        expected_application = _trapped_cost_application(expected_proof)
        previous_consumed = _validate_unique_ids(
            self.previous_consumed_consequence_ids,
            "previous consumed Run For Your Lives consequence ID",
        )
        consumed = _validate_unique_ids(
            self.consumed_consequence_ids,
            "consumed Run For Your Lives consequence ID",
        )
        expected_consumed = (
            *source.consumed_consequence_ids,
            source.source_campaign.consequence.id,
        )
        expected_rules = tuple(
            dict.fromkeys((*source.source_campaign.applied_rule_ids, source.rule_id))
        )
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.proof != expected_proof
            or self.application_request != expected_application
            or previous_consumed != source.consumed_consequence_ids
            or consumed != expected_consumed
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Run For Your Lives Trapped result has stale provenance")
        object.__setattr__(
            self,
            "previous_consumed_consequence_ids",
            previous_consumed,
        )
        object.__setattr__(self, "consumed_consequence_ids", consumed)


def _validate_decision_for_request(
    request: RunForYourLivesTrappedCostRequest,
    decision: TrappedEscapeCostDecision,
) -> None:
    if not isinstance(decision, TrappedEscapeCostDecision):
        raise TypeError("decision must be a TrappedEscapeCostDecision")
    consequence = request.source_campaign.consequence
    player_ids = consequence.player_character_ids
    if (
        tuple(
            actor_id
            for actor_id in player_ids
            if actor_id in decision.affected_actor_ids
        )
        != decision.affected_actor_ids
    ):
        raise ValueError("Trapped affected actors must follow the player group order")
    if (
        decision.consequence_reference_ids
        != consequence.specification.concrete_consequence_reference_ids
    ):
        raise ValueError(
            "Trapped decision disagrees with registered consequence references"
        )


def _trapped_cost_proof(
    request: RunForYourLivesTrappedCostRequest,
    decision: TrappedEscapeCostDecision,
) -> TrappedEscapeCostProof:
    consequence = request.source_campaign.consequence
    return TrappedEscapeCostProof(
        id=f"{request.id}:proof",
        source_request_id=request.id,
        source_consequence_id=consequence.id,
        source_specification_id=consequence.specification.id,
        decision_id=decision.id,
        campaign_id=consequence.campaign_id,
        battle_id=consequence.battle_id,
        retreat_id=consequence.retreat_id,
        player_character_ids=consequence.player_character_ids,
        cover_kind=consequence.cover_kind,
        cover_proof_id=consequence.cover_proof_id,
        rearguard_actor_id=consequence.rearguard_actor_id,
        cost_kind=decision.cost_kind,
        affected_actor_ids=decision.affected_actor_ids,
        consequence_reference_ids=decision.consequence_reference_ids,
        rule_id=request.rule_id,
    )


def _trapped_cost_application(
    proof: TrappedEscapeCostProof,
) -> TrappedEscapeCostApplicationRequest:
    common = {
        "id": f"{proof.source_request_id}:application",
        "source_proof_id": proof.id,
        "campaign_id": proof.campaign_id,
        "battle_id": proof.battle_id,
        "retreat_id": proof.retreat_id,
        "affected_actor_ids": proof.affected_actor_ids,
        "consequence_reference_ids": proof.consequence_reference_ids,
        "rule_id": proof.rule_id,
    }
    if proof.cost_kind is TrappedEscapeCostKind.WOUNDS:
        return TrappedWoundCostApplicationRequest(**common)
    if proof.cost_kind is TrappedEscapeCostKind.CAPTURE:
        return TrappedCaptureCostApplicationRequest(**common)
    return TrappedOtherCostApplicationRequest(**common)


def _validate_application_request(
    request: TrappedEscapeCostApplicationRequest,
    branch_name: str,
) -> None:
    for value, name in (
        (request.id, f"Trapped {branch_name} application id"),
        (request.source_proof_id, f"Trapped {branch_name} source_proof_id"),
        (request.campaign_id, f"Trapped {branch_name} campaign_id"),
        (request.battle_id, f"Trapped {branch_name} battle_id"),
        (request.retreat_id, f"Trapped {branch_name} retreat_id"),
        (request.rule_id, f"Trapped {branch_name} rule_id"),
    ):
        _validate_non_empty_string(value, name)
    object.__setattr__(
        request,
        "affected_actor_ids",
        _validate_unique_non_empty_ids(
            request.affected_actor_ids,
            f"Trapped {branch_name} affected actor ID",
        ),
    )
    object.__setattr__(
        request,
        "consequence_reference_ids",
        _validate_unique_non_empty_ids(
            request.consequence_reference_ids,
            f"Trapped {branch_name} consequence reference ID",
        ),
    )
    if request.decision_owner is not DecisionOwner.GM:
        raise ValueError(f"the GM applies the Trapped {branch_name} cost")
    if request.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
        raise ValueError(f"Trapped {branch_name} application uses an unknown rule")


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
