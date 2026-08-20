from __future__ import annotations

from towr.domain.action_execution_models import (
    SkippedCastingTestAfterAttackRequest,
    SkippedCastingTestAfterAttackResult,
)
from towr.domain.magic_models import (
    MiscastPoolIncreaseRequest,
    MiscastPoolIncreaseSourceKind,
    MiscastPoolResolutionRequest,
)
from towr.domain.turn_models import CombatActionKind
from towr.rules.attack_action_execution import ATTACK_ACTION_EXECUTION_RULE_ID
from towr.rules.miscast_pool_resolution import (
    MISCAST_POOL_RULE_ID,
    resolve_miscast_pool_increase,
)


SKIPPED_CASTING_TEST_RULE_ID = "RULE-MAGIC-004:skipped-casting-test"


def resolve_skipped_casting_test_after_attack(
    request: SkippedCastingTestAfterAttackRequest,
) -> SkippedCastingTestAfterAttackResult:
    """Add one Miscast die when an active caster spends an action attacking."""
    attack = request.attack
    if attack.slot.declaration.kind is not CombatActionKind.ATTACK:
        raise ValueError("skipped Casting Test source must be an Attack action")
    receipt = attack.slot.execution
    assert receipt is not None
    if receipt.executor_rule_id != ATTACK_ACTION_EXECUTION_RULE_ID:
        raise ValueError("Attack action receipt uses another executor")

    source = MiscastPoolIncreaseRequest(
        resolution_id=f"{request.id}:increase",
        target_id=request.caster_id,
        amount=1,
        source_kind=MiscastPoolIncreaseSourceKind.ACTION,
        source_id=attack.request_id,
        trigger_rule_id=request.rule_id,
        rule_id=request.rule_id,
    )
    pool = resolve_miscast_pool_increase(
        MiscastPoolResolutionRequest(
            id=f"{request.id}:miscast-pool",
            source=source,
            state=request.state,
            wizard_level=request.wizard_level,
            rule_id=MISCAST_POOL_RULE_ID,
        )
    )
    return SkippedCastingTestAfterAttackResult(
        request_id=request.id,
        caster_id=request.caster_id,
        attack=attack,
        source=source,
        miscast_pool=pool,
        state=pool.state,
        applied_rule_ids=_unique_rule_ids(
            request.rule_id,
            *pool.applied_rule_ids,
        ),
    )


def _unique_rule_ids(*rule_ids: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(rule_ids))
