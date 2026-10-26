from towr.simulation.npc_magic_models import NpcMagicSimulationResult
from towr.simulation.npc_magic_summary_models import NpcMagicSimulationSummary


def summarize_npc_magic_simulation(result: NpcMagicSimulationResult) -> NpcMagicSimulationSummary:
    """Project a complete typed result without executing trials or retaining records."""
    if not isinstance(result, NpcMagicSimulationResult):
        raise TypeError("magic summary requires a typed completed simulation result")
    return NpcMagicSimulationSummary(
        result.source_request, result.outcome_counts, result.total_action_count,
        result.total_started_round_count, result.total_completed_round_count,
    )
