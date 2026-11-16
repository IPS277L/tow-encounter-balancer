"""Bounded weapon-assisted Help for a named allied Attack or Protection Test."""
from dataclasses import replace

from towr.domain.condition_models import Condition
from towr.domain.help_models import (
    HELP_BONUS_RULE_ID, HelpActionExecutionRequest, HelpBonusApplicationRequest,
    HelpBonusApplicationResult, _expected_help_application,
)
from towr.domain.pc_heavy_wound_models import usable_weapon_hand
from towr.domain.pc_melee_models import PcHelpTarget, PcMeleePolicy
from towr.domain.test_models import Skill


def pc_help_beneficiary(state):
    strategy = pc_selected_help_policy(state)
    return None if strategy is None else eligible_pc_help_beneficiary(state, strategy)


def pc_selected_help_policy(state):
    actor = state.round_state.active_turn.actor_id
    if actor not in state.source.pc_activation_order:
        return None
    source = state.source.participant(actor)
    if source.policy is PcMeleePolicy.AUTOMATIC_COMBAT:
        from towr.domain.pc_tactical_models import select_pc_tactic
        return select_pc_tactic(state).help_policy
    return source.help_policy


def eligible_pc_help_beneficiary(state, strategy, actor=None, *, planned_choice=None):
    from towr.domain.pc_melee_result_models import _pc_recover_needed
    actor = actor or state.round_state.active_turn.actor_id
    if actor not in state.source.pc_activation_order:
        return None
    if strategy is None:
        return None
    member = state.participant(actor)
    if (member.injury.dead or member.injury.conditions.has(Condition.DEFENCELESS)
            or member.injury.conditions.has(Condition.DEAFENED)
            or _pc_recover_needed(member) or usable_weapon_hand(member) is None):
        return None
    ally = state.participant(strategy.beneficiary_id)
    if (ally.injury.dead or ally.injury.conditions.has(Condition.DEFENCELESS)
            or ally.injury.conditions.has(Condition.DRAINED)):
        return None
    if strategy.target is PcHelpTarget.ATTACK:
        from towr.domain.pc_melee_result_models import pc_attack_skill
        from towr.domain.turn_models import CombatActionKind
        recipient=state.source.participant(ally.actor_id)
        view=state
        if recipient.policy is PcMeleePolicy.AUTOMATIC_COMBAT:
            if state.source.pc_activation_order.index(actor)>=state.source.pc_activation_order.index(ally.actor_id):
                return None
            if planned_choice is None:
                from towr.domain.pc_tactical_models import select_pc_tactic
                planned_choice=select_pc_tactic(state,ally.actor_id)
            if planned_choice.action is not CombatActionKind.ATTACK:
                return None
            if planned_choice.weapon_item_id is not None:
                from towr.domain.pc_weapon_inventory import pc_weapon_inventory_view
                view=pc_weapon_inventory_view(state,ally.actor_id,planned_choice.weapon_item_id)
                if view is None:
                    return None
        if pc_attack_skill(view,ally.actor_id) is not strategy.skill:
            return None
        if strategy.skill is Skill.SHOOTING:
            from towr.domain.pc_melee_models import PC_RANGED_WEAPONS
            from towr.domain.pc_backup_weapon_models import pc_active_weapon
            if (pc_active_weapon(state,actor) not in PC_RANGED_WEAPONS
                    or member.ranged is None or not member.ranged.loaded):
                return None
        if (_pc_recover_needed(view.participant(ally.actor_id)) or strategy.beneficiary_id in (
                *state.round_state.completed_turn_entity_ids,*state.round_state.excluded_turn_entity_ids)):
            return None
    else:
        from towr.domain.pc_melee_result_models import pc_protection_skill,pc_selected_npc_attack_profile
        incoming = pc_help_incoming_actor(state, strategy)
        skill = (pc_protection_skill(ally,pc_selected_npc_attack_profile(state,incoming).skill,
            state.source.participant(ally.actor_id).close_shooting_protection_skill)
            if incoming is not None else None)
        if (incoming is not None and pc_selected_npc_attack_profile(state,incoming).skill is Skill.SHOOTING
                and state.source.participant(ally.actor_id).policy is PcMeleePolicy.AUTOMATIC_COMBAT):
            from towr.domain.pc_generated_ranged_advice import pc_close_shooting_protection
            from towr.domain.pc_melee_result_models import pc_melee_action_id
            skill,_=pc_close_shooting_protection(state,ally.actor_id,incoming,
                pc_melee_action_id(state,incoming)+':protection')
        if skill is not strategy.skill or incoming is None:
            return None
    return strategy.beneficiary_id


def pc_help_incoming_actor(state, strategy=None):
    """Select the first current live NPC, without anticipating future PC outcomes."""
    strategy = strategy or pc_selected_help_policy(state)
    if strategy is None:
        return None
    target = next((pc for pc in state.source.enemy_target_priority
        if not state.participant(pc).injury.dead),None)
    if target != strategy.beneficiary_id:
        return None
    unavailable = (*state.round_state.completed_turn_entity_ids,*state.round_state.excluded_turn_entity_ids)
    from towr.domain.pc_npc_ranged_models import pc_npc_ranged_weapon
    return next((enemy for enemy in state.source.enemy_activation_order
        if not state.enemy(enemy).state.injury.defeated and enemy not in state.exited_npc_ids
        and enemy not in unavailable and (pc_npc_ranged_weapon(state,enemy) is None
            or pc_npc_ranged_weapon(state,enemy).loaded)),None)


