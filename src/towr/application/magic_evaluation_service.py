"""Bounded evaluation of a fully admitted magic candidate list (ADR-0040)."""
from towr.application.magic_evaluation_errors import MagicBalanceEvaluationError
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.balance.magic_assessment import assess_magic_candidate
from towr.balance.magic_evaluation_models import (
    MagicBalanceCandidateResult, MagicBalanceEvaluationRequest, MagicBalanceEvaluationResult,
)
from towr.simulation.npc_magic_models import NpcMagicSimulationResult
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation


def evaluate_magic_candidates(
    request: MagicBalanceEvaluationRequest, execution: SimulationExecutionOptions,
) -> MagicBalanceEvaluationResult:
    """Execute each candidate once, retaining only source-bound aggregates.

    Candidates run in input order; process options apply within each candidate.
    Process callers need an importable entry point with a main guard (ADR-0039).
    """
    if not isinstance(request, MagicBalanceEvaluationRequest):
        raise TypeError("magic evaluation requires a typed request")
    if not isinstance(execution, SimulationExecutionOptions):
        raise TypeError("magic evaluation requires explicit typed execution options")
    candidates = []
    for candidate, source in zip(request.candidates, request.simulation_requests):
        try:
            if execution.mode is SimulationExecutionMode.SEQUENTIAL:
                result = run_npc_magic_simulation(source)
            else:
                result = run_npc_magic_simulation_parallel(source, workers=execution.workers,
                                                          batch_size=execution.batch_size)
            if not isinstance(result, NpcMagicSimulationResult):
                raise TypeError("magic candidate runner must return a typed simulation result")
            if result.source_request != source:
                raise ValueError("magic candidate runner result must belong to the exact request")
            summary = summarize_npc_magic_simulation(result)
            assessment = assess_magic_candidate(source, summary, request.window)
            candidates.append(MagicBalanceCandidateResult(candidate.candidate_id, assessment))
            del result  # Release this candidate's full records before the next runner.
        except Exception as error:
            raise MagicBalanceEvaluationError(candidate.candidate_id) from error
    return MagicBalanceEvaluationResult(request, tuple(candidates))
