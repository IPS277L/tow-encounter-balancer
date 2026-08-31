from __future__ import annotations

from dataclasses import dataclass

from towr.domain.campaign_captivity_models import (
    CampaignCaptivityRecord,
    CampaignCaptivityState,
)
from towr.domain.retreat_models import RUN_FOR_YOUR_LIVES_RULE_ID
from towr.domain.run_for_your_lives_trapped_models import (
    RunForYourLivesTrappedCostResult,
    TrappedCaptureCostApplicationRequest,
    TrappedEscapeCostKind,
)


@dataclass(frozen=True, slots=True)
class TrappedCaptureAssignment:
    capture_id: str
    captive_actor_id: str
    captor_reference_id: str
    consequence_reference_id: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.capture_id, "Trapped capture ID"),
            (self.captive_actor_id, "Trapped captive actor_id"),
            (self.captor_reference_id, "Trapped captor_reference_id"),
            (
                self.consequence_reference_id,
                "Trapped capture consequence_reference_id",
            ),
        ):
            _validate_non_empty_string(value, name)


@dataclass(frozen=True, slots=True)
class RunForYourLivesTrappedCaptureRequest:
    id: str
    source_cost: RunForYourLivesTrappedCostResult
    state: CampaignCaptivityState
    assignments: tuple[TrappedCaptureAssignment, ...]
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Trapped capture request id")
        if not isinstance(self.source_cost, RunForYourLivesTrappedCostResult):
            raise TypeError(
                "source_cost must be a RunForYourLivesTrappedCostResult"
            )
        application = self.source_cost.application_request
        if (
            self.source_cost.decision.cost_kind is not TrappedEscapeCostKind.CAPTURE
            or self.source_cost.proof.cost_kind
            is not TrappedEscapeCostKind.CAPTURE
            or not isinstance(application, TrappedCaptureCostApplicationRequest)
        ):
            raise ValueError("Trapped escape cost is not capture")
        if not isinstance(self.state, CampaignCaptivityState):
            raise TypeError("state must be a CampaignCaptivityState")
        if self.state.campaign_id != application.campaign_id:
            raise ValueError("captivity state belongs to another campaign")
        if self.state.has_source_application(application.id):
            raise ValueError("Trapped capture application was already consumed")

        assignments = tuple(self.assignments)
        if not all(
            isinstance(item, TrappedCaptureAssignment) for item in assignments
        ):
            raise TypeError(
                "assignments must contain TrappedCaptureAssignment values"
            )
        if (
            tuple(item.captive_actor_id for item in assignments)
            != application.affected_actor_ids
        ):
            raise ValueError(
                "Trapped capture assignments must match the affected PC group order"
            )
        if (
            tuple(item.consequence_reference_id for item in assignments)
            != application.consequence_reference_ids
        ):
            raise ValueError(
                "Trapped capture assignments disagree with consequence references"
            )
        _validate_unique_values(
            tuple(item.capture_id for item in assignments),
            "Trapped capture IDs",
        )
        existing_ids = {item.id for item in self.state.captures}
        if any(item.capture_id in existing_ids for item in assignments):
            raise ValueError("Trapped capture ID is already registered")
        if any(
            self.state.is_captive(item.captive_actor_id) for item in assignments
        ):
            raise ValueError("Trapped capture target is already captive")
        _validate_non_empty_string(self.rule_id, "Trapped capture rule_id")
        if self.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
            raise ValueError("Trapped capture application uses an unknown rule")
        object.__setattr__(self, "assignments", assignments)


@dataclass(frozen=True, slots=True)
class RunForYourLivesTrappedCaptureResult:
    request_id: str
    rule_id: str
    source_request: RunForYourLivesTrappedCaptureRequest
    captures: tuple[CampaignCaptivityRecord, ...]
    previous_state: CampaignCaptivityState
    state: CampaignCaptivityState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Trapped capture result request_id",
        )
        _validate_non_empty_string(self.rule_id, "Trapped capture result rule_id")
        if not isinstance(
            self.source_request,
            RunForYourLivesTrappedCaptureRequest,
        ):
            raise TypeError(
                "source_request must be a RunForYourLivesTrappedCaptureRequest"
            )
        captures = tuple(self.captures)
        if not all(isinstance(item, CampaignCaptivityRecord) for item in captures):
            raise TypeError(
                "captures must contain CampaignCaptivityRecord values"
            )
        if not isinstance(self.previous_state, CampaignCaptivityState):
            raise TypeError("previous_state must be a CampaignCaptivityState")
        if not isinstance(self.state, CampaignCaptivityState):
            raise TypeError("state must be a CampaignCaptivityState")
        source = self.source_request
        expected_captures = _capture_records(source)
        expected_state = _state_after_capture(source, expected_captures)
        expected_rules = tuple(
            dict.fromkeys((*source.source_cost.applied_rule_ids, source.rule_id))
        )
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or captures != expected_captures
            or self.previous_state != source.state
            or self.state != expected_state
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Run For Your Lives Trapped capture result is stale")
        object.__setattr__(self, "captures", captures)


def _capture_records(
    request: RunForYourLivesTrappedCaptureRequest,
) -> tuple[CampaignCaptivityRecord, ...]:
    source = request.source_cost
    application = source.application_request
    assert isinstance(application, TrappedCaptureCostApplicationRequest)
    return tuple(
        CampaignCaptivityRecord(
            id=assignment.capture_id,
            campaign_id=application.campaign_id,
            captive_actor_id=assignment.captive_actor_id,
            captor_reference_id=assignment.captor_reference_id,
            consequence_reference_id=assignment.consequence_reference_id,
            source_application_id=application.id,
            source_proof_id=source.proof.id,
            source_consequence_id=source.proof.source_consequence_id,
            battle_id=application.battle_id,
            retreat_id=application.retreat_id,
            rule_id=request.rule_id,
        )
        for assignment in request.assignments
    )


def _state_after_capture(
    request: RunForYourLivesTrappedCaptureRequest,
    captures: tuple[CampaignCaptivityRecord, ...],
) -> CampaignCaptivityState:
    return CampaignCaptivityState(
        campaign_id=request.state.campaign_id,
        captures=(*request.state.captures, *captures),
    )


def _validate_unique_values(values: tuple[str, ...], name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
