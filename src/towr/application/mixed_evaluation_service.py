from towr.application.mixed_evaluation_errors import MixedBalanceEvaluationError
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.balance.mixed_assessment import assess_mixed_candidate
from towr.balance.mixed_evaluation_models import (
    MixedBalanceCandidateResult, MixedBalanceEvaluationRequest, MixedBalanceEvaluationResult,
)
from towr.simulation.npc_mixed_models import NpcMixedSimulationResult
from towr.simulation.npc_mixed_parallel import run_npc_mixed_simulation_parallel
from towr.simulation.npc_mixed_simulation import run_npc_mixed_simulation
from towr.simulation.npc_mixed_summary import summarize_npc_mixed_simulation


def evaluate_mixed_candidates(
    request: MixedBalanceEvaluationRequest, execution: SimulationExecutionOptions,
) -> MixedBalanceEvaluationResult:
    """Execute the fully admitted list once, retaining only source-bound aggregates.

    Candidates run sequentially; process options apply within each candidate.
    The process caller requires an importable guarded entry point, as in M7.
    """
    if not isinstance(request, MixedBalanceEvaluationRequest):
        raise TypeError("balance evaluation requires a typed request")
    if not isinstance(execution, SimulationExecutionOptions):
        raise TypeError("balance evaluation requires explicit typed execution options")
    candidates = []
    for candidate, source in zip(request.candidates, request.simulation_requests):
        try:
            if execution.mode is SimulationExecutionMode.SEQUENTIAL:
                result = run_npc_mixed_simulation(source)
            else:
                result = run_npc_mixed_simulation_parallel(source, workers=execution.workers,
                                                          batch_size=execution.batch_size)
            if not isinstance(result, NpcMixedSimulationResult):
                raise TypeError("candidate runner must return a typed simulation result")
            if result.source_request != source:
                raise ValueError("candidate runner result must belong to the exact request")
            summary = summarize_npc_mixed_simulation(result)
            assessment = assess_mixed_candidate(source, summary, request.window)
            candidates.append(MixedBalanceCandidateResult(candidate.candidate_id, assessment))
            del result  # Do not retain the preceding candidate's records while running the next one.
        except Exception as error:
            raise MixedBalanceEvaluationError(candidate.candidate_id) from error
    return MixedBalanceEvaluationResult(request, tuple(candidates))
