from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from towr.domain.action_execution_models import (
    AttackActionExecutionRequest,
    AttackActionExecutionResult,
)
from towr.domain.move_quietly_models import (
    MOVE_QUIETLY_RULE_ID,
    MoveQuietlyActionExecutionResult,
    MoveQuietlyHiddenAttackOpportunity,
    MoveQuietlyOutcome,
)
from towr.domain.spatial_models import SpatialBattleState
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind


HIDDEN_ATTACK_OPPORTUNITY_RULE_ID = (
    "RULE-COMBAT-014:hidden-attack-opportunity-consumption"
)


class HiddenAttackOpportunityLossReason(str, Enum):
    OTHER_ACTION = "other_action"
    LEFT_HIDING_POSITION = "left_hiding_position"
    DIFFERENT_TARGET = "different_target"
    TARGET_AWARE = "target_aware"


@dataclass(frozen=True, slots=True)
class MoveQuietlyHiddenAttackExecutionRequest:
    id: str
    move_quietly: MoveQuietlyActionExecutionResult
    opportunity: MoveQuietlyHiddenAttackOpportunity
    actor_id: str
    target_id: str
    spatial_state: SpatialBattleState
    hiding_position_id: str
    target_is_unaware: bool
    attack: AttackActionExecutionRequest
    consumed_opportunity_ids: tuple[str, ...] = ()
    rule_id: str = HIDDEN_ATTACK_OPPORTUNITY_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "hidden Attack request id")
        _validate_opportunity_source(self.move_quietly, self.opportunity)
        _validate_non_empty_string(self.actor_id, "hidden Attack actor_id")
        _validate_non_empty_string(self.target_id, "hidden Attack target_id")
        if not isinstance(self.spatial_state, SpatialBattleState):
            raise TypeError("spatial_state must be a SpatialBattleState")
        _validate_non_empty_string(
            self.hiding_position_id,
            "hiding_position_id",
        )
        _validate_bool(self.target_is_unaware, "target_is_unaware")
        if not isinstance(self.attack, AttackActionExecutionRequest):
            raise TypeError("attack must be an AttackActionExecutionRequest")
        _validate_non_empty_string(self.rule_id, "hidden Attack rule_id")
        consumed = _validate_consumed_ids(self.consumed_opportunity_ids)
        if self.opportunity.id in consumed:
            raise ValueError("hidden Attack opportunity was already consumed")
        object.__setattr__(self, "consumed_opportunity_ids", consumed)

        if self.actor_id != self.opportunity.actor_id:
            raise ValueError("hidden Attack opportunity belongs to another actor")
        if self.target_id not in self.opportunity.unaware_enemy_ids:
            raise ValueError("hidden Attack target was not unaware after hiding")
        if not self.target_is_unaware:
            raise ValueError("an aware target may oppose the Attack Test")
        if self.hiding_position_id != self.opportunity.hiding_position_id:
            raise ValueError("the actor left the hidden Attack position")
        if self.attack.id == self.move_quietly.request_id:
            raise ValueError("Move Quietly cannot be its own follow-up Attack")
        if (
            self.attack.actor_id != self.actor_id
            or self.attack.target_id != self.target_id
        ):
            raise ValueError("hidden Attack has stale actor or target provenance")
        if self.spatial_state.round_number != self.attack.state.round_number:
            raise ValueError("Attack and spatial snapshots must use one round")
        source_placement = self.move_quietly.spatial_state.placement_for(
            self.actor_id
        )
        actor_placement = self.spatial_state.placement_for(self.actor_id)
        if actor_placement != source_placement:
            raise ValueError("the actor left the hidden Attack placement")
        target_placement = self.spatial_state.placement_for(self.target_id)
        if target_placement.side_id == actor_placement.side_id:
            raise ValueError("hidden Attack target must be an enemy")
        if self.attack.kernel_request.attack.defender_test is not None:
            raise ValueError("hidden Attack must use an unopposed Attack Test")


