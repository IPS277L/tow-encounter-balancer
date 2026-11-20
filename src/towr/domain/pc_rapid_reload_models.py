"""Immediate Rapid Reload choices from actual shared-inventory Reload receipts.

The grant records a decision before either follow-up Test. The automatic owner
declines a partial-reload Aim: another Reload would consume it without benefit.
Explicit native callers may still choose that legal option.
"""
from __future__ import annotations
from towr.domain.injury_models import injury_wound_count

from dataclasses import replace
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition
from towr.domain.talent_action_grant_models import RAPID_RELOAD_RULE_ID, RapidReloadGrant
from towr.domain.talent_actor_models import actor_acquired_talents, actor_has_talent
from towr.domain.talent_catalog import TalentId
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatTurnStartResult,
)
from towr.domain.weapon_inventory_models import WeaponItemLocation

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcMeleeState
    from towr.domain.pc_tactical_models import PcTacticalChoice
    from towr.domain.reload_models import ReloadActionExecutionResult


def actor_moved_this_turn(state: PcMeleeState, actor: str) -> bool:
    """Read movement receipts since this actual turn began, including Close moves.

    Round-wide free-move usage cannot describe within-Zone movement and would
    incorrectly include movement which occurred before this actor's turn.
    """
    from towr.domain.pc_battlefield_movement_models import PcBattlefieldMoveProof
    from towr.domain.pc_battlefield_manoeuvre_models import (
        PcBattlefieldChargeProof, PcBattlefieldRunProof, PcBattlefieldCarefulProof,
    )
    from towr.domain.pc_short_opening_models import PcNpcApproachProof
    from towr.domain.pc_shield_models import PcShieldApproachProof
    from towr.domain.pc_weighted_net_models import PcNetApproachProof
    from towr.domain.pc_briarroot_weapon_models import PcBriarrootWeaponApproachProof
    from towr.domain.pc_give_ground_models import PcGiveGroundProof
    from towr.domain.pc_broken_battlefield_models import PcBrokenMoveProof
    from towr.domain.pc_falling_models import PcFallingProof
    from towr.domain.pc_brawn_displacement_models import PcBrawnShoveProof
    turn = state.round_state.active_turn
    if turn is None or turn.actor_id != actor:
        raise ValueError('current-turn movement requires the actual active actor')
    movement_types = (PcBattlefieldMoveProof, PcNpcApproachProof, PcShieldApproachProof,
        PcNetApproachProof, PcBriarrootWeaponApproachProof, PcGiveGroundProof, PcBrokenMoveProof)
    for proof in reversed(state.history):
        if type(proof) is CombatTurnStartResult:
            if proof.turn.actor_id != actor or proof.state.round_number != state.round_state.round_number:
                raise ValueError('Rapid Reload lost its actual current-turn start')
            return False
        if type(proof) in movement_types and proof.actor_id == actor:
            return True
        if type(proof) in (PcBattlefieldChargeProof, PcBattlefieldRunProof, PcBattlefieldCarefulProof):
            if proof.request.actor_id == actor:
                return True
        if type(proof) is PcFallingProof and proof.actor_id == actor:
            return True
        if type(proof) is PcBrawnShoveProof and proof.request.target_id == actor:
            return True
    raise ValueError('Rapid Reload requires its actual turn-start journal source')


def rapid_reload_current_turn_eligible(state: PcMeleeState, actor: str) -> bool:
    if not actor_has_talent(state, actor, TalentId.RAPID_RELOAD):
        return False
    from towr.domain.pc_magic_weapon_models import actor_injury
    injury = actor_injury(state, actor)
    return (not any(injury.conditions.has(value) for value in (
        Condition.STAGGERED, Condition.DEFENCELESS, Condition.BROKEN))
        and not actor_moved_this_turn(state, actor))


