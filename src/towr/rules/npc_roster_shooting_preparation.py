"""State-derived M8 Shooting preparation; no RNG, policy choice or scene mutation."""
from __future__ import annotations

from typing import TYPE_CHECKING
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.condition_models import Condition
from towr.domain.npc_attack_preparation_models import NpcAttackPreparationRequest
from towr.domain.npc_champion_attack_models import NpcChampionAttackRequest
from towr.domain.npc_prone_shooting import PRONE_TARGET_RULE_ID
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionRequest
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackRequest
from towr.domain.npc_roster_minion_attack_models import NpcRosterMinionAttackRequest
from towr.domain.npc_roster_turn_models import _validate_phase_source
from towr.domain.protection_models import ProtectionPreparationRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.resolution_models import KernelAttackRequest
from towr.domain.test_models import DiceModifier, Skill
from towr.rules.npc_attack_preparation import prepare_npc_attack, prepare_npc_attack_protection

if TYPE_CHECKING:
    from towr.domain.npc_stationary_wound_models import NpcStationaryWoundContext
    from towr.domain.npc_crushed_rib_models import NpcCrushedRibContext


def prepare_npc_roster_shooting(
    *, request_id: str, state: NpcRosterCastingState, actor_id: str, target_id: str,
    selected_attack_id: str, target_range: RangedWeaponRange,
    has_enemy_in_close_range: bool, range_approved_by_gm: bool,
    defender_is_aware: bool, selected_protection_skill: Skill | None,
    can_target_leave_zone: bool,
    stationary_wounds: NpcStationaryWoundContext | None = None,
    crushed_rib_context: NpcCrushedRibContext | None = None,
) -> NpcRosterMinionAttackRequest | NpcRosterChampionAttackRequest:
    """Preserve authored departure and derive effective Give Ground eligibility.

    Only a normal Shooting action is prepared; callers still own explicit range,
    awareness and Protection decisions. PG1.4 Prone pp120,123 (ADR-0046),
    Giving Ground p119 / Wounds Table p190 (ADR-0049).
    """
    _validate_phase_source(state)
    if crushed_rib_context is not None:
        from towr.domain.npc_crushed_rib_models import NpcCrushedRibContext
        if not isinstance(crushed_rib_context, NpcCrushedRibContext):
            raise TypeError('Shooting requires a typed Crushed Rib context')
        if stationary_wounds is not None:
            raise ValueError('Crushed Rib and stationary contexts are mutually exclusive')
        crushed_rib_context.validate_source(state, target_id)
    if stationary_wounds is not None:
        from towr.domain.npc_stationary_wound_models import NpcStationaryWoundContext
        if not isinstance(stationary_wounds, NpcStationaryWoundContext):
            raise TypeError('stationary Shooting requires a typed full-source context')
        stationary_wounds.validate_source(state, target_id)
    if not isinstance(can_target_leave_zone, bool):
        raise TypeError('can_target_leave_zone must be an explicit boolean')
    actor, target = state.roster.participant(actor_id), state.roster.participant(target_id)
    target_prone = target.state.injury.conditions.has(Condition.PRONE)
    can_give_ground = (can_target_leave_zone and not target_prone
                       and (stationary_wounds is None or stationary_wounds.can_give_ground))
    prepared = prepare_npc_attack(NpcAttackPreparationRequest(
        request_id + ':prepare', request_id + ':attack', request_id + ':attacker-test',
        actor.attack_snapshot(request_id + ':snapshot'), selected_attack_id, target_id, target_range,
        target.state.current_resilience, has_enemy_in_close_range,
        actor.state.injury.conditions.has(Condition.STAGGERED), range_approved_by_gm,
        (DiceModifier(PRONE_TARGET_RULE_ID, -1),) if target_prone else ()))
    if prepared.selected_profile.skill is not Skill.SHOOTING:
        raise ValueError('bound Shooting preparation requires a Shooting profile')
    protected = prepare_npc_attack_protection(prepared, ProtectionPreparationRequest(
        request_id + ':protect', target_id, prepared.attack, Skill.SHOOTING, defender_is_aware,
        target.state.injury.conditions.has(Condition.DEFENCELESS), target.state.wields_weapon,
        target.state.holds_shield, selected_protection_skill,
        target.protection_options(request_id + ':protection-test')))
    execution = AttackActionExecutionRequest(request_id, state.round_state, actor_id, target_id, 1,
        KernelAttackRequest(request_id + ':kernel', target_id, protected.attack, target.definition.injury_policy,
            target.state.injury, can_give_ground,
            target_id in state.spatial_state.gave_ground_entity_ids))
    if target_id == state.wizard.actor_id:
        preparation, consumption = None, None
        if crushed_rib_context is not None:
            if crushed_rib_context.consumption is None:
                from towr.domain.crushed_rib_test_models import CrushedRibTestPreparationRequest
                from towr.rules.crushed_rib_test_resolution import prepare_crushed_rib_test
                if protected.attack.defender_test is None:
                    raise ValueError('pending Crushed Rib requires an actual opposed Protection Test')
                preparation = prepare_crushed_rib_test(CrushedRibTestPreparationRequest(
                    request_id + ':crushed-rib', target_id, target.state.injury, protected.attack.defender_test))
            else:
                consumption = crushed_rib_context.consumption.consumption
        return NpcRosterChampionAttackRequest(state, NpcChampionAttackRequest(
            state.champion_attack, protected, execution, stationary_wounds=stationary_wounds,
            crushed_rib_preparation=preparation, crushed_rib_consumption=consumption),
            crushed_rib_context=crushed_rib_context)
    return NpcRosterMinionAttackRequest(state, NpcRosterAttackExecutionRequest(
        state.minion_attack, protected, execution))
