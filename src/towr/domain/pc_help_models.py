"""Bounded weapon-assisted Help for a named allied Attack or Protection Test."""
from towr.domain.injury_models import injury_is_defeated
from dataclasses import replace

from towr.domain.condition_models import Condition
from towr.domain.help_models import (
    HELP_BONUS_RULE_ID, HelpActionExecutionRequest, HelpBonusApplicationRequest,
    HelpBonusApplicationResult, _expected_help_application,
)
from towr.domain.pc_heavy_wound_models import usable_weapon_hand
from towr.domain.pc_melee_models import PcHelpTarget, PcMeleePolicy
from towr.domain.test_models import Skill
from towr.domain.reload_models import ranged_weapon_is_loaded


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


def help_side_order(state,actor):
    from towr.domain.pc_actor_models import pc_actor_side
    from towr.domain.turn_models import CombatSide
    return (state.source.player_activation_order if pc_actor_side(state,actor) is CombatSide.PLAYERS_AND_ALLIES
        else state.source.enemy_activation_order)


def help_recipient_attack(state,actor,*,planned_choice=None):
    """Current attainable Attack and physical item, with no resource mutation."""
    from towr.domain.pc_medical_models import effective_medical_injury
    from towr.domain.pc_melee_result_models import pc_attack_skill,pc_selected_npc_attack_profile,_pc_recover_needed
    from towr.domain.turn_models import CombatActionKind
    injury=effective_medical_injury(state,actor)
    if injury_is_defeated(injury) or any(injury.conditions.has(c) for c in
            (Condition.DEFENCELESS,Condition.BROKEN)):return None
    if actor in state.source.pc_activation_order:
        source=state.source.participant(actor);view=state
        if source.policy is PcMeleePolicy.AUTOMATIC_COMBAT:
            if planned_choice is None:
                from towr.domain.pc_tactical_models import select_pc_tactic
                planned_choice=select_pc_tactic(state,actor)
            if planned_choice.action is not CombatActionKind.ATTACK:return None
            if planned_choice.weapon_item_id is not None or planned_choice.unarmed_attack:
                from towr.domain.pc_weapon_inventory import pc_weapon_inventory_view
                view=pc_weapon_inventory_view(state,actor,planned_choice.weapon_item_id)
                if view is None:return None
        elif source.help_policy is not None:return None
        if _pc_recover_needed(view.participant(actor),unarmed_available=source.pc.brawn is not None):return None
        member=view.participant(actor);skill=pc_attack_skill(view,actor)
        if skill is Skill.SHOOTING and (member.ranged is None or not ranged_weapon_is_loaded(member.ranged)):return None
        inventory=member.weapon_inventory
    else:
        if injury.conditions.has(Condition.PRONE):return None
        from towr.domain.pc_medical_tactics import choose_medical_action
        if choose_medical_action(state,actor) is not None:return None
        from towr.domain.pc_npc_ranged_models import pc_npc_ranged_weapon
        weapon=pc_npc_ranged_weapon(state,actor)
        if weapon is not None and not ranged_weapon_is_loaded(weapon):return None
        view=state;skill=pc_selected_npc_attack_profile(state,actor).skill
        inventory=state.enemy(actor).state.weapon_inventory
    return view,skill,None if inventory is None else inventory.active_item_id,planned_choice


def help_recipient_protection(state,actor,incoming,test_id):
    """One actual Protection Test, selected by injury role rather than side."""
    from towr.domain.pc_melee_result_models import pc_attack_skill,pc_selected_npc_attack_profile,_pc_test,pc_protection_skill
    incoming_skill=(pc_attack_skill(state,incoming) if incoming in state.source.pc_activation_order else
        pc_selected_npc_attack_profile(state,incoming).skill)
    if actor not in state.source.pc_activation_order:
        from towr.domain.pc_generated_equipment import npc_protection_test
        profile,test=npc_protection_test(state,actor,incoming,test_id,attack_skill=incoming_skill)
        return profile.skill,test
    source=state.source.participant(actor)
    if source.policy is PcMeleePolicy.AUTOMATIC_COMBAT and incoming_skill in (Skill.SHOOTING,Skill.THROWING):
        from towr.domain.pc_generated_ranged_advice import pc_shooting_protection
        return pc_shooting_protection(state,actor,incoming,test_id,attack_skill=incoming_skill)
    if source.policy is PcMeleePolicy.AUTOMATIC_COMBAT and incoming_skill is Skill.BRAWN:
        from towr.domain.pc_generated_ranged_advice import pc_brawn_protection
        return pc_brawn_protection(state,actor,test_id)
    skill=pc_protection_skill(state.participant(actor),incoming_skill,source.close_shooting_protection_skill)
    return skill,_pc_test(state,actor,test_id,skill,oppose_attack=True,incoming_attack_skill=incoming_skill)