def rapid_reload_forecast_eligible(state: PcMeleeState, actor: str, *, future_turn: bool) -> bool:
    """Future stationary turns use present Conditions, never another actor's clock."""
    if type(future_turn) is not bool:
        raise TypeError('Rapid Reload forecast must distinguish current and future turns')
    if not future_turn:
        return rapid_reload_current_turn_eligible(state, actor)
    from towr.domain.pc_magic_weapon_models import actor_injury
    return (actor_has_talent(state, actor, TalentId.RAPID_RELOAD)
        and not any(actor_injury(state, actor).conditions.has(value) for value in (
            Condition.STAGGERED, Condition.DEFENCELESS, Condition.BROKEN)))


def pending_rapid_reload(state: PcMeleeState) -> RapidReloadGrant | None:
    turn = state.round_state.active_turn
    if turn is None or len(turn.action_slots) != 2 or turn.action_slots[-1].executed:
        return None
    grant = turn.action_slots[-1].rapid_reload
    if grant is None:
        return None
    replace(grant)
    if (grant.owned_talent not in actor_acquired_talents(state, turn.actor_id)
            or not rapid_reload_current_turn_eligible(state, turn.actor_id)):
        raise ValueError('Rapid Reload changed its actual Talent or movement/Condition source')
    from towr.domain.pc_magic_weapon_models import actor_inventory
    inventory = actor_inventory(state, turn.actor_id)
    item = None if inventory is None else inventory.active
    if (item is None or item.id != grant.weapon_instance_id
            or item.location is not WeaponItemLocation.HELD
            or item.reload != grant.source_reload.state):
        raise ValueError('Rapid Reload lost the same actual held Reloaded weapon')
    return grant


def rapid_reload_committed_tactic(state: PcMeleeState, actor: str) -> PcTacticalChoice | None:
    grant = pending_rapid_reload(state)
    if grant is None or grant.actor_id != actor:
        return None
    from towr.domain.pc_tactical_models import PcTacticalChoice
    return PcTacticalChoice(actor, grant.action_kind, grant.target_id, None, 0.0,
        'committed_rapid_reload', weapon_item_id=grant.weapon_instance_id,
        ranged_bonus=grant.ranged_bonus)


def _reload_source(state: PcMeleeState) -> ReloadActionExecutionResult | None:
    from towr.domain.pc_ranged_models import PcRangedReloadProof
    from towr.domain.pc_npc_ranged_models import PcNpcRangedReloadProof
    turn = state.round_state.active_turn
    if (turn is None or len(turn.action_slots) != 1 or not turn.action_slots[0].executed
            or turn.action_slots[0].declaration.kind is not CombatActionKind.IMPROVISE):
        return None
    receipt = turn.action_slots[0].execution
    return next((proof.result for proof in reversed(state.history)
        if type(proof) in (PcRangedReloadProof, PcNpcRangedReloadProof)
        and proof.result.slot.execution == receipt), None)


def _aim_available(state: PcMeleeState, actor: str) -> bool:
    from towr.domain.pc_aim_source_models import actor_can_aim
    return actor_can_aim(state, actor)


def _requires_aim(state, actor, target, weapon):
    from towr.domain.ranged_weapon_profiles import ranged_weapon_combat_profile, RangedWeaponRange
    from towr.domain.pc_short_opening_models import pc_enemy_range
    from towr.domain.pc_aim_models import current_pc_aim
    from towr.domain.pc_npc_aim_models import current_npc_aim
    profile = ranged_weapon_combat_profile(weapon.weapon_id)
    aim = (current_pc_aim(state, actor) if actor in state.source.pc_activation_order
        else current_npc_aim(state, actor))
    return ((profile.requires_aim_before_attack
        or pc_enemy_range(state, actor, target) is RangedWeaponRange.EXTREME)
        and (aim is None or aim.bonus.target_id != target))


