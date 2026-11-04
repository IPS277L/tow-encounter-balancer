"""Bounded weapon-assisted Help for a named allied Attack or Protection Test."""
from dataclasses import replace

from towr.domain.condition_models import Condition
from towr.domain.help_models import (
    HELP_BONUS_RULE_ID, HelpActionExecutionRequest, HelpBonusApplicationRequest,
    HelpBonusApplicationResult, _expected_help_application,
)
from towr.domain.pc_heavy_wound_models import usable_weapon_hand
from towr.domain.pc_melee_models import PcHelpTarget
from towr.domain.test_models import Skill


def pc_help_beneficiary(state):
    from towr.domain.pc_melee_result_models import _pc_recover_needed
    actor = state.round_state.active_turn.actor_id
    if actor not in state.source.pc_activation_order:
        return None
    participant = state.source.participant(actor)
    strategy = participant.help_policy
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
    if strategy.target is PcHelpTarget.MELEE_ATTACK:
        if (_pc_recover_needed(ally) or strategy.beneficiary_id in (
                *state.round_state.completed_turn_entity_ids,*state.round_state.excluded_turn_entity_ids)):
            return None
    else:
        skill = Skill.DEFENCE if usable_weapon_hand(ally) is not None else Skill.ATHLETICS
        if skill is not strategy.protection_skill or pc_help_incoming_actor(state) is None:
            return None
    return strategy.beneficiary_id


def pc_help_incoming_actor(state):
    """Select the first current live NPC, without anticipating future PC outcomes."""
    actor = state.round_state.active_turn.actor_id
    strategy = state.source.participant(actor).help_policy
    target = next((pc for pc in state.source.enemy_target_priority
        if not state.participant(pc).injury.dead),None)
    if target != strategy.beneficiary_id:
        return None
    unavailable = (*state.round_state.completed_turn_entity_ids,*state.round_state.excluded_turn_entity_ids)
    return next((enemy for enemy in state.source.enemy_activation_order
        if not state.enemy(enemy).state.injury.defeated and enemy not in unavailable),None)


def build_pc_help_action(state):
    from towr.domain.pc_melee_result_models import pc_melee_action_id, _pc_test
    beneficiary = pc_help_beneficiary(state)
    if beneficiary is None:
        raise ValueError('the explicit Help strategy cannot select an eligible ally')
    actor = state.round_state.active_turn.actor_id
    strategy = state.source.participant(actor).help_policy
    action_id = pc_melee_action_id(state,actor)
    skill = Skill.MELEE if strategy.target is PcHelpTarget.MELEE_ATTACK else strategy.protection_skill
    intended = (pc_melee_action_id(state,beneficiary)+':attack' if skill is Skill.MELEE else
        pc_melee_action_id(state,pc_help_incoming_actor(state))+':protection')
    return HelpActionExecutionRequest(action_id+':help:execute',state.round_state,actor,
        state.participant(actor).injury.conditions,beneficiary,
        intended,1,_pc_test(state,actor,action_id+':help:test',skill),skill,skill)


def build_pc_attack_help(state, test):
    return build_pc_test_help(state,state.round_state.active_turn.actor_id,Skill.MELEE,test)


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
        skill,test = Skill.MELEE,attack.attacker_test
    else:
        if attack.defender_test is None:
            return ()
        actor = next(pc for pc in state.source.enemy_target_priority if not state.participant(pc).injury.dead)
        skill = Skill.DEFENCE if usable_weapon_hand(state.participant(actor)) is not None else Skill.ATHLETICS
        test = attack.defender_test
    base = replace(test,dice_modifiers=tuple(modifier
        for modifier in test.dice_modifiers
        if modifier.rule_id != HELP_BONUS_RULE_ID))
    return build_pc_test_help(state,actor,skill,base)[1]
