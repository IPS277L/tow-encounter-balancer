from towr.application.ranged_evaluation_errors import RangedBalanceEvaluationError
from towr.application.ranged_evaluation_service import evaluate_ranged_candidates
from towr.application.ranged_simulation_models import SimulationExecutionOptions
from towr.application.ranged_staged_evaluation_errors import RangedStagedEvaluationError
from towr.balance.ranged_evaluation_models import RangedBalanceEvaluationResult
from towr.balance.ranged_staged_evaluation import ranged_continuation_candidate_ids
from towr.balance.ranged_staged_evaluation_models import (
    RangedStagedEvaluationRequest, RangedStagedEvaluationResult, _stage_request,
)


def evaluate_ranged_candidates_staged(
    request: RangedStagedEvaluationRequest, execution: SimulationExecutionOptions,
) -> RangedStagedEvaluationResult:
    """Rerun complete batches with fixed options, retaining only full stage reports."""
    if not isinstance(request, RangedStagedEvaluationRequest):
        raise TypeError("staged evaluation requires a typed request")
    if not isinstance(execution, SimulationExecutionOptions):
        raise TypeError("staged evaluation requires explicit typed execution options")
    candidates = request.candidates
    reports = []
    for index in range(len(request.stages)):
        try:
            source = _stage_request(request, index, candidates)
            report = evaluate_ranged_candidates(source, execution)
            if not isinstance(report, RangedBalanceEvaluationResult):
                raise TypeError("stage evaluator must return a typed evaluation report")
            if report.source_request != source:
                raise ValueError("stage report must belong to the exact request")
            reports.append(report)
            kept = set(ranged_continuation_candidate_ids(report))
            candidates = tuple(candidate for candidate in candidates if candidate.candidate_id in kept)
        except RangedBalanceEvaluationError as error:
            raise RangedStagedEvaluationError(index, error.candidate_id) from error
        except Exception as error:
            raise RangedStagedEvaluationError(index, None) from error
        if not candidates:
            break
    return RangedStagedEvaluationResult(request, tuple(reports))
