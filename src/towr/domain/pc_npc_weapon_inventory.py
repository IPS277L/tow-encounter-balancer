"""Generated NPC equipment choices and source-bound incidental transitions."""
from towr.domain.injury_models import injury_is_defeated
from dataclasses import dataclass,replace
from towr.domain.pc_musician_effect_models import musician_defends_ties

from towr.domain.condition_models import Condition
from towr.domain.weapon_catalog import WeaponGroup,WeaponKind,weapon_profile
from towr.domain.weapon_inventory_models import WeaponGrip,WeaponItemLocation
from towr.domain.weapon_equip_models import WeaponEquipTransition,plan_weapon_equip
from towr.domain.weapon_use_models import build_weapon_use,build_weapon_protection_use
from towr.domain.test_models import Skill


def npc_selected_weapon_profile(state,actor):
    enemy=state.enemy(actor)
    source=enemy.definition.generated_components
    if source is None:return None
    inventory=enemy.state.weapon_inventory
    item=None if inventory is None else inventory.active
    if item is None or item.location is not WeaponItemLocation.HELD:
        if source.brawn is not None:
            from towr.domain.generated_npc_models import generated_unarmed_attack_profile
            return generated_unarmed_attack_profile(source)
        if item is None:return None
    from towr.domain.generated_npc_models import generated_weapon_attack_profile
    grip=item.grip or item.source.initial_grip
    if grip is None:
        from towr.domain.ranged_weapon_profiles import RangedWeaponHands
        grip=(WeaponGrip.BOTH if weapon_profile(item.kind).hands is RangedWeaponHands.TWO_HANDED else WeaponGrip.LEFT)
    return generated_weapon_attack_profile(source,item.source_item_id,grip)


def _usable_npc_grips(state,enemy):
    from towr.domain.injury_models import CharacterInjuryState
    if type(enemy.state.injury) is CharacterInjuryState:
        from towr.domain.pc_medical_models import medical_effective_body
        from towr.domain.pc_heavy_wound_models import usable_hands
        body=medical_effective_body(state,enemy.state.actor_id)
        available=tuple(WeaponGrip(hand.value) for hand in usable_hands(body))
    else:
        available=(WeaponGrip.LEFT,WeaponGrip.RIGHT)
    return tuple(hand for hand in available
        if hand not in enemy.state.tool_inventory.occupied_hands)


def npc_has_working_shield(state,actor):
    enemy=state.enemy(actor)
    if not enemy.state.holds_shield:
        return False
    from towr.domain.injury_models import CharacterInjuryState
    if type(enemy.state.injury) is not CharacterInjuryState:
        return True
    inventory=enemy.state.weapon_inventory
    return inventory is not None and inventory.shield_hand in _usable_npc_grips(state,enemy)


def npc_attack_weapon_use(state,actor,target=None):
    enemy=state.enemy(actor)
    if enemy.definition.generated_components is None:return None
    inventory=enemy.state.weapon_inventory
    primary=None if inventory is None else inventory.active
    if primary is None or primary.location is not WeaponItemLocation.HELD:
        return build_weapon_use(actor,inventory,None,usable_hands=_usable_npc_grips(state,enemy)) if enemy.definition.generated_components.brawn is not None else None
    from towr.domain.pc_armour_models import actor_bound_to_chivalric_combat
    if (weapon_profile(primary.kind).group in (WeaponGroup.SHOOTING,WeaponGroup.THROWING)
            and actor_bound_to_chivalric_combat(state,actor)):
        return None
    try:base=build_weapon_use(actor,inventory,primary.id,usable_hands=_usable_npc_grips(state,enemy))
    except ValueError:return None
    from towr.domain.weapon_effect_preparation import weapon_test_modifiers,weapon_damage_preparation
    from towr.domain.pc_shield_models import pc_shield_resilience
    from towr.domain.pc_mount_models import pc_is_mounted
    from towr.domain.pc_actor_models import pc_actor_npc_snapshot
    from towr.domain.pc_medical_models import effective_medical_injury
    conditions=None if target is None else effective_medical_injury(state,target).conditions
    actor_conditions=effective_medical_injury(state,actor).conditions
    resilience=(None if target is None else pc_shield_resilience(state,target)
        if target in state.source.pc_activation_order else pc_actor_npc_snapshot(state,target).state.current_resilience)
    def value(use):
        mods=weapon_test_modifiers(use,actor_conditions,target_conditions=conditions,
            target_mounted=target is not None and pc_is_mounted(state,target),
            talents=enemy.definition.generated_components.talents).modifiers
        prepared=None if resilience is None else weapon_damage_preparation(use,
            enemy.definition.generated_components.strength,resilience)
        from towr.domain.pc_magic_weapon_models import magic_contributor_value
        return sum(mod.amount for mod in mods if mod.amount<0 or not actor_conditions.has(Condition.DRAINED))*.25+(
            0 if prepared is None else sum(mod.amount for mod in prepared.modifiers))+(
                0 if target is None else magic_contributor_value(state,use,target))
    best,score=base,value(base)
    for item in inventory.items:
        if item.id==primary.id or item.location is not WeaponItemLocation.HELD:continue
        try:use=build_weapon_use(actor,inventory,primary.id,(item.id,),_usable_npc_grips(state,enemy))
        except ValueError:continue
        candidate=value(use)
        if candidate>score+1e-12:best,score=use,candidate
    return best


