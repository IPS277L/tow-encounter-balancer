"""Finite automatic PC weapon and reload advice (ADR-0125).

Prepared views are comparisons only. No rolls, proof receipts or real Fate spends
are created here. A finite Fate budget follows every forecast Test branch.
"""
from dataclasses import replace
from functools import lru_cache
from collections import defaultdict

from towr.domain.condition_models import Condition
from towr.domain.test_models import Skill,TestRequest,DiceModifier,TestQuality,_expected_initial_roll_parameters
from towr.domain.turn_models import CombatActionKind
from towr.domain.ranged_weapon_profiles import (RangedWeaponId,ranged_weapon_combat_profile,
    ranged_weapon_reload_profile,RangedReloadTrigger,REPEATER_SHOOTING_BONUS_RULE_ID)


def initial_fate_budget(state,actor):
    fate=state.participant(actor).fate
    return fate.remaining_spends,fate.lucky_free_spend_available


def pc_fate_branches(state,actor,skill,request,budget):
    """Exact (successes, remaining-budget, probability) for one future Test."""
    from towr.domain.pc_tactical_models import _binomial,_distribution
    from towr.domain.pc_melee_models import PcFatePolicy
    source=state.source.participant(actor);policy=source.glorious_policy
    grim=any(m.quality is TestQuality.GRIM for m in request.quality_modifiers)
    glorious=any(m.quality is TestQuality.GLORIOUS for m in request.quality_modifiers)
    if (source.fate_policy is not PcFatePolicy.CONFIGURED or policy is None or skill not in policy.skills
            or glorious or request.reroll_locks or not (budget[0] or budget[1])):
        return tuple((successes,budget,chance) for successes,chance in enumerate(_distribution(request)) if chance)
    parameters=_expected_initial_roll_parameters(request);dice,threshold=parameters[5:7]
    delta=sum(m.amount for m in request.success_modifiers)
    values=defaultdict(float)
    for successes,chance in enumerate(_binomial(dice,threshold*10)):
        useful=successes>0 if grim else successes<dice
        cost=0 if budget[1] else 1
        spend=(useful and successes<=policy.maximum_initial_successes
            and budget[0]-cost>=policy.minimum_remaining_spends)
        after=(budget[0]-cost,False) if spend else budget
        if grim:
            outcomes=((successes,1.0),) if spend else enumerate(_binomial(successes,threshold*10))
        elif spend:
            outcomes=((successes+n,p) for n,p in enumerate(_binomial(dice-successes,threshold*10)))
        else:outcomes=((successes,1.0),)
        for final,probability in outcomes:
            values[max(0,final+delta),after]+=chance*probability
    return tuple((successes,after,chance) for (successes,after),chance in values.items() if chance)


