from __future__ import annotations

from dataclasses import replace

from towr.domain.hidden_attack_models import MoveQuietlyHiddenAttackExecutionRequest
from towr.domain.hidden_ranged_weapon_attack_models import (
    MoveQuietlyHiddenRangedAttackExecutionRequest,
)
from towr.domain.hiding_position_models import (
    HidingPositionRegistrationRequest,
    HidingPositionRegistrationResult,
    HidingPositionState,
    RegisteredHiddenAttackExecutionRequest,
    RegisteredHiddenAttackExecutionResult,
    _registered_attack_rule_ids,
    _registered_state,
    _registration_rule_ids,
)
from towr.domain.move_quietly_models import MoveQuietlyActionExecutionRequest
from towr.rules.dice import RandomSource
from towr.rules.hidden_attack_resolution import execute_move_quietly_hidden_attack
from towr.rules.hidden_ranged_weapon_attack_resolution import (
    execute_move_quietly_hidden_ranged_attack,
)
from towr.rules.kernel import ResolutionDecisionProvider
from towr.rules.prepared_hidden_ranged_attack_resolution import (
    execute_prepared_hidden_ranged_attack,
)


def execute_registered_hidden_attack(
    request: RegisteredHiddenAttackExecutionRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> RegisteredHiddenAttackExecutionResult:
    """Return one hidden Attack and its registered position as a single result.

    The request validates history before RNG. Exceptions leave input snapshots
    unchanged; consumed random values and decision-provider effects are not undone.
    """
    if not isinstance(request, RegisteredHiddenAttackExecutionRequest):
        raise TypeError("request must be a RegisteredHiddenAttackExecutionRequest")
    attack = request.attack
    if isinstance(attack, MoveQuietlyHiddenAttackExecutionRequest):
        execution = execute_move_quietly_hidden_attack(attack, rng, decisions=decisions)
    elif isinstance(attack, MoveQuietlyHiddenRangedAttackExecutionRequest):
        execution = execute_move_quietly_hidden_ranged_attack(
            attack, rng, decisions=decisions,
        )
    else:
        execution = execute_prepared_hidden_ranged_attack(
            attack, rng, decisions=decisions,
        )
    registration = register_revealed_hiding_position(HidingPositionRegistrationRequest(
        id=f"{request.id}:registration", state=request.state, execution=execution,
    ))
    return RegisteredHiddenAttackExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        registration=registration,
        applied_rule_ids=_registered_attack_rule_ids(request, registration),
    )


def register_revealed_hiding_position(
    request: HidingPositionRegistrationRequest,
) -> HidingPositionRegistrationResult:
    if not isinstance(request, HidingPositionRegistrationRequest):
        raise TypeError("request must be a HidingPositionRegistrationRequest")
    return HidingPositionRegistrationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        previous_state=request.state,
        state=_registered_state(request),
        applied_rule_ids=_registration_rule_ids(request),
    )


def prepare_move_quietly_with_hiding_positions(
    state: HidingPositionState,
    request: MoveQuietlyActionExecutionRequest,
) -> MoveQuietlyActionExecutionRequest:
    """Bind the actor's current history and revalidate the chosen hiding spot."""
    if not isinstance(state, HidingPositionState):
        raise TypeError("state must be a HidingPositionState")
    if not isinstance(request, MoveQuietlyActionExecutionRequest):
        raise TypeError("request must be a MoveQuietlyActionExecutionRequest")
    if request.actor_id != state.actor_id:
        raise ValueError("Move Quietly belongs to another actor")
    return replace(request, used_hiding_position_ids=state.used_hiding_position_ids)