def build_pc_help_action(state):
    from towr.domain.pc_melee_result_models import pc_melee_action_id, _pc_test
    from towr.domain.pc_generated_talents import expected_wild_attack
    if expected_wild_attack(state) is not None:
        raise ValueError('selected Wild Attack must pay Staggered before its Melee Help Test')
    beneficiary = pc_help_beneficiary(state)
    if beneficiary is None:
        raise ValueError('the explicit Help strategy cannot select an eligible ally')
    actor = state.round_state.active_turn.actor_id
    strategy = pc_selected_help_policy(state)
    action_id = pc_melee_action_id(state,actor)
    skill = strategy.skill
    intended = (pc_melee_action_id(state,beneficiary)+':attack' if strategy.target is PcHelpTarget.ATTACK else
        pc_melee_action_id(state,pc_help_incoming_actor(state))+':protection')
    test=_pc_test(state,actor,action_id+':help:test',skill)
    if skill is Skill.SHOOTING:
        from towr.domain.pc_ranged_models import pc_repeater_attack_modifiers
        test=replace(test,dice_modifiers=(*test.dice_modifiers,*pc_repeater_attack_modifiers(state,actor)))
    return HelpActionExecutionRequest(action_id+':help:execute',state.round_state,actor,
        state.participant(actor).injury.conditions,beneficiary,
        intended,1,test,skill,skill)


def build_pc_attack_help(state, test):
    from towr.domain.pc_melee_result_models import pc_attack_skill
    actor=state.round_state.active_turn.actor_id
    return build_pc_test_help(state,actor,pc_attack_skill(state,actor),test)


def build_pc_test_help(state, actor, skill, test):
    """Retain every exact intended-Test application, including zero/capped dice."""
    from towr.domain.pc_melee_result_models import PcHelpProof
    applications = []
    for proof in state.history:
        if not isinstance(proof,PcHelpProof):
            continue
        execution = proof.execution
        if (execution.bonus.beneficiary_id != actor or execution.bonus.beneficiary_test_id != test.id
                or execution.bonus.beneficiary_skill is not skill):
            continue
        if proof.beneficiary_weapon_item_id is not None:
            from towr.domain.pc_backup_weapon_models import pc_active_weapon_item_id
            if proof.beneficiary_weapon_item_id!=pc_active_weapon_item_id(state,actor):
                continue
        request = HelpBonusApplicationRequest(test.id+':apply:'+execution.request_id,
            execution,actor,skill,test)
        updated,modifier = _expected_help_application(request)
        application = HelpBonusApplicationResult(request.id,request.rule_id,request,updated,
            modifier,(request.rule_id,execution.rule_id))
        applications.append(application)
        test = updated
    if state.participant(actor).injury.conditions.has(Condition.DRAINED):
        test = replace(test,dice_modifiers=tuple(modifier for modifier in test.dice_modifiers
            if modifier.amount <= 0))
    return test,tuple(applications)


def pc_attack_help_applications(state, attack):
    """Recover the exact receipt chain for a prepared PC Attack, before Fate."""
    actor = state.round_state.active_turn.actor_id
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_melee_result_models import pc_attack_skill
        skill,test = pc_attack_skill(state,actor),attack.attacker_test
    else:
        if attack.defender_test is None:
            return ()
        slots = state.round_state.active_turn.action_slots
        grant = (slots[-1].enduring_strength or slots[-1].crown_of_antlers) if slots else None
        actor = (grant.target_id if grant is not None
            else next(pc for pc in state.source.enemy_target_priority if not state.participant(pc).injury.dead))
        from towr.domain.pc_melee_result_models import pc_protection_skill,pc_selected_npc_attack_profile
        skill = pc_protection_skill(state.participant(actor),
            pc_selected_npc_attack_profile(state,state.round_state.active_turn.actor_id).skill,
            state.source.participant(actor).close_shooting_protection_skill)
        test = attack.defender_test
        if (pc_selected_npc_attack_profile(state,state.round_state.active_turn.actor_id).skill is Skill.SHOOTING
                and state.source.participant(actor).policy is PcMeleePolicy.AUTOMATIC_COMBAT):
            from towr.domain.pc_generated_ranged_advice import pc_close_shooting_protection
            skill,_=pc_close_shooting_protection(state,actor,state.round_state.active_turn.actor_id,test.id)
    base = replace(test,dice_modifiers=tuple(modifier
        for modifier in test.dice_modifiers
        if modifier.rule_id != HELP_BONUS_RULE_ID))
    return build_pc_test_help(state,actor,skill,base)[1]


def pc_help_beneficiary_weapon(state,strategy):
    """Bind automatic Help to the concrete item of its promised future Test."""
    if strategy is None:
        return None
    target=strategy.beneficiary_id
    inventory=state.participant(target).weapon_inventory
    if inventory is None or strategy.skill is Skill.ATHLETICS:
        return None
    if strategy.target is PcHelpTarget.ATTACK and state.source.participant(target).policy is PcMeleePolicy.AUTOMATIC_COMBAT:
        from towr.domain.pc_tactical_models import select_pc_tactic
        return select_pc_tactic(state,target).weapon_item_id or inventory.active_item_id
    return inventory.active_item_id