def pc_attack_value(state,actor,*,extra=0,enhancement=None,wild=False,bonus=False,target_id=None,allow_empty=False):
    """Expected immediate actual prepared Attack, including its best target."""
    from towr.domain.pc_tactical_models import _distribution,_impact_value
    from towr.domain.pc_melee_models import PC_RANGED_WEAPONS
    from towr.domain.pc_melee_result_models import _pc_test,pc_melee_action_id
    from towr.domain.pc_backup_weapon_models import pc_active_weapon
    from towr.domain.pc_potion_models import pc_effective_definition
    from towr.domain.pc_help_models import build_pc_test_help
    from towr.domain.pc_weapon_models import pc_weapon_damage,pc_weapon_damage_modifiers,pc_weapon_attack_modifiers
    from towr.domain.pc_generated_equipment import npc_protection_test
    from towr.domain.pc_npc_ability_models import pc_npc_allows_enemy_higher_ground
    from towr.domain.pc_talent_advice import pc_test_distribution,pc_wild_test_variant
    from towr.domain.pc_generated_talents import has_generated_talent
    from towr.domain.generated_npc_models import GeneratedTalent
    member=state.participant(actor);weapon=pc_active_weapon(state,actor)
    shooting=weapon in PC_RANGED_WEAPONS;skill=Skill.SHOOTING if shooting else Skill.MELEE
    pc=pc_effective_definition(state,actor)
    if enhancement is not None:pc=replace(pc,**{enhancement:getattr(pc,enhancement)+1})
    from towr.domain.pc_heavy_wound_models import usable_weapon_hand
    if usable_weapon_hand(member) is None:return 0.0,None
    if shooting and (member.ranged is None or (not member.ranged.loaded and not allow_empty)):return 0.0,None
    best=(0.0,None)
    targets=(target_id,) if target_id is not None else state.source.participant(actor).target_priority
    for target in targets:
        enemy=state.enemy(target)
        if enemy.state.injury.defeated or target in state.exited_npc_ids:continue
        modifiers=[]
        if shooting:
            if enemy.state.injury.conditions.has(Condition.PRONE):modifiers.append(DiceModifier('RULE-HEALTH-008:prone-shooting',-1))
            if bonus and not member.injury.conditions.has(Condition.DRAINED):
                modifiers.append(ranged_weapon_reload_profile(RangedWeaponId(weapon.value)).optional_bonus_modifier())
        else:
            if state.source.facts.outnumbering_bonus_approved and sum(not m.injury.conditions.has(Condition.DEFENCELESS) for m in state.live_party)>sum(not e.state.injury.conditions.has(Condition.DEFENCELESS) for e in state.live_enemies):
                modifiers.append(DiceModifier('RULE-COMBAT-007:outnumbering',1))
            if enemy.state.injury.conditions.has(Condition.PRONE) and pc_npc_allows_enemy_higher_ground(enemy.definition):modifiers.append(DiceModifier('RULE-COMBAT-007:higher-ground',1))
            modifiers.extend(pc_weapon_attack_modifiers(weapon,enemy.state.injury.conditions))
        if extra:modifiers.append(DiceModifier('tactics:prospective-help',extra))
        request=_pc_test(state,actor,pc_melee_action_id(state,actor)+':attack',skill,tuple(modifiers))
        if enhancement is not None and skill is Skill.MELEE:request=replace(request,profile=pc.melee_profile)
        request,_=build_pc_test_help(state,actor,skill,request)
        if wild and not shooting:request=pc_wild_test_variant(request,weapon,member.injury.conditions)
        protection_profile,protection=npc_protection_test(state,target,actor,'tactics:protection',attack_skill=skill)
        defenceless=enemy.state.injury.conditions.has(Condition.DEFENCELESS)
        damage=pc_weapon_damage(weapon,pc.strength)
        base=damage.base+sum(m.amount for m in pc_weapon_damage_modifiers(weapon,enemy.state.current_resilience))
        ignores=shooting and ranged_weapon_combat_profile(RangedWeaponId(weapon.value)).ignores_armour
        resistance=enemy.state.current_resilience.toughness if ignores else enemy.state.current_resilience.total
        stance=(skill is Skill.MELEE and not defenceless and protection_profile.skill is Skill.DEFENCE
            and enemy.state.injury.conditions.has(Condition.STAGGERED) and not wild
            and not member.injury.conditions.has(Condition.STAGGERED)
            and has_generated_talent(enemy.definition,GeneratedTalent.DEFENSIVE_STANCE))
        value=_impact_value(pc_test_distribution(state,actor,skill,request,include_policy=state.source.participant(actor).pc.ranged is not None),
            (1.0,) if defenceless else _distribution(protection),base,resistance,damage.success_multiplier,
            enemy.state.injury.conditions.has(Condition.STAGGERED),defenceless,stance)
        if best[1] is None or value>best[0]+1e-12:best=value,target
    return best


def _distribution_request_value(state,actor,request,skill,target,*,budget):
    """Separate final successes from Fate budget to value a future shot."""
    from towr.domain.pc_tactical_models import _distribution,_impact_value
    from towr.domain.pc_generated_equipment import npc_protection_test
    from towr.domain.pc_backup_weapon_models import pc_active_weapon
    from towr.domain.pc_potion_models import pc_effective_definition
    from towr.domain.pc_weapon_models import pc_weapon_damage,pc_weapon_damage_modifiers
    from towr.domain.pc_melee_models import PC_RANGED_WEAPONS
    enemy=state.enemy(target);weapon=pc_active_weapon(state,actor)
    selected,protection=npc_protection_test(state,target,actor,'tactics:protection',attack_skill=skill)
    defenceless=enemy.state.injury.conditions.has(Condition.DEFENCELESS)
    damage=pc_weapon_damage(weapon,pc_effective_definition(state,actor).strength)
    base=damage.base+sum(m.amount for m in pc_weapon_damage_modifiers(weapon,enemy.state.current_resilience))
    ignores=weapon in PC_RANGED_WEAPONS and ranged_weapon_combat_profile(RangedWeaponId(weapon.value)).ignores_armour
    resilience=enemy.state.current_resilience.toughness if ignores else enemy.state.current_resilience.total
    distribution=(1.0,) if defenceless else _distribution(protection)
    from towr.domain.pc_generated_talents import has_generated_talent
    from towr.domain.generated_npc_models import GeneratedTalent
    stance=(skill is Skill.MELEE and selected.skill is Skill.DEFENCE and not defenceless
        and enemy.state.injury.conditions.has(Condition.STAGGERED)
        and not state.participant(actor).injury.conditions.has(Condition.STAGGERED)
        and not any(m.quality is TestQuality.GLORIOUS and m.rule_id=='RULE-TALENT-002:wild-attack' for m in request.quality_modifiers)
        and has_generated_talent(enemy.definition,GeneratedTalent.DEFENSIVE_STANCE))
    rows=[]
    for successes,after,chance in pc_fate_branches(state,actor,skill,request,budget):
        literal=(0.0,)*successes+(1.0,)
        rows.append((_impact_value(literal,distribution,base,resilience,damage.success_multiplier,
            enemy.state.injury.conditions.has(Condition.STAGGERED),defenceless,stance),after,chance))
    return tuple(rows)