@dataclass(frozen=True, slots=True)
class MoveQuietlyHiddenAttackExecutionResult:
    request_id: str
    rule_id: str
    source_request: MoveQuietlyHiddenAttackExecutionRequest
    attack: AttackActionExecutionResult
    revealed_hiding_position_id: str
    previous_consumed_opportunity_ids: tuple[str, ...]
    consumed_opportunity_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "hidden Attack request_id")
        _validate_non_empty_string(self.rule_id, "hidden Attack result rule_id")
        if not isinstance(
            self.source_request,
            MoveQuietlyHiddenAttackExecutionRequest,
        ):
            raise TypeError(
                "source_request must be a "
                "MoveQuietlyHiddenAttackExecutionRequest"
            )
        if not isinstance(self.attack, AttackActionExecutionResult):
            raise TypeError("attack must be an AttackActionExecutionResult")
        _validate_non_empty_string(
            self.revealed_hiding_position_id,
            "revealed_hiding_position_id",
        )

        source = self.source_request
        if self.request_id != source.id or self.rule_id != source.rule_id:
            raise ValueError("hidden Attack result has stale provenance")
        if (
            self.attack.request_id != source.attack.id
            or self.attack.actor_id != source.actor_id
            or self.attack.target_id != source.target_id
            or self.attack.slot_index != source.attack.slot_index
            or self.attack.previous_state != source.attack.state
            or self.attack.resolution.request_id
            != source.attack.kernel_request.id
            or self.revealed_hiding_position_id
            != source.opportunity.hiding_position_id
        ):
            raise ValueError("hidden Attack result belongs to another Attack")
        previous = _validate_consumed_ids(
            self.previous_consumed_opportunity_ids
        )
        if previous != source.consumed_opportunity_ids:
            raise ValueError("hidden Attack result has a stale consumption chain")
        consumed = _validate_consumed_ids(self.consumed_opportunity_ids)
        if consumed != (*previous, source.opportunity.id):
            raise ValueError(
                "consumed opportunity IDs must append the hidden opportunity"
            )
        object.__setattr__(
            self,
            "previous_consumed_opportunity_ids",
            previous,
        )
        object.__setattr__(self, "consumed_opportunity_ids", consumed)
        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            source.move_quietly.rule_id,
            *self.attack.applied_rule_ids,
        }
        if not required <= set(rule_ids):
            raise ValueError("hidden Attack trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


@dataclass(frozen=True, slots=True)
class MoveQuietlyHiddenAttackLossRequest:
    id: str
    move_quietly: MoveQuietlyActionExecutionResult
    opportunity: MoveQuietlyHiddenAttackOpportunity
    actor_id: str
    spatial_state: SpatialBattleState
    hiding_position_id: str | None
    next_action_id: str
    declaration: CombatActionDeclaration
    target_id: str | None = None
    target_is_unaware: bool | None = None
    consumed_opportunity_ids: tuple[str, ...] = ()
    rule_id: str = HIDDEN_ATTACK_OPPORTUNITY_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "hidden opportunity loss request id")
        _validate_opportunity_source(self.move_quietly, self.opportunity)
        _validate_non_empty_string(self.actor_id, "hidden opportunity actor_id")
        if not isinstance(self.spatial_state, SpatialBattleState):
            raise TypeError("spatial_state must be a SpatialBattleState")
        if self.hiding_position_id is not None:
            _validate_non_empty_string(
                self.hiding_position_id,
                "hiding_position_id",
            )
        _validate_non_empty_string(self.next_action_id, "next_action_id")
        if not isinstance(self.declaration, CombatActionDeclaration):
            raise TypeError("declaration must be a CombatActionDeclaration")
        _validate_non_empty_string(self.rule_id, "hidden opportunity rule_id")
        if self.next_action_id == self.move_quietly.request_id:
            raise ValueError("Move Quietly cannot be its own next action")
        if self.actor_id != self.opportunity.actor_id:
            raise ValueError("hidden opportunity belongs to another actor")
        consumed = _validate_consumed_ids(self.consumed_opportunity_ids)
        if self.opportunity.id in consumed:
            raise ValueError("hidden Attack opportunity was already consumed")
        object.__setattr__(self, "consumed_opportunity_ids", consumed)

        self.spatial_state.placement_for(self.actor_id)
        if self.declaration.kind is CombatActionKind.ATTACK:
            if self.target_id is None:
                raise ValueError("Attack loss context requires a target_id")
            _validate_non_empty_string(self.target_id, "hidden Attack target_id")
            if not isinstance(self.target_is_unaware, bool):
                raise TypeError(
                    "Attack loss context requires target_is_unaware"
                )
            self.spatial_state.placement_for(self.target_id)
        elif self.target_id is not None or self.target_is_unaware is not None:
            raise ValueError("only an Attack loss context may name a target")
        _expected_loss_reason(self)


