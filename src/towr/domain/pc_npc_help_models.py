"""Named physical NPC Help for a later Melee Test, without an automatic AI choice."""
from dataclasses import dataclass,replace

from towr.domain.automatic_help_models import AutomaticHelpEffectKind
from towr.domain.condition_models import Condition
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.test_models import Skill


PEASANT_HELP_RULE_ID='RULE-PROFILE-TALABEC-001:torches-and-pitchforks'
MILITIA_HELP_RULE_ID='RULE-PROFILE-IMPERIAL-001:strength-in-numbers'
HORDE_HELP_RULE_ID='RULE-PROFILE-GREENSKIN-001:horde'
WAAAGH_HELP_RULE_ID='RULE-PROFILE-GREENSKIN-004:power-of-the-waaagh'
CULTIST_HELP_RULE_ID='RULE-PROFILE-IMPERIAL-005:torches-and-pitchforks'
_HELP_RULE_IDS=(PEASANT_HELP_RULE_ID,MILITIA_HELP_RULE_ID,HORDE_HELP_RULE_ID,WAAAGH_HELP_RULE_ID,
    CULTIST_HELP_RULE_ID)


@dataclass(frozen=True,slots=True)
class PcNpcHelpPolicy:
    helper_id: str
    beneficiary_id: str

    def __post_init__(self):
        for value in (self.helper_id,self.beneficiary_id):
            if type(value) is not str or not value.strip():
                raise TypeError('NPC Help actor IDs must be exact nonempty strings')
        if self.helper_id==self.beneficiary_id:
            raise ValueError('NPC cannot Help itself')


def pc_npc_automatic_help_rule(definition) -> str | None:
    validate_pc_book_npc_definition(definition)
    if definition.id=='pc-book-npc:empire_peasant':return PEASANT_HELP_RULE_ID
    if definition.id=='pc-book-npc:free_company_militia_blades':return MILITIA_HELP_RULE_ID
    if definition.id=='pc-book-npc:sigmarite_cultist_warhammer':return CULTIST_HELP_RULE_ID
    if definition.id in ('pc-book-npc:goblin_warrior_spear','pc-book-npc:night_goblin_spear'):
        return HORDE_HELP_RULE_ID
    if definition.id in ('pc-book-npc:orc_boy_choppas','pc-book-npc:big_un_choppas',
            'pc-book-npc:orc_boy_spear_shield','pc-book-npc:big_un_spear_shield',
            'pc-book-npc:orc_boy_spear','pc-book-npc:big_un_spear'):
        return WAAAGH_HELP_RULE_ID
    return None


def pc_npc_automatic_help_effect(definition) -> AutomaticHelpEffectKind:
    rule=pc_npc_automatic_help_rule(definition)
    if rule is None:
        raise ValueError('NPC has no admitted automatic Help ability')
    return (AutomaticHelpEffectKind.FREE_SUCCESS if rule==WAAAGH_HELP_RULE_ID
        else AutomaticHelpEffectKind.BONUS_DIE_BEYOND_CAP)


def validate_pc_npc_help_policies(source) -> None:
    if type(source.npc_help_policies) is not tuple:
        raise TypeError('NPC Help policies require a canonical tuple')
    helpers=[]
    recipients=[]
    for policy in source.npc_help_policies:
        if type(policy) is not PcNpcHelpPolicy:
            raise TypeError('NPC Help policy must be its exact typed pair')
        replace(policy)
        if (policy.helper_id not in source.enemy_activation_order
                or policy.beneficiary_id not in source.enemy_activation_order):
            raise ValueError('NPC Help must name two opposition actors in the source')
        if pc_npc_automatic_help_rule(source.enemy(policy.helper_id).definition) is None:
            raise ValueError('NPC Help requires an admitted canonical automatic Help ability')
        if source.enemy_activation_order.index(policy.helper_id)>=source.enemy_activation_order.index(policy.beneficiary_id):
            raise ValueError('NPC Help recipient must activate later in the same round')
        helpers.append(policy.helper_id)
        recipients.append(policy.beneficiary_id)
    if len(set(helpers))!=len(helpers):
        raise ValueError('each NPC helper requires one named recipient')
    if set(helpers)&set(recipients):
        raise ValueError('NPC Help chains are outside this policy')


