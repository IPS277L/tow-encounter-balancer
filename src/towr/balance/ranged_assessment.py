from towr.balance.ranged_assessment_models import ObjectiveRateWindow, RangedCandidateAssessment
from towr.simulation.npc_ranged_models import NpcRangedSimulationRequest
from towr.simulation.npc_ranged_summary_models import NpcRangedSimulationSummary


def assess_ranged_candidate(
    source_request: NpcRangedSimulationRequest,
    summary: NpcRangedSimulationSummary,
    window: ObjectiveRateWindow,
) -> RangedCandidateAssessment:
    """Assess one completed aggregate without executing or retaining individual trials."""
    return RangedCandidateAssessment(source_request, summary, window)
