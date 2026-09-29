from towr.application.mixed_evaluation_errors import MixedBalanceEvaluationError
from towr.application.mixed_evaluation_service import evaluate_mixed_candidates
from towr.application.ranged_simulation_models import SimulationExecutionOptions
from towr.application.mixed_staged_evaluation_errors import MixedStagedEvaluationError
from towr.balance.mixed_evaluation_models import MixedBalanceEvaluationResult
from towr.balance.mixed_staged_evaluation import mixed_continuation_candidate_ids
from towr.balance.mixed_staged_evaluation_models import (
    MixedStagedEvaluationRequest, MixedStagedEvaluationResult, _stage_request,
)


def evaluate_mixed_candidates_staged(
    request: MixedStagedEvaluationRequest, execution: SimulationExecutionOptions,
) -> MixedStagedEvaluationResult:
    """Rerun complete batches with fixed options, retaining only full stage reports."""
    if not isinstance(request, MixedStagedEvaluationRequest):
        raise TypeError("staged evaluation requires a typed request")
    if not isinstance(execution, SimulationExecutionOptions):
        raise TypeError("staged evaluation requires explicit typed execution options")
    candidates = request.candidates
    reports = []
    for index in range(len(request.stages)):
        try:
            source = _stage_request(request, index, candidates)
            report = evaluate_mixed_candidates(source, execution)
            if not isinstance(report, MixedBalanceEvaluationResult):
                raise TypeError("stage evaluator must return a typed evaluation report")
            if report.source_request != source:
                raise ValueError("stage report must belong to the exact request")
            reports.append(report)
            kept = set(mixed_continuation_candidate_ids(report))
            candidates = tuple(candidate for candidate in candidates if candidate.candidate_id in kept)
        except MixedBalanceEvaluationError as error:
            raise MixedStagedEvaluationError(index, error.candidate_id) from error
        except Exception as error:
            raise MixedStagedEvaluationError(index, None) from error
        if not candidates:
            break
    return MixedStagedEvaluationResult(request, tuple(reports))
