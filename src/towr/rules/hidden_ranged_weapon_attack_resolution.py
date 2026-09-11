from __future__ import annotations

from towr.domain.hidden_attack_models import HIDDEN_ATTACK_OPPORTUNITY_RULE_ID
from towr.domain.hidden_ranged_weapon_attack_models import (
    MoveQuietlyHiddenRangedAttackExecutionRequest,
    MoveQuietlyHiddenRangedAttackExecutionResult,
)
from towr.rules.dice import RandomSource
from towr.rules.kernel import ResolutionDecisionProvider
from towr.rules.ranged_weapon_attack_resolution import (
    execute_ranged_weapon_attack,
)


def execute_move_quietly_hidden_ranged_attack(
    request: MoveQuietlyHiddenRangedAttackExecutionRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> MoveQuietlyHiddenRangedAttackExecutionResult:
    """Consume one hidden opportunity through one profile-aware Attack."""
    if request.rule_id != HIDDEN_ATTACK_OPPORTUNITY_RULE_ID:
        raise ValueError("hidden ranged Attack uses an unknown source rule")
    ranged_attack = execute_ranged_weapon_attack(
        request.ranged_attack,
        rng,
        decisions=decisions,
    )
    hidden = request.hidden_attack
    return MoveQuietlyHiddenRangedAttackExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        ranged_attack=ranged_attack,
        revealed_hiding_position_id=hidden.opportunity.hiding_position_id,
        previous_consumed_opportunity_ids=hidden.consumed_opportunity_ids,
        consumed_opportunity_ids=(
            *hidden.consumed_opportunity_ids,
            hidden.opportunity.id,
        ),
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    hidden.move_quietly.rule_id,
                    *ranged_attack.applied_rule_ids,
                )
            )
        ),
    )
