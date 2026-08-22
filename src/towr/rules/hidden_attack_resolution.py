from __future__ import annotations

from towr.domain.hidden_attack_models import (
    HIDDEN_ATTACK_OPPORTUNITY_RULE_ID,
    MoveQuietlyHiddenAttackExecutionRequest,
    MoveQuietlyHiddenAttackExecutionResult,
    MoveQuietlyHiddenAttackLossRequest,
    MoveQuietlyHiddenAttackLossResult,
    _expected_loss_reason,
)
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.dice import RandomSource
from towr.rules.kernel import ResolutionDecisionProvider


def execute_move_quietly_hidden_attack(
    request: MoveQuietlyHiddenAttackExecutionRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> MoveQuietlyHiddenAttackExecutionResult:
    """Consume one hidden opportunity through the ordinary Attack executor."""
    if request.rule_id != HIDDEN_ATTACK_OPPORTUNITY_RULE_ID:
        raise ValueError("hidden Attack uses an unknown source rule")
    attack = execute_attack_action(
        request.attack,
        rng,
        decisions=decisions,
    )
    return MoveQuietlyHiddenAttackExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        attack=attack,
        revealed_hiding_position_id=request.opportunity.hiding_position_id,
        previous_consumed_opportunity_ids=request.consumed_opportunity_ids,
        consumed_opportunity_ids=(
            *request.consumed_opportunity_ids,
            request.opportunity.id,
        ),
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    request.move_quietly.rule_id,
                    *attack.applied_rule_ids,
                )
            )
        ),
    )


def lose_move_quietly_hidden_attack(
    request: MoveQuietlyHiddenAttackLossRequest,
) -> MoveQuietlyHiddenAttackLossResult:
    """Consume an opportunity when the owner's next action cannot use it."""
    if request.rule_id != HIDDEN_ATTACK_OPPORTUNITY_RULE_ID:
        raise ValueError("hidden opportunity loss uses an unknown source rule")
    return MoveQuietlyHiddenAttackLossResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        reason=_expected_loss_reason(request),
        previous_consumed_opportunity_ids=request.consumed_opportunity_ids,
        consumed_opportunity_ids=(
            *request.consumed_opportunity_ids,
            request.opportunity.id,
        ),
        applied_rule_ids=(request.rule_id, request.move_quietly.rule_id),
    )
