"""Ordinary, rolled Help for generated NPCs; no named free-Help substitution."""
from towr.domain.injury_models import injury_is_defeated
from dataclasses import dataclass,replace

from towr.domain.condition_models import Condition
from towr.domain.help_models import HelpActionExecutionRequest
from towr.domain.pc_melee_models import PcHelpPolicy,PcHelpTarget
from towr.domain.test_models import Skill,InlineProfile,TestRequest,QualityModifier,TestQuality


@dataclass(frozen=True,slots=True)
class NpcNormalHelpSelection:
    policy:PcHelpPolicy
    beneficiary_test_id:str
    beneficiary_weapon_item_id:str|None
    utility:float


def _conditions(state,actor):
    from towr.domain.pc_medical_models import effective_medical_injury
    return effective_medical_injury(state,actor).conditions


def npc_help_weapon_use(state,actor,skill):
    from towr.domain.pc_npc_weapon_inventory import npc_attack_weapon_use,npc_protection_weapon_use
    from towr.domain.pc_melee_result_models import pc_selected_npc_attack_profile
    if skill in (Skill.DEFENCE,Skill.MELEE):
        if skill is Skill.DEFENCE or pc_selected_npc_attack_profile(state,actor).skill is not skill:
            return npc_protection_weapon_use(state,actor,skill)
    if pc_selected_npc_attack_profile(state,actor).skill is skill:
        return npc_attack_weapon_use(state,actor)
    return None


def npc_help_test(state,actor,test_id,skill):
    from towr.domain.generated_npc_models import generated_npc_combat_ratings
    from towr.domain.pc_armour_models import actor_armour_test_modifiers,actor_armour_quality_modifiers
    from towr.domain.pc_magic_models import magic_test_modifiers
    from towr.domain.weapon_effect_preparation import weapon_test_modifiers
    source=state.enemy(actor).definition.generated_components
    if source is None:
        raise ValueError('ordinary NPC Help requires its complete generated Skill source')
    ws,melee,defence=generated_npc_combat_ratings(source)
    profiles={Skill.MELEE:(ws,melee),Skill.DEFENCE:(ws,defence),
        Skill.ATHLETICS:(source.agility,source.athletics),Skill.ENDURANCE:(source.toughness,source.endurance),
        Skill.BRAWN:(source.strength,source.brawn),
        Skill.THROWING:(source.ballistic_skill if source.ranged is None else source.ranged.ballistic_skill,source.throwing),
        Skill.SHOOTING:(None,None) if source.ranged is None else (source.ranged.ballistic_skill,source.ranged.shooting)}
    values=profiles.get(skill)
    if values is None or any(value is None for value in values):
        raise ValueError('ordinary NPC Help lacks the actual requested Skill')
    conditions=_conditions(state,actor)
    use=npc_help_weapon_use(state,actor,skill)
    modifiers=(() if use is None else weapon_test_modifiers(use,conditions,
        talents=source.talents).modifiers)
    dice,qualities=magic_test_modifiers(state,actor,skill)
    from towr.domain.pc_npc_champion_models import npc_champion_test_modifiers
    body_dice,body_qualities=npc_champion_test_modifiers(state,actor,skill)
    modifiers=(*modifiers,*actor_armour_test_modifiers(state,actor,skill),*dice,*body_dice)
    if conditions.has(Condition.DRAINED):
        modifiers=tuple(mod for mod in modifiers if mod.amount<=0)
    sight=((QualityModifier('RULE-HEALTH-008:blinded',TestQuality.GRIM),)
        if skill is not Skill.ENDURANCE and conditions.has(Condition.BLINDED) else ())
    armour_qualities=(actor_armour_quality_modifiers(state,actor)
        if skill in (Skill.MELEE,Skill.SHOOTING,Skill.THROWING,Skill.BRAWN) else ())
    return TestRequest(test_id,InlineProfile(*values),modifiers,
        tuple(dict.fromkeys((*qualities,*armour_qualities,*sight,*body_qualities))))


