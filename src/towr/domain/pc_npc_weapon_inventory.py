"""Generated NPC equipment choices and source-bound incidental transitions."""
from dataclasses import dataclass,replace

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
    if item is None:return None
    from towr.domain.generated_npc_models import generated_weapon_attack_profile
    grip=item.grip or item.source.initial_grip
    if grip is None:
        from towr.domain.ranged_weapon_profiles import RangedWeaponHands
        grip=(WeaponGrip.BOTH if weapon_profile(item.kind).hands is RangedWeaponHands.TWO_HANDED else WeaponGrip.LEFT)
    return generated_weapon_attack_profile(source,item.source_item_id,grip)


def npc_attack_weapon_use(state,actor,target=None):
    enemy=state.enemy(actor)
    inventory=enemy.state.weapon_inventory
    primary=None if inventory is None else inventory.active
    if primary is None or primary.location is not WeaponItemLocation.HELD:return None
    from towr.domain.pc_armour_models import actor_bound_to_chivalric_combat
    if (weapon_profile(primary.kind).group in (WeaponGroup.SHOOTING,WeaponGroup.THROWING)
            and actor_bound_to_chivalric_combat(state,actor)):
        return None
    try:base=build_weapon_use(actor,inventory,primary.id)
    except ValueError:return None
    from towr.domain.weapon_effect_preparation import weapon_test_modifiers,weapon_damage_preparation
    from towr.domain.pc_shield_models import pc_shield_resilience
    from towr.domain.pc_mount_models import pc_is_mounted
    conditions=None if target is None else state.participant(target).injury.conditions
    resilience=None if target is None else pc_shield_resilience(state,target)
    def value(use):
        mods=weapon_test_modifiers(use,enemy.state.injury.conditions,target_conditions=conditions,
            target_mounted=target is not None and pc_is_mounted(state,target)).modifiers
        prepared=None if resilience is None else weapon_damage_preparation(use,
            enemy.definition.generated_components.strength,resilience)
        return sum(mod.amount for mod in mods if mod.amount<0 or not enemy.state.injury.conditions.has(Condition.DRAINED))*.25+(
            0 if prepared is None else sum(mod.amount for mod in prepared.modifiers))
    best,score=base,value(base)
    for item in inventory.items:
        if item.id==primary.id or item.location is not WeaponItemLocation.HELD:continue
        try:use=build_weapon_use(actor,inventory,primary.id,(item.id,))
        except ValueError:continue
        candidate=value(use)
        if candidate>score+1e-12:best,score=use,candidate
    return best


def npc_protection_weapon_use(state,actor,skill,attack_skill=Skill.MELEE):
    enemy=state.enemy(actor);inventory=enemy.state.weapon_inventory
    if inventory is None or skill not in (Skill.DEFENCE,Skill.MELEE):return None
    held=tuple(item.id for item in inventory.items if item.location is WeaponItemLocation.HELD)
    shield=enemy.state.holds_shield
    if skill is Skill.DEFENCE and attack_skill in (Skill.SHOOTING,Skill.THROWING):
        if not shield:return None
    candidates=(held, *((identifier,) for identifier in held), ())
    from towr.domain.weapon_effect_preparation import weapon_test_modifiers
    best=None;score=float('-inf')
    for ids in candidates:
        try:use=build_weapon_protection_use(actor,inventory,skill,ids,shield)
        except ValueError:continue
        mods=weapon_test_modifiers(use,enemy.state.injury.conditions).modifiers
        value=sum(mod.amount for mod in mods if mod.amount<0 or not enemy.state.injury.conditions.has(Condition.DRAINED))
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
        return tuple(enemy for enemy in self.enemies if not enemy.state.injury.defeated
            and enemy.state.actor_id not in self.exited_npc_ids)


def _view(state,actor,inventory):
    enemy=state.enemy(actor)
    armed=any(item.location is WeaponItemLocation.HELD for item in inventory.items)
    changed=replace(enemy,state=replace(enemy.state,weapon_inventory=inventory,wields_weapon=armed,
        holds_shield=inventory.shield_hand is not None,
        available_attack_ids=tuple(profile.id for profile in enemy.definition.attacks) if armed else ()))
    return _NpcInventoryView(state,tuple(changed if old.state.actor_id==actor else old for old in state.enemies))


def _plan(state,actor,item,grip,*,reload=False):
    inventory=state.enemy(actor).state.weapon_inventory
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
        usable_hands=(WeaponGrip.LEFT,WeaponGrip.RIGHT))
    for binding in state.briarroot_bindings:
        from towr.domain.pc_briarroot_models import BriarrootWeaponKind
        if (binding.attacker_id==actor and binding.kind is BriarrootWeaponKind.HELD
                and transition.after.item(binding.weapon_id).location is not WeaponItemLocation.HELD):
            raise ValueError('an NPC cannot stow its actually Briarroot-bound weapon')
    return transition


