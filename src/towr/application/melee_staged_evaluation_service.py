from towr.application.melee_evaluation_errors import MeleeBalanceEvaluationError
from towr.application.melee_evaluation_service import evaluate_melee_candidates
from towr.application.ranged_simulation_models import SimulationExecutionOptions
from towr.application.melee_staged_evaluation_errors import MeleeStagedEvaluationError
from towr.balance.melee_evaluation_models import MeleeBalanceEvaluationResult
from towr.balance.melee_staged_evaluation import melee_continuation_candidate_ids
from towr.balance.melee_staged_evaluation_models import (
    MeleeStagedEvaluationRequest, MeleeStagedEvaluationResult, _stage_request,
)


def evaluate_melee_candidates_staged(
    request: MeleeStagedEvaluationRequest, execution: SimulationExecutionOptions,
) -> MeleeStagedEvaluationResult:
    """Rerun complete batches with fixed options, retaining only full stage reports."""
    if not isinstance(request, MeleeStagedEvaluationRequest):
        raise TypeError("staged evaluation requires a typed request")
    if not isinstance(execution, SimulationExecutionOptions):
        raise TypeError("staged evaluation requires explicit typed execution options")
    candidates = request.candidates
    reports = []
    for index in range(len(request.stages)):
        try:
            source = _stage_request(request, index, candidates)
            report = evaluate_melee_candidates(source, execution)
            if not isinstance(report, MeleeBalanceEvaluationResult):
                raise TypeError("stage evaluator must return a typed evaluation report")
            if report.source_request != source:
                raise ValueError("stage report must belong to the exact request")
            reports.append(report)
            kept = set(melee_continuation_candidate_ids(report))
            candidates = tuple(candidate for candidate in candidates if candidate.candidate_id in kept)
        except MeleeBalanceEvaluationError as error:
            raise MeleeStagedEvaluationError(index, error.candidate_id) from error
        except Exception as error:
            raise MeleeStagedEvaluationError(index, None) from error
        if not candidates:
            break
    return MeleeStagedEvaluationResult(request, tuple(reports))
