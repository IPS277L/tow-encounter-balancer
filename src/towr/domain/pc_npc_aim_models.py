"""Actual NPC Aim actions and one-use next-action consumption (PG1.4 V116).

Awareness uses the complete generated ranged source, without NPC Fate. Free
positioning is incidental movement and does not itself consume Aim: the next
actual Combat Action applies or loses it through the existing K1 follow-up.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.aim_models import (
    AIM_ACTION_RULE_ID, AIM_FOLLOW_UP_RULE_ID, AimActionExecutionRequest,
    AimActionExecutionResult, AimBonusSnapshot, AimFollowUpOutcome,
    AimFollowUpRequest, AimFollowUpResult,
)
from towr.domain.condition_models import Condition
from towr.domain.ranged_weapon_profiles import (
    RangedWeaponHands, RangedWeaponRange, ranged_weapon_combat_profile,
)
from towr.domain.reload_models import ranged_weapon_is_loaded
from towr.domain.test_models import DiceModifier, QualityModifier, Skill, TestQuality, TestRequest
from towr.domain.turn_models import ActionExecutionReceipt, CombatActionKind

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcMeleeState


@dataclass(frozen=True, slots=True)
class PcNpcAimProof:
    request: AimActionExecutionRequest
    result: AimActionExecutionResult


@dataclass(frozen=True, slots=True)
class PcNpcAimConsumptionProof:
    follow_up: AimFollowUpResult
    action: ActionExecutionReceipt


def _npc_source(source, actor):
    if type(actor) is not str or not actor.strip():
        raise TypeError('NPC Aim needs an exact nonempty actor ID')
    if actor not in source.enemy_activation_order:
        raise ValueError('NPC Aim actor must belong to the opposition source')
    return source.enemy(actor)


def _action(proof):
    from towr.domain.pc_musician_effect_models import PcMusicianActionProof
    from towr.domain.pc_battlefield_musician_models import PcMusicianRecoverProof
    from towr.domain.pc_oath_models import PcLadyPrayerProof
    if type(proof) in (PcMusicianActionProof,PcMusicianRecoverProof,PcLadyPrayerProof):
        return proof.result.slot.execution
    """Only completed typed actions consume Aim; movement and turn clocks do not."""
    from towr.domain.pc_melee_result_models import PcAttackProof, PcNpcHelpProof, PcHelpProof
    from towr.domain.pc_npc_ranged_models import PcNpcRangedReloadProof
    from towr.domain.pc_flagellant_models import PcNpcRecoverProof
    from towr.domain.pc_battlefield_movement_models import PcBattlefieldRecoverProof
    from towr.domain.pc_battlefield_manoeuvre_models import (
        PcBattlefieldChargeProof, PcBattlefieldRunProof,
    )
    from towr.domain.pc_weighted_net_models import PcNetReleaseProof, PcNetPickupProof
    if type(proof) is PcNpcAimProof:
        return proof.result.slot.execution
    if type(proof) is PcAttackProof:
        return proof.execution.state.active_turn.action_slots[proof.execution.slot_index - 1].execution
    if type(proof) in (PcNpcRangedReloadProof, PcBattlefieldRecoverProof,
            PcNetReleaseProof, PcNetPickupProof):
        return proof.result.slot.execution
    if type(proof) in (PcNpcHelpProof, PcHelpProof, PcNpcRecoverProof):
        return proof.execution.slot.execution
    if type(proof) is PcBattlefieldRunProof:
        return proof.result.slot.execution
    if type(proof) is PcBattlefieldChargeProof and not proof.result.attack_allowed:
        return proof.result.round_state.active_turn.action_slots[proof.request.slot_index - 1].execution
    return None


def _consumption(aim, proof, receipt):
    from towr.domain.pc_melee_result_models import PcAttackProof
    from towr.rules.aim_resolution import resolve_aim_follow_up
    if type(proof) is PcAttackProof and proof.npc_ranged_shot is not None:
        preparation = proof.npc_ranged_shot.preparation
        follow_up = preparation.aim_follow_up
        if (follow_up is None or preparation.source_request.aim != aim
                or follow_up.source_request.aim != aim
                or follow_up != resolve_aim_follow_up(follow_up.source_request)):
            raise ValueError('NPC shot lacks its exact canonical one-use Aim preparation')
        expected_outcome = (AimFollowUpOutcome.APPLIED_TO_RANGED_ATTACK
            if proof.request.target_id == aim.bonus.target_id else AimFollowUpOutcome.LOST)
        if follow_up.outcome is not expected_outcome:
            raise ValueError('NPC shot Aim outcome changed its actual target')
    else:
        attack = (proof.request if type(proof) is PcAttackProof
            and receipt.declaration.kind is CombatActionKind.ATTACK else None)
        follow_up = resolve_aim_follow_up(AimFollowUpRequest(
            aim.request_id + ':consume:' + receipt.id, aim, receipt.actor_id, receipt.id,
            receipt.declaration, Skill.MELEE if attack is not None else None, attack))
    request = follow_up.source_request
    if (request.actor_id != receipt.actor_id or request.next_action_id != receipt.id
            or request.declaration != receipt.declaration):
        raise ValueError('NPC Aim consumption differs from its actual next action receipt')
    return PcNpcAimConsumptionProof(follow_up, receipt)


def _journal(state):
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_profile
    bank, seen, consumed = {}, set(), set()
    pending = None
    replacement = None
    for proof in state.history:
        if pending is not None:
            if type(proof) is not PcNpcAimConsumptionProof or proof != pending:
                raise ValueError('NPC next action must consume or lose Aim exactly once')
            validate_pc_melee_source_types(proof, pending)
            aim = proof.follow_up.source_request.aim
            if aim.request_id in consumed:
                raise ValueError('NPC Aim source has already been consumed')
            consumed.add(aim.request_id)
            bank[aim.bonus.actor_id] = replacement
            pending, replacement = None, None
            continue
        if type(proof) is PcNpcAimConsumptionProof:
            raise ValueError('NPC Aim consumption has no actual next action')
        receipt = _action(proof)
        if receipt is None:
            continue
        if receipt.actor_id not in state.source.enemy_activation_order:
            if type(proof) is PcNpcAimProof:
                raise ValueError('NPC Aim proof belongs to a player actor')
            continue
        actor = receipt.actor_id
        previous = bank.get(actor)
        fresh = proof.result if type(proof) is PcNpcAimProof else None
        if fresh is not None:
            if type(proof.request) is not AimActionExecutionRequest or type(fresh) is not AimActionExecutionResult:
                raise TypeError('NPC Aim must retain its exact request and K1 result')
            replace(proof.request)
            replace(fresh)
            profile = pc_npc_ranged_profile(_npc_source(state.source, actor).definition)
            if (profile.awareness_profile is None or fresh.source_request != proof.request
                    or proof.request.actor_id != actor or fresh.bonus.actor_id != actor
                    or proof.request.awareness_test.profile != profile.awareness_profile
                    or fresh.request_id in seen or fresh.request_id in consumed):
                raise ValueError('NPC Aim changed its actor, Awareness source or unique action')
            seen.add(fresh.request_id)
        if previous is not None:
            pending = _consumption(previous, proof, receipt)
            replacement = fresh
        elif fresh is not None:
            bank[actor] = fresh
    return bank, pending


def current_npc_aim(state: PcMeleeState, actor: str) -> AimActionExecutionResult | None:
    _npc_source(state.source, actor)
    return _journal(state)[0].get(actor)


def expected_npc_aim_consumption(state: PcMeleeState) -> PcNpcAimConsumptionProof | None:
    return _journal(state)[1]


def _target(state, actor):
    from towr.domain.pc_battlefield_movement_models import pc_battlefield_attack_available
    live = {member.actor_id for member in state.live_party}
    return next((candidate for candidate in state.source.enemy_target_priority
        if candidate in live and pc_battlefield_attack_available(state, actor, candidate)), None)


def npc_needs_aim(state: PcMeleeState, actor: str) -> bool:
    from towr.domain.pc_npc_ranged_models import pc_npc_ranged_weapon
    from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_profile
    from towr.domain.pc_short_opening_models import pc_enemy_range, pc_has_close_enemy
    _npc_source(state.source, actor)
    enemy = state.enemy(actor)
    weapon = pc_npc_ranged_weapon(state, actor)
    if (weapon is None or not ranged_weapon_is_loaded(weapon)
            or enemy.state.injury.defeated or actor in state.exited_npc_ids
            or not enemy.state.wields_weapon or enemy.state.holds_shield
            or any(enemy.state.injury.conditions.has(condition)
                for condition in (Condition.BROKEN, Condition.DEFENCELESS))):
        return False
    profile = ranged_weapon_combat_profile(weapon.weapon_id)
    if profile.hands is not RangedWeaponHands.TWO_HANDED or pc_has_close_enemy(state, actor):
        return False
    target = _target(state, actor)
    if target is None:
        return False
    if not profile.requires_aim_before_attack and pc_enemy_range(state, actor, target) is not RangedWeaponRange.EXTREME:
        return False
    if pc_npc_ranged_profile(enemy.definition).awareness_profile is None:
        raise ValueError('NPC mandatory Aim requires its complete Awareness source')
    aim = current_npc_aim(state, actor)
    return aim is None or aim.bonus.target_id != target


def _awareness_test(state, actor, target, test_id):
    from towr.domain.pc_npc_distraction_models import pc_npc_distraction_test_modifiers
    from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_profile
    from towr.domain.pc_magic_models import magic_test_modifiers
    enemy = state.enemy(actor)
    profile = pc_npc_ranged_profile(enemy.definition).awareness_profile
    if profile is None:
        raise ValueError('NPC Awareness cannot be inferred from Shooting or another Skill')
    modifiers = pc_npc_distraction_test_modifiers(state, actor, target)
    magic_dice, magic_qualities = magic_test_modifiers(state, actor, Skill.AWARENESS)
    modifiers = (*modifiers, *magic_dice)
    qualities = magic_qualities
    if enemy.state.injury.conditions.has(Condition.BLINDED):
        qualities = (*qualities, QualityModifier('RULE-HEALTH-008:blinded', TestQuality.GRIM))
    if enemy.state.injury.conditions.has(Condition.DRAINED):
        modifiers = tuple(modifier for modifier in modifiers if modifier.amount <= 0)
        # An NPC cannot spend PC Fate to preserve Glorious through Drained.
        qualities = tuple(modifier for modifier in qualities if modifier.quality is not TestQuality.GLORIOUS)
    return TestRequest(test_id, profile, modifiers, qualities)


def build_npc_aim(state: PcMeleeState) -> AimActionExecutionRequest:
    from towr.domain.pc_melee_result_models import _ready, pc_melee_action_id
    from towr.domain.pc_npc_ranged_models import _held_npc_ranged
    _ready(state)
    turn = state.round_state.active_turn
    from towr.domain.pc_rapid_reload_models import pending_rapid_reload
    rapid = pending_rapid_reload(state)
    if (turn is None or turn.actor_id not in state.source.enemy_activation_order
            or len(turn.action_slots) > 1 and rapid is None):
        raise ValueError('NPC Aim requires its own ordinary turn and standard slot')
    actor = turn.actor_id
    if rapid is None and not npc_needs_aim(state, actor):
        raise ValueError('no mandatory NPC Aim is selected for the current legal target')
    _held_npc_ranged(state, actor, loaded=True if rapid is None else rapid.source_reload.state.loaded)
    if turn.action_slots and (turn.action_slots[-1].executed
            or turn.action_slots[-1].declaration.kind is not CombatActionKind.AIM):
        raise ValueError('NPC Aim cannot replace an executed or different action slot')
    target = rapid.target_id if rapid is not None else _target(state, actor)
    if target is None:
        raise ValueError('NPC Aim requires its live legal target')
    action = pc_melee_action_id(state, actor) + ':aim'
    return AimActionExecutionRequest(action, state.round_state, actor, target, len(turn.action_slots) or 1,
        _awareness_test(state, actor, target, action + ':awareness'))


def npc_aim_attack_modifiers(state: PcMeleeState, actor: str, target: str) -> tuple[DiceModifier, ...]:
    aim = current_npc_aim(state, actor)
    if aim is None or aim.bonus.target_id != target or aim.bonus.bonus_dice == 0:
        return ()
    return (DiceModifier(AIM_FOLLOW_UP_RULE_ID, aim.bonus.bonus_dice),)


def project_npc_aim_step(state: PcMeleeState, proof) -> PcMeleeState:
    from towr.domain.pc_melee_result_models import (
        _test_result, pc_melee_selected_action, validate_pc_melee_source_types,
    )
    if type(proof) is PcNpcAimConsumptionProof:
        expected = expected_npc_aim_consumption(state)
        if expected is None or proof != expected:
            raise ValueError('NPC Aim consumption changed its source or actual action')
        validate_pc_melee_source_types(proof, expected)
        return replace(state, history=(*state.history, proof))
    if type(proof) is not PcNpcAimProof:
        raise TypeError('NPC Aim projection requires its exact typed proof')
    if pc_melee_selected_action(state) is not CombatActionKind.AIM:
        raise ValueError('NPC Aim cannot replace the selected actual action')
    request = build_npc_aim(state)
    if proof.request != request or type(proof.result) is not AimActionExecutionResult:
        raise ValueError('NPC Aim changed its actual Awareness, actor, target or source')
    turn = state.round_state.active_turn
    if turn.action_slots[request.slot_index - 1].executed:
        raise ValueError('NPC Aim must execute one unused reserved standard Aim slot')
    result = proof.result
    _test_result(request.awareness_test, result.awareness_test_result)
    slot = turn.action_slots[request.slot_index - 1]
    receipt = ActionExecutionReceipt(request.id, AIM_ACTION_RULE_ID, request.id,
        result.awareness_test_result.trace.request_id, request.actor_id,
        state.round_state.round_number, request.slot_index, slot.declaration)
    executed = replace(slot, execution=receipt)
    clock = replace(state.round_state, active_turn=replace(turn, action_slots=(*turn.action_slots[:-1], executed)))
    expected = PcNpcAimProof(request, AimActionExecutionResult(
        request.id, AIM_ACTION_RULE_ID, request, result.awareness_test_result,
        AimBonusSnapshot(request.id + ':bonus', request.id, request.awareness_test.id,
            request.actor_id, request.target_id, result.awareness_test_result.effective_successes),
        state.round_state, clock, executed,
        tuple(dict.fromkeys((AIM_ACTION_RULE_ID, *result.awareness_test_result.trace.applied_rule_ids)))))
    if proof != expected:
        raise ValueError('NPC Aim altered its roll, bonus, standard slot or round receipt')
    validate_pc_melee_source_types(proof, expected)
    from towr.domain.pc_magic_models import consume_magic_modifiers
    return replace(state, history=(*state.history, proof), round_state=clock,
        magic_modifiers=consume_magic_modifiers(state.magic_modifiers, proof))


def validate_pc_npc_aim_history(state: PcMeleeState) -> None:
    _journal(state)
