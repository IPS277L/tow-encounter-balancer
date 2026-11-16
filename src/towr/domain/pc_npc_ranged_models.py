"""Source-bound NPC ranged weapons and real Exacting actions inside the PC owner."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.action_execution_models import AttackActionExecutionRequest, AttackActionExecutionResult
from towr.domain.condition_models import Condition
from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_profile
from towr.domain.ranged_weapon_attack_models import (
    ReloadableRangedAttackExecutionRequest, ReloadableRangedAttackExecutionResult, _spent_weapon_state,
)
from towr.domain.ranged_weapon_attack_preparation_models import (
    RangedWeaponAttackPreparationRequest, RangedWeaponAttackPreparationResult,
    _applied_rule_ids, _execution_for, _profile_prepared_attack,
)
from towr.domain.ranged_weapon_profiles import (RangedWeaponRange, ranged_weapon_combat_profile,
    ranged_weapon_reload_profile,RangedReloadTrigger,REPEATER_SHOOTING_BONUS_RULE_ID)
from towr.domain.reload_models import (
    ReloadableWeaponState, ReloadActionExecutionRequest, ReloadActionExecutionResult,
    create_initial_ranged_weapon_reload_state, reload_approach_id,
)
from towr.domain.test_models import Skill, TestRequest
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind, ImproviseKind

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcMeleeState


@dataclass(frozen=True, slots=True)
class PcNpcRangedState:
    actor_id: str
    attack_profile_id: str
    weapon_state: ReloadableWeaponState

    def __post_init__(self):
        if any(type(value) is not str or not value.strip() for value in (self.actor_id,self.attack_profile_id)):
            raise TypeError('NPC ranged weapon state requires its actual actor and attack profile')
        if type(self.weapon_state) is not ReloadableWeaponState:
            raise TypeError('NPC ranged weapon requires its exact reload state')
        replace(self.weapon_state)
        if self.weapon_state.weapon_instance_id != self.actor_id+':weapon':
            raise ValueError('NPC ranged weapon instance belongs to another actor')


@dataclass(frozen=True, slots=True)
class PcNpcRangedShotProof:
    preparation: RangedWeaponAttackPreparationResult
    execution: ReloadableRangedAttackExecutionResult


@dataclass(frozen=True, slots=True)
class PcNpcRangedReloadProof:
    request: ReloadActionExecutionRequest
    result: ReloadActionExecutionResult


def initial_pc_npc_ranged_weapons(source) -> tuple[PcNpcRangedState, ...]:
    result = []
    for policy in source.npc_ranged_policies:
        definition = source.enemy(policy.actor_id).definition
        profile = pc_npc_ranged_profile(definition)
        weapon = create_initial_ranged_weapon_reload_state(policy.actor_id+':weapon',profile.weapon_id)
        result.append(PcNpcRangedState(policy.actor_id,definition.attacks[0].id,weapon))
    return tuple(result)


def pc_npc_ranged_weapon(state: PcMeleeState, actor: str) -> ReloadableWeaponState | None:
    return next((entry.weapon_state for entry in state.npc_ranged_weapons if entry.actor_id == actor),None)


def updated_pc_npc_ranged_weapons(state: PcMeleeState, actor: str, weapon: ReloadableWeaponState):
    return tuple(replace(entry,weapon_state=weapon) if entry.actor_id == actor else entry
        for entry in state.npc_ranged_weapons)


def validate_pc_npc_ranged_weapons(state: PcMeleeState) -> None:
    if type(state.npc_ranged_weapons) is not tuple:
        raise TypeError('NPC ranged weapon bank requires a canonical tuple')
    initial = initial_pc_npc_ranged_weapons(state.source)
    if len(initial) != len(state.npc_ranged_weapons):
        raise ValueError('NPC ranged weapon bank changed source membership')
    from towr.domain.pc_melee_result_models import PcAttackProof, validate_pc_melee_source_types
    for actual, original in zip(state.npc_ranged_weapons,initial,strict=True):
        if type(actual) is not PcNpcRangedState:
            raise TypeError('NPC ranged weapon bank requires exact typed states')
        replace(actual)
        expected = original.weapon_state
        for proof in state.history:
            if type(proof) is PcAttackProof and proof.npc_ranged_shot is not None:
                shot = proof.npc_ranged_shot.execution
                if shot.source_request.attack.actor_id != original.actor_id:
                    continue
                previous, current = shot.previous_weapon_state,shot.weapon_state
            elif type(proof) is PcNpcRangedReloadProof and proof.request.actor_id == original.actor_id:
                previous,current = proof.result.previous_state,proof.result.state
            else:
                continue
            if previous != expected:
                raise ValueError('NPC ranged weapon progress detached from its actual history')
            validate_pc_melee_source_types(previous,expected)
            expected = current
        canonical = replace(original,weapon_state=expected)
        if actual != canonical:
            raise ValueError('NPC ranged weapon state changed its actual instance/cycle/progress')
        validate_pc_melee_source_types(actual,canonical)


def _held_npc_ranged(state: PcMeleeState, actor: str, *, loaded: bool) -> ReloadableWeaponState:
    if actor not in state.source.enemy_activation_order:
        raise ValueError('NPC ranged weapon requires an opposition actor')
    enemy = state.enemy(actor)
    profile = pc_npc_ranged_profile(enemy.definition)
    weapon = pc_npc_ranged_weapon(state,actor)
    if (weapon is None or weapon.loaded is not loaded or weapon.weapon_id is not profile.weapon_id
            or weapon.weapon_instance_id != actor+':weapon'
            or not enemy.state.wields_weapon or enemy.state.holds_shield
            or enemy.state.injury.defeated or actor in state.exited_npc_ids
            or any(enemy.state.injury.conditions.has(condition) for condition in (Condition.BROKEN,Condition.DEFENCELESS))):
        raise ValueError('NPC ranged weapon action requires its actual held weapon and usable actor')
    return weapon


def prepare_pc_npc_ranged_shot(state: PcMeleeState, request: AttackActionExecutionRequest):
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    actor = request.actor_id
    weapon = _held_npc_ranged(state,actor,loaded=True)
    profile = pc_npc_ranged_profile(state.enemy(actor).definition)
    policy = next(policy for policy in state.source.npc_ranged_policies if policy.actor_id == actor)
    reload_profile=ranged_weapon_reload_profile(weapon.weapon_id)
    test=request.kernel_request.attack.attacker_test
    selected=any(m.rule_id==REPEATER_SHOOTING_BONUS_RULE_ID for m in test.dice_modifiers)
    if state.enemy(actor).definition.generated_components is not None:
        from towr.domain.pc_generated_ranged_advice import npc_repeater_bonus,pc_close_shooting_protection
        from towr.domain.pc_melee_models import PcMeleePolicy
        from towr.domain.pc_melee_result_models import pc_protection_skill
        ordinary=replace(test,dice_modifiers=tuple(m for m in test.dice_modifiers
            if m.rule_id!=REPEATER_SHOOTING_BONUS_RULE_ID))
        target=request.target_id
        source=state.source.participant(target)
        defender=request.kernel_request.attack.defender_test
        defender_skill=(pc_close_shooting_protection(state,target,actor,defender.id)[0]
            if defender is not None and source.policy is PcMeleePolicy.AUTOMATIC_COMBAT else
            pc_protection_skill(state.participant(target),Skill.SHOOTING,source.close_shooting_protection_skill))
        if selected != npc_repeater_bonus(state,actor,ordinary,
                defender,target,defender_skill=defender_skill):
            raise ValueError('NPC Repeater mode differs from its committed automatic choice')
    cycle=(pc_melee_action_id(state,actor)+':ranged:cycle'
        if reload_profile.trigger is RangedReloadTrigger.AFTER_EVERY_SHOT or selected else None)
    preparation = RangedWeaponAttackPreparationRequest(
        id=pc_melee_action_id(state,actor)+':ranged:prepare',weapon_state=weapon,attack=request,
        target_range=RangedWeaponRange.CLOSE,attacker_strength=profile.strength,
        has_blackpowder_lore=policy.has_blackpowder_lore is True,has_enemy_in_close_range=True,
        next_reload_cycle_id=cycle,
        uses_optional_reload_bonus=selected,aim=None)
    combat_profile = ranged_weapon_combat_profile(weapon.weapon_id)
    attack = _profile_prepared_attack(preparation)
    return RangedWeaponAttackPreparationResult(preparation.id,preparation.rule_id,preparation,
        combat_profile,attack,None,_execution_for(preparation,attack),
        _applied_rule_ids(preparation,combat_profile,None))


def complete_pc_npc_ranged_shot(state,base_request,effective_request,execution: AttackActionExecutionResult):
    preparation = prepare_pc_npc_ranged_shot(state,base_request)
    source = preparation.execution
    request = ReloadableRangedAttackExecutionRequest(source.id,source.attack_skill,effective_request,
        source.weapon_state,source.next_reload_cycle_id,source.uses_optional_reload_bonus,source.rule_id)
    result = ReloadableRangedAttackExecutionResult(request.id,request.rule_id,request,execution,
        request.weapon_state,_spent_weapon_state(request),
        tuple(dict.fromkeys((request.rule_id,*execution.applied_rule_ids))))
    return PcNpcRangedShotProof(preparation,result)


def npc_ranged_reload_declaration(state: PcMeleeState, actor: str):
    weapon = _held_npc_ranged(state,actor,loaded=False)
    return CombatActionDeclaration(CombatActionKind.IMPROVISE,improvise_kind=ImproviseKind.SKILL,
        improvise_approach_id=reload_approach_id(weapon.weapon_instance_id))


def build_pc_npc_ranged_reload(state: PcMeleeState) -> ReloadActionExecutionRequest:
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    if state.round_state.active_turn is None or state.pending or state.pending_wound is not None:
        raise ValueError('NPC Reload requires its actual own turn after mandatory work')
    actor = state.round_state.active_turn.actor_id
    weapon = _held_npc_ranged(state,actor,loaded=False)
    enemy = state.enemy(actor)
    action = pc_melee_action_id(state,actor)
    return ReloadActionExecutionRequest(action+':reload:execute',state.round_state,actor,
        enemy.state.injury.conditions,1,weapon,
        npc_ranged_reload_test(state,actor,action+':reload:dexterity'))


def npc_ranged_reload_test(state: PcMeleeState,actor_id: str,test_id: str) -> TestRequest:
    """One prepared Dexterity Test for execution and finite forecast, no RNG."""
    from towr.domain.pc_npc_distraction_models import pc_npc_distraction_test_modifiers
    from towr.domain.pc_magic_models import magic_test_modifiers
    enemy=state.enemy(actor_id)
    profile=pc_npc_ranged_profile(enemy.definition)
    modifiers=pc_npc_distraction_test_modifiers(state,actor_id,None)
    if enemy.state.injury.conditions.has(Condition.DRAINED):
        modifiers=tuple(m for m in modifiers if m.amount<=0)
    magic_dice,qualities=magic_test_modifiers(state,actor_id,Skill.DEXTERITY)
    return TestRequest(test_id,profile.dexterity_profile,(*modifiers,*magic_dice),qualities)
