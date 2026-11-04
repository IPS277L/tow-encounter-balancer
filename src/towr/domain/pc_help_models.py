"""Bounded weapon-assisted Help for an ally's named upcoming melee Attack."""
from dataclasses import replace

from towr.domain.condition_models import Condition
from towr.domain.help_models import (
    HELP_BONUS_RULE_ID, HelpActionExecutionRequest, HelpBonusApplicationRequest,
    HelpBonusApplicationResult, _expected_help_application,
)
from towr.domain.pc_heavy_wound_models import usable_weapon_hand
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
            or ally.injury.conditions.has(Condition.DRAINED) or _pc_recover_needed(ally)
            or strategy.beneficiary_id in (*state.round_state.completed_turn_entity_ids,
                *state.round_state.excluded_turn_entity_ids)):
        return None
    return strategy.beneficiary_id


def build_pc_help_action(state):
    from towr.domain.pc_melee_result_models import pc_melee_action_id, _pc_test
    beneficiary = pc_help_beneficiary(state)
    if beneficiary is None:
        raise ValueError('the explicit Help strategy cannot select an eligible ally')
    actor = state.round_state.active_turn.actor_id
    action_id = pc_melee_action_id(state,actor)
    return HelpActionExecutionRequest(action_id+':help:execute',state.round_state,actor,
        state.participant(actor).injury.conditions,beneficiary,
        pc_melee_action_id(state,beneficiary)+':attack',1,
        _pc_test(state,actor,action_id+':help:test',Skill.MELEE),Skill.MELEE,Skill.MELEE)


def build_pc_attack_help(state, test):
    """Retain every exact intended-Test application, including zero/capped dice."""
    from towr.domain.pc_melee_result_models import PcHelpProof
    actor = state.round_state.active_turn.actor_id
    applications = []
    for proof in state.history:
        if not isinstance(proof,PcHelpProof):
            continue
        execution = proof.execution
        if execution.bonus.beneficiary_id != actor or execution.bonus.beneficiary_test_id != test.id:
            continue
        request = HelpBonusApplicationRequest(test.id+':apply:'+execution.request_id,
            execution,actor,Skill.MELEE,test)
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
    if state.round_state.active_turn.actor_id not in state.source.pc_activation_order:
        return ()
    base = replace(attack.attacker_test,dice_modifiers=tuple(modifier
        for modifier in attack.attacker_test.dice_modifiers
        if modifier.rule_id != HELP_BONUS_RULE_ID))
    return build_pc_attack_help(state,base)[1]
