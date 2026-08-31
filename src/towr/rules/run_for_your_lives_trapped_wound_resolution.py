from __future__ import annotations

from towr.domain.retreat_models import RUN_FOR_YOUR_LIVES_RULE_ID
from towr.domain.run_for_your_lives_trapped_models import (
    TrappedWoundCostApplicationRequest,
)
from towr.domain.run_for_your_lives_trapped_wound_models import (
    RunForYourLivesTrappedWoundRequest,
    RunForYourLivesTrappedWoundResult,
    _expected_target_progress,
    _replay_completed_wounds,
    _result_rule_ids,
)
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleCompletionResult,
    CharacterWoundLifecycleRollResult,
)
from towr.rules.dice import RandomSource
from towr.rules.injury_resolution import WoundDecisionProvider
from towr.rules.wound_lifecycle_resolution import roll_character_wound_lifecycle


def begin_run_for_your_lives_trapped_wound_application(
    request: RunForYourLivesTrappedWoundRequest,
    rng: RandomSource,
    *,
    decisions: WoundDecisionProvider | None = None,
) -> RunForYourLivesTrappedWoundResult:
    """Roll the first assigned Trapped Wound and stop for its Near Miss window."""
    if request.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
        raise ValueError("Trapped Wound application uses an unknown rule")
    replay = _replay_completed_wounds(request, ())
    next_request = replay.next_request
    assert next_request is not None
    pending = roll_character_wound_lifecycle(
        next_request,
        rng,
        decisions=decisions,
    )
    return _result(request, (), pending)


def advance_run_for_your_lives_trapped_wound_application(
    result: RunForYourLivesTrappedWoundResult,
    completion: CharacterWoundLifecycleCompletionResult,
    rng: RandomSource,
    *,
    decisions: WoundDecisionProvider | None = None,
) -> RunForYourLivesTrappedWoundResult:
    """Commit one pending Wound, then roll the next eligible assigned Wound."""
    pending = result.pending_wound
    if pending is None:
        raise ValueError("Trapped Wound application is already complete")
    if not isinstance(completion, CharacterWoundLifecycleCompletionResult):
        raise TypeError("completion must be a Wound lifecycle completion result")
    if completion.source_request.roll != pending:
        raise ValueError("Wound completion belongs to another Trapped application")
    completions = (
        *(
            item
            for target_progress in result.target_progress
            for item in target_progress.completions
        ),
        completion,
    )
    replay = _replay_completed_wounds(result.source_request, completions)
    next_pending = (
        None
        if replay.next_request is None
        else roll_character_wound_lifecycle(
            replay.next_request,
            rng,
            decisions=decisions,
        )
    )
    return _result(result.source_request, completions, next_pending)


def _result(
    request: RunForYourLivesTrappedWoundRequest,
    completions: tuple[CharacterWoundLifecycleCompletionResult, ...],
    pending: CharacterWoundLifecycleRollResult | None,
) -> RunForYourLivesTrappedWoundResult:
    application = request.source_cost.application_request
    assert isinstance(application, TrappedWoundCostApplicationRequest)
    return RunForYourLivesTrappedWoundResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        target_progress=_expected_target_progress(
            request,
            completions,
            pending,
        ),
        pending_wound=pending,
        previous_consumed_application_ids=request.consumed_application_ids,
        consumed_application_ids=(
            *request.consumed_application_ids,
            application.id,
        ),
        applied_rule_ids=_result_rule_ids(request, completions, pending),
    )
