"""Assess a completed magic aggregate without executing trials."""
from towr.balance.magic_assessment_models import MagicCandidateAssessment, ObjectiveRateWindow
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest
from towr.simulation.npc_magic_summary_models import NpcMagicSimulationSummary


def assess_magic_candidate(
    source_request: NpcMagicSimulationRequest,
    summary: NpcMagicSimulationSummary,
    window: ObjectiveRateWindow,
) -> MagicCandidateAssessment:
    """Keep the supplied input, summary and window; derive rates over every trial."""
    return MagicCandidateAssessment(source_request, summary, window)
