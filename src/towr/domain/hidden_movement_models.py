from __future__ import annotations

from dataclasses import dataclass

from towr.domain.hidden_attack_models import (
    HIDDEN_ATTACK_OPPORTUNITY_RULE_ID,
    HiddenAttackOpportunityLossReason,
    _validate_consumed_ids,
    _validate_non_empty_string,
    _validate_opportunity_source,
    _validate_rule_ids,
)
from towr.domain.move_quietly_models import MoveQuietlyActionExecutionResult
from towr.domain.movement_models import FreeMovementResult


@dataclass(frozen=True, slots=True)
class HiddenFreeMovementLossRequest:
    id: str
    move_quietly: MoveQuietlyActionExecutionResult
    movement: FreeMovementResult
    consumed_opportunity_ids: tuple[str, ...] = ()
    rule_id: str = HIDDEN_ATTACK_OPPORTUNITY_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "hidden movement loss id")
        if not isinstance(self.move_quietly, MoveQuietlyActionExecutionResult):
            raise TypeError("move_quietly must be a MoveQuietlyActionExecutionResult")
        opportunity = self.move_quietly.hidden_attack_opportunity
        _validate_opportunity_source(self.move_quietly, opportunity)
        assert opportunity is not None
        if not isinstance(self.movement, FreeMovementResult):
            raise TypeError("movement must be a completed FreeMovementResult")
        if self.rule_id != HIDDEN_ATTACK_OPPORTUNITY_RULE_ID:
            raise ValueError("hidden movement loss uses an unknown rule")
        movement = self.movement
        if movement.rule_id != "RULE-COMBAT-014:free-movement":
            raise ValueError("movement uses an unsupported source rule")
        if movement.actor_id != opportunity.actor_id:
            raise ValueError("movement belongs to another actor")
        source = self.move_quietly
        if movement.previous_state.placement_for(movement.actor_id) != (
            source.spatial_state.placement_for(movement.actor_id)
        ):
            raise ValueError("movement must start from the hidden placement")
        if movement.previous_state.graph != source.spatial_state.graph:
            raise ValueError("movement uses a different Zone graph")
        source_round = source.round_state.round_number
        if movement.round_state.round_number < source_round:
            raise ValueError("movement must follow Move Quietly")
        if movement.round_state.round_number == source_round:
            # Both hiding choices already spend this actor's free move.
            raise ValueError("Move Quietly already used free movement this round")
        if movement.request_id == source.request_id:
            raise ValueError("Move Quietly cannot be its own movement follow-up")
        if isinstance(self.consumed_opportunity_ids, str):
            raise TypeError("consumed opportunity IDs must not be a string")
        consumed = _validate_consumed_ids(self.consumed_opportunity_ids)
        if opportunity.id in consumed:
            raise ValueError("hidden Attack opportunity was already consumed")
        object.__setattr__(self, "consumed_opportunity_ids", consumed)


@dataclass(frozen=True, slots=True)
class HiddenFreeMovementLossResult:
    request_id: str
    rule_id: str
    source_request: HiddenFreeMovementLossRequest
    reason: HiddenAttackOpportunityLossReason
    consumed_opportunity_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, HiddenFreeMovementLossRequest):
            raise TypeError("source_request must be a HiddenFreeMovementLossRequest")
        source = self.source_request
        if self.request_id != source.id or self.rule_id != source.rule_id:
            raise ValueError("hidden movement loss has stale provenance")
        if self.reason is not HiddenAttackOpportunityLossReason.LEFT_HIDING_POSITION:
            raise ValueError("hidden movement loss must leave the hiding position")
        consumed = _validate_consumed_ids(self.consumed_opportunity_ids)
        opportunity = source.move_quietly.hidden_attack_opportunity
        assert opportunity is not None
        if consumed != (*source.consumed_opportunity_ids, opportunity.id):
            raise ValueError("hidden movement loss has inconsistent consumption")
        rules = _validate_rule_ids(self.applied_rule_ids)
        if rules != _hidden_movement_rule_ids(source):
            raise ValueError("hidden movement loss trace is inconsistent")
        object.__setattr__(self, "consumed_opportunity_ids", consumed)
        object.__setattr__(self, "applied_rule_ids", rules)

    @property
    def previous_consumed_opportunity_ids(self) -> tuple[str, ...]:
        return self.source_request.consumed_opportunity_ids


def _hidden_movement_rule_ids(request: HiddenFreeMovementLossRequest) -> tuple[str, ...]:
    return tuple(dict.fromkeys((
        request.rule_id,
        *request.move_quietly.applied_rule_ids,
        *request.movement.applied_rule_ids,
    )))