def rapid_reload_options(state: PcMeleeState) -> tuple[CombatActionSlotRequest, ...]:
    """All source-bound native Aim/Attack grants, without rolling or mutation."""
    if (state.pending or state.pending_wound is not None or state.magic_pending is not None
            or not state.live_party or not state.live_enemies):
        return ()
    from towr.domain.pc_aim_models import expected_pc_aim_consumption
    from towr.domain.pc_npc_aim_models import expected_npc_aim_consumption
    if expected_pc_aim_consumption(state) is not None or expected_npc_aim_consumption(state) is not None:
        return ()
    reload = _reload_source(state)
    if reload is None or not reload.exacting.test_result.succeeded:
        return ()
    actor = state.round_state.active_turn.actor_id
    if not rapid_reload_current_turn_eligible(state, actor):
        return ()
    from towr.domain.pc_magic_weapon_models import actor_inventory
    from towr.domain.pc_battlefield_movement_models import pc_battlefield_attack_available
    from towr.domain.pc_short_opening_models import pc_has_close_enemy
    from towr.domain.ranged_weapon_profiles import (
        ranged_weapon_combat_profile, RangedWeaponHands, RangedReloadTrigger,
    )
    inventory = actor_inventory(state, actor)
    item = None if inventory is None else inventory.active
    if (item is None or item.id != reload.state.weapon_instance_id
            or item.location is not WeaponItemLocation.HELD or item.reload != reload.state):
        return ()
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_heavy_wound_models import usable_weapon_hand
        if usable_weapon_hand(state.participant(actor)) is None:
            return ()
        targets = state.source.participant(actor).target_priority
        live = {enemy.state.actor_id for enemy in state.live_enemies}
    else:
        from towr.domain.pc_battlefield_movement_models import _enemies
        targets = _enemies(state,actor)
        live = set(targets)
    profile = ranged_weapon_combat_profile(reload.state.weapon_id)
    if profile.hands is RangedWeaponHands.TWO_HANDED and pc_has_close_enemy(state, actor):
        return ()
    owned = next(t for t in actor_acquired_talents(state, actor) if t.id is TalentId.RAPID_RELOAD)
    from towr.domain.pc_magic_weapon_models import actor_injury
    bonus_available = (profile.reload.trigger is RangedReloadTrigger.AFTER_OPTIONAL_BONUS
        and not actor_injury(state, actor).conditions.has(Condition.DRAINED))
    result = []
    for target in targets:
        if target not in live or not pc_battlefield_attack_available(state, actor, target):
            continue
        kinds = []
        if reload.state.loaded and not _requires_aim(state, actor, target, reload.state):
            kinds.append(CombatActionKind.ATTACK)
        if _aim_available(state, actor):
            kinds.append(CombatActionKind.AIM)
        for kind in kinds:
            for bonus in ((False, True) if kind is CombatActionKind.ATTACK and bonus_available else (False,)):
                identifier = (f'{state.source.id}:r{state.round_state.round_number}:{actor}'
                    f':rapid-{kind.value}:reserve')
                grant = RapidReloadGrant(actor, state.round_state.round_number, identifier,
                    reload, owned, target, kind, bonus)
                result.append(CombatActionSlotRequest(identifier, state.round_state, actor,
                    CombatActionDeclaration(kind), ActionSlotGrant.ABILITY, RAPID_RELOAD_RULE_ID,
                    rapid_reload=grant))
    return tuple(result)


def build_pc_rapid_reload_second_action(state: PcMeleeState) -> CombatActionSlotRequest | None:
    """Choose an immediate shot, otherwise useful mandatory Aim, on the same item."""
    options = rapid_reload_options(state)
    attacks = tuple(option for option in options if option.declaration.kind is CombatActionKind.ATTACK)
    if attacks:
        actor = attacks[0].actor_id
        if actor in state.source.pc_activation_order:
            from towr.domain.pc_ranged_advice import ranged_action_choices
            # The regular finite advisor can compare modes, but cannot change
            # the physical item, declaration or target of this granted action.
            choices = ranged_action_choices(state, actor, _rapid_follow_up=True)
            legal = {(o.rapid_reload.target_id, o.rapid_reload.ranged_bonus): o for o in attacks}
            candidates = tuple(c for c in choices if c.action is CombatActionKind.ATTACK
                and c.weapon_item_id == attacks[0].rapid_reload.weapon_instance_id
                and (c.target_id, c.ranged_bonus) in legal)
            if candidates:
                chosen = max(candidates, key=lambda value: value.utility)
                return legal[chosen.target_id, chosen.ranged_bonus]
        elif any(option.rapid_reload.ranged_bonus for option in attacks):
            target = attacks[0].rapid_reload.target_id
            bonus = _npc_automatic_mode(state, actor, target)
            return next(option for option in attacks
                if option.rapid_reload.target_id == target and option.rapid_reload.ranged_bonus is bonus)
        return attacks[0]
    return next((option for option in options if option.rapid_reload.source_reload.completed
        and option.declaration.kind is CombatActionKind.AIM), None)