def npc_protection_weapon_use(state,actor,skill,attack_skill=Skill.MELEE):
    enemy=state.enemy(actor);inventory=enemy.state.weapon_inventory
    from towr.domain.pc_medical_models import effective_medical_injury
    actor_conditions=effective_medical_injury(state,actor).conditions
    if inventory is None or skill not in (Skill.DEFENCE,Skill.MELEE):return None
    held=tuple(item.id for item in inventory.items if item.location is WeaponItemLocation.HELD)
    shield=npc_has_working_shield(state,actor)
    if skill is Skill.DEFENCE and attack_skill in (Skill.SHOOTING,Skill.THROWING):
        if not shield:return None
    candidates=(held, *((identifier,) for identifier in held), ())
    from towr.domain.weapon_effect_preparation import weapon_test_modifiers
    best=None;score=float('-inf')
    for ids in candidates:
        try:use=build_weapon_protection_use(actor,inventory,skill,ids,shield,_usable_npc_grips(state,enemy))
        except ValueError:continue
        source=enemy.definition.generated_components
        mods=weapon_test_modifiers(use,actor_conditions,
            talents=() if source is None else source.talents).modifiers
        value=sum(mod.amount for mod in mods if mod.amount<0 or not actor_conditions.has(Condition.DRAINED))
        if value>score:best,score=use,value
    return best


@dataclass(frozen=True,slots=True)
class _NpcInventoryView:
    previous: object
    enemies: tuple
    def __getattr__(self,name):return getattr(self.previous,name)
    def enemy(self,actor):return next(enemy for enemy in self.enemies if enemy.state.actor_id==actor)
    @property
    def live_enemies(self):
        return tuple(enemy for enemy in self.enemies if not injury_is_defeated(enemy.state.injury)
            and enemy.state.actor_id not in self.exited_npc_ids)


def _view(state,actor,inventory):
    enemy=state.enemy(actor)
    armed=any(item.location is WeaponItemLocation.HELD for item in inventory.items)
    changed=replace(enemy,state=replace(enemy.state,weapon_inventory=inventory,wields_weapon=armed,
        holds_shield=inventory.shield_hand is not None,
        available_attack_ids=npc_inventory_attack_ids(enemy.definition,inventory)))
    return _NpcInventoryView(state,tuple(changed if old.state.actor_id==actor else old for old in state.enemies))


def npc_inventory_attack_ids(definition,inventory):
    held=inventory is not None and any(item.location is WeaponItemLocation.HELD for item in inventory.items)
    return tuple(profile.id for profile in definition.attacks if held or profile.hands is None)


