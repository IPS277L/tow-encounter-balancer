from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.hidden_attack_models import (
    MoveQuietlyHiddenAttackLossRequest,
    MoveQuietlyHiddenAttackLossResult,
    _validate_non_empty_string,
    _validate_opportunity_source,
    _validate_rule_ids,
)
from towr.domain.hidden_continuation_models import (
    HiddenOpportunityContinuationOutcome,
    MoveQuietlyHiddenAttackContinuationRequest,
    MoveQuietlyHiddenAttackContinuationResult,
)
from towr.domain.hiding_position_models import (
    HidingPositionState,
    RegisteredHiddenAttackExecutionRequest,
    RegisteredHiddenAttackExecutionResult,
    _unique_ids,
)
from towr.domain.hidden_movement_models import (
    HiddenFreeMovementLossRequest,
    HiddenFreeMovementLossResult,
)
from towr.domain.hidden_give_ground_models import (
    HiddenGiveGroundLossRequest,
    HiddenGiveGroundLossResult,
)
from towr.domain.move_quietly_models import (
    MOVE_QUIETLY_RULE_ID,
    MoveQuietlyActionExecutionRequest,
    MoveQuietlyActionExecutionResult,
    MoveQuietlyHiddenAttackOpportunity,
    MoveQuietlyOutcome,
)


HIDDEN_LIFECYCLE_RULE_ID = "RULE-COMBAT-014:hidden-lifecycle"

type HiddenLifecycleCompletedResult = (
    MoveQuietlyActionExecutionResult
    | MoveQuietlyHiddenAttackContinuationResult
    | MoveQuietlyHiddenAttackLossResult
    | HiddenFreeMovementLossResult
    | HiddenGiveGroundLossResult
    | RegisteredHiddenAttackExecutionResult
)


@dataclass(frozen=True, slots=True)
class HiddenLifecycleState:
    hiding_positions: HidingPositionState
    active_move_quietly: MoveQuietlyActionExecutionResult | None = None
    consumed_opportunity_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.hiding_positions, HidingPositionState):
            raise TypeError("hiding_positions must be a HidingPositionState")
        consumed = _unique_ids(self.consumed_opportunity_ids, "consumed opportunity IDs")
        object.__setattr__(self, "consumed_opportunity_ids", consumed)
        if self.active_move_quietly is not None:
            _validate_activation_source(self, self.active_move_quietly)

    @property
    def actor_id(self) -> str:
        return self.hiding_positions.actor_id

    @property
    def opportunity(self) -> MoveQuietlyHiddenAttackOpportunity | None:
        if self.active_move_quietly is None:
            return None
        return self.active_move_quietly.hidden_attack_opportunity


@dataclass(frozen=True, slots=True)
class HiddenLifecycleApplicationRequest:
    id: str
    state: HiddenLifecycleState
    completed: HiddenLifecycleCompletedResult
    rule_id: str = HIDDEN_LIFECYCLE_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "hidden lifecycle application id")
        _validate_state(self.state)
        if self.rule_id != HIDDEN_LIFECYCLE_RULE_ID:
            raise ValueError("unknown hidden lifecycle rule")
        completed = self.completed
        if isinstance(completed, MoveQuietlyActionExecutionResult):
            _validate_lifecycle_move_quietly(self.state, completed.source_request)
            if completed.outcome is MoveQuietlyOutcome.HIDDEN:
                _validate_activation_source(self.state, completed)
        elif isinstance(completed, MoveQuietlyHiddenAttackContinuationResult):
            _validate_lifecycle_continuation(self.state, completed.source_request)
        elif isinstance(completed, MoveQuietlyHiddenAttackLossResult):
            _validate_lifecycle_loss(self.state, completed.source_request)
        elif isinstance(completed, HiddenFreeMovementLossResult):
            _validate_lifecycle_movement(self.state, completed.source_request)
        elif isinstance(completed, HiddenGiveGroundLossResult):
            _validate_lifecycle_give_ground(self.state, completed.source_request)
        elif isinstance(completed, RegisteredHiddenAttackExecutionResult):
            _validate_lifecycle_attack(self.state, completed.source_request)
        else:
            raise TypeError("completed must be a supported hidden lifecycle result")


@dataclass(frozen=True, slots=True)
class HiddenLifecycleApplicationResult:
    request_id: str
    rule_id: str
    source_request: HiddenLifecycleApplicationRequest
    state: HiddenLifecycleState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, HiddenLifecycleApplicationRequest):
            raise TypeError("source_request must be a HiddenLifecycleApplicationRequest")
        source = self.source_request
        _validate_state(self.state)
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.state != _lifecycle_state_after(source)
        ):
            raise ValueError("hidden lifecycle result has stale provenance or state")
        rules = _validate_rule_ids(self.applied_rule_ids)
        if rules != _lifecycle_rule_ids(source):
            raise ValueError("hidden lifecycle trace is inconsistent")
        object.__setattr__(self, "applied_rule_ids", rules)

    @property
    def previous_state(self) -> HiddenLifecycleState:
        return self.source_request.state

    @property
    def completed(self) -> HiddenLifecycleCompletedResult:
        return self.source_request.completed


def _validate_state(state: HiddenLifecycleState) -> None:
    if not isinstance(state, HiddenLifecycleState):
        raise TypeError("state must be a HiddenLifecycleState")


