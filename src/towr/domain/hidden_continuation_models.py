from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from towr.domain.hidden_attack_models import (
    HIDDEN_ATTACK_OPPORTUNITY_RULE_ID,
    HiddenAttackOpportunityLossReason,
    _validate_bool,
    _validate_consumed_ids,
    _validate_non_empty_string,
    _validate_opportunity_source,
    _validate_rule_ids,
)
from towr.domain.move_quietly_models import (
    MoveQuietlyActionExecutionResult,
    MoveQuietlyHiddenAttackOpportunity,
)
from towr.domain.spatial_models import SpatialBattleState
from towr.domain.turn_models import ActionExecutionReceipt


class HiddenOpportunityContinuationOutcome(str, Enum):
    PRESERVED = "preserved"
    LOST = "lost"


@dataclass(frozen=True, slots=True)
class MoveQuietlyHiddenAttackContinuationRequest:
    id: str
    move_quietly: MoveQuietlyActionExecutionResult
    opportunity: MoveQuietlyHiddenAttackOpportunity
    action: ActionExecutionReceipt
    spatial_state: SpatialBattleState
    hiding_position_id: str | None
    position_revealed: bool
    consumed_opportunity_ids: tuple[str, ...] = ()
    rule_id: str = HIDDEN_ATTACK_OPPORTUNITY_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "hidden continuation id")
        _validate_opportunity_source(self.move_quietly, self.opportunity)
        if not isinstance(self.action, ActionExecutionReceipt):
            raise TypeError("action must be an ActionExecutionReceipt")
        if not isinstance(self.spatial_state, SpatialBattleState):
            raise TypeError("spatial_state must be a SpatialBattleState")
        if self.hiding_position_id is not None:
            _validate_non_empty_string(self.hiding_position_id, "hiding_position_id")
        _validate_bool(self.position_revealed, "position_revealed")
        if self.rule_id != HIDDEN_ATTACK_OPPORTUNITY_RULE_ID:
            raise ValueError("hidden continuation uses an unknown rule")
        if self.action.declaration.produces_attack:
            raise ValueError("hidden continuation requires a non-attacking action")
        if self.action.actor_id != self.opportunity.actor_id:
            raise ValueError("continuation action belongs to another actor")
        if self.action.round_number != self.spatial_state.round_number:
            raise ValueError("continuation action and spatial snapshot use different rounds")
        source_round = self.move_quietly.round_state.round_number
        if (
            self.action.round_number < source_round
            or (
                self.action.round_number == source_round
                and self.action.slot_index <= self.move_quietly.slot.index
            )
        ):
            raise ValueError("continuation action must follow Move Quietly")
        identifiers = (self.id, self.action.id, self.move_quietly.request_id)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("continuation IDs must be distinct")
        self.spatial_state.placement_for(self.opportunity.actor_id)
        if isinstance(self.consumed_opportunity_ids, str):
            raise TypeError("consumed opportunity IDs must not be a string")
        consumed = _validate_consumed_ids(self.consumed_opportunity_ids)
        if self.opportunity.id in consumed:
            raise ValueError("hidden Attack opportunity was already consumed")
        object.__setattr__(self, "consumed_opportunity_ids", consumed)


@dataclass(frozen=True, slots=True)
class MoveQuietlyHiddenAttackContinuationResult:
    request_id: str
    rule_id: str
    source_request: MoveQuietlyHiddenAttackContinuationRequest
    outcome: HiddenOpportunityContinuationOutcome
    loss_reason: HiddenAttackOpportunityLossReason | None
    previous_consumed_opportunity_ids: tuple[str, ...]
    consumed_opportunity_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, MoveQuietlyHiddenAttackContinuationRequest):
            raise TypeError("source_request must be a hidden continuation request")
        source = self.source_request
        if self.request_id != source.id or self.rule_id != source.rule_id:
            raise ValueError("hidden continuation result has stale provenance")
        if not isinstance(self.outcome, HiddenOpportunityContinuationOutcome):
            raise TypeError("outcome must be a HiddenOpportunityContinuationOutcome")
        reason = _continuation_loss_reason(source)
        expected = (
            HiddenOpportunityContinuationOutcome.PRESERVED if reason is None
            else HiddenOpportunityContinuationOutcome.LOST
        )
        if self.outcome is not expected or self.loss_reason is not reason:
            raise ValueError("hidden continuation outcome is inconsistent")
        previous = _validate_consumed_ids(self.previous_consumed_opportunity_ids)
        consumed = _validate_consumed_ids(self.consumed_opportunity_ids)
        expected_consumed = source.consumed_opportunity_ids
        if reason is not None:
            expected_consumed = (*expected_consumed, source.opportunity.id)
        if previous != source.consumed_opportunity_ids or consumed != expected_consumed:
            raise ValueError("hidden continuation consumption is inconsistent")
        rules = _validate_rule_ids(self.applied_rule_ids)
        if rules != _continuation_rule_ids(source):
            raise ValueError("hidden continuation trace is inconsistent")
        object.__setattr__(self, "previous_consumed_opportunity_ids", previous)
        object.__setattr__(self, "consumed_opportunity_ids", consumed)
        object.__setattr__(self, "applied_rule_ids", rules)

    @property
    def remaining_opportunity(self) -> MoveQuietlyHiddenAttackOpportunity | None:
        if self.outcome is HiddenOpportunityContinuationOutcome.PRESERVED:
            return self.source_request.opportunity
        return None


def _continuation_loss_reason(
    request: MoveQuietlyHiddenAttackContinuationRequest,
) -> HiddenAttackOpportunityLossReason | None:
    actor = request.opportunity.actor_id
    if (
        request.spatial_state.placement_for(actor)
        != request.move_quietly.spatial_state.placement_for(actor)
        or request.hiding_position_id != request.opportunity.hiding_position_id
    ):
        return HiddenAttackOpportunityLossReason.LEFT_HIDING_POSITION
    if request.position_revealed:
        return HiddenAttackOpportunityLossReason.POSITION_REVEALED
    return None


def _continuation_rule_ids(
    request: MoveQuietlyHiddenAttackContinuationRequest,
) -> tuple[str, ...]:
    return tuple(dict.fromkeys((
        request.rule_id,
        request.move_quietly.rule_id,
        *request.move_quietly.applied_rule_ids,
        request.action.executor_rule_id,
    )))
