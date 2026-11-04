from dataclasses import replace

from towr.simulation.pc_melee_models import PcMeleeSimulationResult
from towr.simulation.pc_melee_summary_models import PcMeleeDefeatCount, PcMeleeSimulationSummary


def summarize_pc_melee_simulation(result: PcMeleeSimulationResult) -> PcMeleeSimulationSummary:
    if not isinstance(result, PcMeleeSimulationResult):
        raise TypeError('summarization requires a typed simulation result')
    replace(result)
    return PcMeleeSimulationSummary(result.source_request, result.outcome_counts,
        result.total_action_count, result.total_started_round_count, result.total_completed_round_count,
        sum(bool(record.defeated_pc_ids) for record in result.records),
        tuple(PcMeleeDefeatCount(member.actor_id,
            sum(member.actor_id in record.defeated_pc_ids for record in result.records))
            for member in result.source_request.scenario.party))
