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
from towr.domain.resolution_models import GiveGroundResolutionRequest, GiveGroundResolutionResult
from towr.domain.spatial_models import SpatialBattleState


@dataclass(frozen=True, slots=True)
class HiddenGiveGroundExecutionRequest:
    id: str
    move_quietly: MoveQuietlyActionExecutionResult
    movement: GiveGroundResolutionRequest
    consumed_opportunity_ids: tuple[str, ...] = ()
    rule_id: str = HIDDEN_ATTACK_OPPORTUNITY_RULE_ID
    intervening_movements: tuple[FreeMovementResult | GiveGroundResolutionResult, ...] = ()

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "hidden Give Ground execution id")
        if not isinstance(self.movement, GiveGroundResolutionRequest):
            raise TypeError("movement must be a GiveGroundResolutionRequest")
        if self.rule_id != HIDDEN_ATTACK_OPPORTUNITY_RULE_ID:
            raise ValueError("hidden Give Ground execution uses an unknown rule")
        if isinstance(self.intervening_movements, (str, bytes)):
            raise TypeError("intervening movements must not be a string")
        intervening = tuple(self.intervening_movements)
        consumed = _validate_hidden_give_ground_context(
            self.move_quietly, self.movement, self.consumed_opportunity_ids, intervening,
        )
        object.__setattr__(self, "consumed_opportunity_ids", consumed)
        object.__setattr__(self, "intervening_movements", intervening)


@dataclass(frozen=True, slots=True)
class HiddenGiveGroundLossRequest:
    id: str
    move_quietly: MoveQuietlyActionExecutionResult
    movement: GiveGroundResolutionResult
    consumed_opportunity_ids: tuple[str, ...] = ()
    rule_id: str = HIDDEN_ATTACK_OPPORTUNITY_RULE_ID
    intervening_movements: tuple[FreeMovementResult | GiveGroundResolutionResult, ...] = ()

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "hidden Give Ground loss id")
        if not isinstance(self.movement, GiveGroundResolutionResult):
            raise TypeError("movement must be a completed GiveGroundResolutionResult")
        if self.rule_id != HIDDEN_ATTACK_OPPORTUNITY_RULE_ID:
            raise ValueError("hidden Give Ground loss uses an unknown rule")
        if isinstance(self.intervening_movements, (str, bytes)):
            raise TypeError("intervening movements must not be a string")
        intervening = tuple(self.intervening_movements)
        consumed = _validate_hidden_give_ground_context(
            self.move_quietly, self.movement, self.consumed_opportunity_ids, intervening,
        )
        if "RULE-COMBAT-015:give-ground" not in self.movement.applied_rule_ids:
            raise ValueError("Give Ground movement trace is incomplete")
        object.__setattr__(self, "consumed_opportunity_ids", consumed)
        object.__setattr__(self, "intervening_movements", intervening)


@dataclass(frozen=True, slots=True)
class HiddenGiveGroundLossResult:
    request_id: str
    rule_id: str
    source_request: HiddenGiveGroundLossRequest
    reason: HiddenAttackOpportunityLossReason
    consumed_opportunity_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, HiddenGiveGroundLossRequest):
            raise TypeError("source_request must be a HiddenGiveGroundLossRequest")
        source = self.source_request
        if self.request_id != source.id or self.rule_id != source.rule_id:
            raise ValueError("hidden Give Ground loss has stale provenance")
        if self.reason is not HiddenAttackOpportunityLossReason.LEFT_HIDING_POSITION:
            raise ValueError("hidden Give Ground loss must leave the hiding position")
        opportunity = source.move_quietly.hidden_attack_opportunity
        assert opportunity is not None
        consumed = _validate_consumed_ids(self.consumed_opportunity_ids)
        if consumed != (*source.consumed_opportunity_ids, opportunity.id):
            raise ValueError("hidden Give Ground loss has inconsistent consumption")
        rules = _validate_rule_ids(self.applied_rule_ids)
        if rules != _hidden_give_ground_rule_ids(source):
            raise ValueError("hidden Give Ground loss trace is inconsistent")
        object.__setattr__(self, "consumed_opportunity_ids", consumed)
        object.__setattr__(self, "applied_rule_ids", rules)

    @property
    def previous_consumed_opportunity_ids(self) -> tuple[str, ...]:
        return self.source_request.consumed_opportunity_ids


