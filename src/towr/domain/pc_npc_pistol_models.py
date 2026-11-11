"""Source-bound NPC firearms and real Exacting actions inside the PC owner."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.action_execution_models import AttackActionExecutionRequest, AttackActionExecutionResult
from towr.domain.condition_models import Condition
from towr.domain.pc_npc_pistol_source_models import pc_npc_pistol_profile
from towr.domain.ranged_weapon_attack_models import (
    ReloadableRangedAttackExecutionRequest, ReloadableRangedAttackExecutionResult, _spent_weapon_state,
)
from towr.domain.ranged_weapon_attack_preparation_models import (
    RangedWeaponAttackPreparationRequest, RangedWeaponAttackPreparationResult,
    _applied_rule_ids, _execution_for, _profile_prepared_attack,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponRange, ranged_weapon_combat_profile
from towr.domain.reload_models import (
    ReloadableWeaponState, ReloadActionExecutionRequest, ReloadActionExecutionResult,
    create_initial_ranged_weapon_reload_state, reload_approach_id,
)
from towr.domain.test_models import Skill, TestRequest
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind, ImproviseKind

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcMeleeState


@dataclass(frozen=True, slots=True)
class PcNpcPistolState:
    actor_id: str
    attack_profile_id: str
    weapon_state: ReloadableWeaponState

    def __post_init__(self):
        if any(type(value) is not str or not value.strip() for value in (self.actor_id,self.attack_profile_id)):
            raise TypeError('NPC Pistol state requires its actual actor and attack profile')
        if type(self.weapon_state) is not ReloadableWeaponState:
            raise TypeError('NPC Pistol requires its exact reload state')
        replace(self.weapon_state)
        if self.weapon_state.weapon_instance_id != self.actor_id+':weapon':
            raise ValueError('NPC Pistol instance belongs to another actor')


@dataclass(frozen=True, slots=True)
class PcNpcPistolShotProof:
    preparation: RangedWeaponAttackPreparationResult
    execution: ReloadableRangedAttackExecutionResult


@dataclass(frozen=True, slots=True)
class PcNpcPistolReloadProof:
    request: ReloadActionExecutionRequest
    result: ReloadActionExecutionResult


def initial_pc_npc_pistols(source) -> tuple[PcNpcPistolState, ...]:
    result = []
    for policy in source.npc_pistol_policies:
        definition = source.enemy(policy.actor_id).definition
        profile = pc_npc_pistol_profile(definition)
        weapon = create_initial_ranged_weapon_reload_state(policy.actor_id+':weapon',profile.weapon_id)
        result.append(PcNpcPistolState(policy.actor_id,definition.attacks[0].id,weapon))
    return tuple(result)


def pc_npc_pistol_weapon(state: PcMeleeState, actor: str) -> ReloadableWeaponState | None:
    return next((entry.weapon_state for entry in state.npc_pistols if entry.actor_id == actor),None)


def updated_pc_npc_pistols(state: PcMeleeState, actor: str, weapon: ReloadableWeaponState):
    return tuple(replace(entry,weapon_state=weapon) if entry.actor_id == actor else entry
        for entry in state.npc_pistols)


def validate_pc_npc_pistols(state: PcMeleeState) -> None:
    if type(state.npc_pistols) is not tuple:
        raise TypeError('NPC firearm bank requires a canonical tuple')
    initial = initial_pc_npc_pistols(state.source)
    if len(initial) != len(state.npc_pistols):
        raise ValueError('NPC firearm bank changed source membership')
    from towr.domain.pc_melee_result_models import PcAttackProof, validate_pc_melee_source_types
    for actual, original in zip(state.npc_pistols,initial,strict=True):
        if type(actual) is not PcNpcPistolState:
            raise TypeError('NPC firearm bank requires exact typed states')
        replace(actual)
        expected = original.weapon_state
        for proof in state.history:
            if type(proof) is PcAttackProof and proof.npc_pistol_shot is not None:
                shot = proof.npc_pistol_shot.execution
                if shot.source_request.attack.actor_id != original.actor_id:
                    continue
                previous, current = shot.previous_weapon_state,shot.weapon_state
            elif type(proof) is PcNpcPistolReloadProof and proof.request.actor_id == original.actor_id:
                previous,current = proof.result.previous_state,proof.result.state
            else:
                continue
            if previous != expected:
                raise ValueError('NPC firearm progress detached from its actual history')
            validate_pc_melee_source_types(previous,expected)
            expected = current
        canonical = replace(original,weapon_state=expected)
        if actual != canonical:
            raise ValueError('NPC firearm state changed its actual instance/cycle/progress')
        validate_pc_melee_source_types(actual,canonical)


def _held_npc_pistol(state: PcMeleeState, actor: str, *, loaded: bool) -> ReloadableWeaponState:
    if actor not in state.source.enemy_activation_order:
        raise ValueError('NPC firearm requires an opposition actor')
    enemy = state.enemy(actor)
    profile = pc_npc_pistol_profile(enemy.definition)
    weapon = pc_npc_pistol_weapon(state,actor)
    if (weapon is None or weapon.loaded is not loaded or weapon.weapon_id is not profile.weapon_id
            or weapon.weapon_instance_id != actor+':weapon'
            or not enemy.state.wields_weapon or enemy.state.holds_shield
            or enemy.state.injury.defeated or actor in state.exited_npc_ids
            or any(enemy.state.injury.conditions.has(condition) for condition in (Condition.BROKEN,Condition.DEFENCELESS))):
        raise ValueError('NPC firearm action requires its actual held weapon and usable actor')
    return weapon


def prepare_pc_npc_pistol_shot(state: PcMeleeState, request: AttackActionExecutionRequest):
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    actor = request.actor_id
    weapon = _held_npc_pistol(state,actor,loaded=True)
    profile = pc_npc_pistol_profile(state.enemy(actor).definition)
    policy = next(policy for policy in state.source.npc_pistol_policies if policy.actor_id == actor)
    preparation = RangedWeaponAttackPreparationRequest(
        id=pc_melee_action_id(state,actor)+':pistol:prepare',weapon_state=weapon,attack=request,
        target_range=RangedWeaponRange.CLOSE,attacker_strength=profile.strength,
        has_blackpowder_lore=policy.has_blackpowder_lore,has_enemy_in_close_range=True,
        next_reload_cycle_id=pc_melee_action_id(state,actor)+':pistol:cycle',
        uses_optional_reload_bonus=False,aim=None)
    combat_profile = ranged_weapon_combat_profile(weapon.weapon_id)
    attack = _profile_prepared_attack(preparation)
    return RangedWeaponAttackPreparationResult(preparation.id,preparation.rule_id,preparation,
        combat_profile,attack,None,_execution_for(preparation,attack),
        _applied_rule_ids(preparation,combat_profile,None))


def complete_pc_npc_pistol_shot(state,base_request,effective_request,execution: AttackActionExecutionResult):
    preparation = prepare_pc_npc_pistol_shot(state,base_request)
    source = preparation.execution
    request = ReloadableRangedAttackExecutionRequest(source.id,source.attack_skill,effective_request,
        source.weapon_state,source.next_reload_cycle_id,source.uses_optional_reload_bonus,source.rule_id)
    result = ReloadableRangedAttackExecutionResult(request.id,request.rule_id,request,execution,
        request.weapon_state,_spent_weapon_state(request),
        tuple(dict.fromkeys((request.rule_id,*execution.applied_rule_ids))))
    return PcNpcPistolShotProof(preparation,result)


def npc_pistol_reload_declaration(state: PcMeleeState, actor: str):
    weapon = _held_npc_pistol(state,actor,loaded=False)
    return CombatActionDeclaration(CombatActionKind.IMPROVISE,improvise_kind=ImproviseKind.SKILL,
        improvise_approach_id=reload_approach_id(weapon.weapon_instance_id))


def build_pc_npc_pistol_reload(state: PcMeleeState) -> ReloadActionExecutionRequest:
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    from towr.domain.pc_npc_distraction_models import pc_npc_distraction_test_modifiers
    if state.round_state.active_turn is None or state.pending or state.pending_wound is not None:
        raise ValueError('NPC Reload requires its actual own turn after mandatory work')
    actor = state.round_state.active_turn.actor_id
    weapon = _held_npc_pistol(state,actor,loaded=False)
    enemy = state.enemy(actor)
    profile = pc_npc_pistol_profile(enemy.definition)
    action = pc_melee_action_id(state,actor)
    modifiers = pc_npc_distraction_test_modifiers(state,actor,None)
    if enemy.state.injury.conditions.has(Condition.DRAINED):
        modifiers = tuple(modifier for modifier in modifiers if modifier.amount <= 0)
    return ReloadActionExecutionRequest(action+':reload:execute',state.round_state,actor,
        enemy.state.injury.conditions,1,weapon,
        TestRequest(action+':reload:dexterity',profile.dexterity_profile,modifiers))
