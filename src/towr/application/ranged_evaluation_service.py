from towr.application.ranged_evaluation_errors import RangedBalanceEvaluationError
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.balance.ranged_assessment import assess_ranged_candidate
from towr.balance.ranged_evaluation_models import (
    RangedBalanceCandidateResult, RangedBalanceEvaluationRequest, RangedBalanceEvaluationResult,
)
from towr.simulation.npc_ranged_models import NpcRangedSimulationResult
from towr.simulation.npc_ranged_parallel import run_npc_ranged_simulation_parallel
from towr.simulation.npc_ranged_simulation import run_npc_ranged_simulation
from towr.simulation.npc_ranged_summary import summarize_npc_ranged_simulation


def evaluate_ranged_candidates(
    request: RangedBalanceEvaluationRequest, execution: SimulationExecutionOptions,
) -> RangedBalanceEvaluationResult:
    """Execute the fully admitted list once, retaining only source-bound aggregates.

    Candidates run sequentially; process options apply within each candidate.
    The process caller requires an importable guarded entry point, as in M3.
    """
    if not isinstance(request, RangedBalanceEvaluationRequest):
        raise TypeError("balance evaluation requires a typed request")
    if not isinstance(execution, SimulationExecutionOptions):
        raise TypeError("balance evaluation requires explicit typed execution options")
    candidates = []
    for candidate, source in zip(request.candidates, request.simulation_requests):
        try:
            if execution.mode is SimulationExecutionMode.SEQUENTIAL:
                result = run_npc_ranged_simulation(source)
            else:
                result = run_npc_ranged_simulation_parallel(source, workers=execution.workers,
                                                          batch_size=execution.batch_size)
            if not isinstance(result, NpcRangedSimulationResult):
                raise TypeError("candidate runner must return a typed simulation result")
            if result.source_request != source:
                raise ValueError("candidate runner result must belong to the exact request")
            summary = summarize_npc_ranged_simulation(result)
            assessment = assess_ranged_candidate(source, summary, request.window)
            candidates.append(RangedBalanceCandidateResult(candidate.candidate_id, assessment))
            del result  # Do not retain the preceding candidate's records while running the next one.
        except Exception as error:
            raise RangedBalanceEvaluationError(candidate.candidate_id) from error
    return RangedBalanceEvaluationResult(request, tuple(candidates))
