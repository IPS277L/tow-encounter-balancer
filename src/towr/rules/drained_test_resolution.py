from __future__ import annotations

from towr.domain.drained_test_models import (
    DRAINED_TEST_PREPARATION_RULE_ID,
    DrainedTestPreparationRequest,
    DrainedTestPreparationResult,
    _expected_drained_test_preparation,
)


def prepare_drained_test(
    request: DrainedTestPreparationRequest,
) -> DrainedTestPreparationResult:
    """Remove bonuses and non-Fate Glorious forbidden by Drained."""
    if request.rule_id != DRAINED_TEST_PREPARATION_RULE_ID:
        raise ValueError("Drained Test preparation uses an unknown rule")
    drained_active, removed, removed_quality, test = (
        _expected_drained_test_preparation(request)
    )
    effective = request.combat_surgeon_effective_effects
    return DrainedTestPreparationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        drained_active=drained_active,
        removed_bonus_modifiers=removed,
        removed_quality_modifiers=removed_quality,
        test=test,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    *(effective.applied_rule_ids if effective else ()),
                    *(proof.rule_id for proof in request.fate_glorious_proofs),
                )
            )
        ),
    )