def _validate_activation_source(
    state: HiddenLifecycleState, source: MoveQuietlyActionExecutionResult,
) -> None:
    if not isinstance(source, MoveQuietlyActionExecutionResult):
        raise TypeError("active source must be a MoveQuietlyActionExecutionResult")
    opportunity = source.hidden_attack_opportunity
    if opportunity is None:
        raise ValueError("activation requires a successful hidden Move Quietly result")
    _validate_opportunity_source(source, opportunity)
    if source.actor_id != state.actor_id:
        raise ValueError("hidden source belongs to another actor")
    if opportunity.id in state.consumed_opportunity_ids:
        raise ValueError("hidden opportunity was already consumed")
    if opportunity.hiding_position_id in state.hiding_positions.used_hiding_position_ids:
        raise ValueError("active hiding position was already used")
    if (source.source_request.used_hiding_position_ids
            != state.hiding_positions.used_hiding_position_ids):
        raise ValueError("hidden source has stale hiding position history")


def _validate_lifecycle_move_quietly(
    state: HiddenLifecycleState,
    request: MoveQuietlyActionExecutionRequest,
) -> None:
    _validate_state(state)
    if not isinstance(request, MoveQuietlyActionExecutionRequest):
        raise TypeError("request must be a MoveQuietlyActionExecutionRequest")
    if state.active_move_quietly is not None:
        raise ValueError("resolve the active hidden opportunity before activation")
    if request.actor_id != state.actor_id:
        raise ValueError("Move Quietly belongs to another actor")
    if request.rule_id != MOVE_QUIETLY_RULE_ID:
        raise ValueError("Move Quietly request uses an unknown source rule")
    if f"{request.id}:hidden" in state.consumed_opportunity_ids:
        raise ValueError("Move Quietly source opportunity was already consumed")
    if request.used_hiding_position_ids != state.hiding_positions.used_hiding_position_ids:
        raise ValueError("Move Quietly has stale hiding position history")


def _validate_current_opportunity(
    state: HiddenLifecycleState,
    source: MoveQuietlyActionExecutionResult,
    consumed: tuple[str, ...],
) -> None:
    _validate_state(state)
    if state.active_move_quietly is None:
        raise ValueError("no active hidden opportunity")
    if source != state.active_move_quietly:
        raise ValueError("request does not use the active hidden source")
    if consumed != state.consumed_opportunity_ids:
        raise ValueError("request has a stale opportunity consumption chain")


def _validate_lifecycle_continuation(
    state: HiddenLifecycleState,
    request: MoveQuietlyHiddenAttackContinuationRequest,
) -> None:
    if not isinstance(request, MoveQuietlyHiddenAttackContinuationRequest):
        raise TypeError("request must be a hidden continuation request")
    _validate_current_opportunity(state, request.move_quietly, request.consumed_opportunity_ids)


def _validate_lifecycle_loss(
    state: HiddenLifecycleState,
    request: MoveQuietlyHiddenAttackLossRequest,
) -> None:
    if not isinstance(request, MoveQuietlyHiddenAttackLossRequest):
        raise TypeError("request must be a hidden opportunity loss request")
    _validate_current_opportunity(state, request.move_quietly, request.consumed_opportunity_ids)


def _validate_lifecycle_movement(
    state: HiddenLifecycleState,
    request: HiddenFreeMovementLossRequest,
) -> None:
    if not isinstance(request, HiddenFreeMovementLossRequest):
        raise TypeError("request must be a HiddenFreeMovementLossRequest")
    _validate_current_opportunity(state, request.move_quietly, request.consumed_opportunity_ids)


def _validate_lifecycle_give_ground(
    state: HiddenLifecycleState,
    request: HiddenGiveGroundLossRequest,
) -> None:
    if not isinstance(request, HiddenGiveGroundLossRequest):
        raise TypeError("request must be a HiddenGiveGroundLossRequest")
    _validate_current_opportunity(state, request.move_quietly, request.consumed_opportunity_ids)


def _validate_lifecycle_attack(
    state: HiddenLifecycleState,
    request: RegisteredHiddenAttackExecutionRequest,
) -> None:
    if not isinstance(request, RegisteredHiddenAttackExecutionRequest):
        raise TypeError("request must be a registered hidden Attack request")
    hidden = request.hidden_request
    _validate_current_opportunity(state, hidden.move_quietly, hidden.consumed_opportunity_ids)
    if request.state != state.hiding_positions:
        raise ValueError("registered Attack has stale hiding position history")


def _lifecycle_state_after(request: HiddenLifecycleApplicationRequest) -> HiddenLifecycleState:
    state, completed = request.state, request.completed
    if isinstance(completed, MoveQuietlyActionExecutionResult):
        if completed.outcome is not MoveQuietlyOutcome.HIDDEN:
            return state
        return replace(state, active_move_quietly=completed)
    if isinstance(completed, MoveQuietlyHiddenAttackContinuationResult):
        if completed.outcome is HiddenOpportunityContinuationOutcome.PRESERVED:
            return state
    if isinstance(completed, (
        MoveQuietlyHiddenAttackContinuationResult, MoveQuietlyHiddenAttackLossResult,
        HiddenFreeMovementLossResult,
        HiddenGiveGroundLossResult,
    )):
        return replace(state, active_move_quietly=None,
                       consumed_opportunity_ids=completed.consumed_opportunity_ids)
    return HiddenLifecycleState(
        hiding_positions=completed.state,
        consumed_opportunity_ids=completed.execution.consumed_opportunity_ids,
    )


def _lifecycle_rule_ids(request: HiddenLifecycleApplicationRequest) -> tuple[str, ...]:
    return tuple(dict.fromkeys((request.rule_id, *request.completed.applied_rule_ids)))