def _validate_hidden_give_ground_context(
    source: MoveQuietlyActionExecutionResult,
    movement: GiveGroundResolutionRequest | GiveGroundResolutionResult,
    consumed_opportunity_ids: tuple[str, ...],
    intervening_movements: tuple[FreeMovementResult | GiveGroundResolutionResult, ...],
) -> tuple[str, ...]:
    if not isinstance(source, MoveQuietlyActionExecutionResult):
        raise TypeError("move_quietly must be a MoveQuietlyActionExecutionResult")
    opportunity = source.hidden_attack_opportunity
    _validate_opportunity_source(source, opportunity)
    assert opportunity is not None
    if movement.mover_id != opportunity.actor_id:
        raise ValueError("Give Ground belongs to another actor")
    before = movement.state if isinstance(movement, GiveGroundResolutionRequest) else movement.previous_state
    if before.placement_for(movement.mover_id) != source.spatial_state.placement_for(movement.mover_id):
        raise ValueError("Give Ground must start from the hidden placement")
    if before.graph != source.spatial_state.graph:
        raise ValueError("Give Ground uses a different Zone graph")
    source_round = source.spatial_state.round_number
    if before.round_number < source_round:
        raise ValueError("Give Ground must follow Move Quietly")
    if intervening_movements:
        _validate_intervening_movements(source, before, intervening_movements)
    elif before.round_number == source_round and before != source.spatial_state:
        raise ValueError("same-round Give Ground requires the exact post-hiding spatial snapshot or a movement chain")
    if movement.source.resolution_id == source.request_id:
        raise ValueError("Move Quietly cannot be its own Give Ground source")
    if isinstance(consumed_opportunity_ids, str):
        raise TypeError("consumed opportunity IDs must not be a string")
    consumed = _validate_consumed_ids(consumed_opportunity_ids)
    if opportunity.id in consumed:
        raise ValueError("hidden Attack opportunity was already consumed")
    return consumed


def _validate_intervening_movements(
    source: MoveQuietlyActionExecutionResult,
    before: SpatialBattleState,
    movements: tuple[FreeMovementResult | GiveGroundResolutionResult, ...],
) -> None:
    expected = source.spatial_state
    if before.round_number != expected.round_number:
        raise ValueError("intervening movements only support the Move Quietly round")
    owner_placement = expected.placement_for(source.actor_id)
    for movement in movements:
        if isinstance(movement, FreeMovementResult):
            actor_id = movement.actor_id
            if movement.rule_id != "RULE-COMBAT-014:free-movement":
                raise ValueError("intervening free movement uses an unsupported rule")
        elif isinstance(movement, GiveGroundResolutionResult):
            actor_id = movement.mover_id
            if "RULE-COMBAT-015:give-ground" not in movement.applied_rule_ids:
                raise ValueError("intervening Give Ground trace is incomplete")
        else:
            raise TypeError("intervening movements must be completed free movement or Give Ground")
        if actor_id == source.actor_id:
            raise ValueError("intervening movement cannot move the hidden owner")
        if movement.previous_state != expected:
            raise ValueError("intervening movement chain is not continuous from the hidden source")
        if (movement.state.round_number != source.spatial_state.round_number
                or movement.state.graph != source.spatial_state.graph
                or movement.state.placement_for(source.actor_id) != owner_placement):
            raise ValueError("intervening movement changed the hidden context")
        expected = movement.state
    if before != expected:
        raise ValueError("intervening movement chain does not reach the Give Ground snapshot")


def _hidden_give_ground_rule_ids(request: HiddenGiveGroundLossRequest) -> tuple[str, ...]:
    return tuple(dict.fromkeys((
        request.rule_id,
        *request.move_quietly.applied_rule_ids,
        *(rule for movement in request.intervening_movements for rule in movement.applied_rule_ids),
        *request.movement.applied_rule_ids,
    )))
