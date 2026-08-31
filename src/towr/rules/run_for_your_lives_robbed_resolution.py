from __future__ import annotations

from towr.domain.retreat_models import RUN_FOR_YOUR_LIVES_RULE_ID
from towr.domain.run_for_your_lives_robbed_models import (
    RunForYourLivesRobbedInventoryRequest,
    RunForYourLivesRobbedInventoryResult,
    _robbed_transitions,
)


def apply_run_for_your_lives_robbed(
    request: RunForYourLivesRobbedInventoryRequest,
) -> RunForYourLivesRobbedInventoryResult:
    """Drop the GM-selected carried trappings for every PC, without RNG."""
    if request.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
        raise ValueError("Run For Your Lives Robbed uses an unknown rule")
    consequence_id = request.source_campaign.consequence.id
    return RunForYourLivesRobbedInventoryResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        transitions=_robbed_transitions(request),
        previous_consumed_consequence_ids=request.consumed_consequence_ids,
        consumed_consequence_ids=(
            *request.consumed_consequence_ids,
            consequence_id,
        ),
        applied_rule_ids=tuple(
            dict.fromkeys(
                (*request.source_campaign.applied_rule_ids, request.rule_id)
            )
        ),
    )
