"""Finite automatic PC weapon and reload advice (ADR-0125).

Prepared views are comparisons only. No rolls, proof receipts or real Fate spends
are created here. A finite Fate budget follows every forecast Test branch.
"""
from towr.domain.reload_models import ranged_weapon_is_loaded
from towr.domain.reload_models import ReloadableWeaponState
from dataclasses import replace
from functools import lru_cache
from collections import defaultdict

from towr.domain.condition_models import Condition
from towr.domain.test_models import Skill,DiceModifier,TestQuality,_expected_initial_roll_parameters
from towr.domain.turn_models import CombatActionKind
from towr.domain.ranged_weapon_profiles import (
    RangedWeaponId,ranged_weapon_reload_profile,RangedReloadTrigger,
)


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
    from towr.domain.pc_melee_models import PC_RANGED_WEAPONS, PC_THROWING_WEAPONS
    from towr.domain.pc_melee_result_models import _pc_test,pc_melee_action_id
    from towr.domain.pc_backup_weapon_models import pc_active_weapon
    from towr.domain.pc_potion_models import pc_effective_definition
    from towr.domain.pc_help_models import build_pc_test_help
    from towr.domain.pc_weapon_inventory import pc_attack_weapon_use,pc_weapon_target_modifiers
    from towr.domain.weapon_effect_preparation import weapon_damage_preparation
    from towr.domain.attack_models import DamageImpactSpec,effective_damage_modifiers,effective_ignores_armour
    from towr.domain.pc_generated_equipment import npc_protection_test
    from towr.domain.pc_npc_ability_models import pc_npc_allows_enemy_higher_ground
    from towr.domain.pc_mount_models import pc_is_mounted
    from towr.domain.pc_talent_advice import pc_test_distribution,pc_wild_test_variant
    from towr.domain.pc_generated_talents import has_generated_talent
    from towr.domain.generated_npc_models import GeneratedTalent
    member=state.participant(actor)
    initial_use=pc_attack_weapon_use(state,actor)
    if initial_use is None:return 0.0,None
    weapon=initial_use.kind
    shooting=weapon in PC_RANGED_WEAPONS;throwing=weapon in PC_THROWING_WEAPONS
    skill=initial_use.skill
    pc=pc_effective_definition(state,actor)
    if enhancement is not None:pc=replace(pc,**{enhancement:getattr(pc,enhancement)+1})
    from towr.domain.pc_heavy_wound_models import usable_weapon_hand
    if weapon.value=='weighted_net':
        from towr.domain.pc_weighted_net_models import weighted_net_for_actor,PcNetLocation
        item=weighted_net_for_actor(state,actor)
        if item is None or item.location not in (PcNetLocation.HELD,PcNetLocation.CARRIED):return 0.0,None
    if shooting and (member.ranged is None or (not ranged_weapon_is_loaded(member.ranged) and not allow_empty)):return 0.0,None
    best=(0.0,None)
    from towr.domain.pc_battlefield_movement_models import pc_battlefield_attack_available,pc_battlefield_allows_outnumbering
    targets=(target_id,) if target_id is not None else state.source.participant(actor).target_priority
    for target in targets:
        enemy=state.enemy(target)
        if enemy.state.injury.defeated or target in state.exited_npc_ids:continue
        if not pc_battlefield_attack_available(state,actor,target):continue
        use=pc_attack_weapon_use(state,actor,target)
        if use is None:continue
        if skill is Skill.BRAWN and not any(option.skill in (Skill.ATHLETICS,Skill.ENDURANCE)
                for option in enemy.definition.protection):continue
        modifiers=[]
        if shooting:
            from towr.domain.pc_ranged_models import pc_ranged_profile_modifiers
            from towr.domain.pc_aim_models import pc_aim_attack_modifiers
            modifiers.extend(pc_ranged_profile_modifiers(state,actor,target,require_loaded=False))
            modifiers.extend(pc_aim_attack_modifiers(state,actor,target))
            if enemy.state.injury.conditions.has(Condition.PRONE):modifiers.append(DiceModifier('RULE-HEALTH-008:prone-shooting',-1))
            if bonus and not member.injury.conditions.has(Condition.DRAINED):
                modifiers.append(ranged_weapon_reload_profile(RangedWeaponId(weapon.value)).optional_bonus_modifier())
        elif not throwing:
            if pc_battlefield_allows_outnumbering(state,actor):
                modifiers.append(DiceModifier('RULE-COMBAT-007:outnumbering',1))
            if enemy.state.injury.conditions.has(Condition.PRONE) and pc_npc_allows_enemy_higher_ground(enemy.definition):modifiers.append(DiceModifier('RULE-COMBAT-007:higher-ground',1))
        modifiers.extend(pc_weapon_target_modifiers(use,enemy.state.injury.conditions,
            target_mounted=pc_is_mounted(state,target)))
        if extra:modifiers.append(DiceModifier('tactics:prospective-help',extra))
        request=_pc_test(state,actor,pc_melee_action_id(state,actor)+':attack',skill,tuple(modifiers),weapon_use=use)
        if enhancement is not None and skill in (Skill.MELEE,Skill.BRAWN):
            request=replace(request,profile=pc.brawn_profile if skill is Skill.BRAWN else pc.melee_profile)
        request,_=build_pc_test_help(state,actor,skill,request)
        if wild and not shooting:request=pc_wild_test_variant(request,weapon,member.injury.conditions)
        protection_profile,protection=npc_protection_test(state,target,actor,'tactics:protection',attack_skill=skill)
        defenceless=enemy.state.injury.conditions.has(Condition.DEFENCELESS)
        if use.primary is None:
            from towr.domain.pc_tactical_models import stagger_attack_value
            value=stagger_attack_value(pc_test_distribution(state,actor,skill,request,include_policy=True),
                (1.0,) if defenceless else _distribution(protection),enemy.state.injury.conditions.has(Condition.STAGGERED))
            if best[1] is None or value>best[0]+1e-12:best=value,target
            continue
        if throwing:
            protection_values=(1.0,) if defenceless else _distribution(protection)
            attack_values=pc_test_distribution(state,actor,skill,request,include_policy=True)
            from towr.domain.pc_weapon_area_models import throwing_special_value
            value=throwing_special_value(state,actor,target,use.kind,attack_values,protection_values)
            if value is not None:
                if best[1] is None or value>best[0]+1e-12:best=value,target
                continue
        prepared=weapon_damage_preparation(use,pc.strength,enemy.state.current_resilience)
        damage=prepared.damage
        if damage is None:continue
        impact=DamageImpactSpec(damage,enemy.state.current_resilience,
            prepared.ignores_armour,prepared.modifiers,magical_source=prepared.magical_source)
        base=damage.base+sum(m.amount for m in effective_damage_modifiers(impact))
        ignores=effective_ignores_armour(impact)
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


