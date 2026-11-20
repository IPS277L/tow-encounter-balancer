"""Battle-owned Bash window, physical readiness and immediate Melee request."""
from towr.domain.injury_models import injury_is_defeated
from dataclasses import replace

from towr.domain.attack_models import AttackOutcome
from towr.domain.condition_models import Condition,StaggerOutcome
from towr.domain.talent_actor_models import actor_acquired_talents
from towr.domain.talent_bash_attack_models import BashAttackGrant
from towr.domain.talent_catalog import TalentId
from towr.domain.pc_bash_weapon_models import select_bash_weapon
from towr.domain.pc_immediate_attack_models import (
    PcBashDecisionProof,PcImmediateStrikeProof,PcImmediateStrikeRequest,
)
from towr.domain.test_models import Skill


def _able(state,actor,*,attacking=True):
    from towr.domain.pc_magic_weapon_models import actor_injury
    injury=actor_injury(state,actor)
    dead=(injury_is_defeated(injury)
        or actor in state.exited_npc_ids)
    return not dead and (not attacking or not injury.conditions.has(Condition.DEFENCELESS))


def expected_bash_decision(state):
    """Settle this real first-Stagger window once, including a declined use."""
    from towr.domain.pc_melee_result_models import PcAttackProof
    if state.pending or state.pending_wound is not None or state.magic_pending is not None:return None
    turn=state.round_state.active_turn
    if turn is None or not turn.action_slots or not turn.action_slots[-1].executed:return None
    talent=next((entry for entry in actor_acquired_talents(state,turn.actor_id)
        if entry.id is TalentId.BASH_ATTACK),None)
    if talent is None:return None
    receipt=turn.action_slots[-1].execution
    primary=next(((index,proof) for index,proof in reversed(tuple(enumerate(state.history)))
        if type(proof) is PcAttackProof and proof.execution.slot.execution==receipt),None)
    if primary is None:return None
    index,proof=primary
    if any(type(item) is PcBashDecisionProof and item.grant.source_request.id==proof.request.id
            for item in state.history):return None
    result=proof.execution.resolution
    use=proof.weapon_intent.attack_use
    if (proof.mount_attack is not None or use is None or use.skill is not Skill.BRAWN
            or result.attack.outcome is not AttackOutcome.HIT or result.stagger is None
            or result.stagger.outcome is not StaggerOutcome.CONDITION_ADDED):return None
    grant=BashAttackGrant(proof.request,proof.execution,use,talent)
    from towr.domain.pc_magic_weapon_models import actor_injury
    from towr.domain.pc_oath_models import oath_allows_attack
    selection=(select_bash_weapon(state,grant.actor_id,grant.target_id)
        if oath_allows_attack(state,grant.actor_id,Skill.MELEE)
        and _able(state,grant.actor_id) and _able(state,grant.target_id,attacking=False)
        and actor_injury(state,grant.target_id).conditions.has(Condition.STAGGERED) else None)
    return PcBashDecisionProof(index,grant,selection)


def pending_bash_decision(state):
    from towr.domain.pc_melee_result_models import PcAttackProof,validate_pc_melee_source_types
    consumed={proof.request.grant.id for proof in state.history if type(proof) is PcImmediateStrikeProof}
    for index,proof in reversed(tuple(enumerate(state.history))):
        if type(proof) is PcBashDecisionProof and proof.selection is not None and proof.grant.id not in consumed:
            if proof.source_index>=index or type(state.history[proof.source_index]) is not PcAttackProof:
                raise ValueError('Bash permission lost its actual earlier Brawn Attack')
            source=state.history[proof.source_index]
            actual=(source.request,source.execution,source.weapon_intent.attack_use)
            retained=(proof.grant.source_request,proof.grant.source_execution,proof.grant.weapon_use)
            if (actual!=retained or proof.grant.talent not in actor_acquired_talents(state,proof.grant.actor_id)):
                raise ValueError('Bash permission changed its actual Brawn source or owner')
            validate_pc_melee_source_types(retained,actual)
            if state.round_state!=proof.grant.source_execution.state:
                raise ValueError('Bash permission cannot escape its immediate parent action window')
            return proof
    return None


def expected_bash_pc_shield_release(state):
    decision=pending_bash_decision(state)
    if decision is None or decision.grant.actor_id not in state.source.pc_activation_order:return None
    actor=decision.grant.actor_id
    member=state.participant(actor)
    if decision.selection.release_shield and member.weapon_inventory.shield_hand is not None:
        from towr.domain.pc_shield_models import PcShieldReleaseProof
        return PcShieldReleaseProof(actor,decision.grant.id,member.shield.hand)
    return None