def _plan(state,actor,item,grip,*,reload=False):
    inventory=state.enemy(actor).state.weapon_inventory
    usable=_usable_npc_grips(state,state.enemy(actor))
    if reload and len(usable)!=2:
        raise ValueError('Reload cannot use a hand occupied by an actual instrument')
    needed={WeaponGrip.LEFT,WeaponGrip.RIGHT} if grip is WeaponGrip.BOTH else {grip}
    held=tuple((other.id,other.grip) for other in inventory.items
        if not reload and other.id!=item.id and other.location is WeaponItemLocation.HELD
        and not needed.intersection((WeaponGrip.LEFT,WeaponGrip.RIGHT)
            if other.grip is WeaponGrip.BOTH else (other.grip,)))
    if ((item.id,grip),*held)==tuple((other.id,other.grip) for other in inventory.items
            if other.location is WeaponItemLocation.HELD) and inventory.active_item_id==item.id:
        return None
    transition=plan_weapon_equip(actor,state.round_state.round_number,inventory,
        held_items=((item.id,grip),*held),active_item_id=item.id,
        usable_hands=usable)
    for binding in state.briarroot_bindings:
        from towr.domain.pc_briarroot_models import BriarrootWeaponKind
        if (binding.attacker_id==actor and binding.kind is BriarrootWeaponKind.HELD
                and transition.after.item(binding.weapon_id).location is not WeaponItemLocation.HELD):
            raise ValueError('an NPC cannot stow its actually Briarroot-bound weapon')
    return transition