def net_inventory_action_choices(state,actor,*,incoming_risk=None):
    """Compare the actual carried backup with a held Net, without spending it."""
    from towr.domain.pc_tactical_models import PcTacticalChoice
    from towr.domain.pc_weapon_inventory import pc_weapon_inventory_view,pc_weapon_swap_used
    from towr.domain.pc_combat_equipment_models import PcItemLocation
    member=state.participant(actor)
    if member.weapon_inventory is None:return ()
    from towr.domain.pc_weighted_net_models import weighted_net_for_actor,PcNetLocation
    from towr.domain.pc_melee_models import PcMeleeWeapon
    actual_net=weighted_net_for_actor(state,actor)
    result=[]
    current_risk=incoming_risk(state) if incoming_risk is not None else 0.0
    for item in member.weapon_inventory.items:
        if item.location not in (PcItemLocation.HELD,PcItemLocation.CARRIED):continue
        if (pc_weapon_swap_used(state,actor) and item.id!=member.weapon_inventory.active_item_id
                and item.location is not PcItemLocation.HELD):continue
        view=pc_weapon_inventory_view(state,actor,item.id)
        if view is None:continue
        value,target=pc_attack_value(view,actor)
        if target is None:
            if (state.battlefield is not None and actual_net is not None
                    and actual_net.location not in (PcNetLocation.HELD,PcNetLocation.CARRIED)
                    and item.weapon is not PcMeleeWeapon.WEIGHTED_NET
                    and item.id!=member.weapon_inventory.active_item_id):
                # Draw the available backup even before its melee target is in
                # reach. Subsequent real positioning owns movement/Charge; a
                # spent Net must not trap a healthy armed actor in Recover.
                result.append(PcTacticalChoice(actor,CombatActionKind.RECOVER,actor,None,.05,
                    'prepare_backup_after_deployed_net',weapon_item_id=item.id))
            continue
        if item.id!=member.weapon_inventory.active_item_id and incoming_risk is not None:
            value-=max(0.0,incoming_risk(view)-current_risk)
        result.append(PcTacticalChoice(actor,CombatActionKind.ATTACK,target,None,value,
            'net_or_carried_melee_attack',weapon_item_id=item.id))
    return tuple(result)