def _can_help_skill(state,actor,skill):
    from towr.domain.pc_melee_result_models import pc_selected_npc_attack_profile
    if skill in (Skill.SHOOTING,Skill.THROWING) and pc_selected_npc_attack_profile(state,actor).skill is not skill:
        return False
    if skill in (Skill.SHOOTING,Skill.THROWING) and npc_help_weapon_use(state,actor,skill) is None:
        return False
    if skill is Skill.SHOOTING:
        from towr.domain.pc_npc_ranged_models import pc_npc_ranged_weapon
        from towr.domain.reload_models import ranged_weapon_is_loaded
        weapon=pc_npc_ranged_weapon(state,actor)
        if weapon is None or not ranged_weapon_is_loaded(weapon):return False
        from towr.domain.pc_weapon_models import pc_weapon_allows_close_shooting
        from towr.domain.pc_short_opening_models import pc_enemy_range
        from towr.domain.ranged_weapon_profiles import RangedWeaponRange
        from towr.domain.pc_melee_models import PcMeleeWeapon
        from towr.domain.pc_actor_models import pc_opponent_ids
        if (not pc_weapon_allows_close_shooting(PcMeleeWeapon(weapon.weapon_id.value))
                and any(pc_enemy_range(state,other,actor) is RangedWeaponRange.CLOSE
                    for other in pc_opponent_ids(state,actor))):
            return False
    if skill in (Skill.MELEE,Skill.DEFENCE) and npc_help_weapon_use(state,actor,skill) is None:
        return False
    try:npc_help_test(state,actor,'tactics:npc-help',skill)
    except ValueError:return False
    return True


def _available(state,actor):
    from towr.domain.pc_actor_models import pc_actor_injury
    if actor not in (*state.source.pc_activation_order,*state.source.npc_activation_order):return False
    if actor not in state.source.pc_activation_order and state.enemy(actor).definition.generated_components is None:return False
    injury=pc_actor_injury(state,actor)
    return (not injury_is_defeated(injury) and actor not in state.exited_npc_ids
        and not any(_conditions(state,actor).has(c) for c in (Condition.BROKEN,Condition.DEFENCELESS)))


