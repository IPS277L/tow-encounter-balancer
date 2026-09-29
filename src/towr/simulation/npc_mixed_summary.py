from towr.simulation.npc_mixed_models import NpcMixedSimulationResult
from towr.simulation.npc_mixed_summary_models import NpcMixedSimulationSummary


def summarize_npc_mixed_simulation(result: NpcMixedSimulationResult) -> NpcMixedSimulationSummary:
    """Project a completed result; do not execute trials or retain their records."""
    if not isinstance(result, NpcMixedSimulationResult):
        raise TypeError("simulation summary requires a typed completed result")
    return NpcMixedSimulationSummary(
        result.source_request, result.outcome_counts,
        result.total_attack_count, result.total_visited_round_count,
    )
