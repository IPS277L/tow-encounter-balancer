from towr.application.melee_evaluation_errors import MeleeBalanceEvaluationError
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.balance.melee_assessment import assess_melee_candidate
from towr.balance.melee_evaluation_models import (
    MeleeBalanceCandidateResult, MeleeBalanceEvaluationRequest, MeleeBalanceEvaluationResult,
)
from towr.simulation.npc_melee_models import NpcMeleeSimulationResult
from towr.simulation.npc_melee_parallel import run_npc_melee_simulation_parallel
from towr.simulation.npc_melee_simulation import run_npc_melee_simulation
from towr.simulation.npc_melee_summary import summarize_npc_melee_simulation


def evaluate_melee_candidates(
    request: MeleeBalanceEvaluationRequest, execution: SimulationExecutionOptions,
) -> MeleeBalanceEvaluationResult:
    """Execute the fully admitted list once, retaining only source-bound aggregates.

    Candidates run sequentially; process options apply within each candidate.
    The process caller requires an importable guarded entry point, as in M6.
    """
    if not isinstance(request, MeleeBalanceEvaluationRequest):
        raise TypeError("balance evaluation requires a typed request")
    if not isinstance(execution, SimulationExecutionOptions):
        raise TypeError("balance evaluation requires explicit typed execution options")
    candidates = []
    for candidate, source in zip(request.candidates, request.simulation_requests):
        try:
            if execution.mode is SimulationExecutionMode.SEQUENTIAL:
                result = run_npc_melee_simulation(source)
            else:
                result = run_npc_melee_simulation_parallel(source, workers=execution.workers,
                                                          batch_size=execution.batch_size)
            if not isinstance(result, NpcMeleeSimulationResult):
                raise TypeError("candidate runner must return a typed simulation result")
            if result.source_request != source:
                raise ValueError("candidate runner result must belong to the exact request")
            summary = summarize_npc_melee_simulation(result)
            assessment = assess_melee_candidate(source, summary, request.window)
            candidates.append(MeleeBalanceCandidateResult(candidate.candidate_id, assessment))
            del result  # Do not retain the preceding candidate's records while running the next one.
        except Exception as error:
            raise MeleeBalanceEvaluationError(candidate.candidate_id) from error
    return MeleeBalanceEvaluationResult(request, tuple(candidates))
