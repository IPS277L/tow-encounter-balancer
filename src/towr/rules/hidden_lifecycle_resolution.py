from __future__ import annotations

from towr.domain.hidden_attack_models import MoveQuietlyHiddenAttackLossRequest
from towr.domain.hidden_continuation_models import MoveQuietlyHiddenAttackContinuationRequest
from towr.domain.hidden_lifecycle_models import (
    HiddenLifecycleApplicationRequest,
    HiddenLifecycleApplicationResult,
    HiddenLifecycleState,
    _lifecycle_rule_ids,
    _lifecycle_state_after,
    _validate_lifecycle_attack,
    _validate_lifecycle_continuation,
    _validate_lifecycle_loss,
    _validate_lifecycle_move_quietly,
    _validate_lifecycle_movement,
    _validate_current_opportunity,
    _validate_lifecycle_give_ground,
)
from towr.domain.hidden_give_ground_models import (
    HiddenGiveGroundExecutionRequest,
    HiddenGiveGroundLossRequest,
)
from towr.domain.hidden_movement_models import (
    HiddenFreeMovementExecutionRequest,
    HiddenFreeMovementLossRequest,
)
from towr.domain.hiding_position_models import RegisteredHiddenAttackExecutionRequest
from towr.domain.move_quietly_models import MoveQuietlyActionExecutionRequest
from towr.rules.dice import RandomSource
from towr.rules.free_movement_resolution import resolve_free_movement
from towr.rules.hidden_attack_resolution import lose_move_quietly_hidden_attack
from towr.rules.hidden_continuation_resolution import continue_move_quietly_hidden_attack
from towr.rules.hidden_movement_resolution import lose_hidden_opportunity_after_free_movement
from towr.rules.hidden_give_ground_resolution import lose_hidden_opportunity_after_give_ground
from towr.rules.hiding_position_resolution import execute_registered_hidden_attack
from towr.rules.kernel import ResolutionDecisionProvider
from towr.rules.move_quietly_resolution import execute_move_quietly_action
from towr.rules.spatial_resolution import resolve_give_ground
from towr.rules.test_resolution import TestDecisionProvider


def apply_hidden_lifecycle_result(
    request: HiddenLifecycleApplicationRequest,
) -> HiddenLifecycleApplicationResult:
    """Apply one completed Move Quietly, continuation, loss or registered Attack."""
    if not isinstance(request, HiddenLifecycleApplicationRequest):
        raise TypeError("request must be a HiddenLifecycleApplicationRequest")
    return HiddenLifecycleApplicationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        state=_lifecycle_state_after(request),
        applied_rule_ids=_lifecycle_rule_ids(request),
    )


def execute_hidden_lifecycle_move_quietly(
    state: HiddenLifecycleState,
    request: MoveQuietlyActionExecutionRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> HiddenLifecycleApplicationResult:
    """Execute once from inactive state and activate only a successful hiding result.

    Input snapshots are immutable; RNG and decision-provider effects are not undone.
    """
    _validate_lifecycle_move_quietly(state, request)
    completed = execute_move_quietly_action(request, rng, decisions=decisions)
    return apply_hidden_lifecycle_result(HiddenLifecycleApplicationRequest(
        id=f"{request.id}:hidden-lifecycle", state=state, completed=completed,
    ))


def continue_hidden_lifecycle(
    state: HiddenLifecycleState,
    request: MoveQuietlyHiddenAttackContinuationRequest,
) -> HiddenLifecycleApplicationResult:
    _validate_lifecycle_continuation(state, request)
    completed = continue_move_quietly_hidden_attack(request)
    return apply_hidden_lifecycle_result(HiddenLifecycleApplicationRequest(
        id=f"{request.id}:hidden-lifecycle", state=state, completed=completed,
    ))


def lose_hidden_lifecycle_opportunity(
    state: HiddenLifecycleState,
    request: MoveQuietlyHiddenAttackLossRequest,
) -> HiddenLifecycleApplicationResult:
    """Close one source-bound opportunity without executing or registering an Attack."""
    _validate_lifecycle_loss(state, request)
    completed = lose_move_quietly_hidden_attack(request)
    return apply_hidden_lifecycle_result(HiddenLifecycleApplicationRequest(
        id=f"{request.id}:hidden-lifecycle", state=state, completed=completed,
    ))


def apply_hidden_lifecycle_free_movement(
    state: HiddenLifecycleState,
    request: HiddenFreeMovementLossRequest,
) -> HiddenLifecycleApplicationResult:
    """Apply completed free movement to the active source without moving again."""
    _validate_lifecycle_movement(state, request)
    completed = lose_hidden_opportunity_after_free_movement(request)
    return apply_hidden_lifecycle_result(HiddenLifecycleApplicationRequest(
        id=f"{request.id}:hidden-lifecycle", state=state, completed=completed,
    ))


def execute_hidden_lifecycle_free_movement(
    state: HiddenLifecycleState,
    request: HiddenFreeMovementExecutionRequest,
) -> HiddenLifecycleApplicationResult:
    """Move once and close the active opportunity in one immutable result."""
    if not isinstance(request, HiddenFreeMovementExecutionRequest):
        raise TypeError("request must be a HiddenFreeMovementExecutionRequest")
    _validate_current_opportunity(state, request.move_quietly, request.consumed_opportunity_ids)
    movement = resolve_free_movement(request.movement)
    return apply_hidden_lifecycle_free_movement(state, HiddenFreeMovementLossRequest(
        id=request.id,
        move_quietly=request.move_quietly,
        movement=movement,
        consumed_opportunity_ids=request.consumed_opportunity_ids,
        rule_id=request.rule_id,
    ))


def apply_hidden_lifecycle_give_ground(
    state: HiddenLifecycleState,
    request: HiddenGiveGroundLossRequest,
) -> HiddenLifecycleApplicationResult:
    _validate_lifecycle_give_ground(state, request)
    completed = lose_hidden_opportunity_after_give_ground(request)
    return apply_hidden_lifecycle_result(HiddenLifecycleApplicationRequest(
        id=f"{request.id}:hidden-lifecycle", state=state, completed=completed,
    ))


def execute_hidden_lifecycle_give_ground(
    state: HiddenLifecycleState,
    request: HiddenGiveGroundExecutionRequest,
) -> HiddenLifecycleApplicationResult:
    """Give Ground once and close the active opportunity in one immutable result."""
    if not isinstance(request, HiddenGiveGroundExecutionRequest):
        raise TypeError("request must be a HiddenGiveGroundExecutionRequest")
    _validate_current_opportunity(state, request.move_quietly, request.consumed_opportunity_ids)
    movement = resolve_give_ground(request.movement)
    return apply_hidden_lifecycle_give_ground(state, HiddenGiveGroundLossRequest(
        id=request.id,
        move_quietly=request.move_quietly,
        movement=movement,
        consumed_opportunity_ids=request.consumed_opportunity_ids,
        rule_id=request.rule_id,
        intervening_movements=request.intervening_movements,
    ))


def execute_hidden_lifecycle_attack(
    state: HiddenLifecycleState,
    request: RegisteredHiddenAttackExecutionRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> HiddenLifecycleApplicationResult:
    """Validate current lifecycle before RNG and return all hidden state atomically.

    Input snapshots are immutable; RNG and decision-provider effects are not undone.
    """
    _validate_lifecycle_attack(state, request)
    completed = execute_registered_hidden_attack(request, rng, decisions=decisions)
    return apply_hidden_lifecycle_result(HiddenLifecycleApplicationRequest(
        id=f"{request.id}:hidden-lifecycle", state=state, completed=completed,
    ))