def eligible_pc_help_beneficiary(state,strategy,actor=None,*,planned_choice=None):
    from towr.domain.pc_melee_result_models import _pc_recover_needed
    from towr.domain.pc_actor_models import pc_actor_side,pc_actor_injury
    actor=actor or state.round_state.active_turn.actor_id
    if actor not in state.source.pc_activation_order or strategy is None:return None
    beneficiary=strategy.beneficiary_id
    if (beneficiary==actor or beneficiary not in (*state.source.pc_activation_order,*state.source.npc_activation_order)
            or pc_actor_side(state,actor) is not pc_actor_side(state,beneficiary)):return None
    from towr.domain.pc_armour_models import actor_bound_to_chivalric_combat
    if strategy.skill in (Skill.SHOOTING,Skill.THROWING) and actor_bound_to_chivalric_combat(state,actor):return None
    member=state.participant(actor);body_help=strategy.skill in (Skill.BRAWN,Skill.ENDURANCE,Skill.ATHLETICS)
    if strategy.skill is Skill.BRAWN and state.source.participant(actor).pc.brawn is None:return None
    if (member.injury.dead or any(member.injury.conditions.has(c) for c in (Condition.DEFENCELESS,Condition.DEAFENED))
            or _pc_recover_needed(member,unarmed_available=body_help)
            or not body_help and usable_weapon_hand(member) is None):return None
    from towr.domain.pc_medical_models import effective_medical_injury
    ally=effective_medical_injury(state,beneficiary)
    from towr.domain.pc_allies_in_arms_models import allies_in_arms_choice
    if (injury_is_defeated(ally) or ally.conditions.has(Condition.DEFENCELESS)
            or ally.conditions.has(Condition.DRAINED) and allies_in_arms_choice(state,actor,beneficiary)[0] is None):return None
    if strategy.target is PcHelpTarget.ATTACK:
        order=help_side_order(state,actor)
        if order.index(actor)>=order.index(beneficiary):return None
        if beneficiary in (*state.round_state.completed_turn_entity_ids,*state.round_state.excluded_turn_entity_ids):return None
        selected=help_recipient_attack(state,beneficiary,planned_choice=planned_choice)
        if selected is None or selected[1] is not strategy.skill:return None
        view,skill,item,planned_choice=selected
        if strategy.skill is Skill.SHOOTING:
            from towr.domain.pc_melee_models import PC_RANGED_WEAPONS
            from towr.domain.pc_backup_weapon_models import pc_active_weapon
            if (pc_active_weapon(state,actor) not in PC_RANGED_WEAPONS
                    or member.ranged is None or not ranged_weapon_is_loaded(member.ranged)):return None
            from towr.domain.pc_short_opening_models import pc_has_close_enemy
            from towr.domain.pc_weapon_models import pc_weapon_allows_close_shooting
            if not pc_weapon_allows_close_shooting(pc_active_weapon(state,actor)) and pc_has_close_enemy(state,actor):return None
        elif strategy.skill is Skill.THROWING:
            from towr.domain.pc_melee_models import PC_THROWING_WEAPONS
            from towr.domain.pc_backup_weapon_models import pc_active_weapon
            if pc_active_weapon(state,actor) not in PC_THROWING_WEAPONS:return None
        if strategy.skill in (Skill.SHOOTING,Skill.THROWING) and planned_choice is not None:
            from towr.domain.pc_battlefield_movement_models import pc_battlefield_attack_available
            if not pc_battlefield_attack_available(state,actor,planned_choice.target_id):return None
    else:
        incoming=pc_help_incoming_actor(state,strategy)
        if incoming is None:return None
        from towr.domain.pc_melee_result_models import pc_melee_action_id
        skill,_=help_recipient_protection(state,beneficiary,incoming,pc_melee_action_id(state,incoming)+':protection')
        if skill is not strategy.skill:return None
    return beneficiary


def pc_help_incoming_actor(state,strategy=None):
    """First actual opposing NPC intending this recipient, never a friendly NPC."""
    strategy=strategy or pc_selected_help_policy(state)
    if strategy is None:return None
    from towr.domain.pc_actor_models import pc_opponent_ids
    from towr.domain.pc_battlefield_movement_models import _enemies,pc_battlefield_attack_available
    opponents=pc_opponent_ids(state,strategy.beneficiary_id)
    unavailable=(*state.round_state.completed_turn_entity_ids,*state.round_state.excluded_turn_entity_ids)
    from towr.domain.pc_npc_ranged_models import pc_npc_ranged_weapon
    for incoming in state.source.npc_activation_order:
        if incoming not in opponents or incoming in unavailable:continue
        weapon=pc_npc_ranged_weapon(state,incoming)
        if weapon is not None and not ranged_weapon_is_loaded(weapon):continue
        targets=_enemies(state,incoming)
        if not targets:continue
        predicted=next((target for target in targets if state.battlefield is not None
            and pc_battlefield_attack_available(state,incoming,target)),targets[0])
        if predicted==strategy.beneficiary_id:return incoming
    return None


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
    test=_pc_test(state,actor,action_id+':help:test',skill,weapon_use=pc_help_weapon_use(state))
    if skill is Skill.SHOOTING:
        from towr.domain.pc_ranged_models import pc_repeater_attack_modifiers
        test=replace(test,dice_modifiers=(*test.dice_modifiers,*pc_repeater_attack_modifiers(state,actor)))
    return HelpActionExecutionRequest(action_id+':help:execute',state.round_state,actor,
        state.participant(actor).injury.conditions,beneficiary,
        intended,1,test,skill,skill)