def _utility(view,actor,*,help_successes=0,aim_bonus=0,ignore_aim=False):
    from towr.domain.pc_oath_models import npc_oath_attack_blocked
    if npc_oath_attack_blocked(view, actor):
        return -1.0
    from towr.domain.pc_battlefield_movement_models import pc_battlefield_attack_available
    from towr.domain.pc_npc_ranged_models import pc_npc_ranged_weapon
    from towr.domain.reload_models import ranged_weapon_is_loaded
    from towr.domain.pc_tactical_models import _distribution,_impact_value
    from towr.domain.pc_generated_ranged_advice import pc_shooting_protection
    from towr.domain.pc_melee_result_models import _pc_test,pc_protection_skill
    from towr.domain.pc_shield_models import pc_shield_resilience
    from towr.domain.weapon_effect_preparation import weapon_test_modifiers,weapon_damage_preparation
    from towr.domain.pc_mount_models import pc_is_mounted
    from towr.domain.test_models import TestRequest, DiceModifier
    profile=npc_selected_weapon_profile(view,actor)
    from towr.domain.pc_battlefield_movement_models import _enemies
    target=next(iter(_enemies(view,actor)),None)
    if profile is None or target is None:return -1.0
    use=npc_attack_weapon_use(view,actor,target)
    if use is None:return -1.0
    # Movement is a genuine subsequent transition. A melee approach is useful;
    # a Close-forbidden shot cannot be manufactured in the stationary scene.
    available=pc_battlefield_attack_available(view,actor,target)
    if not available and (profile.skill not in (Skill.MELEE,Skill.BRAWN,Skill.THROWING) or view.battlefield is None):return -1.0
    from towr.domain.pc_medical_models import effective_medical_injury,medical_effective_body
    enemy=view.enemy(actor);member=medical_effective_body(view,target)
    actor_conditions=effective_medical_injury(view,actor).conditions
    mods=weapon_test_modifiers(use,actor_conditions,
        target_conditions=member.injury.conditions,target_mounted=pc_is_mounted(view,target),
        talents=enemy.definition.generated_components.talents).modifiers
    if actor_conditions.has(Condition.DRAINED):mods=tuple(mod for mod in mods if mod.amount<=0)
    if help_successes and not actor_conditions.has(Condition.DRAINED):
        from towr.domain.help_models import HELP_BONUS_RULE_ID
        mods=(*mods,DiceModifier(HELP_BONUS_RULE_ID,help_successes))
    if profile.skill in (Skill.SHOOTING, Skill.THROWING) and not actor_conditions.has(Condition.DRAINED):
        from towr.domain.aim_models import AIM_FOLLOW_UP_RULE_ID
        from towr.domain.pc_npc_aim_models import npc_aim_attack_modifiers
        if aim_bonus:
            mods = (*mods, DiceModifier(AIM_FOLLOW_UP_RULE_ID, aim_bonus))
        elif not ignore_aim:
            mods = (*mods, *npc_aim_attack_modifiers(view, actor, target))
    attacker=TestRequest('tactics:npc-inventory',profile.test_profile,mods)
    target_is_pc=target in view.source.pc_activation_order
    if not target_is_pc:
        from towr.domain.pc_generated_equipment import npc_protection_test
        _,protection=npc_protection_test(view,target,actor,'tactics:npc-inventory:defence',attack_skill=profile.skill)
    elif profile.skill in (Skill.SHOOTING,Skill.THROWING):
        _,protection=pc_shooting_protection(view,target,actor,'tactics:npc-inventory:defence',attack_skill=profile.skill)
    elif profile.skill is Skill.BRAWN and view.source.participant(target).policy.value=='automatic_combat':
        from towr.domain.pc_generated_ranged_advice import pc_brawn_protection
        _,protection=pc_brawn_protection(view,target,'tactics:npc-inventory:defence')
    else:
        skill=pc_protection_skill(member,profile.skill)
        protection=_pc_test(view,target,'tactics:npc-inventory:defence',skill,oppose_attack=True,
            incoming_attack_skill=profile.skill)
    opposed=(1.0,) if member.injury.conditions.has(Condition.DEFENCELESS) else _distribution(protection)
    if use.kind is WeaponKind.UNARMED:
        from towr.domain.pc_tactical_models import stagger_attack_value
        from towr.domain.pc_bash_advice import bash_follow_up_value
        return (stagger_attack_value(_distribution(attacker),opposed,
            member.injury.conditions.has(Condition.STAGGERED),
            defender_wins_ties=musician_defends_ties(view,target))
            +bash_follow_up_value(view,actor,target,_distribution(attacker),opposed))*(1 if available else .5)
    if profile.skill is Skill.THROWING:
        from towr.domain.pc_weapon_area_models import throwing_special_value
        special=throwing_special_value(view,actor,target,use.kind,_distribution(attacker),opposed)
        if special is not None:return special
    resilience=(pc_shield_resilience(view,target) if target_is_pc else view.enemy(target).state.current_resilience)
    damage=weapon_damage_preparation(use,enemy.definition.generated_components.strength,resilience)
    value=_impact_value(_distribution(attacker),opposed,
        damage.damage.base+sum(mod.amount for mod in damage.modifiers),
        resilience.toughness if damage.ignores_armour and not resilience.mundane_armour_ward else resilience.total,
        damage.damage.success_multiplier,member.injury.conditions.has(Condition.STAGGERED),
        member.injury.conditions.has(Condition.DEFENCELESS),
        defender_wins_ties=musician_defends_ties(view,target))
    if profile.skill is Skill.BRAWN:
        from towr.domain.pc_bash_advice import bash_follow_up_value
        value+=bash_follow_up_value(view,actor,target,_distribution(attacker),opposed,
            parent_damage=(damage.damage.base+sum(mod.amount for mod in damage.modifiers),
                damage.damage.success_multiplier,resilience.total))
    if profile.skill is Skill.SHOOTING:
        weapon=pc_npc_ranged_weapon(view,actor)
        if not ranged_weapon_is_loaded(weapon):
            facts=enemy.definition.generated_components
            remaining=max(1,weapon.required_successes-weapon.exacting.accumulated_successes)
            mean=facts.initiative*facts.dexterity/10
            value/=1+remaining/max(mean,.1)
    return value if available else value*.5


@dataclass(frozen=True,slots=True)
class PcNpcWeaponEquipProof:
    transition: WeaponEquipTransition
    @property
    def actor_id(self):return self.transition.actor_id
    def __post_init__(self):
        if type(self.transition) is not WeaponEquipTransition:raise TypeError('NPC equip needs its exact transition')
        replace(self.transition)