def _distribution_request_value(state,actor,request,skill,target,*,budget):
    """Separate final successes from Fate budget to value a future shot."""
    from towr.domain.pc_tactical_models import _distribution,_impact_value
    from towr.domain.pc_generated_equipment import npc_protection_test
    from towr.domain.pc_potion_models import pc_effective_definition
    from towr.domain.pc_weapon_inventory import pc_attack_weapon_use
    from towr.domain.weapon_effect_preparation import weapon_damage_preparation
    from towr.domain.attack_models import DamageImpactSpec,effective_damage_modifiers,effective_ignores_armour
    enemy=state.enemy(target)
    selected,protection=npc_protection_test(state,target,actor,'tactics:protection',attack_skill=skill)
    defenceless=enemy.state.injury.conditions.has(Condition.DEFENCELESS)
    if skill is Skill.THROWING:
        protection_values=(1.0,) if defenceless else _distribution(protection)
        burdened=enemy.state.injury.conditions.has(Condition.BURDENED)
        return tuple((0.0 if burdened or not successes else .2*sum(protection_values[:successes+1]),after,chance)
            for successes,after,chance in pc_fate_branches(state,actor,skill,request,budget))
    use=pc_attack_weapon_use(state,actor,target)
    if use is None:return ()
    prepared=weapon_damage_preparation(use,pc_effective_definition(state,actor).strength,
        enemy.state.current_resilience)
    damage=prepared.damage
    if damage is None:return ()
    impact=DamageImpactSpec(damage,enemy.state.current_resilience,
        prepared.ignores_armour,prepared.modifiers,magical_source=prepared.magical_source)
    base=damage.base+sum(m.amount for m in effective_damage_modifiers(impact))
    ignores=effective_ignores_armour(impact)
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


def _ranged_remaining(member):
    """Forecast counters keyed by real units; actual K1 histories stay untouched."""
    from towr.domain.weapon_catalog import WeaponGroup,weapon_profile
    return tuple((item.id,0 if item.reload is None or item.reload.loaded else
        max(1,item.reload.required_successes-item.reload.exacting.accumulated_successes))
        for item in member.weapon_inventory.items if weapon_profile(item.kind).group is WeaponGroup.SHOOTING)


def _remaining_for(remaining,item_id):
    return next((left for identifier,left in remaining if identifier==item_id),0)


def _remaining_after(remaining,item_id,value):
    return tuple((identifier,value if identifier==item_id else left) for identifier,left in remaining)


