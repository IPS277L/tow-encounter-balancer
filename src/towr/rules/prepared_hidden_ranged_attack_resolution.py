from __future__ import annotations

from towr.domain.prepared_hidden_ranged_attack_models import (
    PreparedHiddenRangedAttackExecutionRequest,
    PreparedHiddenRangedAttackExecutionResult,
    _applied_rule_ids,
)
from towr.rules.dice import RandomSource
from towr.rules.kernel import ResolutionDecisionProvider
from towr.rules.prepared_ranged_weapon_attack_resolution import (
    execute_prepared_ranged_weapon_attack,
)


def execute_prepared_hidden_ranged_attack(
    request: PreparedHiddenRangedAttackExecutionRequest,
    rng: RandomSource,
    *,
    decisions: ResolutionDecisionProvider | None = None,
) -> PreparedHiddenRangedAttackExecutionResult:
    """Execute one prepared shot, then consume its hidden opportunity."""
    if not isinstance(request, PreparedHiddenRangedAttackExecutionRequest):
        raise TypeError("request must be a prepared hidden ranged Attack request")
    prepared = execute_prepared_ranged_weapon_attack(
        request.prepared_attack, rng, decisions=decisions
    )
    hidden = request.hidden_attack
    return PreparedHiddenRangedAttackExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        prepared_attack=prepared,
        revealed_hiding_position_id=hidden.opportunity.hiding_position_id,
        previous_consumed_opportunity_ids=hidden.consumed_opportunity_ids,
        consumed_opportunity_ids=(
            *hidden.consumed_opportunity_ids, hidden.opportunity.id,
        ),
        applied_rule_ids=_applied_rule_ids(request, prepared),
    )