def expected_bash_npc_shield_drop(state):
    decision=pending_bash_decision(state)
    if decision is None or decision.grant.actor_id not in state.source.npc_activation_order:return None
    actor=decision.grant.actor_id
    enemy=state.enemy(actor)
    if not decision.selection.release_shield or not enemy.state.holds_shield:return None
    from towr.domain.pc_npc_shield_models import (
        npc_shield_item,NpcShieldLocation,PcNpcShieldDropProof,_drop_position,_drop_id,_resilience_witness,_with_shield,
    )
    previous=npc_shield_item(state,actor)
    after=replace(previous,location=NpcShieldLocation.DROPPED,ground=_drop_position(state,actor))
    weapon=enemy.state.weapon_inventory.item(decision.selection.use.primary_item_id)
    witness=_resilience_witness(state,actor)
    return PcNpcShieldDropProof(_drop_id(state.source,actor,len(state.history)),len(state.history),
        previous,after,weapon,enemy,_with_shield(enemy,False,**witness),**witness)


def expected_bash_pc_swap(state):
    decision=pending_bash_decision(state)
    if decision is None or decision.grant.actor_id not in state.source.pc_activation_order:return None
    transition=decision.selection.equip
    if transition is None:return None
    member=state.participant(decision.grant.actor_id)
    if member.weapon_inventory!=transition.before:return None
    from towr.domain.pc_weapon_inventory import PcWeaponSwapProof
    from towr.domain.pc_tactical_models import PcTacticalChoice
    from towr.domain.turn_models import CombatActionKind
    actor=decision.grant.actor_id
    intent=PcTacticalChoice(actor,CombatActionKind.ATTACK,decision.grant.target_id,None,
        decision.selection.utility,'bash_immediate',weapon_item_id=transition.after.active_item_id)
    return PcWeaponSwapProof(actor,decision.grant.id,transition.before,transition.after,intent,
        round_number=decision.grant.round_number)


def expected_bash_npc_equip(state):
    decision=pending_bash_decision(state)
    if decision is None or decision.grant.actor_id not in state.source.npc_activation_order:return None
    transition=decision.selection.equip
    if transition is None or state.enemy(decision.grant.actor_id).state.weapon_inventory!=transition.before:return None
    from towr.domain.pc_npc_weapon_inventory import PcNpcWeaponEquipProof
    return PcNpcWeaponEquipProof(transition)


def apply_bash_pc_swap(state,proof):
    """Apply the committed hand arrangement, including actual incidental harm."""
    from towr.domain.pc_weapon_inventory import replace_pc_member,pc_hand
    from towr.domain.pc_heavy_wound_models import critical_for_incidental_hand_use
    from towr.domain.weapon_inventory_models import WeaponGrip
    member=replace_pc_member(state.participant(proof.actor_id),weapon_inventory=proof.state)
    touched={hand for before,after in zip(proof.previous.items,proof.state.items,strict=True)
        if (before.location,before.grip)!=(after.location,after.grip)
        for grip in (before.grip,after.grip) if grip is not None
        for hand in ((WeaponGrip.LEFT,WeaponGrip.RIGHT) if grip is WeaponGrip.BOTH else (grip,))}
    used=pc_hand(WeaponGrip.BOTH if len(touched)==2 else next(iter(touched)))
    return replace_pc_member(member,injury=critical_for_incidental_hand_use(member,used))


def build_pc_bash_strike(state):
    if state.pending or state.pending_wound is not None or state.magic_pending is not None:return None
    decision=pending_bash_decision(state)
    if decision is None:return None
    from towr.domain.pc_magic_weapon_models import actor_inventory,actor_injury
    use=decision.selection.use
    if actor_inventory(state,decision.grant.actor_id)!=use.inventory:return None
    if (not _able(state,decision.grant.actor_id) or not _able(state,decision.grant.target_id,attacking=False)
            or not actor_injury(state,decision.grant.target_id).conditions.has(Condition.STAGGERED)):
        raise ValueError('committed Bash lost its actual live Staggered target')
    from towr.domain.pc_short_opening_models import pc_enemy_range
    if pc_enemy_range(state,decision.grant.actor_id,decision.grant.target_id).value!='close':
        raise ValueError('committed Bash cannot invent a new approach or Charge')
    from towr.domain.pc_weapon_intent_models import build_pc_explicit_attack_weapon_intent
    from towr.domain.pc_melee_result_models import prepare_pc_weapon_kernel
    intent=build_pc_explicit_attack_weapon_intent(state,decision.grant.actor_id,decision.grant.target_id,
        decision.grant.id,weapon_use=use)
    kernel,protection=prepare_pc_weapon_kernel(state,intent,decision.grant.id,charge=None,crown=None)
    return PcImmediateStrikeRequest(decision,state.round_state,kernel,intent),protection
