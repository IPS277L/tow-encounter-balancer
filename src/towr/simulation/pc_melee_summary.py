from dataclasses import replace

from towr.simulation.pc_melee_models import PcMeleeSimulationResult, PcNearMissBurnCount, PcGloriousSpendCount, PcHelpActionCount, PcAllyRecoverActionCount
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
            for member in result.source_request.scenario.party),
        sum(any(item.count for item in record.near_miss_burn_counts) for record in result.records),
        tuple(PcNearMissBurnCount(member.actor_id,
            sum(record.near_miss_burn_counts[index].count for record in result.records))
            for index, member in enumerate(result.source_request.scenario.party)),
        sum(any(item.count for item in record.glorious_spend_counts) for record in result.records),
        tuple(PcGloriousSpendCount(member.actor_id,
            sum(record.glorious_spend_counts[index].count for record in result.records))
            for index,member in enumerate(result.source_request.scenario.party)),
        sum(any(item.count for item in record.help_action_counts) for record in result.records),
        tuple(PcHelpActionCount(member.actor_id,
            sum(record.help_action_counts[index].count for record in result.records))
            for index,member in enumerate(result.source_request.scenario.party)),
        sum(any(item.count for item in record.ally_recover_action_counts) for record in result.records),
        tuple(PcAllyRecoverActionCount(member.actor_id,
            sum(record.ally_recover_action_counts[index].count for record in result.records))
            for index,member in enumerate(result.source_request.scenario.party)))
