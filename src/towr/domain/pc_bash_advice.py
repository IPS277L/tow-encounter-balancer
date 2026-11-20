"""Bounded one-step Bash continuation for automatic combat, without new rolls."""
from towr.domain.condition_models import Condition
from towr.domain.talent_actor_models import actor_acquired_talents
from towr.domain.talent_catalog import TalentId
from towr.domain.test_models import Skill,TestRequest,TestProfile
from towr.domain.pc_bash_weapon_models import select_bash_weapon


def bash_weapon_available(state,actor,target):
    from towr.domain.pc_magic_weapon_models import actor_injury
    from towr.domain.pc_oath_models import oath_allows_attack
    if not oath_allows_attack(state,actor,Skill.MELEE):
        return None
    if not any(entry.id is TalentId.BASH_ATTACK for entry in actor_acquired_talents(state,actor)):
        return None
    victim=actor_injury(state,target)
    if victim.conditions.has(Condition.STAGGERED) or victim.conditions.has(Condition.DEFENCELESS):
        return None
    return select_bash_weapon(state,actor,target)


def bash_follow_up_value(state,actor,target,attack,protection,*,parent_damage=None):
    """Value only HIT branches that actually could add the first Staggered.

    The continuation uses the real available Melee implements and an uncharged
    ordinary Test. It reserves no Fate, hands, equipment or future action. The
    current defence estimate is deliberately conservative: it grants no extra
    advantage from the prospective target Staggered. This is tactical advice,
    never permission to execute or a second simulation inside the search.
    """
    selected=bash_weapon_available(state,actor,target)
    if selected is None:return 0.0
    from towr.domain.pc_magic_weapon_models import actor_injury
    from towr.domain.pc_mount_models import pc_is_mounted
    from towr.domain.weapon_effect_preparation import weapon_test_modifiers,weapon_damage_preparation
    from towr.domain.pc_tactical_models import _distribution,_impact_value
    from towr.domain.attack_models import DamageImpactSpec,effective_damage_modifiers,effective_ignores_armour
    from towr.domain.pc_shield_models import pc_shield_resilience
    from towr.domain.pc_armour_models import actor_armour_test_modifiers
    from towr.domain.pc_musician_effect_models import musician_defends_ties,pc_attack_success_wins
    use=selected.use
    conditions=actor_injury(state,actor).conditions
    victim=actor_injury(state,target).conditions
    talents=actor_acquired_talents(state,actor)
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_potion_models import pc_effective_definition
        pc=pc_effective_definition(state,actor)
        profile,strength=pc.melee_profile,pc.strength
    else:
        from towr.domain.generated_npc_models import generated_npc_combat_ratings
        components=state.enemy(actor).definition.generated_components
        ws,melee,_=generated_npc_combat_ratings(components)
        profile,strength=TestProfile(ws,melee),components.strength
    if target in state.source.pc_activation_order:
        from towr.domain.pc_melee_result_models import pc_protection_skill,_pc_test
        resilience=pc_shield_resilience(state,target)
        skill=pc_protection_skill(state.participant(target),Skill.MELEE)
        defence=_pc_test(state,target,'tactics:bash:protection',skill,oppose_attack=True,
            incoming_attack_skill=Skill.MELEE)
    else:
        from towr.domain.pc_actor_models import pc_actor_npc_snapshot
        from towr.domain.pc_generated_equipment import npc_protection_test
        resilience=pc_actor_npc_snapshot(state,target).state.current_resilience
        _,defence=npc_protection_test(state,target,actor,'tactics:bash:protection',attack_skill=Skill.MELEE)
    mods=weapon_test_modifiers(use,conditions,target_conditions=victim,
        actor_mounted=pc_is_mounted(state,actor),target_mounted=pc_is_mounted(state,target),
        charging=False,talents=talents).modifiers
    mods=(*mods,*actor_armour_test_modifiers(state,actor,Skill.MELEE))
    if conditions.has(Condition.DRAINED):mods=tuple(mod for mod in mods if mod.amount<=0)
    test=TestRequest('tactics:bash:attack',profile,mods)
    damage=weapon_damage_preparation(use,strength,resilience,actor_mounted=pc_is_mounted(state,actor),charging=False)
    if damage.damage is None:return 0.0
    impact=DamageImpactSpec(damage.damage,resilience,damage.ignores_armour,damage.modifiers,
        magical_source=damage.magical_source)
    base=damage.damage.base+sum(mod.amount for mod in effective_damage_modifiers(impact))
    continuation=_impact_value(_distribution(test),_distribution(defence),base,
        resilience.toughness if effective_ignores_armour(impact) else resilience.total,
        damage.damage.success_multiplier,True,
        defender_wins_ties=musician_defends_ties(state,target))
    # Releasing a working Shield has a real defensive opportunity cost.
    continuation=max(0.0,continuation-(.1 if selected.release_shield else 0.0))
    trigger=0.0
    for successes,chance in enumerate(attack):
        if not successes:continue
        for opposed,other in enumerate(protection[:successes+1]):
            if not pc_attack_success_wins(state,actor,target,successes,opposed):continue
            if parent_damage is None or parent_damage[0]+(successes-opposed)*parent_damage[1]<=parent_damage[2]:
                trigger+=chance*other
    return trigger*continuation
