"""Generate and evaluate one admitted balance command using the standard RNG."""
from towr.application.ranged_balance_errors import RangedBalanceGenerationError, RangedBalanceExecutionError
from towr.application.ranged_balance_models import RangedBalanceCommand, RangedBalanceResult
from towr.application.ranged_candidate_generation import generate_ranged_candidates
from towr.application.ranged_candidate_generation_errors import RangedCandidateGenerationError
from towr.application.ranged_candidate_generation_models import RangedCandidateGenerationResult
from towr.application.ranged_staged_evaluation_errors import RangedStagedEvaluationError
from towr.application.ranged_staged_evaluation_service import evaluate_ranged_candidates_staged


def execute_ranged_balance(command: RangedBalanceCommand) -> RangedBalanceResult:
    """Return a complete source-bound result; no retry, fallback or partial output.

    Process execution requires an importable, guarded caller entry point.
    KeyboardInterrupt/SystemExit propagate without reclassification.
    """
    if not isinstance(command, RangedBalanceCommand):
        raise TypeError("balance execution requires a typed balance command")
    try:
        generated = generate_ranged_candidates(command.generation_request)
        if not isinstance(generated, RangedCandidateGenerationResult):
            raise TypeError("generator must return a typed generation result")
        if generated.source_request != command.generation_request:
            raise ValueError("generation result must belong to the command request")
    except RangedCandidateGenerationError as error:
        raise RangedBalanceGenerationError(command.request_id, error.candidate_id, error.counts) from error
    except Exception as error:
        raise RangedBalanceGenerationError(command.request_id) from error
    try:
        evaluated = evaluate_ranged_candidates_staged(generated.evaluation_request, command.execution)
        return RangedBalanceResult(generated, evaluated)
    except RangedStagedEvaluationError as error:
        raise RangedBalanceExecutionError(command.request_id, error.stage_index, error.candidate_id) from error
    except Exception as error:
        raise RangedBalanceExecutionError(command.request_id) from error