def pc_npc_help_beneficiary(state) -> str | None:
    turn=state.round_state.active_turn
    if turn is None:return None
    actor=turn.actor_id
    policy=next((p for p in state.source.npc_help_policies if p.helper_id==actor),None)
    if policy is None:return None
    helper=state.enemy(actor).state.injury
    if helper.defeated or actor in state.exited_npc_ids or any(helper.conditions.has(c) for c in
            (Condition.DEAFENED,Condition.DEFENCELESS,Condition.BROKEN)):
        return None
    recipient=state.enemy(policy.beneficiary_id).state.injury
    unavailable=(*state.round_state.completed_turn_entity_ids,*state.round_state.excluded_turn_entity_ids,
        *state.exited_npc_ids)
    if (recipient.defeated or policy.beneficiary_id in unavailable
            or any(recipient.conditions.has(c) for c in (Condition.DEFENCELESS,Condition.BROKEN))):
        return None
    from towr.domain.pc_flagellant_models import pc_flagellant_recover_selected
    if pc_flagellant_recover_selected(state, policy.beneficiary_id):
        return None
    if (recipient.conditions.has(Condition.DRAINED)
            and pc_npc_automatic_help_effect(state.enemy(actor).definition)
                is AutomaticHelpEffectKind.BONUS_DIE_BEYOND_CAP):
        return None
    return policy.beneficiary_id


def build_pc_npc_help_action(state):
    from towr.domain.automatic_help_models import AutomaticHelpActionRequest
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    beneficiary=pc_npc_help_beneficiary(state)
    if beneficiary is None:
        raise ValueError('the named NPC Help policy has no eligible future attacker')
    actor=state.round_state.active_turn.actor_id
    return AutomaticHelpActionRequest(pc_melee_action_id(state,actor)+':npc-help:execute',state.round_state,
        actor,state.enemy(actor).state.injury.conditions,beneficiary,
        pc_melee_action_id(state,beneficiary)+':attack',1,Skill.MELEE,
        pc_npc_automatic_help_rule(state.enemy(actor).definition),
        pc_npc_automatic_help_effect(state.enemy(actor).definition))


def build_pc_npc_attack_help(state,actor,test):
    if not state.source.npc_help_policies:return test,()
    from towr.domain.pc_melee_result_models import PcNpcHelpProof
    from towr.domain.automatic_help_models import (AutomaticHelpBonusApplicationRequest,
        AutomaticHelpBonusApplicationResult,_expected_automatic_help_application)
    applications=[]
    for proof in state.history:
        if type(proof) is not PcNpcHelpProof:continue
        execution=proof.execution
        bonus=execution.bonus
        if (bonus.beneficiary_id!=actor or bonus.beneficiary_test_id!=test.id
                or bonus.beneficiary_skill is not Skill.MELEE):continue
        request=AutomaticHelpBonusApplicationRequest(test.id+':apply:'+execution.request_id,
            execution,actor,Skill.MELEE,test)
        updated,modifier=_expected_automatic_help_application(request)
        application=AutomaticHelpBonusApplicationResult(request.id,request,updated,modifier,
            (execution.source_request.rule_id,bonus.rule_id))
        applications.append(application)
        test=updated
    if state.enemy(actor).state.injury.conditions.has(Condition.DRAINED):
        test=replace(test,dice_modifiers=tuple(m for m in test.dice_modifiers if m.amount<=0))
    return test,tuple(applications)


def pc_npc_attack_help_applications(state,attack):
    actor=state.round_state.active_turn.actor_id
    if actor not in state.source.enemy_activation_order or not state.source.npc_help_policies:return ()
    test=attack.attacker_test
    base=replace(test,dice_modifiers=tuple(m for m in test.dice_modifiers
        if m.rule_id not in _HELP_RULE_IDS),success_modifiers=tuple(m for m in test.success_modifiers
        if m.rule_id not in _HELP_RULE_IDS))
    return build_pc_npc_attack_help(state,actor,base)[1]
