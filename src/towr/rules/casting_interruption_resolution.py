from __future__ import annotations

from dataclasses import replace

from towr.domain.action_execution_models import (
    SkippedCastingTestAfterAttackRequest,
    SkippedCastingTestAfterAttackResult,
)
from towr.domain.magic_models import (
    CastingAbandonmentOutcome,
    CastingAbandonmentRequest,
    CastingAbandonmentResult,
    MiscastPoolIncreaseRequest,
    MiscastPoolIncreaseSourceKind,
    MiscastPoolResolutionRequest,
    MiscastPreparationRequest,
    MiscastRollRequest,
)
from towr.domain.turn_models import CombatActionKind
from towr.rules.attack_action_execution import ATTACK_ACTION_EXECUTION_RULE_ID
from towr.rules.miscast_pool_resolution import (
    MISCAST_POOL_RULE_ID,
    resolve_miscast_pool_increase,
)
from towr.rules.miscast_resolution import prepare_miscast


SKIPPED_CASTING_TEST_RULE_ID = "RULE-MAGIC-004:skipped-casting-test"
VOLUNTARY_CASTING_ABANDONMENT_RULE_ID = (
    "RULE-MAGIC-004:voluntary-casting-abandonment"
)


def abandon_casting(
    request: CastingAbandonmentRequest,
) -> CastingAbandonmentResult:
    """End active Casting and prepare a voluntary Miscast when possible."""
    if request.state.miscast_dice == 0:
        state = replace(
            request.state,
            casting_successes=0,
            casting_lore_id=None,
            latest_casting_roll_successes=0,
        )
        return CastingAbandonmentResult(
            request_id=request.id,
            caster_id=request.caster_id,
            wizard_level=request.wizard_level,
            previous_state=request.state,
            state=state,
            outcome=CastingAbandonmentOutcome.ENDED_WITHOUT_MISCAST,
            preparation=None,
            applied_rule_ids=(request.rule_id,),
        )

    source = MiscastRollRequest(
        resolution_id=f"{request.id}:miscast-source",
        source_resolution_id=request.id,
        target_id=request.caster_id,
        pool_dice_count=request.state.miscast_dice,
        rule_id=request.rule_id,
    )
    preparation = prepare_miscast(
        MiscastPreparationRequest(
            id=f"{request.id}:preparation",
            source=source,
            state=request.state,
            spell_to_cast=request.spell_to_cast,
            rule_id=request.rule_id,
        )
    )
    return CastingAbandonmentResult(
        request_id=request.id,
        caster_id=request.caster_id,
        wizard_level=request.wizard_level,
        previous_state=request.state,
        state=preparation.state,
        outcome=CastingAbandonmentOutcome.MISCAST_PREPARED,
        preparation=preparation,
        applied_rule_ids=_unique_rule_ids(
            request.rule_id,
            *preparation.applied_rule_ids,
        ),
    )


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