def ranged_action_choices(state,actor,*,incoming_risk=None,_budget=None,_remaining=None,_horizon=None,
        _future_turn=False):
    """Comparable immediate choices with a finite continuation per Fate branch."""
    from towr.domain.pc_tactical_models import PcTacticalChoice
    from towr.domain.pc_melee_result_models import _pc_test,pc_melee_action_id
    from towr.domain.pc_backup_weapon_models import pc_active_weapon
    from towr.domain.pc_melee_models import PC_RANGED_WEAPONS
    from towr.domain.pc_weapon_inventory import (
        pc_weapon_inventory_view,pc_weapon_pickup_view,pc_attack_weapon_use,pc_weapon_target_modifiers,
    )
    from towr.domain.pc_combat_equipment_models import PcItemLocation
    from towr.domain.pc_heavy_wound_models import usable_hands,usable_weapon_hand
    from towr.domain.pc_shield_models import PcShieldLocation
    from towr.domain.pc_help_models import build_pc_test_help
    from towr.domain.pc_battlefield_movement_models import pc_battlefield_attack_available,pc_battlefield_allows_outnumbering
    member=state.participant(actor);inventory=member.weapon_inventory
    if inventory is None:return ()
    horizon=min(3,max(1,state.source.max_rounds-state.round_state.round_number+1)) if _horizon is None else _horizon
    if horizon<=0:return ()
    views={};current_views={}
    for item in inventory.items:
        if item.location not in (PcItemLocation.HELD,PcItemLocation.CARRIED):continue
        current=pc_weapon_inventory_view(state,actor,item.id,future_turn=_future_turn)
        if current is not None:current_views[item.id]=current
        view=pc_weapon_inventory_view(state,actor,item.id,future_turn=True)
        if view is not None and usable_weapon_hand(view.participant(actor)) is not None:views[item.id]=view
    remaining=_ranged_remaining(member) if _remaining is None else _remaining
    targets=tuple(t for t in state.source.participant(actor).target_priority
        if not state.enemy(t).state.injury.defeated and t not in state.exited_npc_ids)
    budget=initial_fate_budget(state,actor) if _budget is None else _budget
    shot_rows={}
    for item_id,view in views.items():
        weapon=pc_active_weapon(view,actor)
        base_use=pc_attack_weapon_use(view,actor)
        if base_use is None:continue
        skill=base_use.skill
        modes=(False,True) if (skill is Skill.SHOOTING and ranged_weapon_reload_profile(RangedWeaponId(weapon.value)).trigger is RangedReloadTrigger.AFTER_OPTIONAL_BONUS
            and not member.injury.conditions.has(Condition.DRAINED)) else (False,)
        for bonus in modes:
            target=pc_attack_value(view,actor,bonus=bonus,allow_empty=True)[1]
            # A hypothetical empty gun can still be valued AFTER an exact future Reload.
            if target is None and skill is Skill.SHOOTING:
                target=next((target for target in targets if pc_battlefield_attack_available(view,actor,target)),None)
            if target is None:continue
            use=pc_attack_weapon_use(view,actor,target)
            if use is None:continue
            modifiers=[]
            if skill is Skill.SHOOTING:
                from towr.domain.pc_ranged_models import pc_ranged_profile_modifiers
                from towr.domain.pc_aim_models import pc_aim_attack_modifiers
                modifiers.extend(pc_ranged_profile_modifiers(view,actor,target,require_loaded=False))
                modifiers.extend(pc_aim_attack_modifiers(view,actor,target))
            if skill is Skill.SHOOTING and state.enemy(target).state.injury.conditions.has(Condition.PRONE):modifiers.append(DiceModifier('RULE-HEALTH-008:prone-shooting',-1))
            if bonus:modifiers.append(ranged_weapon_reload_profile(RangedWeaponId(weapon.value)).optional_bonus_modifier())
            if skill is Skill.MELEE:
                if pc_battlefield_allows_outnumbering(view,actor):modifiers.append(DiceModifier('RULE-COMBAT-007:outnumbering',1))
                from towr.domain.pc_npc_ability_models import pc_npc_allows_enemy_higher_ground
                if (state.enemy(target).state.injury.conditions.has(Condition.PRONE)
                        and pc_npc_allows_enemy_higher_ground(state.enemy(target).definition)):
                    modifiers.append(DiceModifier('RULE-COMBAT-007:higher-ground',1))
            from towr.domain.pc_mount_models import pc_is_mounted
            modifiers.extend(pc_weapon_target_modifiers(use,state.enemy(target).state.injury.conditions,
                target_mounted=pc_is_mounted(view,target)))
            request=_pc_test(view,actor,pc_melee_action_id(view,actor)+':attack',skill,tuple(modifiers),weapon_use=use)
            request,_=build_pc_test_help(view,actor,skill,request)
            shot_rows[item_id,bonus]=request,skill,target
    reload_views={};reload_tests={};current_reload_ids=set()
    if len(usable_hands(member))==2:
        for item in inventory.items:
            if item.id not in views or type(item.reload) is not ReloadableWeaponState:continue
            if pc_weapon_inventory_view(state,actor,item.id,for_reload=True,future_turn=_future_turn) is not None:
                current_reload_ids.add(item.id)
            view=pc_weapon_inventory_view(state,actor,item.id,for_reload=True,future_turn=True)
            if view is not None:
                reload_views[item.id]=view
                reload_tests[item.id]=_pc_test(view,actor,'tactics:pc-reload:'+item.id,Skill.DEXTERITY)
    source_shield=state.source.participant(actor).shield is not None
    held_shield=member.shield is not None and member.shield.location is PcShieldLocation.HELD
    from towr.domain.weapon_inventory_models import WeaponGrip
    can_restore={item_id:source_shield and len(usable_hands(member))==2
        and view.participant(actor).weapon_inventory.active.grip is not WeaponGrip.BOTH
        for item_id,view in views.items()}
    can_keep_shield={item_id:view.participant(actor).weapon_inventory.active.grip is not WeaponGrip.BOTH
        for item_id,view in views.items()}
    @lru_cache(maxsize=None)
    def attack_rows(item_id,bonus,remaining_budget):
        request,skill,target=shot_rows[item_id,bonus]
        return _distribution_request_value(views[item_id],actor,request,skill,target,budget=remaining_budget)
    @lru_cache(maxsize=None)
    def reload_rows(item_id,remaining_budget):
        return pc_fate_branches(reload_views[item_id],actor,Skill.DEXTERITY,reload_tests[item_id],remaining_budget)
    @lru_cache(maxsize=None)
    def continuation(turns,remaining,active,shield,remaining_budget):
        if turns<=0:return 0.0
        options=[]
        for item_id,view in views.items():
            weapon=pc_active_weapon(view,actor);shooting=weapon in PC_RANGED_WEAPONS
            left=_remaining_for(remaining,item_id)
            if shooting and left:
                if item_id in reload_tests:
                    value=sum(chance*continuation(turns-1,
                            _remaining_after(remaining,item_id,max(0,left-successes)),item_id,False,after)
                        for successes,after,chance in reload_rows(item_id,remaining_budget))
                    options.append(value)
                continue
            if not shield and can_restore[item_id]:
                options.append(continuation(turns-1,remaining,item_id,True,remaining_budget));continue
            for bonus in (False,True):
                spec=shot_rows.get((item_id,bonus))
                if spec is None:continue
                request,skill,target=spec
                profile=ranged_weapon_reload_profile(RangedWeaponId(weapon.value)) if shooting else None
                next_remaining=(_remaining_after(remaining,item_id,profile.required_successes)
                    if shooting and (bonus or profile.trigger is RangedReloadTrigger.AFTER_EVERY_SHOT) else remaining)
                value=sum(chance*(utility+continuation(turns-1,next_remaining,item_id,
                        shield and can_keep_shield[item_id],after))
                    for utility,after,chance in attack_rows(item_id,bonus,remaining_budget))
                options.append(value)
        return max(options,default=0.0)
    result=[]
    current_risk=incoming_risk(state) if incoming_risk is not None else 0.0
    for item_id,view in views.items():
        if item_id not in current_views:continue
        weapon=pc_active_weapon(view,actor);shooting=weapon in PC_RANGED_WEAPONS
        viewed_member=view.participant(actor)
        switch=item_id!=inventory.active_item_id
        cost=(max(0.0,incoming_risk(view)-current_risk) if incoming_risk is not None and switch else 0.0)
        left=_remaining_for(remaining,item_id)
        if shooting and left:
            if item_id in current_reload_ids:
                reload_cost=(max(0.0,incoming_risk(reload_views[item_id])-current_risk)
                    if incoming_risk is not None else 0.0)
                value=sum(chance*continuation(horizon-1,
                        _remaining_after(remaining,item_id,max(0,left-successes)),item_id,False,after)
                    for successes,after,chance in reload_rows(item_id,budget))/horizon-reload_cost
                result.append(PcTacticalChoice(actor,CombatActionKind.IMPROVISE,actor,None,value,'reload_selected_weapon',weapon_item_id=item_id,ranged_reload=True))
            continue
        if (viewed_member.shield is not None and viewed_member.shield.location is PcShieldLocation.DROPPED and can_restore[item_id]):
            value=continuation(horizon-1,remaining,item_id,True,budget)/horizon-cost
            result.append(PcTacticalChoice(actor,CombatActionKind.RECOVER,actor,None,value,'restore_selected_weapon_shield',weapon_item_id=item_id));continue
        for bonus in (False,True):
            spec=shot_rows.get((item_id,bonus))
            if spec is None:continue
            request,skill,target=spec
            if shooting:
                from towr.domain.pc_aim_models import pc_ranged_needs_aim,pc_aim_target
                if pc_ranged_needs_aim(view,actor,target):
                    from towr.domain.pc_heavy_wound_models import restriction_sources
                    from towr.domain.injury_models import WoundRestriction
                    source=view.source.participant(actor).pc
                    if (source.ranged.awareness is not None and pc_aim_target(view,actor) == target
                            and not restriction_sources(viewed_member.injury,WoundRestriction.CANNOT_AIM)):
                        value=0.01+pc_attack_value(view,actor,target_id=target)[0]/2-cost
                        result.append(PcTacticalChoice(actor,CombatActionKind.AIM,target,None,value,
                            'aim_required_before_shot',weapon_item_id=item_id))
                    continue
            profile=ranged_weapon_reload_profile(RangedWeaponId(weapon.value)) if shooting else None
            next_remaining=(_remaining_after(remaining,item_id,profile.required_successes)
                if shooting and (bonus or profile.trigger is RangedReloadTrigger.AFTER_EVERY_SHOT) else remaining)
            value=sum(chance*(utility+continuation(horizon-1,next_remaining,item_id,
                    held_shield and can_keep_shield[item_id],after))
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
                            choices=ranged_action_choices(after_price,actor,_budget=after,_remaining=remaining,
                                _horizon=horizon-1,_future_turn=True)
                            future[after]=max((c.utility for c in choices),default=0.0)*(horizon-1)
                        wild_value+=chance*(utility+future[after])
                    wild_value=wild_value/horizon-cost-penalty
                    result.append(PcTacticalChoice(actor,CombatActionKind.ATTACK,target,None,wild_value,
                        'wild_prepared_weapon_attack',wild_attack=True,weapon_item_id=item_id))
    for item in inventory.items:
        if item.location is not PcItemLocation.DROPPED:continue
        view=pc_weapon_pickup_view(state,actor,item.id)
        if view is None:continue
        future=ranged_action_choices(view,actor,_budget=budget,_remaining=remaining,
            _horizon=horizon-1,_future_turn=True)
        score=max((choice.utility for choice in future),default=0.0)*(horizon-1)/horizon
        if incoming_risk is not None:score-=max(0.0,incoming_risk(view)-current_risk)
        result.append(PcTacticalChoice(actor,CombatActionKind.RECOVER,actor,None,score,'recover_selected_weapon',weapon_item_id=inventory.active_item_id,pickup_item_id=item.id))
    # A ready Attack wins an exactly equal forecast against buying Reload
    # first. Otherwise source order would reload gun A while gun B is ready.
    return tuple(sorted(result,key=lambda choice:choice.ranged_reload))


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
    from towr.domain.pc_armour_models import actor_bound_to_chivalric_combat
    if skill in (Skill.SHOOTING,Skill.THROWING) and actor_bound_to_chivalric_combat(state,actor):return ()
    if skill is Skill.SHOOTING and (weapon not in PC_RANGED_WEAPONS or member.ranged is None or not ranged_weapon_is_loaded(member.ranged)):return ()
    modes=(False,)
    if (skill is Skill.SHOOTING and not member.injury.conditions.has(Condition.DRAINED)
            and ranged_weapon_reload_profile(RangedWeaponId(weapon.value)).trigger is RangedReloadTrigger.AFTER_OPTIONAL_BONUS):modes=(False,True)
    horizon=min(3,max(1,state.source.max_rounds-state.round_state.round_number+1))
    remaining=_ranged_remaining(member)
    budget=initial_fate_budget(state,actor)
    cache={} if future_cache is None else future_cache
    def future(remaining,after):
        key=(actor,member.weapon_inventory.active_item_id,remaining,after,horizon-1,
            member.injury.conditions,member.weapon_hand,member.shield.location if member.shield is not None else None)
        if key not in cache:
            choices=ranged_action_choices(state,actor,_budget=after,_remaining=remaining,
                _horizon=horizon-1,_future_turn=True)
            cache[key]=max((choice.utility for choice in choices),default=0.0)*(horizon-1)
        return cache[key]
    values=[]
    for bonus in modes:
        test=request
        if bonus:
            modifier=ranged_weapon_reload_profile(RangedWeaponId(weapon.value)).optional_bonus_modifier()
            test=replace(test,dice_modifiers=(*test.dice_modifiers,modifier))
        after_test=(_remaining_after(remaining,member.weapon_inventory.active_item_id,
            ranged_weapon_reload_profile(RangedWeaponId(weapon.value)).required_successes) if bonus else remaining)
        value=sum(chance*(benefit(successes)+future(after_test,after))
            for successes,after,chance in pc_fate_branches(state,actor,skill,test,budget))/horizon
        values.append((bonus,value))
    return tuple(values)