@dataclass(frozen=True, slots=True)
class MoveQuietlyHiddenAttackLossResult:
    request_id: str
    rule_id: str
    source_request: MoveQuietlyHiddenAttackLossRequest
    reason: HiddenAttackOpportunityLossReason
    previous_consumed_opportunity_ids: tuple[str, ...]
    consumed_opportunity_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "hidden opportunity loss request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "hidden opportunity loss rule_id",
        )
        if not isinstance(
            self.source_request,
            MoveQuietlyHiddenAttackLossRequest,
        ):
            raise TypeError(
                "source_request must be a MoveQuietlyHiddenAttackLossRequest"
            )
        if not isinstance(self.reason, HiddenAttackOpportunityLossReason):
            raise TypeError("reason must be a HiddenAttackOpportunityLossReason")
        source = self.source_request
        if self.request_id != source.id or self.rule_id != source.rule_id:
            raise ValueError("hidden opportunity loss has stale provenance")
        if self.reason is not _expected_loss_reason(source):
            raise ValueError("hidden opportunity loss reason is inconsistent")
        previous = _validate_consumed_ids(
            self.previous_consumed_opportunity_ids
        )
        if previous != source.consumed_opportunity_ids:
            raise ValueError("hidden opportunity loss has stale consumption")
        consumed = _validate_consumed_ids(self.consumed_opportunity_ids)
        if consumed != (*previous, source.opportunity.id):
            raise ValueError(
                "consumed opportunity IDs must append the lost opportunity"
            )
        object.__setattr__(
            self,
            "previous_consumed_opportunity_ids",
            previous,
        )
        object.__setattr__(self, "consumed_opportunity_ids", consumed)
        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        if {self.rule_id, source.move_quietly.rule_id} - set(rule_ids):
            raise ValueError("hidden opportunity loss trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def _validate_opportunity_source(
    move_quietly: MoveQuietlyActionExecutionResult,
    opportunity: MoveQuietlyHiddenAttackOpportunity,
) -> None:
    if not isinstance(move_quietly, MoveQuietlyActionExecutionResult):
        raise TypeError("move_quietly must be a MoveQuietlyActionExecutionResult")
    if not isinstance(opportunity, MoveQuietlyHiddenAttackOpportunity):
        raise TypeError("opportunity must be a MoveQuietlyHiddenAttackOpportunity")
    if (
        move_quietly.outcome is not MoveQuietlyOutcome.HIDDEN
        or move_quietly.hidden_attack_opportunity != opportunity
        or opportunity.source_request_id != move_quietly.request_id
        or opportunity.rule_id != MOVE_QUIETLY_RULE_ID
    ):
        raise ValueError("hidden Attack opportunity has stale provenance")


def _expected_loss_reason(
    request: MoveQuietlyHiddenAttackLossRequest,
) -> HiddenAttackOpportunityLossReason:
    if request.declaration.kind is not CombatActionKind.ATTACK:
        return HiddenAttackOpportunityLossReason.OTHER_ACTION
    source_placement = request.move_quietly.spatial_state.placement_for(
        request.actor_id
    )
    current_placement = request.spatial_state.placement_for(request.actor_id)
    if (
        current_placement != source_placement
        or request.hiding_position_id != request.opportunity.hiding_position_id
    ):
        return HiddenAttackOpportunityLossReason.LEFT_HIDING_POSITION
    assert request.target_id is not None
    if request.target_id not in request.opportunity.unaware_enemy_ids:
        return HiddenAttackOpportunityLossReason.DIFFERENT_TARGET
    if request.target_is_unaware is not True:
        return HiddenAttackOpportunityLossReason.TARGET_AWARE
    raise ValueError("eligible hidden Attack requires the execution contract")


def _validate_consumed_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    identifiers = tuple(values)
    for identifier in identifiers:
        _validate_non_empty_string(identifier, "consumed opportunity id")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("consumed opportunity IDs must be unique")
    return identifiers


def _validate_rule_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    rule_ids = tuple(values)
    if not rule_ids:
        raise ValueError("applied_rule_ids must not be empty")
    for rule_id in rule_ids:
        _validate_non_empty_string(rule_id, "applied Rule ID")
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("applied_rule_ids must be unique")
    return rule_ids


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
