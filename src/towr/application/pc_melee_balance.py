"""Generate all PC count candidates before executing aggregate-only evaluation."""
from collections.abc import Callable
from dataclasses import replace

from towr.application.pc_melee_balance_models import (
    PcMeleeBalanceExecutionError, PcMeleeBalancePhase, PcMeleeBalanceRequest,
    PcMeleeBalanceResult, PcMeleeCandidateResult, pc_melee_candidate_id,
    pc_melee_count_vectors, project_pc_melee_candidate, select_pc_melee_candidate_ids,
    validate_pc_melee_balance_request,
)
from towr.balance.pc_melee_assessment import PcMeleeCandidateAssessment
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_summary_models import PcMeleeSimulationSummary


def evaluate_pc_melee_balance(request: PcMeleeBalanceRequest,
        simulator: Callable[[PcMeleeSimulationRequest], PcMeleeSimulationSummary]) -> PcMeleeBalanceResult:
    """No retry, fallback, or partial report; the caller selects execution backend."""
    try:
        validate_pc_melee_balance_request(request)
        if not callable(simulator):
            raise TypeError('simulator must be callable')
    except Exception as error:
        raise PcMeleeBalanceExecutionError(PcMeleeBalancePhase.GENERATION) from error
    # Keep generation separate: even a late invalid projection must not consume
    # RNG or create a process pool for any preceding candidate.
    prepared = []
    for index, counts in enumerate(pc_melee_count_vectors(request)):
        candidate_id = pc_melee_candidate_id(request, counts)
        try:
            prepared.append((candidate_id, counts, project_pc_melee_candidate(request, counts)))
        except Exception as error:
            raise PcMeleeBalanceExecutionError(PcMeleeBalancePhase.GENERATION, candidate_id, index) from error
    results = []
    for index, (candidate_id, counts, source) in enumerate(prepared):
        try:
            summary = simulator(source)
            if type(summary) is not PcMeleeSimulationSummary:
                raise TypeError('simulator must return a PC aggregate summary')
            replace(summary)
            if summary.source_request != source:
                raise ValueError('simulator returned an aggregate from another complete request')
            assessment = PcMeleeCandidateAssessment(source, summary, request.window)
            results.append(PcMeleeCandidateResult(candidate_id, counts, source, summary, assessment))
        except Exception as error:
            raise PcMeleeBalanceExecutionError(PcMeleeBalancePhase.EVALUATION, candidate_id, index) from error
    try:
        candidates = tuple(results)
        return PcMeleeBalanceResult(request, candidates, select_pc_melee_candidate_ids(candidates, request.top_k))
    except Exception as error:
        raise PcMeleeBalanceExecutionError(PcMeleeBalancePhase.EVALUATION) from error
