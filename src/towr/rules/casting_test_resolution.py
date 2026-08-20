from __future__ import annotations

from dataclasses import replace

from towr.domain.magic_models import (
    CastingTestRequest,
    CastingTestResult,
    MiscastPoolIncreaseRequest,
    MiscastPoolIncreaseSourceKind,
)
from towr.rules.dice import RandomSource
from towr.rules.miscast_pool_resolution import (
    RULE_OF_NINE_RULE_ID,
    rule_of_nine_reroll_lock,
)
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


CASTING_TEST_RULE_ID = "RULE-MAGIC-004:casting-test"


def resolve_casting_test(
    request: CastingTestRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> CastingTestResult:
    guarded_test = replace(
        request.test,
        reroll_locks=(
            *request.test.reroll_locks,
            rule_of_nine_reroll_lock(),
        ),
    )
    test = resolve_test(guarded_test, rng, decisions=decisions)
    latest_successes = test.successes
    state = replace(
        request.state,
        casting_successes=(
            request.state.casting_successes + latest_successes
        ),
        casting_lore_id=request.lore_id,
        latest_casting_roll_successes=latest_successes,
    )
    miscast_dice = test.trace.final_values.count(9)
    follow_ups = (
        (
            MiscastPoolIncreaseRequest(
                resolution_id=f"{request.id}:rule-of-nine",
                target_id=request.caster_id,
                amount=miscast_dice,
                source_kind=MiscastPoolIncreaseSourceKind.TEST,
                source_id=request.test.id,
                trigger_rule_id=request.rule_id,
                rule_id=RULE_OF_NINE_RULE_ID,
            ),
        )
        if miscast_dice
        else ()
    )
    return CastingTestResult(
        request_id=request.id,
        caster_id=request.caster_id,
        lore_id=request.lore_id,
        test=test,
        state=state,
        previous_casting_successes=request.state.casting_successes,
        latest_roll_successes=latest_successes,
        miscast_dice_added=miscast_dice,
        follow_ups=follow_ups,
        applied_rule_ids=(request.rule_id, RULE_OF_NINE_RULE_ID),
    )
