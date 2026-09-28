"""Generate and evaluate one admitted balance command using the standard RNG."""
from towr.application.melee_balance_errors import MeleeBalanceGenerationError, MeleeBalanceExecutionError
from towr.application.melee_balance_models import MeleeBalanceCommand, MeleeBalanceResult
from towr.application.melee_candidate_generation import generate_melee_candidates
from towr.application.melee_candidate_generation_errors import MeleeCandidateGenerationError
from towr.application.melee_candidate_generation_models import MeleeCandidateGenerationResult
from towr.application.melee_staged_evaluation_errors import MeleeStagedEvaluationError
from towr.application.melee_staged_evaluation_service import evaluate_melee_candidates_staged


def execute_melee_balance(command: MeleeBalanceCommand) -> MeleeBalanceResult:
    """Return a complete source-bound result; no retry, fallback or partial output.

    Process execution requires an importable, guarded caller entry point.
    KeyboardInterrupt/SystemExit propagate without reclassification.
    """
    if not isinstance(command, MeleeBalanceCommand):
        raise TypeError("balance execution requires a typed balance command")
    try:
        generated = generate_melee_candidates(command.generation_request)
        if not isinstance(generated, MeleeCandidateGenerationResult):
            raise TypeError("generator must return a typed generation result")
        if generated.source_request != command.generation_request:
            raise ValueError("generation result must belong to the command request")
    except MeleeCandidateGenerationError as error:
        raise MeleeBalanceGenerationError(command.request_id, error.candidate_id, error.counts) from error
    except Exception as error:
        raise MeleeBalanceGenerationError(command.request_id) from error
    try:
        evaluated = evaluate_melee_candidates_staged(generated.evaluation_request, command.execution)
        return MeleeBalanceResult(generated, evaluated)
    except MeleeStagedEvaluationError as error:
        raise MeleeBalanceExecutionError(command.request_id, error.stage_index, error.candidate_id) from error
    except Exception as error:
        raise MeleeBalanceExecutionError(command.request_id) from error
