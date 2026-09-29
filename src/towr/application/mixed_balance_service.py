"""Generate and evaluate one admitted balance command using the standard RNG."""
from towr.application.mixed_balance_errors import MixedBalanceGenerationError, MixedBalanceExecutionError
from towr.application.mixed_balance_models import MixedBalanceCommand, MixedBalanceResult
from towr.application.mixed_candidate_generation import generate_mixed_candidates
from towr.application.mixed_candidate_generation_errors import MixedCandidateGenerationError
from towr.application.mixed_candidate_generation_models import MixedCandidateGenerationResult
from towr.application.mixed_staged_evaluation_errors import MixedStagedEvaluationError
from towr.application.mixed_staged_evaluation_service import evaluate_mixed_candidates_staged


def execute_mixed_balance(command: MixedBalanceCommand) -> MixedBalanceResult:
    """Return a complete source-bound result; no retry, fallback or partial output.

    Process execution requires an importable, guarded caller entry point.
    KeyboardInterrupt/SystemExit propagate without reclassification.
    """
    if not isinstance(command, MixedBalanceCommand):
        raise TypeError("balance execution requires a typed balance command")
    try:
        generated = generate_mixed_candidates(command.generation_request)
        if not isinstance(generated, MixedCandidateGenerationResult):
            raise TypeError("generator must return a typed generation result")
        if generated.source_request != command.generation_request:
            raise ValueError("generation result must belong to the command request")
    except MixedCandidateGenerationError as error:
        raise MixedBalanceGenerationError(command.request_id, error.candidate_id, error.counts) from error
    except Exception as error:
        raise MixedBalanceGenerationError(command.request_id) from error
    try:
        evaluated = evaluate_mixed_candidates_staged(generated.evaluation_request, command.execution)
        return MixedBalanceResult(generated, evaluated)
    except MixedStagedEvaluationError as error:
        raise MixedBalanceExecutionError(command.request_id, error.stage_index, error.candidate_id) from error
    except Exception as error:
        raise MixedBalanceExecutionError(command.request_id) from error
