"""Source-bound PC ranged shots, optional Repeater bonus and Exacting reload."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.action_execution_models import AttackActionExecutionRequest, AttackActionExecutionResult
from towr.domain.attack_models import DamageImpactSpec
from towr.domain.condition_models import Condition
from towr.domain.fate_models import FateGloriousSpendResult
from towr.domain.pc_heavy_wound_models import PcBodyFactKind, usable_hands, usable_weapon_hand
from towr.domain.pc_melee_models import PC_TWO_HANDED_RANGED_WEAPONS, PC_RANGED_WEAPONS, PcRepeaterBonusPolicy, PcWeaponHand, PcTwoHandedGrip
from towr.domain.pc_short_opening_models import pc_enemy_range, pc_has_close_enemy, PcRangedCloseUnsupported
from towr.domain.pc_shield_models import PcShieldLocation
from towr.domain.pc_weapon_models import pc_weapon_allows_close_shooting
from towr.domain.ranged_weapon_attack_models import (
    ReloadableRangedAttackExecutionRequest, ReloadableRangedAttackExecutionResult,
    RangedWeaponAttackExecutionResult, _spent_weapon_state,
)
from towr.domain.ranged_weapon_attack_preparation_models import (
    RangedWeaponAttackPreparationRequest, RangedWeaponAttackPreparationResult,
    _applied_rule_ids, _execution_for, _profile_prepared_attack, _within_optimum, _aim_follow_up_for,
    OUTSIDE_OPTIMUM_RANGE_RULE_ID, SHORT_RANGE_SHOOTING_BONUS_RULE_ID,
    ARMOURED_TARGET_DAMAGE_BONUS_RULE_ID, BLUNDERBUSS_NEARBY_STAGGER_RULE_ID,
)
from towr.domain.ranged_weapon_profiles import (
    RangedWeaponId, RangedWeaponRange, RangedReloadTrigger, ranged_weapon_combat_profile,
)
from towr.domain.reload_models import (
    FreeReloadWeaponState, ReloadableWeaponState, ReloadActionExecutionRequest, ReloadActionExecutionResult,
    create_initial_ranged_weapon_reload_state, reload_approach_id,
)
from towr.domain.test_models import DiceModifier, Skill
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind, ImproviseKind

if TYPE_CHECKING:
    from towr.domain.pc_melee_models import PcMeleeParticipant
    from towr.domain.pc_melee_result_models import PcFateDecline, PcMeleeState, PcMeleeUnsupported


@dataclass(frozen=True, slots=True)
class PcRangedShotProof:
    preparation: RangedWeaponAttackPreparationResult
    execution: ReloadableRangedAttackExecutionResult | RangedWeaponAttackExecutionResult


@dataclass(frozen=True, slots=True)
class PcRangedReloadProof:
    request: ReloadActionExecutionRequest
    result: ReloadActionExecutionResult
    fate_decline: PcFateDecline | None
    glorious: FateGloriousSpendResult | None = None


def initial_pc_ranged(source: PcMeleeParticipant) -> FreeReloadWeaponState | ReloadableWeaponState | None:
    if source.pc.weapon not in PC_RANGED_WEAPONS:
        return None
    result = create_initial_ranged_weapon_reload_state(source.actor_id+':weapon', RangedWeaponId(source.pc.weapon.value))
    assert type(result) in (FreeReloadWeaponState, ReloadableWeaponState)
    return result


def _held_pc_ranged(state: PcMeleeState, actor: str, *, loaded: bool) -> FreeReloadWeaponState | ReloadableWeaponState:
    source = state.source.participant(actor)
    member = state.participant(actor)
    weapon = member.ranged
    if (source.pc.weapon not in PC_RANGED_WEAPONS or source.pc.ranged is None
            or member.using_backup_weapon
            or type(weapon) not in (FreeReloadWeaponState, ReloadableWeaponState)
            or weapon.weapon_id is not RangedWeaponId(source.pc.weapon.value)
            or weapon.weapon_instance_id != actor+':weapon'
            or (type(weapon) is ReloadableWeaponState and weapon.loaded is not loaded)
            or (type(weapon) is FreeReloadWeaponState and not loaded)
            or type(usable_weapon_hand(member)) not in (PcWeaponHand, PcTwoHandedGrip)
            or loaded and not pc_weapon_allows_close_shooting(source.pc.weapon) and pc_has_close_enemy(state,actor)
            or member.injury.dead or member.injury.conditions.has(Condition.DEFENCELESS)):
        raise ValueError('PC ranged action requires its actual held weapon and loaded state')
    return weapon


def pc_repeater_bonus_selected(state: PcMeleeState, actor: str) -> bool:
    """Fixed source choice before the initial roll; never reconsider after Fate."""
    member = state.participant(actor)
    source = state.source.participant(actor).pc
    return (not member.using_backup_weapon and source.ranged is not None
        and source.ranged.repeater_bonus_policy is PcRepeaterBonusPolicy.WHEN_AVAILABLE
        and not member.injury.conditions.has(Condition.DRAINED))


def pc_repeater_attack_modifiers(state: PcMeleeState, actor: str) -> tuple[DiceModifier, ...]:
    if not pc_repeater_bonus_selected(state, actor):
        return ()
    weapon = _held_pc_ranged(state, actor, loaded=True)
    return (ranged_weapon_combat_profile(weapon.weapon_id).reload.optional_bonus_modifier(),)


def pc_ranged_profile_modifiers(state: PcMeleeState, actor: str, target: str) -> tuple[DiceModifier, ...]:
    weapon = _held_pc_ranged(state,actor,loaded=True)
    profile = ranged_weapon_combat_profile(weapon.weapon_id)
    distance = pc_enemy_range(state,actor,target)
    modifiers = []
    if not _within_optimum(profile,distance):
        modifiers.append(DiceModifier(OUTSIDE_OPTIMUM_RANGE_RULE_ID,-1))
    if distance is RangedWeaponRange.SHORT and profile.short_range_shooting_bonus_dice:
        modifiers.append(DiceModifier(SHORT_RANGE_SHOOTING_BONUS_RULE_ID,profile.short_range_shooting_bonus_dice))
    return tuple(modifiers)


def pc_conditioned_ranged_attack(state: PcMeleeState, actor: str,
        preparation: RangedWeaponAttackPreparationResult) -> AttackActionExecutionRequest:
    """Apply the actual PC Conditions after pure K1 weapon traits, before Fate."""
    attack = preparation.execution.attack
    if not state.participant(actor).injury.conditions.has(Condition.DRAINED):
        return attack
    kernel = attack.kernel_request
    test = kernel.attack.attacker_test
    return replace(attack,kernel_request=replace(kernel,attack=replace(kernel.attack,
        attacker_test=replace(test,dice_modifiers=tuple(m for m in test.dice_modifiers if m.amount <= 0)))))


def prepare_pc_ranged_shot(
    state: PcMeleeState, request: AttackActionExecutionRequest,
) -> RangedWeaponAttackPreparationResult:
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    actor = request.actor_id
    weapon = _held_pc_ranged(state, actor, loaded=True)
    source = state.source.participant(actor).pc
    profile = ranged_weapon_combat_profile(weapon.weapon_id)
    bonus = pc_repeater_bonus_selected(state, actor)
    consumes = profile.reload.trigger is RangedReloadTrigger.AFTER_EVERY_SHOT or bonus
    # The public owner already includes these traits in its conditioned Test.
    # K1 preparation takes the unprepared profile and proves them independently.
    kernel = request.kernel_request
    test = kernel.attack.attacker_test
    from towr.domain.aim_models import AIM_FOLLOW_UP_RULE_ID
    from towr.domain.pc_aim_models import current_pc_aim
    aim = current_pc_aim(state,actor)
    modifiers = tuple(m for m in test.dice_modifiers
        if m.rule_id not in (OUTSIDE_OPTIMUM_RANGE_RULE_ID,SHORT_RANGE_SHOOTING_BONUS_RULE_ID,AIM_FOLLOW_UP_RULE_ID))
    impact = kernel.attack.impact_spec
    if type(impact) is not DamageImpactSpec:
        raise TypeError('PC ranged preparation requires its exact Damage impact')
    damage_modifiers = tuple(m for m in impact.damage_modifiers
        if m.rule_id != ARMOURED_TARGET_DAMAGE_BONUS_RULE_ID)
    secondary = tuple(effect for effect in kernel.attack.secondary_effects
        if effect.rule_id != BLUNDERBUSS_NEARBY_STAGGER_RULE_ID)
    unprepared = request if (modifiers == test.dice_modifiers and damage_modifiers == impact.damage_modifiers
        and secondary == kernel.attack.secondary_effects) else replace(request,
        kernel_request=replace(kernel,attack=replace(kernel.attack,
            attacker_test=replace(test,dice_modifiers=modifiers),
            impact_spec=replace(impact,damage_modifiers=damage_modifiers),secondary_effects=secondary)))
    preparation = RangedWeaponAttackPreparationRequest(
        id=pc_melee_action_id(state, actor)+':ranged:prepare',
        weapon_state=weapon,
        attack=unprepared,
        target_range=pc_enemy_range(state,actor,request.target_id),
        attacker_strength=source.strength,
        has_blackpowder_lore=source.ranged.has_blackpowder_lore is True,
        has_enemy_in_close_range=pc_has_close_enemy(state,actor),
        next_reload_cycle_id=pc_melee_action_id(state, actor)+':ranged:cycle' if consumes else None,
        uses_optional_reload_bonus=bonus,
        aim=aim,
    )
    attack = _profile_prepared_attack(preparation)
    follow_up = _aim_follow_up_for(preparation,attack)
    result = RangedWeaponAttackPreparationResult(
        request_id=preparation.id,
        rule_id=preparation.rule_id,
        source_request=preparation,
        profile=profile,
        profile_attack=attack,
        aim_follow_up=follow_up,
        execution=_execution_for(preparation, follow_up.attack if follow_up is not None else attack),
        applied_rule_ids=_applied_rule_ids(preparation, profile, follow_up),
    )
    if pc_conditioned_ranged_attack(state,actor,result) != request:
        raise ValueError('PC ranged Attack differs from its conditioned canonical weapon profile')
    return result


def complete_pc_ranged_shot(
    state: PcMeleeState,
    base_request: AttackActionExecutionRequest,
    effective_request: AttackActionExecutionRequest,
    execution: AttackActionExecutionResult,
) -> PcRangedShotProof:
    """Bind preparation before Fate and consumption to the effective Attack."""
    preparation = prepare_pc_ranged_shot(state, base_request)
    source = preparation.execution
    if type(source.weapon_state) is FreeReloadWeaponState:
        request = replace(source,attack=effective_request)
        result = RangedWeaponAttackExecutionResult(request.id,request.rule_id,request,execution,
            source.weapon_state,source.weapon_state,
            tuple(dict.fromkeys((request.rule_id,*execution.applied_rule_ids))))
        return PcRangedShotProof(preparation,result)
    request = ReloadableRangedAttackExecutionRequest(
        id=source.id,
        attack_skill=source.attack_skill,
        attack=effective_request,
        weapon_state=source.weapon_state,
        next_reload_cycle_id=source.next_reload_cycle_id,
        uses_optional_reload_bonus=source.uses_optional_reload_bonus,
        rule_id=source.rule_id,
    )
    result = ReloadableRangedAttackExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        attack=execution,
        previous_weapon_state=request.weapon_state,
        weapon_state=_spent_weapon_state(request),
        applied_rule_ids=tuple(dict.fromkeys((request.rule_id, *execution.applied_rule_ids))),
    )
    return PcRangedShotProof(preparation, result)


def ranged_reload_declaration(state: PcMeleeState, actor: str) -> CombatActionDeclaration:
    weapon = _held_pc_ranged(state, actor, loaded=False)
    assert type(weapon) is ReloadableWeaponState
    return CombatActionDeclaration(CombatActionKind.IMPROVISE,
        improvise_kind=ImproviseKind.SKILL,
        improvise_approach_id=reload_approach_id(actor+':weapon'))


def build_pc_ranged_reload(state: PcMeleeState) -> ReloadActionExecutionRequest:
    from towr.domain.pc_melee_result_models import _pc_test, pc_melee_action_id
    turn = state.round_state.active_turn
    if turn is None:
        raise ValueError('PC ranged Reload requires its own active turn')
    actor = turn.actor_id
    weapon = _held_pc_ranged(state, actor, loaded=False)
    assert type(weapon) is ReloadableWeaponState
    member = state.participant(actor)
    if len(usable_hands(member)) != 2 or (member.shield is not None
            and member.shield.location is PcShieldLocation.HELD):
        raise ValueError('PC ranged Reload requires two available hands')
    action = pc_melee_action_id(state, actor)
    return ReloadActionExecutionRequest(
        id=action+':reload:execute',
        round_state=state.round_state,
        actor_id=actor,
        actor_conditions=member.injury.conditions,
        slot_index=1,
        weapon_state=weapon,
        dexterity_test=_pc_test(state, actor, action+':reload:dexterity', Skill.DEXTERITY),
    )


def pc_ranged_unsupported(state: PcMeleeState) -> PcMeleeUnsupported | PcRangedCloseUnsupported | None:
    """Stop only at the actual next Shoot/Reload boundary after continuations."""
    if (state.pending or state.pending_wound is not None
            or not state.live_party or not state.live_enemies):
        return None
    turn = state.round_state.active_turn
    if (turn is None or turn.action_slots
            or turn.actor_id not in state.source.pc_activation_order):
        return None
    actor = turn.actor_id
    member = state.participant(actor)
    weapon = member.ranged
    if (state.source.participant(actor).pc.weapon not in PC_RANGED_WEAPONS
            or member.using_backup_weapon
            or weapon is None or member.injury.dead
            or member.injury.conditions.has(Condition.DEFENCELESS)):
        return None
    from towr.domain.pc_melee_result_models import PcMeleeUnsupported, _pc_recover_needed
    from towr.domain.pc_backup_weapon_models import pc_backup_candidate_hand
    if pc_backup_candidate_hand(state,actor) is not None:
        return None
    hands = usable_hands(member)
    primary = state.source.participant(actor).pc.weapon
    required_hands = 2 if primary in PC_TWO_HANDED_RANGED_WEAPONS else 1
    if (not pc_weapon_allows_close_shooting(primary) and len(hands) >= required_hands
            and pc_has_close_enemy(state,actor)):
        if _pc_recover_needed(member):
            return None  # Standard Recover is still the actual next selected action.
        close = tuple(enemy.state.actor_id for enemy in state.live_enemies
            if pc_enemy_range(state,actor,enemy.state.actor_id) is RangedWeaponRange.CLOSE)
        from towr.domain.pc_melee_result_models import pc_melee_action_id
        return PcRangedCloseUnsupported(actor,pc_melee_action_id(state,actor)+':ranged:close',close,
            state.round_state.round_number)
    if not hands or state.source.participant(actor).pc.weapon in PC_TWO_HANDED_RANGED_WEAPONS and len(hands) < 2:
        reason = 'ranged_grip_unavailable'
    elif (type(weapon) is ReloadableWeaponState and not weapon.loaded and len(hands) == 1
            and usable_weapon_hand(member) is not None and not _pc_recover_needed(member)):
        reason = 'ranged_reload_hands_unavailable'
    else:
        return None
    facts = tuple(f for f in member.body_facts if f.kind in (
        PcBodyFactKind.UNUSABLE_ARM, PcBodyFactKind.LOST_ARM, PcBodyFactKind.CLUTCH_STOMACH))
    fact = max(facts, key=lambda f: f.wound_sequence)
    wound = member.injury.wounds[fact.wound_sequence-1]
    source_id = (f'{weapon.rule_id}:{actor}:w{wound.sequence}:{fact.kind.value}:'
        f'{weapon.weapon_instance_id}:{(weapon.reload_cycle_id or "initial-loaded") if type(weapon) is ReloadableWeaponState else "free-reload"}:{reason}')
    return PcMeleeUnsupported(actor, source_id, reason, wound.sequence, wound.table_total)