def _npc_automatic_mode(state: PcMeleeState, actor: str, target: str) -> bool:
    """Compare repeater modes before committing the second action, without RNG."""
    from towr.domain.pc_melee_result_models import pc_selected_npc_attack_profile, _pc_test
    from towr.domain.pc_weapon_intent_models import build_pc_explicit_attack_weapon_intent
    from towr.domain.pc_generated_equipment import generated_attack_modifiers
    from towr.domain.pc_npc_ability_models import pc_npc_attack_modifiers
    from towr.domain.pc_npc_distraction_models import pc_npc_distraction_test_modifiers
    from towr.domain.pc_npc_ranged_models import pc_npc_ranged_profile_modifiers
    from towr.domain.pc_npc_aim_models import npc_aim_attack_modifiers
    from towr.domain.pc_npc_help_models import build_pc_npc_attack_help
    from towr.domain.pc_magic_models import magic_test_modifiers
    from towr.domain.pc_generated_ranged_advice import npc_repeater_bonus
    from towr.domain.pc_mount_models import pc_is_mounted
    from towr.domain.test_models import TestRequest, Skill, DiceModifier
    from towr.domain.pc_medical_models import medical_effective_body
    enemy, member = state.enemy(actor), medical_effective_body(state,target)
    action = f'{state.source.id}:r{state.round_state.round_number}:{actor}:attack2'
    intent = build_pc_explicit_attack_weapon_intent(state, actor, target, action)
    profile = pc_selected_npc_attack_profile(state, actor)
    conditions, target_conditions = enemy.state.injury.conditions, member.injury.conditions
    modifiers = (*pc_npc_attack_modifiers(enemy.definition, conditions,
        target_conditions=target_conditions, attacker_wounds=injury_wound_count(enemy.state.injury)),
        *generated_attack_modifiers(enemy.definition, conditions, target_conditions,
            target_mounted=pc_is_mounted(state,target), weapon_use=intent.attack_use,
            actor_mounted=pc_is_mounted(state,actor)),
        *pc_npc_ranged_profile_modifiers(state,actor,target),
        *npc_aim_attack_modifiers(state,actor,target),
        *pc_npc_distraction_test_modifiers(state,actor,target))
    if target_conditions.has(Condition.PRONE):
        modifiers = (*modifiers, DiceModifier('RULE-HEALTH-008:prone-shooting', -1))
    if conditions.has(Condition.DRAINED):
        modifiers = tuple(value for value in modifiers if value.amount <= 0)
    dice, qualities = magic_test_modifiers(state, actor, Skill.SHOOTING)
    test = TestRequest(action+':attack', profile.test_profile, (*modifiers, *dice), qualities)
    test, _ = build_pc_npc_attack_help(state, actor, test)
    skill = intent.protection_skill
    if skill is None:defender=None
    elif target in state.source.pc_activation_order:
        defender=_pc_test(state,target,action+':protection',skill,oppose_attack=True,
            incoming_attack_skill=Skill.SHOOTING,weapon_use=intent.protection_use)
    else:
        from towr.domain.pc_generated_equipment import npc_protection_test
        _,defender=npc_protection_test(state,target,actor,action+':protection',attack_skill=Skill.SHOOTING,
            weapon_use=intent.protection_use)
    return npc_repeater_bonus(state,actor,test,defender,target,defender_skill=skill)
