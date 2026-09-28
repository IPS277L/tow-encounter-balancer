from towr.balance.melee_assessment_models import ObjectiveRateWindow, MeleeCandidateAssessment
from towr.simulation.npc_melee_models import NpcMeleeSimulationRequest
from towr.simulation.npc_melee_summary_models import NpcMeleeSimulationSummary


def assess_melee_candidate(
    source_request: NpcMeleeSimulationRequest,
    summary: NpcMeleeSimulationSummary,
    window: ObjectiveRateWindow,
) -> MeleeCandidateAssessment:
    """Assess one completed aggregate without executing or retaining individual trials."""
    return MeleeCandidateAssessment(source_request, summary, window)