def expected_npc_weapon_equip(state):
    from towr.domain.pc_medical_tactics import committed_medical_intent
    if committed_medical_intent(state) is not None:return None
    from towr.domain.pc_bash_attack_models import expected_bash_npc_equip
    bash=expected_bash_npc_equip(state)
    if bash is not None:return bash
    turn=state.round_state.active_turn
    if (turn is None or turn.actor_id not in state.source.npc_activation_order or turn.action_slots
            or state.pending or state.pending_wound is not None or state.magic_pending is not None):return None
    actor=turn.actor_id;enemy=state.enemy(actor);inventory=enemy.state.weapon_inventory
    from towr.domain.pc_medical_models import effective_medical_injury
    actor_conditions=effective_medical_injury(state,actor).conditions
    if actor_conditions.has(Condition.BROKEN):
        return None
    if (enemy.definition.generated_components is None or inventory is None or injury_is_defeated(enemy.state.injury)
            or any(actor_conditions.has(condition) for condition in (Condition.DEFENCELESS,Condition.BROKEN))):return None
    if (len(inventory.items)==1 and inventory.active is not None
            and inventory.active.location is WeaponItemLocation.HELD
            and not weapon_profile(inventory.active.kind).variable_grip
            and enemy.definition.generated_components.brawn is None):
        return None  # No alternative item or grip can require an equip transition.
    from towr.domain.turn_models import CombatTurnStartResult
    for proof in reversed(state.history):
        if type(proof) is CombatTurnStartResult:break
        if type(proof) is PcNpcWeaponEquipProof and proof.actor_id==actor:return None
    # Source order and current selection break exact utility ties.
    best=None;value=_utility(state,actor)
    if enemy.definition.generated_components.brawn is not None and inventory.active_item_id is not None:
        unarmed=replace(inventory,active_item_id=None)
        candidate=_utility(_view(state,actor,unarmed),actor)
        if candidate>value+1e-12:
            best=WeaponEquipTransition(actor,state.round_state.round_number,inventory,unarmed)
            value=candidate
    from towr.domain.ranged_weapon_profiles import RangedWeaponHands
    for item in inventory.items:
        if item.location not in (WeaponItemLocation.HELD,WeaponItemLocation.CARRIED):continue
        profile=weapon_profile(item.kind)
        grips=((WeaponGrip.BOTH,WeaponGrip.LEFT,WeaponGrip.RIGHT) if profile.variable_grip else
            (WeaponGrip.BOTH,) if profile.hands is RangedWeaponHands.TWO_HANDED else
            (item.grip,WeaponGrip.LEFT,WeaponGrip.RIGHT) if item.grip is not None else (WeaponGrip.LEFT,WeaponGrip.RIGHT))
        for grip in dict.fromkeys(grips):
            empty=item.reload is not None and not item.reload.loaded
            try:plan=_plan(state,actor,item,grip,reload=empty)
            except ValueError:continue
            if plan is None:continue
            candidate=_utility(_view(state,actor,plan.after),actor)
            # Reload really needs a free other hand even at an equal score.
            prepare_reload=(item.id==inventory.active_item_id and empty and plan.changes_equipment)
            if candidate>value+1e-12 or prepare_reload and candidate>=value-1e-12:
                best,value=plan,candidate
    return None if best is None else PcNpcWeaponEquipProof(best)


def apply_npc_weapon_equip(state,proof):
    expected=expected_npc_weapon_equip(state)
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    if expected is None or proof!=expected:raise ValueError('NPC equip changed its actual selected source/turn')
    validate_pc_melee_source_types(proof,expected)
    return _view(state,proof.actor_id,proof.transition.after).enemies


def npc_shield_release_weapon(state):
    """Propose a weapon-first release; its physical receipt belongs to Shield."""
    turn=state.round_state.active_turn
    if turn is None or turn.actor_id not in state.source.npc_activation_order:return None
    actor=turn.actor_id;enemy=state.enemy(actor);inventory=enemy.state.weapon_inventory
    if inventory is None or not enemy.state.holds_shield:return None
    without=_view(state,actor,replace(inventory,shield_hand=None))
    proposed=expected_npc_weapon_equip(without)
    if proposed is None:return None
    selected=proposed.transition.after.active
    if selected is None or selected.grip is not WeaponGrip.BOTH:return None
    if _utility(_view(without,actor,proposed.transition.after),actor)<=_utility(state,actor)+1e-12:return None
    return inventory.item(selected.id)
