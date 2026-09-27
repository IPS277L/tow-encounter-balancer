from __future__ import annotations

from towr.domain.npc_objective_models import NpcDefeatObjective, NpcDefeatObjectiveAssessment
from towr.domain.npc_rounds_chain_summary_models import NpcRoundsChainSummary


def assess_npc_defeat_objective(
    report: NpcRoundsChainSummary, objective: NpcDefeatObjective,
) -> NpcDefeatObjectiveAssessment:
    """Assess the named targets without executing actions or consuming pending work."""
    return NpcDefeatObjectiveAssessment(report, objective)
?