def ranged_action_choices(state,actor,*,incoming_risk=None,_budget=None,_left=None,_horizon=None):
    """Comparable immediate choices with a finite continuation per Fate branch."""
    from towr.domain.pc_tactical_models import PcTacticalChoice
    from towr.domain.pc_melee_result_models import _pc_test,pc_melee_action_id
    from towr.domain.pc_backup_weapon_models import pc_active_weapon
    from towr.domain.pc_melee_models import PC_RANGED_WEAPONS
    from towr.domain.pc_weapon_inventory import (pc_weapon_inventory_view,pc_weapon_pickup_view,pc_weapon_swap_used)
    from towr.domain.pc_combat_equipment_models import PcItemLocation
    from towr.domain.pc_heavy_wound_models import usable_hands,usable_weapon_hand
    from towr.domain.pc_shield_models import PcShieldLocation
    from towr.domain.pc_help_models import build_pc_test_help
    member=state.participant(actor);inventory=member.weapon_inventory
    if inventory is None:return ()
    horizon=min(3,max(1,state.source.max_rounds-state.round_state.round_number+1)) if _horizon is None else _horizon
    if horizon<=0:return ()
    views={}
    swapped=pc_weapon_swap_used(state,actor)
    for item in inventory.items:
        if swapped and item.id!=inventory.active_item_id:continue
        view=pc_weapon_inventory_view(state,actor,item.id)
        if view is not None and usable_weapon_hand(view.participant(actor)) is not None:views[item.id]=view
    ranged_id=state.source.participant(actor).combat_equipment[0].id
    ranged=member.ranged
    remaining=(0 if ranged.loaded else max(1,ranged.required_successes-ranged.exacting.accumulated_successes)) if _left is None else _left
    targets=tuple(t for t in state.source.participant(actor).target_priority
        if not state.enemy(t).state.injury.defeated and t not in state.exited_npc_ids)
    budget=initial_fate_budget(state,actor) if _budget is None else _budget
    shot_rows={};shot_targets={}
    for item_id,view in views.items():
        weapon=pc_active_weapon(view,actor);skill=Skill.SHOOTING if weapon in PC_RANGED_WEAPONS else Skill.MELEE
        modes=(False,True) if (skill is Skill.SHOOTING and ranged_weapon_reload_profile(RangedWeaponId(weapon.value)).trigger is RangedReloadTrigger.AFTER_OPTIONAL_BONUS
            and not member.injury.conditions.has(Condition.DRAINED)) else (False,)
        for bonus in modes:
            target=pc_attack_value(view,actor,bonus=bonus,allow_empty=True)[1]
            # A hypothetical empty gun can still be valued AFTER an exact future Reload.
            if target is None and skill is Skill.SHOOTING:target=targets[0] if targets else None
            if target is None:continue
            modifiers=[]
            if skill is Skill.SHOOTING and state.enemy(target).state.injury.conditions.has(Condition.PRONE):modifiers.append(DiceModifier('RULE-HEALTH-008:prone-shooting',-1))
            if bonus:modifiers.append(ranged_weapon_reload_profile(RangedWeaponId(weapon.value)).optional_bonus_modifier())
            if skill is Skill.MELEE:
                from towr.domain.pc_weapon_models import pc_weapon_attack_modifiers
                if state.source.facts.outnumbering_bonus_approved and len(state.live_party)>len(state.live_enemies):modifiers.append(DiceModifier('RULE-COMBAT-007:outnumbering',1))
                if state.enemy(target).state.injury.conditions.has(Condition.PRONE):modifiers.append(DiceModifier('RULE-COMBAT-007:higher-ground',1))
                modifiers.extend(pc_weapon_attack_modifiers(weapon,state.enemy(target).state.injury.conditions))
            request=_pc_test(view,actor,pc_melee_action_id(view,actor)+':attack',skill,tuple(modifiers))
            request,_=build_pc_test_help(view,actor,skill,request)
            shot_rows[item_id,bonus]=request,skill,target
            shot_targets[item_id,bonus]=target
    reload_view=views.get(ranged_id)
    reload_test=(_pc_test(reload_view,actor,'tactics:pc-reload',Skill.DEXTERITY) if reload_view is not None and len(usable_hands(member))==2 else None)
    source_shield=state.source.participant(actor).shield is not None
    held_shield=member.shield is not None and member.shield.location is PcShieldLocation.HELD
    can_restore=source_shield and len(usable_hands(member))==2
    @lru_cache(maxsize=None)
    def attack_rows(item_id,bonus,remaining_budget):
        request,skill,target=shot_rows[item_id,bonus]
        return _distribution_request_value(views[item_id],actor,request,skill,target,budget=remaining_budget)
    @lru_cache(maxsize=None)
    def reload_rows(remaining_budget):
        return pc_fate_branches(reload_view,actor,Skill.DEXTERITY,reload_test,remaining_budget)
    @lru_cache(maxsize=None)
    def continuation(turns,left,active,shield,remaining_budget):
        if turns<=0:return 0.0
        options=[]
        for item_id,view in views.items():
            weapon=pc_active_weapon(view,actor);shooting=weapon in PC_RANGED_WEAPONS
            if shooting and left:
                if reload_test is not None:
                    value=sum(chance*continuation(turns-1,max(0,left-successes),item_id,False,after)
                        for successes,after,chance in reload_rows(remaining_budget))
                    options.append(value)
                continue
            if not shield and can_restore:
                options.append(continuation(turns-1,left,item_id,True,remaining_budget));continue
            for bonus in (False,True):
                spec=shot_rows.get((item_id,bonus))
                if spec is None:continue
                request,skill,target=spec
                next_left=(3 if bonus or (shooting and ranged_weapon_reload_profile(RangedWeaponId(weapon.value)).trigger is RangedReloadTrigger.AFTER_EVERY_SHOT) else left)
                value=sum(chance*(utility+continuation(turns-1,next_left,item_id,shield,after))
                    for utility,after,chance in attack_rows(item_id,bonus,remaining_budget))
                options.append(value)
        return max(options,default=0.0)
    result=[]
    current_risk=incoming_risk(state) if incoming_risk is not None else 0.0
    for item_id,view in views.items():
        weapon=pc_active_weapon(view,actor);shooting=weapon in PC_RANGED_WEAPONS
        viewed_member=view.participant(actor)
        switch=item_id!=inventory.active_item_id
        cost=(max(0.0,incoming_risk(view)-current_risk) if incoming_risk is not None and switch else 0.0)
        if shooting and remaining:
            if reload_test is not None:
                value=sum(chance*continuation(horizon-1,max(0,remaining-successes),item_id,False,after)
                    for successes,after,chance in pc_fate_branches(view,actor,Skill.DEXTERITY,reload_test,budget))/horizon-cost
                result.append(PcTacticalChoice(actor,CombatActionKind.IMPROVISE,actor,None,value,'reload_selected_weapon',weapon_item_id=item_id,ranged_reload=True))
            continue
        if (viewed_member.shield is not None and viewed_member.shield.location is PcShieldLocation.DROPPED and can_restore):
            value=continuation(horizon-1,remaining,item_id,True,budget)/horizon-cost
            result.append(PcTacticalChoice(actor,CombatActionKind.RECOVER,actor,None,value,'restore_selected_weapon_shield',weapon_item_id=item_id));continue
        for bonus in (False,True):
            spec=shot_rows.get((item_id,bonus))
            if spec is None:continue
            request,skill,target=spec
            next_left=(3 if bonus or (shooting and ranged_weapon_reload_profile(RangedWeaponId(weapon.value)).trigger is RangedReloadTrigger.AFTER_EVERY_SHOT) else remaining)
            value=sum(chance*(utility+continuation(horizon-1,next_left,item_id,held_shield,after))
                for utility,after,chance in attack_rows(item_id,bonus,budget))/horizon-cost
            result.append(PcTacticalChoice(actor,CombatActionKind.ATTACK,target,None,value,'best_prepared_weapon_attack',weapon_item_id=item_id,ranged_bonus=bonus))
            if skill is Skill.MELEE and not bonus:
                from towr.domain.pc_talent_advice import pc_wild_eligible,pc_wild_test_variant
                if pc_wild_eligible(view,actor):
                    wild_request=pc_wild_test_variant(request,weapon,viewed_member.injury.conditions)
                    staggered=replace(viewed_member,injury=replace(viewed_member.injury,
                        conditions=viewed_member.injury.conditions.with_condition(Condition.STAGGERED)))
                    after_price=replace(view,party=tuple(staggered if m.actor_id==actor else m for m in view.party))
                    penalty=(max(0.0,incoming_risk(after_price)-incoming_risk(view)) if incoming_risk is not None else 0.0)
                    future={}
                    wild_value=0.0
                    for utility,after,chance in _distribution_request_value(view,actor,wild_request,skill,target,budget=budget):
                        if after not in future:
                            choices=ranged_action_choices(after_price,actor,_budget=after,_left=remaining,_horizon=horizon-1)
                            future[after]=max((c.utility for c in choices),default=0.0)*(horizon-1)
                        wild_value+=chance*(utility+future[after])
                    wild_value=wild_value/horizon-cost-penalty
                    result.append(PcTacticalChoice(actor,CombatActionKind.ATTACK,target,None,wild_value,
                        'wild_prepared_weapon_attack',wild_attack=True,weapon_item_id=item_id))
    for item in inventory.items:
        if item.location is not PcItemLocation.DROPPED:continue
        view=pc_weapon_pickup_view(state,actor,item.id)
        if view is None:continue
        future=ranged_action_choices(view,actor,_budget=budget,_left=remaining,_horizon=horizon-1)
        score=max((choice.utility for choice in future),default=0.0)*(horizon-1)/horizon
        if incoming_risk is not None:score-=max(0.0,incoming_risk(view)-current_risk)
        result.append(PcTacticalChoice(actor,CombatActionKind.RECOVER,actor,None,score,'recover_selected_weapon',weapon_item_id=inventory.active_item_id,pickup_item_id=item.id))
    return tuple(result)