def pc_help_weapon_use(state):
    from towr.domain.pc_generated_talents import pending_wild_attack
    from towr.domain.pc_weapon_inventory import pc_attack_weapon_use, pc_protection_weapon_use
    from towr.domain.pc_melee_result_models import pc_attack_skill
    actor = state.round_state.active_turn.actor_id
    paid = pending_wild_attack(state)
    if paid is not None:
        return paid.help_weapon_use
    strategy = pc_selected_help_policy(state)
    if strategy is None:
        return None
    if strategy.skill is Skill.DEFENCE:
        return pc_protection_weapon_use(state.participant(actor), strategy.skill)
    if strategy.skill is Skill.BRAWN:
        from towr.domain.weapon_use_models import build_weapon_use
        from towr.domain.pc_weapon_inventory import _usable_pc_grips
        member=state.participant(actor)
        return build_weapon_use(actor,member.weapon_inventory,None,usable_hands=_usable_pc_grips(member))
    return pc_attack_weapon_use(state, actor) if strategy.skill is pc_attack_skill(state, actor) else None


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
            actual=(pc_active_weapon_item_id(state,actor) if actor in state.source.pc_activation_order else
                state.enemy(actor).state.weapon_inventory.active_item_id)
            if proof.beneficiary_weapon_item_id!=actual:
                continue
        request = HelpBonusApplicationRequest(test.id+':apply:'+execution.request_id,
            execution,actor,skill,test)
        updated,modifier = _expected_help_application(request)
        application = HelpBonusApplicationResult(request.id,request.rule_id,request,updated,
            modifier,(request.rule_id,execution.rule_id))
        applications.append(application)
        test = updated
    from towr.domain.pc_generated_talents import actor_conditions
    if actor_conditions(state,actor).has(Condition.DRAINED):
        test = replace(test,dice_modifiers=tuple(modifier for modifier in test.dice_modifiers
            if modifier.amount <= 0))
    return test,tuple(applications)


def pc_attack_help_applications(state, attack, *, mount_attack=False,weapon_intent=None):
    """Exact ordinary Help chains on both sides of this Attack, before Fate."""
    if weapon_intent is None:
        from towr.domain.pc_weapon_intent_models import build_pc_attack_weapon_intent
        weapon_intent=build_pc_attack_weapon_intent(state)
    active=state.round_state.active_turn.actor_id
    pc_attacks=active in state.source.pc_activation_order
    pc_actor=active if pc_attacks else weapon_intent.target_id
    npc_actor=weapon_intent.target_id if pc_attacks else active
    from towr.domain.pc_melee_result_models import pc_attack_skill,pc_selected_npc_attack_profile
    pairs=[]
    if pc_attacks and not mount_attack:
        pairs.append((pc_actor,weapon_intent.attack_skill,attack.attacker_test))
    elif not pc_attacks and attack.defender_test is not None:
        pairs.append((pc_actor,weapon_intent.protection_skill,attack.defender_test))
    if pc_attacks and attack.defender_test is not None:
        pairs.append((npc_actor,weapon_intent.protection_skill,attack.defender_test))
    elif not pc_attacks and not mount_attack:
        pairs.append((npc_actor,weapon_intent.attack_skill,attack.attacker_test))
    applications=[]
    for actor,skill,test in pairs:
        base=replace(test,dice_modifiers=tuple(modifier for modifier in test.dice_modifiers
            if modifier.rule_id!=HELP_BONUS_RULE_ID))
        applications.extend(build_pc_test_help(state,actor,skill,base)[1])
    return tuple(applications)


def pc_help_beneficiary_weapon(state,strategy):
    """Bind automatic Help to the concrete item of its promised future Test."""
    if strategy is None:
        return None
    target=strategy.beneficiary_id
    from towr.domain.pc_magic_weapon_models import actor_inventory
    inventory=actor_inventory(state,target)
    if inventory is None or strategy.skill in (Skill.ATHLETICS,Skill.ENDURANCE):return None
    if strategy.target is PcHelpTarget.ATTACK:
        selected=help_recipient_attack(state,target)
        if selected is not None:return selected[2]
    return inventory.active_item_id
