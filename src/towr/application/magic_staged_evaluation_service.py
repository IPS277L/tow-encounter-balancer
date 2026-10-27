"""Complete repeated magic batches through the existing bounded evaluator."""
from towr.application.magic_evaluation_errors import MagicBalanceEvaluationError
from towr.application.magic_evaluation_service import evaluate_magic_candidates
from towr.application.magic_staged_evaluation_errors import MagicStagedEvaluationError
from towr.application.ranged_simulation_models import SimulationExecutionOptions
from towr.balance.magic_evaluation_models import MagicBalanceEvaluationResult
from towr.balance.magic_staged_evaluation import magic_continuation_candidate_ids
from towr.balance.magic_staged_evaluation_models import (
    MagicStagedEvaluationRequest, MagicStagedEvaluationResult, _stage_request,
)


def evaluate_magic_candidates_staged(
    request: MagicStagedEvaluationRequest, execution: SimulationExecutionOptions,
) -> MagicStagedEvaluationResult:
    """Run reached stages in order with fixed options and no prefix reuse.

    The process caller needs an importable entry point with a main guard.
    Successful results retain only inputs and complete aggregate stage reports.
    """
    if not isinstance(request, MagicStagedEvaluationRequest):
        raise TypeError("magic staged evaluation requires a typed request")
    if not isinstance(execution, SimulationExecutionOptions):
        raise TypeError("magic staged evaluation requires explicit typed execution options")
    candidates = request.candidates
    reports = []
    for index in range(len(request.stages)):
        try:
            source = _stage_request(request, index, candidates)
            report = evaluate_magic_candidates(source, execution)
            if not isinstance(report, MagicBalanceEvaluationResult):
                raise TypeError("magic stage evaluator must return a typed evaluation report")
            if report.source_request != source:
                raise ValueError("magic stage report must belong to the exact request")
            reports.append(report)
            kept = set(magic_continuation_candidate_ids(report))
            candidates = tuple(candidate for candidate in candidates if candidate.candidate_id in kept)
        except MagicBalanceEvaluationError as error:
            raise MagicStagedEvaluationError(index, error.candidate_id) from error
        except Exception as error:
            raise MagicStagedEvaluationError(index, None) from error
        if not candidates:
            break
    return MagicStagedEvaluationResult(request, tuple(reports))
