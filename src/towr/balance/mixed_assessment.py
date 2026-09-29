from towr.balance.mixed_assessment_models import ObjectiveRateWindow, MixedCandidateAssessment
from towr.simulation.npc_mixed_models import NpcMixedSimulationRequest
from towr.simulation.npc_mixed_summary_models import NpcMixedSimulationSummary


def assess_mixed_candidate(
    source_request: NpcMixedSimulationRequest,
    summary: NpcMixedSimulationSummary,
    window: ObjectiveRateWindow,
) -> MixedCandidateAssessment:
    """Assess one completed aggregate without executing or retaining individual trials."""
    return MixedCandidateAssessment(source_request, summary, window)