def npc_normal_help_choice(state,actor=None):
    """Compare same-side real future Tests with one's actual Attack.

    Forward order prevents Help chains. Role selects Test/resource owners;
    side selects allies and enemies, including original allied NPCs.
    """
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    from towr.domain.pc_npc_weapon_inventory import _utility
    from towr.domain.pc_allies_in_arms_models import allies_in_arms_choice
    from towr.domain.pc_tactical_models import _distribution
    from towr.domain.pc_help_models import help_side_order,help_recipient_attack,help_recipient_protection
    from towr.domain.pc_actor_models import pc_actor_side,pc_opponent_ids
    from towr.domain.pc_battlefield_movement_models import _enemies,pc_battlefield_attack_available
    from towr.domain.pc_ranged_advice import pc_attack_value
    from towr.domain.pc_mount_attack_models import pc_uses_mount_attack
    from towr.domain.turn_models import CombatSide
    turn=state.round_state.active_turn
    if actor is None:actor=None if turn is None else turn.actor_id
    if actor not in state.source.npc_activation_order:return None
    order=help_side_order(state,actor)
    if sum(_available(state,ally) for ally in order)<2:return None
    unavailable=(*state.round_state.completed_turn_entity_ids,*state.round_state.excluded_turn_entity_ids)
    plans={};attack_values={}
    def attack_value(owner,extra=0,view=None):
        selected=state if view is None else view
        key=owner,extra,id(selected)
        if key not in attack_values:
            attack_values[key]=(pc_attack_value(selected,owner,extra=extra)[0]
                if owner in state.source.pc_activation_order else _utility(selected,owner,help_successes=extra))
        return attack_values[key]
    def incoming_prediction(owner):
        if owner in state.source.pc_activation_order:return pc_attack_value(state,owner)
        targets=_enemies(state,owner)
        predicted=next((target for target in targets if state.battlefield is not None
            and pc_battlefield_attack_available(state,owner,target)),targets[0] if targets else None)
        return attack_value(owner),predicted
    def plan(helper):
        if helper in plans:return plans[helper]
        plans[helper]=None
        if not _available(state,helper) or helper in unavailable or _conditions(state,helper).has(Condition.DEAFENED):return None
        best=None;own=max(0.,attack_value(helper));helper_index=order.index(helper)
        for beneficiary in order:
            if beneficiary==helper or not _available(state,beneficiary):continue
            removal,removal_value=allies_in_arms_choice(state,helper,beneficiary)
            for kind in (PcHelpTarget.ATTACK,PcHelpTarget.FIRST_INCOMING_PROTECTION):
                if kind is PcHelpTarget.ATTACK:
                    if (beneficiary in unavailable or order.index(beneficiary)<=helper_index
                            or beneficiary in state.source.npc_activation_order and plan(beneficiary) is not None
                            or pc_uses_mount_attack(state,beneficiary)):continue
                    selected=help_recipient_attack(state,beneficiary)
                    if selected is None:continue
                    view,skill,item,_=selected
                    intended=pc_melee_action_id(state,beneficiary)+':attack'
                    before=attack_value(beneficiary,view=view)
                    benefit=lambda successes,beneficiary=beneficiary,before=before,view=view:max(0.,attack_value(beneficiary,successes,view)-before)
                else:
                    opponents=pc_opponent_ids(state,beneficiary)
                    opposing_order=(state.source.enemy_activation_order if pc_actor_side(state,beneficiary)
                        is CombatSide.PLAYERS_AND_ALLIES else state.source.player_activation_order)
                    incoming=next((other for other in opposing_order if other in opponents and other not in unavailable),None)
                    next_round=incoming is None
                    if incoming is None:incoming=next((other for other in opposing_order if other in opponents),None)
                    if incoming is None or next_round and state.round_state.round_number>=state.source.max_rounds:continue
                    before,predicted=incoming_prediction(incoming)
                    if predicted!=beneficiary:continue
                    intended=pc_melee_action_id(state,incoming,
                        round_number=state.round_state.round_number+int(next_round))+':protection'
                    skill,test=help_recipient_protection(state,beneficiary,incoming,intended)
                    from towr.domain.pc_magic_weapon_models import actor_inventory
                    inventory=actor_inventory(state,beneficiary)
                    item=(inventory.active_item_id if inventory is not None and skill in (Skill.DEFENCE,Skill.MELEE) else None)
                    base_mean=sum(i*p for i,p in enumerate(_distribution(test)))
                    from towr.domain.test_models import _expected_initial_roll_parameters
                    remaining=max(0,min(10,test.profile.maximum_dice)-_expected_initial_roll_parameters(test)[5])
                    benefit=lambda successes,before=before,remaining=remaining,test=test,base_mean=base_mean:min(before,
                        min(successes,remaining)*test.profile.threshold/10/(1+base_mean))
                if not _can_help_skill(state,helper,skill):continue
                if _conditions(state,beneficiary).has(Condition.DRAINED):
                    if removal is None:continue
                    benefit=lambda successes:0.
                help_test=npc_help_test(state,helper,'tactics:npc-help',skill)
                value=sum(probability*benefit(successes) for successes,probability in enumerate(_distribution(help_test)))+removal_value
                candidate=NpcNormalHelpSelection(PcHelpPolicy(beneficiary,kind,skill),intended,item,value)
                if value>own+1e-12 and (best is None or value>best.utility+1e-12):best=candidate
        plans[helper]=best
        return best
    return plan(actor)


def build_npc_normal_help_action(state):
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    choice=npc_normal_help_choice(state)
    if choice is None:raise ValueError('NPC has no selected ordinary Help')
    actor=state.round_state.active_turn.actor_id
    action_id=pc_melee_action_id(state,actor)
    return HelpActionExecutionRequest(action_id+':help:execute',state.round_state,actor,
        _conditions(state,actor),choice.policy.beneficiary_id,choice.beneficiary_test_id,1,
        npc_help_test(state,actor,action_id+':help:test',choice.policy.skill),
        choice.policy.skill,choice.policy.skill)


def complete_npc_ranged_help(state,request,execution):
    if request.help_skill is not Skill.SHOOTING:return None
    from towr.domain.pc_npc_ranged_models import pc_npc_ranged_weapon
    from towr.domain.pc_ranged_models import PcRangedHelpUseProof
    weapon=pc_npc_ranged_weapon(state,request.actor_id)
    return PcRangedHelpUseProof(request.actor_id,request.id,request.help_test,execution,weapon,weapon,False,None)
