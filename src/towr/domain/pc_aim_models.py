"""Actual Aim actions, one-use follow-ups and paid second-slot PC shots."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.aim_models import (
    AIM_ACTION_RULE_ID, AimActionExecutionRequest, AimActionExecutionResult,
    AimFollowUpRequest, AimFollowUpResult, AimFollowUpOutcome, AimBonusSnapshot,
)
from towr.domain.condition_models import Condition
from towr.domain.fate_models import FateSecondActionSpendRequest, FateSecondActionSpendResult
from towr.domain.pc_heavy_wound_models import usable_weapon_hand, critical_for_action, restriction_sources
from towr.domain.injury_models import WoundRestriction
from towr.domain.pc_melee_models import PcMeleeWeapon, PcTwoHandedGrip
from towr.domain.pc_short_opening_models import pc_has_close_enemy
from towr.domain.test_models import Skill, DiceModifier
from towr.domain.turn_models import (
    ActionExecutionReceipt, CombatActionKind, CombatActionDeclaration,
    CombatActionSlotRequest, ActionSlotGrant,
)

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcFateDecline


@dataclass(frozen=True, slots=True)
class PcAimProof:
    request: AimActionExecutionRequest
    result: AimActionExecutionResult
    fate_decline: PcFateDecline


@dataclass(frozen=True, slots=True)
class PcAimSecondActionProof:
    result: FateSecondActionSpendResult


@dataclass(frozen=True, slots=True)
class PcAimConsumptionProof:
    follow_up: AimFollowUpResult
    action: ActionExecutionReceipt


def _action(proof):
    from towr.domain.pc_melee_result_models import PcAttackProof, PcRecoverProof, PcHelpProof
    from towr.domain.pc_ranged_models import PcRangedReloadProof
    if type(proof) is PcAimProof:
        return proof.result.slot.execution
    if type(proof) is PcAttackProof:
        return proof.execution.state.active_turn.action_slots[proof.execution.slot_index-1].execution
    if type(proof) in (PcRecoverProof, PcRangedReloadProof):
        return proof.result.slot.execution
    if type(proof) is PcHelpProof:
        return proof.execution.slot.execution
    return None


def _consumption(aim, proof, receipt):
    from towr.domain.pc_melee_result_models import PcAttackProof
    from towr.rules.aim_resolution import resolve_aim_follow_up
    if type(proof) is PcAttackProof and proof.ranged_shot is not None:
        follow_up = proof.ranged_shot.preparation.aim_follow_up
        if (follow_up is None or follow_up.source_request.aim != aim
                or follow_up.outcome is not AimFollowUpOutcome.APPLIED_TO_RANGED_ATTACK):
            raise ValueError('PC ranged shot lost its actual one-use Aim follow-up')
    else:
        attack = proof.request if type(proof) is PcAttackProof else None
        follow_up = resolve_aim_follow_up(AimFollowUpRequest(
            aim.request_id+':consume:'+receipt.id, aim, receipt.actor_id, receipt.id,
            receipt.declaration, Skill.MELEE if attack is not None else None, attack))
    source = follow_up.source_request
    if (source.actor_id != receipt.actor_id or source.next_action_id != receipt.id
            or source.declaration != receipt.declaration):
        raise ValueError('Aim consumption differs from its actual next action receipt')
    return PcAimConsumptionProof(follow_up,receipt)


def _journal(state):
    """A single next-action consumption is completed before any other transition."""
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    enabled = any(m.pc.weapon is PcMeleeWeapon.HOCHLAND_LONG_RIFLE for m in state.source.party)
    if not enabled:
        if any(type(p) in (PcAimProof,PcAimSecondActionProof,PcAimConsumptionProof) for p in state.history):
            raise ValueError('Aim receipts require an admitted Hochland participant')
        return {}, None
    bank, consumed = {}, set()
    pending = None
    replacement = None
    for proof in state.history:
        if pending is not None:
            if type(proof) is not PcAimConsumptionProof or proof != pending:
                raise ValueError('the actual next action must consume or lose Aim exactly once')
            validate_pc_melee_source_types(proof,pending)
            aim = proof.follow_up.source_request.aim
            if aim.request_id in consumed:
                raise ValueError('Aim source has already been consumed')
            consumed.add(aim.request_id)
            bank[aim.bonus.actor_id] = replacement
            pending, replacement = None, None
            continue
        if type(proof) is PcAimConsumptionProof:
            raise ValueError('Aim consumption has no actual next action')
        receipt = _action(proof)
        if receipt is None or receipt.actor_id not in state.source.pc_activation_order:
            continue
        actor = receipt.actor_id
        previous = bank.get(actor)
        fresh = proof.result if type(proof) is PcAimProof else None
        if fresh is not None:
            replace(fresh)
            if (state.source.participant(actor).pc.weapon is not PcMeleeWeapon.HOCHLAND_LONG_RIFLE
                    or fresh.request_id in consumed or fresh.bonus.actor_id != actor):
                raise ValueError('Aim source belongs to another actor, loadout or consumed action')
        if previous is not None:
            pending = _consumption(previous,proof,receipt)
            replacement = fresh
        elif fresh is not None:
            bank[actor] = fresh
    return bank, pending


def current_pc_aim(state, actor):
    return _journal(state)[0].get(actor)


def expected_pc_aim_consumption(state):
    return _journal(state)[1]


def pc_hochland_needs_aim(state, actor):
    member = state.participant(actor)
    if (state.source.participant(actor).pc.weapon is not PcMeleeWeapon.HOCHLAND_LONG_RIFLE
            or member.using_backup_weapon):
        return False
    target = next(a for a in state.source.participant(actor).target_priority
        if not state.enemy(a).state.injury.defeated and a not in state.exited_npc_ids)
    aim = current_pc_aim(state,actor)
    return aim is None or aim.bonus.target_id != target


def build_pc_aim(state):
    from towr.domain.pc_melee_result_models import _pc_test, pc_melee_action_id, _ready
    _ready(state)
    turn = state.round_state.active_turn
    if turn is None or turn.actor_id not in state.source.pc_activation_order or len(turn.action_slots) > 1:
        raise ValueError('Aim requires its own standard PC action')
    actor = turn.actor_id
    member = state.participant(actor)
    source = state.source.participant(actor)
    if (source.pc.weapon is not PcMeleeWeapon.HOCHLAND_LONG_RIFLE or member.using_backup_weapon
            or usable_weapon_hand(member) is not PcTwoHandedGrip.BOTH
            or not member.ranged.loaded or pc_has_close_enemy(state,actor)
            or restriction_sources(member.injury,WoundRestriction.CANNOT_AIM)
            or member.injury.conditions.has(Condition.DEFENCELESS)):
        raise ValueError('Aim requires the actual held loaded Hochland and clear Short range')
    target = next(a for a in source.target_priority if not state.enemy(a).state.injury.defeated)
    action = pc_melee_action_id(state,actor)+':aim'
    return AimActionExecutionRequest(action,state.round_state,actor,target,len(turn.action_slots) or 1,
        _pc_test(state,actor,action+':awareness',Skill.AWARENESS))


def pc_aim_attack_modifiers(state, actor, target):
    aim = current_pc_aim(state,actor)
    if aim is None or aim.bonus.target_id != target or aim.bonus.bonus_dice == 0:
        return ()
    from towr.domain.aim_models import AIM_FOLLOW_UP_RULE_ID
    return (DiceModifier(AIM_FOLLOW_UP_RULE_ID,aim.bonus.bonus_dice),)


def build_pc_aim_second_action(state):
    if (state.pending or state.pending_wound is not None or not state.live_party or not state.live_enemies
            or expected_pc_aim_consumption(state) is not None):
        return None
    turn = state.round_state.active_turn
    if (turn is None or turn.actor_id not in state.source.pc_activation_order
            or len(turn.action_slots) != 1 or not turn.action_slots[0].executed
            or turn.action_slots[0].declaration.kind is not CombatActionKind.AIM):
        return None
    actor = turn.actor_id
    source, member = state.source.participant(actor), state.participant(actor)
    policy = source.aim_second_action_policy
    aim = current_pc_aim(state,actor)
    if (policy is None or member.using_backup_weapon or aim is None
            or aim.request_id != turn.action_slots[0].execution.id
            or member.injury.conditions.has(Condition.DEFENCELESS)
            or usable_weapon_hand(member) is not PcTwoHandedGrip.BOTH
            or not member.ranged.loaded or pc_has_close_enemy(state,actor)
            or state.enemy(aim.bonus.target_id).state.injury.defeated
            or pc_hochland_needs_aim(state,actor)):
        return None
    fate = member.fate
    cost = 0 if fate.lucky_free_spend_available else 1
    if not fate.can_spend or fate.remaining_spends-cost < policy.minimum_remaining_session_spends:
        return None
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    action = pc_melee_action_id(state,actor)+':aim-second'
    return FateSecondActionSpendRequest(action+':fate',fate,CombatActionSlotRequest(
        action+':reserve',state.round_state,actor,CombatActionDeclaration(CombatActionKind.ATTACK),ActionSlotGrant.FATE))


def project_pc_aim_step(state, proof):
    from towr.domain.pc_melee_result_models import (
        _party_update, _test_result, _decline, pc_after_test, validate_pc_melee_source_types,
        pc_melee_selected_action,
    )
    if type(proof) is PcAimConsumptionProof:
        expected = expected_pc_aim_consumption(state)
        if expected is None or proof != expected:
            raise ValueError('Aim consumption changed its source or actual action')
        validate_pc_melee_source_types(proof,expected)
        return replace(state,history=(*state.history,proof))
    if type(proof) is PcAimSecondActionProof:
        from towr.rules.fate_resolution import spend_fate_for_second_action
        request = build_pc_aim_second_action(state)
        if request is None:
            raise ValueError('no admitted funded Aim second action is due')
        expected = PcAimSecondActionProof(spend_fate_for_second_action(request))
        if proof != expected:
            raise ValueError('second action changed its funding, actor, session, slot or declaration')
        validate_pc_melee_source_types(proof,expected)
        return replace(state,history=(*state.history,proof),round_state=proof.result.slot_result.state,
            party=_party_update(state,request.state.actor_id,fate=proof.result.state))
    if pc_melee_selected_action(state) is not CombatActionKind.AIM:
        raise ValueError('Aim cannot replace the selected action')
    request = build_pc_aim(state)
    if proof.request != request or type(proof.result) is not AimActionExecutionResult:
        raise ValueError('Aim changed its actual Awareness, actor, target or held weapon source')
    result = proof.result
    turn = state.round_state.active_turn
    if (len(turn.action_slots) < request.slot_index or turn.action_slots[request.slot_index-1].executed
            or turn.action_slots[request.slot_index-1].declaration.kind is not CombatActionKind.AIM):
        raise ValueError('Aim requires its one unused standard Aim slot')
    _test_result(request.awareness_test,result.awareness_test_result)
    _decline(state,proof.fate_decline,request.actor_id,request.awareness_test.id,'test')
    turn = state.round_state.active_turn
    slot = turn.action_slots[request.slot_index-1]
    receipt = ActionExecutionReceipt(request.id,AIM_ACTION_RULE_ID,request.id,
        result.awareness_test_result.trace.request_id,request.actor_id,state.round_state.round_number,
        request.slot_index,slot.declaration)
    executed = replace(slot,execution=receipt)
    combat = replace(state.round_state,active_turn=replace(turn,action_slots=(*turn.action_slots[:-1],executed)))
    expected = PcAimProof(request,AimActionExecutionResult(request.id,AIM_ACTION_RULE_ID,request,
        result.awareness_test_result,AimBonusSnapshot(request.id+':bonus',request.id,request.awareness_test.id,
            request.actor_id,request.target_id,result.awareness_test_result.successes),state.round_state,combat,
        executed,tuple(dict.fromkeys((AIM_ACTION_RULE_ID,*result.awareness_test_result.trace.applied_rule_ids)))),proof.fate_decline)
    if proof != expected:
        raise ValueError('Aim altered its roll, bonus, slot receipt or round')
    validate_pc_melee_source_types(proof,expected)
    member = state.participant(request.actor_id)
    injury = pc_after_test(state,request.actor_id,critical_for_action(member,CombatActionKind.AIM,
        used_hand=usable_weapon_hand(member)))
    return replace(state,history=(*state.history,proof),round_state=combat,
        party=_party_update(state,request.actor_id,injury=injury))


def validate_pc_aim_history(state):
    _journal(state)