def _utility(view,actor):
    from towr.domain.pc_battlefield_movement_models import pc_battlefield_attack_available
    from towr.domain.pc_npc_ranged_models import pc_npc_ranged_weapon
    from towr.domain.reload_models import ranged_weapon_is_loaded
    from towr.domain.pc_tactical_models import _distribution,_impact_value
    from towr.domain.pc_generated_ranged_advice import pc_shooting_protection
    from towr.domain.pc_melee_result_models import _pc_test,pc_protection_skill
    from towr.domain.pc_shield_models import pc_shield_resilience
    from towr.domain.weapon_effect_preparation import weapon_test_modifiers,weapon_damage_preparation
    from towr.domain.pc_mount_models import pc_is_mounted
    from towr.domain.test_models import TestRequest
    profile=npc_selected_weapon_profile(view,actor)
    target=next((target for target in view.source.enemy_target_priority
        if not view.participant(target).injury.dead),None)
    if profile is None or target is None:return -1.0
    use=npc_attack_weapon_use(view,actor,target)
    if use is None:return -1.0
    # Movement is a genuine subsequent transition. A melee approach is useful;
    # a Close-forbidden shot cannot be manufactured in the stationary scene.
    available=pc_battlefield_attack_available(view,actor,target)
    if not available and (profile.skill is not Skill.MELEE or view.battlefield is None):return -1.0
    enemy=view.enemy(actor);member=view.participant(target)
    mods=weapon_test_modifiers(use,enemy.state.injury.conditions,
        target_conditions=member.injury.conditions,target_mounted=pc_is_mounted(view,target)).modifiers
    if enemy.state.injury.conditions.has(Condition.DRAINED):mods=tuple(mod for mod in mods if mod.amount<=0)
    attacker=TestRequest('tactics:npc-inventory',profile.test_profile,mods)
    if profile.skill in (Skill.SHOOTING,Skill.THROWING):
        _,protection=pc_shooting_protection(view,target,actor,'tactics:npc-inventory:defence')
    else:
        skill=pc_protection_skill(member,profile.skill)
        protection=_pc_test(view,target,'tactics:npc-inventory:defence',skill,oppose_attack=True,
            incoming_attack_skill=profile.skill)
    opposed=(1.0,) if member.injury.conditions.has(Condition.DEFENCELESS) else _distribution(protection)
    if profile.skill is Skill.THROWING:
        return .2*sum(chance*sum(opposed[:successes+1]) for successes,chance in enumerate(_distribution(attacker))
            if successes) if not member.injury.conditions.has(Condition.BURDENED) else 0.0
    resilience=pc_shield_resilience(view,target)
    damage=weapon_damage_preparation(use,enemy.definition.generated_components.strength,resilience)
    value=_impact_value(_distribution(attacker),opposed,
        damage.damage.base+sum(mod.amount for mod in damage.modifiers),
        resilience.toughness if damage.ignores_armour and not resilience.mundane_armour_ward else resilience.total,
        damage.damage.success_multiplier,member.injury.conditions.has(Condition.STAGGERED),
        member.injury.conditions.has(Condition.DEFENCELESS))
    if profile.skill is Skill.SHOOTING:
        weapon=pc_npc_ranged_weapon(view,actor)
        if not ranged_weapon_is_loaded(weapon):
            facts=enemy.definition.generated_components.ranged
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
    turn=state.round_state.active_turn
    if (turn is None or turn.actor_id not in state.source.enemy_activation_order or turn.action_slots
            or state.pending or state.pending_wound is not None or state.magic_pending is not None):return None
    actor=turn.actor_id;enemy=state.enemy(actor);inventory=enemy.state.weapon_inventory
    if (enemy.definition.generated_components is None or inventory is None or enemy.state.injury.defeated
            or any(enemy.state.injury.conditions.has(condition) for condition in (Condition.DEFENCELESS,Condition.BROKEN))):return None
    if len(inventory.items)==1 and inventory.active.location is WeaponItemLocation.HELD and not weapon_profile(inventory.active.kind).variable_grip:
        return None  # No alternative item or grip can require an equip transition.
    from towr.domain.turn_models import CombatTurnStartResult
    for proof in reversed(state.history):
        if type(proof) is CombatTurnStartResult:break
        if type(proof) is PcNpcWeaponEquipProof and proof.actor_id==actor:return None
    # Source order and current selection break exact utility ties.
    best=None;value=_utility(state,actor)
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
    if turn is None or turn.actor_id not in state.source.enemy_activation_order:return None
    actor=turn.actor_id;enemy=state.enemy(actor);inventory=enemy.state.weapon_inventory
    if inventory is None or not enemy.state.holds_shield:return None
    without=_view(state,actor,replace(inventory,shield_hand=None))
    proposed=expected_npc_weapon_equip(without)
    if proposed is None:return None
    selected=proposed.transition.after.active
    if selected.grip is not WeaponGrip.BOTH:return None
    if _utility(_view(without,actor,proposed.transition.after),actor)<=_utility(state,actor)+1e-12:return None
    return inventory.item(selected.id)
