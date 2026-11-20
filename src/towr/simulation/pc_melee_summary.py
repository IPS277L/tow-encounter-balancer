from dataclasses import replace

from towr.simulation.pc_ranged_statistics import PcRangedCount,pc_ranged_count_actors

from towr.simulation.pc_npc_ranged_statistics import PcNpcRangedCount
from towr.simulation.pc_extra_attack_statistics import PcExtraAttackCount,pc_extra_attack_actors
from towr.simulation.pc_rapid_reload_statistics import (
    PcRapidReloadCount, rapid_reload_count_actors, npc_aim_count_actors,
)
from towr.simulation.pc_immediate_attack_statistics import (
    PcImmediateAttackCount, immediate_attack_count_actors,
)
from towr.simulation.pc_companion_statistics import sum_companion_counts
from towr.simulation.pc_musician_statistics import sum_musician_counts
from towr.simulation.pc_oath_statistics import sum_oath_counts

from towr.simulation.pc_melee_models import PcMeleeSimulationResult, PcNearMissBurnCount, PcGloriousSpendCount, PcHelpActionCount, PcAllyRecoverActionCount, PcNpcExitCount, PcNpcHelpActionCount, PcNpcExtraAttackCount, PcNpcRecoverActionCount, PcNpcWarpedFormCount
from towr.simulation.pc_melee_models import PcAimCount, PcAimCounts, pc_has_aim_capability, PcPotionUseCount, PcMagicCount
from towr.domain.pc_melee_result_models import PcMeleeOutcome
from towr.simulation.pc_melee_summary_models import PcMeleeDefeatCount, PcMeleeSimulationSummary


def summarize_pc_melee_simulation(result: PcMeleeSimulationResult) -> PcMeleeSimulationSummary:
    if not isinstance(result, PcMeleeSimulationResult):
        raise TypeError('summarization requires a typed simulation result')
    replace(result)
    inventory = tuple((member.actor_id, item.id)
        for member in result.source_request.scenario.party for item in member.consumables)
    wizards = tuple(member.actor_id for member in result.source_request.scenario.party if member.wizard is not None)
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
            for index,member in enumerate(result.source_request.scenario.party)),
        sum(any(item.count for item in record.npc_exit_counts) for record in result.records),
        tuple(PcNpcExitCount(enemy.state.actor_id,
            sum(record.npc_exit_counts[index].count for record in result.records))
            for index,enemy in enumerate(result.source_request.scenario.enemies)),
        sum(record.outcome is PcMeleeOutcome.OBJECTIVE_ACHIEVED and any(item.count for item in record.npc_exit_counts)
            for record in result.records),
        sum(any(item.count for item in record.npc_help_action_counts) for record in result.records),
        tuple(PcNpcHelpActionCount(enemy.state.actor_id,
            sum(record.npc_help_action_counts[index].count for record in result.records))
            for index,enemy in enumerate(result.source_request.scenario.enemies)),
        sum(any(item.count for item in record.npc_extra_attack_counts) for record in result.records),
        tuple(PcNpcExtraAttackCount(enemy.state.actor_id,
            sum(record.npc_extra_attack_counts[index].count for record in result.records))
            for index,enemy in enumerate(result.source_request.scenario.enemies)),
        sum(any(item.count for item in record.npc_recover_action_counts) for record in result.records),
        tuple(PcNpcRecoverActionCount(enemy.state.actor_id,
            sum(record.npc_recover_action_counts[index].count for record in result.records))
            for index,enemy in enumerate(result.source_request.scenario.enemies)),
        sum(any(item.count for item in record.npc_warped_form_counts) for record in result.records),
        tuple(PcNpcWarpedFormCount(enemy.state.actor_id,
            sum(record.npc_warped_form_counts[index].count for record in result.records))
            for index,enemy in enumerate(result.source_request.scenario.enemies)),
        aim=(PcAimCounts(tuple(PcAimCount(member.actor_id,
            sum(record.aim.action_counts[index].count for record in result.records))
            for index,member in enumerate(result.source_request.scenario.party)),
            tuple(PcAimCount(member.actor_id,
                sum(record.aim.second_action_spend_counts[index].count for record in result.records))
                for index,member in enumerate(result.source_request.scenario.party)))
            if pc_has_aim_capability(result.source_request.scenario) else None),
        potion_use_counts=(tuple(PcPotionUseCount(actor_id,item_id,
            sum(record.potion_use_counts[index].count for record in result.records))
            for index,(actor_id,item_id) in enumerate(inventory)) if inventory else None),
        magic_counts=(tuple(PcMagicCount(actor_id, **{name:
            sum(getattr(record.magic_counts[index],name) for record in result.records)
            for name in ('casting_actions','spell_casts','miscasts','unsupported_miscasts')})
            for index,actor_id in enumerate(wizards)) if wizards else None),
        pc_extra_attack_counts=(tuple(PcExtraAttackCount(member.actor_id,
            sum(record.pc_extra_attack_counts[index].count for record in result.records))
            for index,member in enumerate(result.source_request.scenario.party))
            if pc_extra_attack_actors(result.source_request.scenario) else None),
        pc_extra_attack_trial_count=(sum(any(row.count for row in record.pc_extra_attack_counts)
            for record in result.records) if pc_extra_attack_actors(result.source_request.scenario) else None),
        rapid_reload_counts=(tuple(PcRapidReloadCount(actor,
            sum(record.rapid_reload_counts[index].count for record in result.records))
            for index,actor in enumerate(rapid_reload_count_actors(result.source_request.scenario)))
            if rapid_reload_count_actors(result.source_request.scenario) else None),
        immediate_attack_counts=(tuple(PcImmediateAttackCount(actor,
            sum(record.immediate_attack_counts[index].count for record in result.records))
            for index,actor in enumerate(immediate_attack_count_actors(result.source_request.scenario)))
            if immediate_attack_count_actors(result.source_request.scenario) else None),
        companion_counts=sum_companion_counts(tuple(record.companion_counts for record in result.records),
            result.source_request.scenario),
        music_counts=sum_musician_counts(tuple(record.music_counts for record in result.records),
            result.source_request.scenario),
        oath_counts=sum_oath_counts(tuple(record.oath_counts for record in result.records),
            result.source_request.scenario),
        npc_aim_counts=(tuple(PcAimCount(actor,
            sum(record.npc_aim_counts[index].count for record in result.records))
            for index,actor in enumerate(npc_aim_count_actors(result.source_request.scenario)))
            if npc_aim_count_actors(result.source_request.scenario) else None),
        pc_ranged_counts=(tuple(PcRangedCount(actor,**{name:
            sum(getattr(record.pc_ranged_counts[index],name) for record in result.records)
            for name in ('shots','bonus_shots','shooting_help_tests','bonus_help_tests','reload_actions','weapon_swaps')})
            for index,actor in enumerate(pc_ranged_count_actors(result.source_request.scenario)))
            if pc_ranged_count_actors(result.source_request.scenario) else None),
        npc_ranged_counts=(tuple(PcNpcRangedCount(policy.actor_id,**{name:
            sum(getattr(record.npc_ranged_counts[index],name) for record in result.records)
            for name in ('shots','bonus_shots','reload_actions')})
            for index,policy in enumerate(result.source_request.scenario.npc_ranged_policies))
            if result.source_request.scenario.npc_ranged_policies else None))