def pc_help_mode_values(state,actor,skill,request,benefit,*,future_cache=None):
    """Value Help plus finite own continuation, charging only a chosen Trait.

    Ordinary Help is not a shot. An optional repeater bonus belongs to a
    Shooting Test, so its price is Reload3 even when that Test was Help.
    """
    from towr.domain.pc_melee_models import PC_RANGED_WEAPONS
    from towr.domain.pc_backup_weapon_models import pc_active_weapon
    from towr.domain.pc_heavy_wound_models import usable_weapon_hand
    member=state.participant(actor);weapon=pc_active_weapon(state,actor)
    if usable_weapon_hand(member) is None:return ()
    if skill is Skill.SHOOTING and (weapon not in PC_RANGED_WEAPONS or member.ranged is None or not member.ranged.loaded):return ()
    modes=(False,)
    if (skill is Skill.SHOOTING and not member.injury.conditions.has(Condition.DRAINED)
            and ranged_weapon_reload_profile(RangedWeaponId(weapon.value)).trigger is RangedReloadTrigger.AFTER_OPTIONAL_BONUS):modes=(False,True)
    horizon=min(3,max(1,state.source.max_rounds-state.round_state.round_number+1))
    left=0 if member.ranged.loaded else max(1,member.ranged.required_successes-member.ranged.exacting.accumulated_successes)
    budget=initial_fate_budget(state,actor)
    cache={} if future_cache is None else future_cache
    def future(remaining,after):
        key=(actor,member.weapon_inventory.active_item_id,remaining,after,horizon-1,
            member.injury.conditions,member.weapon_hand,member.shield.location if member.shield is not None else None)
        if key not in cache:
            choices=ranged_action_choices(state,actor,_budget=after,_left=remaining,_horizon=horizon-1)
            cache[key]=max((choice.utility for choice in choices),default=0.0)*(horizon-1)
        return cache[key]
    values=[]
    for bonus in modes:
        test=request
        if bonus:
            modifier=ranged_weapon_reload_profile(RangedWeaponId(weapon.value)).optional_bonus_modifier()
            test=replace(test,dice_modifiers=(*test.dice_modifiers,modifier))
        remaining=3 if bonus else left
        value=sum(chance*(benefit(successes)+future(remaining,after))
            for successes,after,chance in pc_fate_branches(state,actor,skill,test,budget))/horizon
        values.append((bonus,value))
    return tuple(values)
