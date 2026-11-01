"""Pure ADR-0050 eligibility/source checks; no rules, RNG or dispatcher."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundEntryId
from towr.domain.npc_magic_scenario_models import NpcMagicScenario, NpcMagicStationaryWoundPolicy
from towr.domain.npc_roster_casting_models import NpcRosterCastingState, NpcRosterCastingResult
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_leg_spasm_models import (
    NpcRosterLegSpasmStandResult, leg_spasm_prone_effects_supported,
)
from towr.domain.npc_stationary_wound_models import NpcStationaryWoundContext, stationary_wound_scope_supported
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndResult
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.turn_models import ActionSlotGrant

if TYPE_CHECKING:
    from towr.domain.npc_magic_scene_models import NpcMagicSceneFrame
    from towr.domain.npc_magic_step_models import NpcMagicStep


def magic_stationary_wound_policy_enabled(scenario: NpcMagicScenario, state: NpcRosterCastingState) -> bool:
    if not isinstance(scenario, NpcMagicScenario) or not isinstance(state, NpcRosterCastingState):
        raise TypeError('stationary policy requires typed scenario and full state')
    policy = scenario.stationary_wound_continuation
    if policy is not None and not isinstance(policy, NpcMagicStationaryWoundPolicy):
        raise TypeError('stationary scenario permission requires its typed policy enum')
    return policy is not None


def _pending(state: NpcRosterCastingState) -> bool:
    return (state.pending_miscast_continuation is not None or state.pending_miscast is not None
            or state.pending_interruption is not None or state.pending_movement is not None
            or state.pending_minion_attack is not None
            or state.champion_attack is not None and state.champion_attack.pending is not None)


def magic_stationary_wound_required(scenario: NpcMagicScenario, state: NpcRosterCastingState, actor_id: str) -> bool:
    """A selected Wound family cannot fall back to the looser legacy guards."""
    return (magic_stationary_wound_policy_enabled(scenario, state) and actor_id == state.wizard.actor_id
            and any(w.entry_id is WoundEntryId.LEG_SPASM
                    for w in state.roster.participant(actor_id).state.injury.wounds))


def magic_leg_spasm_stand_family(scenario: NpcMagicScenario, state: NpcRosterCastingState) -> bool:
    if not magic_stationary_wound_policy_enabled(scenario, state) or _pending(state):
        return False
    turn = state.round_state.active_turn
    if (turn is None or turn.actor_id != state.wizard.actor_id or len(turn.action_slots) != 1
            or turn.action_slots[0].grant is not ActionSlotGrant.STANDARD or turn.action_slots[0].executed):
        return False
    injury = state.roster.participant(turn.actor_id).state.injury
    return (not injury.dead and injury.conditions.has(Condition.PRONE)
            and injury.conditions.conditions <= {Condition.PRONE, Condition.STAGGERED}
            and leg_spasm_prone_effects_supported(injury))


def magic_leg_spasm_stand_eligible(
    scenario: NpcMagicScenario, state: NpcRosterCastingState, frame: NpcMagicSceneFrame | None,
) -> bool:
    if not magic_leg_spasm_stand_family(scenario, state) or frame is None:
        return False
    from towr.domain.npc_magic_journal_policy import magic_scene_key
    if frame != scenario.frame_for(magic_scene_key(state)):
        return False
    actor_id = state.wizard.actor_id
    return (actor_id not in state.spatial_state.free_move_used_entity_ids
            and not any(p.target_range is RangedWeaponRange.CLOSE
                        and actor_id in (p.first_actor_id, p.second_actor_id) for p in frame.pair_ranges))


def magic_stationary_wound_context(
    scenario: NpcMagicScenario, state: NpcRosterCastingState, actor_id: str,
) -> NpcStationaryWoundContext | None:
    if not magic_stationary_wound_policy_enabled(scenario, state) or _pending(state):
        return None
    if not stationary_wound_scope_supported(state, actor_id):
        return None
    return NpcStationaryWoundContext(state, actor_id, scenario.facts.no_external_condition_sources)


def validate_magic_stationary_wound_step(scenario: NpcMagicScenario, step: NpcMagicStep) -> None:
    result, state = step.result, step.before
    context = None
    actor = None
    if isinstance(result, NpcRosterCastingResult):
        context, actor = result.source.stationary_wounds, result.source.casting.actor_id
    elif isinstance(result, NpcRosterChampionAttackResult):
        context, actor = result.source.attack.stationary_wounds, result.source.attack.execution.target_id
    elif isinstance(result, NpcWoundTurnEndResult):
        context, actor = result.source.stationary_wounds, result.source.actor_id
    if not magic_stationary_wound_policy_enabled(scenario, state):
        if isinstance(result, NpcRosterLegSpasmStandResult) or context is not None:
            raise ValueError('stationary Wound journal phases require their independent scenario policy')
        return
    from towr.domain.npc_magic_journal_policy import magic_scene_key
    frame = scenario.frame_for(magic_scene_key(state))
    stand = magic_leg_spasm_stand_eligible(scenario, state, frame)
    if isinstance(result, NpcRosterLegSpasmStandResult):
        replace(result)  # Revalidate the transported primitive without executing it.
        if (not stand or result.source.underlying_cause_allows_removal is not scenario.facts.no_external_condition_sources
                or result.source.actor_has_enemy_in_close_range is not False):
            raise ValueError('Leg Spasm stand differs from current source, scene or resource policy')
        return
    from towr.domain.npc_broken_recover_models import NpcBrokenRecoverResult
    from towr.domain.npc_broken_run_models import NpcBrokenRunResult
    from towr.domain.npc_roster_minion_attack_models import NpcRosterMinionAttackResult
    from towr.domain.npc_roster_prone_models import NpcRosterProneStandResult
    if stand and isinstance(result, (NpcRosterCastingResult, NpcRosterChampionAttackResult,
            NpcRosterMinionAttackResult, NpcBrokenRecoverResult, NpcBrokenRunResult, NpcRosterProneStandResult)):
        raise ValueError('eligible Leg Spasm self-stand is mandatory before the action')
    if actor is not None:
        expected = magic_stationary_wound_context(scenario, state, actor)
        if expected is None and magic_stationary_wound_required(scenario, state, actor):
            raise ValueError('unsupported stationary Wound source cannot fall back to legacy admission')
        if context != expected:
            raise ValueError('stationary context differs from the complete scenario source and actor role')
