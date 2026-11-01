"""Generate and evaluate one admitted magic balance command (ADR-0043)."""
from towr.application.magic_balance_errors import MagicBalanceGenerationError, MagicBalanceExecutionError
from towr.application.magic_balance_models import (
    MagicBalanceCommand, MagicBalanceResult, _validate_generation_result_source, _validate_staged_result_source,
)
from towr.application.magic_candidate_generation import generate_magic_candidates
from towr.application.magic_candidate_generation_errors import MagicCandidateGenerationError
from towr.application.magic_candidate_generation_models import _validate_generation_source
from towr.application.magic_staged_evaluation_errors import MagicStagedEvaluationError
from towr.application.magic_staged_evaluation_service import evaluate_magic_candidates_staged


def execute_magic_balance(command: MagicBalanceCommand) -> MagicBalanceResult:
    """Return a complete source-bound result or the active phase's typed failure.

    Runners retain their standard indexed RNG and explicit execution options.
    Process callers require an importable main guard. No retry, fallback or
    partial result is added here; BaseException propagates directly.
    """
    if not isinstance(command, MagicBalanceCommand):
        raise TypeError('balance execution requires a typed magic balance command')
    try:
        _validate_generation_source(command.generation_request)
        generated = generate_magic_candidates(command.generation_request)
        _validate_generation_result_source(generated)
        if generated.source_request != command.generation_request:
            raise ValueError('generation result must belong to the full command request')
    except MagicCandidateGenerationError as error:
        raise MagicBalanceGenerationError(command.request_id, error.candidate_id, error.counts,
                                           schema_version=command.schema_version) from error
    except Exception as error:
        raise MagicBalanceGenerationError(command.request_id, schema_version=command.schema_version) from error
    try:
        evaluated = evaluate_magic_candidates_staged(generated.evaluation_request, command.execution)
        _validate_staged_result_source(evaluated)
        if evaluated.source_request != generated.evaluation_request:
            raise ValueError('evaluation result must belong to the exact generated request')
        return MagicBalanceResult(generated, evaluated)
    except MagicStagedEvaluationError as error:
        raise MagicBalanceExecutionError(command.request_id, error.stage_index, error.candidate_id,
                                          schema_version=command.schema_version) from error
    except Exception as error:
        raise MagicBalanceExecutionError(command.request_id, schema_version=command.schema_version) from error
