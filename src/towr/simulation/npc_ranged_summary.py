from towr.simulation.npc_ranged_models import NpcRangedSimulationResult
from towr.simulation.npc_ranged_summary_models import NpcRangedSimulationSummary


def summarize_npc_ranged_simulation(result: NpcRangedSimulationResult) -> NpcRangedSimulationSummary:
    """Project a completed result; do not execute trials or retain their records."""
    if not isinstance(result, NpcRangedSimulationResult):
        raise TypeError("simulation summary requires a typed completed result")
    return NpcRangedSimulationSummary(
        result.source_request, result.outcome_counts,
        result.total_attack_count, result.total_visited_round_count,
    )
