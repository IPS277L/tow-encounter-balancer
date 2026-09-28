from towr.simulation.npc_melee_models import NpcMeleeSimulationResult
from towr.simulation.npc_melee_summary_models import NpcMeleeSimulationSummary


def summarize_npc_melee_simulation(result: NpcMeleeSimulationResult) -> NpcMeleeSimulationSummary:
    """Project a completed result; do not execute trials or retain their records."""
    if not isinstance(result, NpcMeleeSimulationResult):
        raise TypeError("simulation summary requires a typed completed result")
    return NpcMeleeSimulationSummary(
        result.source_request, result.outcome_counts,
        result.total_attack_count, result.total_visited_round_count,
    )
