"""Actual PC weapon locations and source-bound reversible incidental swaps."""
from __future__ import annotations

from dataclasses import dataclass,replace,field
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition
from towr.domain.pc_combat_equipment_models import (
    PcItemLocation as SourceItemLocation, PcWeaponItem, validate_pc_weapon_inventory,
)

from towr.domain.weapon_inventory_models import (
    WeaponGrip, WeaponItemLocation, WeaponItemSource, WeaponInventoryState,
    initial_weapon_inventory, weapon_reload_target,
)
from towr.domain.weapon_catalog import WeaponKind, WeaponGroup, weapon_profile

if TYPE_CHECKING:
    from towr.domain.pc_tactical_models import PcTacticalChoice


@dataclass(frozen=True,slots=True)
class PcWeaponSwapProof:
    actor_id: str
    action_id: str
    previous: WeaponInventoryState
    state: WeaponInventoryState
    intent: PcTacticalChoice
    round_number: int = field(kw_only=True)

    def __post_init__(self):
        from towr.domain.pc_tactical_models import PcTacticalChoice
        if any(type(v) is not str or not v.strip() for v in (self.actor_id,self.action_id)):
            raise TypeError('weapon swap needs exact actor/action identifiers')
        if type(self.previous) is not WeaponInventoryState or type(self.state) is not WeaponInventoryState:
            raise TypeError('weapon swap needs its actual typed before/after inventories')
        replace(self.previous);replace(self.state)
        if type(self.intent) is not PcTacticalChoice or self.intent.actor_id!=self.actor_id:
            raise TypeError('weapon swap must commit the actual actor tactical choice')
        if getattr(self.intent,'weapon_item_id',None)!=self.state.active_item_id:
            raise ValueError('weapon swap must commit its actual next weapon item')
        from towr.domain.weapon_equip_models import WeaponEquipTransition
        WeaponEquipTransition(self.actor_id,self.round_number,self.previous,self.state)
        if self.previous==self.state:
            raise ValueError('equip must change actual equipment or selection')

    @property
    def changes_equipment(self):
        return any((a.location,a.grip)!=(b.location,b.grip)
            for a,b in zip(self.previous.items,self.state.items,strict=True))


def pc_grip(hand):
    from towr.domain.pc_melee_models import PcWeaponHand, PcTwoHandedGrip
    if hand is None:
        return None
    if hand is PcTwoHandedGrip.BOTH:
        return WeaponGrip.BOTH
    if type(hand) is not PcWeaponHand:
        raise TypeError('a weapon grip requires its actual PC hand')
    return WeaponGrip(hand.value)


def pc_hand(grip):
    from towr.domain.pc_melee_models import PcWeaponHand, PcTwoHandedGrip
    if grip is None:
        return None
    if type(grip) is not WeaponGrip:
        raise TypeError('a PC hand view requires its actual weapon grip')
    return PcTwoHandedGrip.BOTH if grip is WeaponGrip.BOTH else PcWeaponHand(grip.value)


def pc_item_weapon(item):
    from towr.domain.pc_melee_models import PcMeleeWeapon
    return PcMeleeWeapon(item.kind.value)


def initial_pc_weapon_inventory(source):
    """Compile immutable initial facts once; never synchronize from runtime flags."""
    from towr.domain.pc_melee_models import PcMeleeWeapon
    items = source.combat_equipment
    if items is None:
        items = (() if source.pc.weapon is PcMeleeWeapon.UNARMED else
            (PcWeaponItem('weapon',source.pc.weapon,SourceItemLocation.HELD,source.initial_weapon_hand),))
        if source.backup_weapon_policy is not None:
            items += (PcWeaponItem('backup-weapon',source.backup_weapon_policy.weapon,
                SourceItemLocation.CARRIED,None),)
    primary = next((item for item in items if item.location is SourceItemLocation.HELD),None)
    sources=[]
    for item in items:
        kind=WeaponKind(item.weapon.value)
        sources.append(WeaponItemSource(item.id,kind,WeaponItemLocation(item.location.value),
            pc_grip(item.hand),quantity=item.quantity,initially_loaded=item.initially_loaded,
            initial_charges=item.initial_charges,gm_fit_confirmed=item.gm_fit_confirmed))
    shield=None if source.shield is None else pc_grip(source.shield.initial_hand)
    inventory=initial_weapon_inventory(source.actor_id,tuple(sources),shield_hand=shield)
    selected=(None if primary is None else next(unit.id for unit in inventory.items if unit.source_item_id==primary.id))
    return replace(inventory,active_item_id=selected)


def pc_member_ranged(member,item_id=None):
    """Read-only K1 resource view, without asserting that the unit is usable.

    The selected Shooting unit takes precedence. Otherwise the first Shooting
    unit witnesses retained source membership, including a stowed or dropped
    gun. Action decisions must additionally check the actual selected weapon.
    """
    from towr.domain.reload_models import FreeReloadWeaponState
    from towr.domain.ranged_weapon_profiles import RangedWeaponId
    inventory=member.weapon_inventory
    item=(inventory.item(item_id) if item_id is not None else inventory.active)
    if item is None or weapon_profile(item.kind).group is not WeaponGroup.SHOOTING:
        if item_id is not None:
            return None
        item=next((unit for unit in inventory.items
            if weapon_profile(unit.kind).group is WeaponGroup.SHOOTING),None)
    if item is None:
        return None
    return item.reload if item.reload is not None else FreeReloadWeaponState(item.id,RangedWeaponId(item.kind.value))


def replace_pc_member(member, **changes):
    """Apply an owner's checked item/Shield changes atomically.

    Location and resources live only in the inventory. Hand and ranged kwargs
    are commands from validated proof owners, never independent state fields.
    """
    from towr.domain.pc_shield_models import PcShieldLocation
    from towr.domain.reload_models import ReloadableWeaponState, FreeReloadWeaponState
    inventory=changes.pop('weapon_inventory',member.weapon_inventory)
    if type(inventory) is not WeaponInventoryState:
        raise TypeError('PC equipment update requires its actual common inventory')
    identity=lambda value: tuple((item.id,item.source,item.initial_actor_id,item.source_item_id,item.unit_index)
        for item in value.items)
    if identity(inventory)!=identity(member.weapon_inventory):
        raise ValueError('an equipment update cannot replace source membership')
    items=list(inventory.items)
    if 'using_backup_weapon' in changes:
        raise TypeError('select the actual inventory item, not a backup flag')
    if 'ranged' in changes:
        ranged=changes.pop('ranged')
        if type(ranged) not in (ReloadableWeaponState,FreeReloadWeaponState):
            raise TypeError('a ranged update must retain its real K1 resource source')
        item=inventory.item(ranged.weapon_instance_id)
        if ranged.weapon_id.value!=item.kind.value:
            raise ValueError('ranged update belongs to a different physical weapon')
        inventory=inventory.with_item(replace(item,reload=ranged if type(ranged) is ReloadableWeaponState else None))
        items=list(inventory.items)
    if 'weapon_hand' in changes:
        hand=changes.pop('weapon_hand')
        selected=inventory.active
        if selected is None:
            raise ValueError('a hand update requires its selected physical item')
        grip=pc_grip(hand)
        location=(WeaponItemLocation.HELD if grip is not None else
            WeaponItemLocation.DROPPED if selected.location is WeaponItemLocation.HELD else selected.location)
        items=[replace(item,grip=grip,location=location) if item.id==selected.id else item for item in items]
    shield=changes.get('shield',member.shield)
    shield_hand=(None if shield is None or shield.location is PcShieldLocation.DROPPED else pc_grip(shield.hand))
    inventory=WeaponInventoryState(tuple(items),inventory.active_item_id,shield_hand)
    return replace(member,weapon_inventory=inventory,**changes)


def drop_pc_weapons_in_hand(member,side):
    """A wound drops every actual item held by the affected anatomical hand."""
    grip=pc_grip(side)
    items=tuple(replace(item,location=WeaponItemLocation.DROPPED,grip=None)
        if item.location is WeaponItemLocation.HELD and item.grip in (grip,WeaponGrip.BOTH)
        else item for item in member.weapon_inventory.items)
    return replace_pc_member(member,weapon_inventory=replace(member.weapon_inventory,items=items))


def equipment_usable_hands(member):
    """Anatomical hands left available by actual held non-weapon tools."""
    from towr.domain.pc_heavy_wound_models import usable_hands
    occupied = member.tool_inventory.occupied_hands
    return tuple(side for side in usable_hands(member) if WeaponGrip(side.value) not in occupied)


def _usable_pc_grips(member):
    return tuple(WeaponGrip(side.value) for side in equipment_usable_hands(member))


def pc_attack_weapon_use(state,actor,target=None):
    """Select actual Attack contributors; a spare hand is not an automatic bonus."""
    from towr.domain.weapon_use_models import build_weapon_use
    from towr.domain.weapon_effect_preparation import weapon_test_modifiers,weapon_damage_preparation
    from towr.domain.pc_heavy_wound_models import injured_hands
    from towr.domain.pc_mount_models import pc_is_mounted
    from towr.domain.pc_potion_models import pc_effective_definition
    from towr.domain.attack_models import DamageImpactSpec,effective_damage_modifiers
    from towr.domain.pc_medical_models import medical_effective_body
    member=medical_effective_body(state,actor)
    inventory=member.weapon_inventory
    primary=inventory.active
    if primary is None or primary.location is not WeaponItemLocation.HELD:
        return (build_weapon_use(actor,inventory,None,usable_hands=_usable_pc_grips(member))
            if state.source.participant(actor).pc.brawn is not None else None)
    from towr.domain.pc_armour_models import actor_bound_to_chivalric_combat
    if (weapon_profile(primary.kind).group in (WeaponGroup.SHOOTING,WeaponGroup.THROWING)
            and actor_bound_to_chivalric_combat(state,actor)):
        return None
    try:
        base=build_weapon_use(actor,inventory,primary.id,usable_hands=_usable_pc_grips(member))
    except ValueError:
        return (build_weapon_use(actor,inventory,None,usable_hands=_usable_pc_grips(member))
            if state.source.participant(actor).pc.brawn is not None else None)
    if target is None or target not in state.source.npc_activation_order:
        return base
    enemy=state.enemy(target)
    from towr.domain.pc_medical_models import effective_medical_injury
    target_conditions=effective_medical_injury(state,target).conditions
    pc=pc_effective_definition(state,actor)
    injured={WeaponGrip(hand.value) for hand in injured_hands(member)}
    def value(use):
        dice=weapon_test_modifiers(use,member.injury.conditions,
            target_conditions=target_conditions,target_mounted=pc_is_mounted(state,target),
            talents=state.source.participant(actor).talents).modifiers
        prepared=weapon_damage_preparation(use,pc.strength,enemy.state.current_resilience)
        damage=(() if prepared.damage is None else effective_damage_modifiers(DamageImpactSpec(
            prepared.damage,enemy.state.current_resilience,damage_modifiers=prepared.modifiers,
            magical_source=prepared.magical_source)))
        bonuses=sum(mod.amount for mod in dice if mod.amount<0 or not member.injury.conditions.has(Condition.DRAINED))
        from towr.domain.pc_magic_weapon_models import magic_contributor_value
        return (.25*bonuses+sum(mod.amount for mod in damage)-len(injured & set(use.used_hands))
            +magic_contributor_value(state,use,target))
    best,best_value=base,value(base)
    for item in inventory.items:
        if item.id==primary.id or item.location is not WeaponItemLocation.HELD:
            continue
        try:
            candidate=build_weapon_use(actor,inventory,primary.id,(item.id,),_usable_pc_grips(member))
        except ValueError:
            continue
        score=value(candidate)
        if score>best_value+1e-12:
            best,best_value=candidate,score
    return best


def pc_protection_weapon_use(member,skill,attack_skill=None,*,talents=()):
    """Prepare Defence implements independently from the selected Attack item."""
    from towr.domain.weapon_use_models import build_weapon_protection_use
    from towr.domain.weapon_effect_preparation import weapon_test_modifiers
    from towr.domain.pc_heavy_wound_models import injured_hands
    from towr.domain.pc_shield_models import pc_has_working_shield
    from towr.domain.test_models import Skill
    if skill not in (Skill.DEFENCE,Skill.MELEE):
        return None
    inventory=member.weapon_inventory
    shield=pc_has_working_shield(member)
    required_shield=skill is Skill.DEFENCE and attack_skill in (Skill.SHOOTING,Skill.THROWING)
    if required_shield and not shield:
        return None
    usable=_usable_pc_grips(member)
    held=tuple(item.id for item in inventory.items if item.location is WeaponItemLocation.HELD
        and all(side in usable for side in ((WeaponGrip.LEFT,WeaponGrip.RIGHT)
            if item.grip is WeaponGrip.BOTH else (item.grip,))))
    # The admitted Close-Shooting tactic uses a usable held implement, then
    # falls back to an unarmed Melee counter only when none is available.
    # An empty use must not silently evade that implement's printed penalties
    # or the actual injured-hand consequences.
    sets=[*(((),) if skill is Skill.DEFENCE or not held else ()),
        *((identifier,) for identifier in held)]
    if len(held)==2:
        sets.append(held)
    injured={WeaponGrip(side.value) for side in injured_hands(member)}
    best=None
    best_score=None
    for ids in sets:
        use_shield=required_shield or (not ids and shield and skill is Skill.DEFENCE)
        try:
            candidate=build_weapon_protection_use(member.actor_id,inventory,skill,ids,use_shield,usable)
        except ValueError:
            continue
        modifiers=weapon_test_modifiers(candidate,member.injury.conditions,talents=talents).modifiers
        delta=sum(mod.amount for mod in modifiers if mod.amount<0 or not member.injury.conditions.has(Condition.DRAINED))
        score=(.25*delta-len(injured & set(candidate.used_hands)),-len(candidate.used_hands))
        if best_score is None or score>best_score:
            best,best_score=candidate,score
    return best


def pc_weapon_target_modifiers(use,target_conditions,*,target_mounted=False):
    from towr.domain.weapon_effect_preparation import weapon_kind_target_test_modifiers
    from towr.domain.test_models import DiceModifier
    totals={}
    for item_id in use.item_ids:
        for modifier in weapon_kind_target_test_modifiers(use.inventory.item(item_id).kind,
                use.skill,target_conditions,target_mounted=target_mounted):
            totals[modifier.rule_id]=totals.get(modifier.rule_id,0)+modifier.amount
    return tuple(DiceModifier(rule,amount) for rule,amount in totals.items() if amount)


def pc_weapon_swap_used(state,actor_id):
    from towr.domain.pc_medical_equipment_models import PcMedicalEquipmentProof
    return any(type(proof) in (PcWeaponSwapProof,PcMedicalEquipmentProof) and proof.actor_id==actor_id
        and proof.round_number==state.round_state.round_number and proof.changes_equipment
        for proof in state.history)


def pending_pc_weapon_swap(state,actor_id=None):
    from towr.domain.pc_shield_models import PcShieldReleaseProof
    turn=state.round_state.active_turn
    if turn is None:
        return None
    actor_id=turn.actor_id if actor_id is None else actor_id
    if actor_id!=turn.actor_id or any(slot.executed for slot in turn.action_slots):
        return None
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    action=pc_melee_action_id(state,actor_id)
    return next((proof for proof in reversed(state.history)
        if getattr(proof,'actor_id',None)==actor_id and (
            type(proof) is PcWeaponSwapProof and proof.action_id==action
            or type(proof) is PcShieldReleaseProof and proof.action_id==action+':shield:release'
                and proof.intent is not None)),None)


def pc_weapon_swap_hand(state,actor_id,item_id):
    """Prefer a healthy available hand; release a Shield before injured use."""
    from towr.domain.pc_heavy_wound_models import usable_hands,injured_hands
    from towr.domain.pc_melee_models import PcWeaponHand,PcTwoHandedGrip
    from towr.domain.pc_shield_models import PcShieldLocation
    from towr.domain.pc_weapon_models import pc_weapon_requires_two_hands, pc_weapon_supports_variable_grip
    from towr.domain.pc_medical_models import medical_effective_body
    member=medical_effective_body(state,actor_id)
    inventory=getattr(member,'weapon_inventory',None)
    if inventory is None:
        return None
    item=next((item for item in inventory.items if item.id==item_id),None)
    if item is None:
        return None
    hands=equipment_usable_hands(member)
    if pc_weapon_requires_two_hands(pc_item_weapon(item)):
        return PcTwoHandedGrip.BOTH if len(hands)==2 else None
    source=state.source.participant(actor_id)
    preferred=(pc_hand(item.grip) or (source.backup_weapon_policy.preferred_hand
        if source.backup_weapon_policy is not None and pc_item_weapon(item) is source.backup_weapon_policy.weapon
        else source.initial_weapon_hand))
    if pc_weapon_supports_variable_grip(pc_item_weapon(item)):
        from towr.domain.pc_backup_weapon_models import preferred_variable_weapon_hand
        candidate=preferred_variable_weapon_hand(member,preferred)
        if candidate is PcTwoHandedGrip.BOTH and len(hands)==2 or candidate in hands:
            return candidate
        shield=(member.shield.hand if member.shield is not None
            and member.shield.location is PcShieldLocation.HELD else None)
        return next((side for pool in (tuple(side for side in hands if side is not shield
            and side not in injured_hands(member)),hands) for side in (preferred,*PcWeaponHand) if side in pool),None)
    order=(preferred,*(side for side in PcWeaponHand if side is not preferred))
    shield=(member.shield.hand if member.shield is not None
        and member.shield.location is PcShieldLocation.HELD else None)
    injured=injured_hands(member)
    return next((side for occupied,hurt in ((False,False),(True,False),(False,True),(True,True))
        for side in order if side in hands and (side==shield)==occupied and (side in injured)==hurt),None)


def _swapped_member(state,actor_id,item_id,*,forecast,allow_dropped=False,for_reload=False,
        stow_other_weapons=False):
    from towr.domain.pc_shield_models import PcShieldLocation,PcShieldState
    from towr.domain.pc_melee_models import PcTwoHandedGrip
    raw_member=state.participant(actor_id)
    from towr.domain.pc_medical_models import medical_effective_body
    member=medical_effective_body(state,actor_id)
    inventory=getattr(member,'weapon_inventory',None)
    if inventory is None:
        return None
    if item_id is None:
        if state.source.participant(actor_id).pc.brawn is None or for_reload:
            return None
        return replace_pc_member(raw_member,weapon_inventory=replace(inventory,active_item_id=None))
    target=next((item for item in inventory.items if item.id==item_id),None)
    if (target is None or target.location is WeaponItemLocation.DEPLOYED
            or (target.location is WeaponItemLocation.DROPPED and not allow_dropped)):
        return None
    from towr.domain.pc_heavy_wound_models import usable_hands
    usable=_usable_pc_grips(member)
    if target.location is WeaponItemLocation.HELD:
        needed=(WeaponGrip.LEFT,WeaponGrip.RIGHT) if target.grip is WeaponGrip.BOTH else (target.grip,)
        if all(side in usable for side in needed) and not for_reload and not stow_other_weapons:
            return replace(raw_member,weapon_inventory=replace(inventory,active_item_id=item_id))
    hand=pc_weapon_swap_hand(state,actor_id,item_id)
    if hand is None:
        return None
    grip=pc_grip(hand)
    if for_reload and len(usable)!=2:
        return None
    occupied={WeaponGrip.LEFT,WeaponGrip.RIGHT} if grip is WeaponGrip.BOTH or for_reload else {grip}
    shield=member.shield
    if for_reload and shield is not None and shield.location is PcShieldLocation.UNAVAILABLE:
        return None
    if shield is not None and shield.location is PcShieldLocation.HELD and pc_grip(shield.hand) in occupied:
        if not forecast:
            return None
        shield=PcShieldState(PcShieldLocation.DROPPED,None)
    trapped={binding.weapon_id for binding in getattr(state,'briarroot_bindings',())
        if binding.attacker_id==actor_id}
    items=[]
    for item in inventory.items:
        if item.id==item_id:
            item=replace(item,location=WeaponItemLocation.HELD,grip=grip)
        elif item.location is WeaponItemLocation.HELD:
            item_hands={WeaponGrip.LEFT,WeaponGrip.RIGHT} if item.grip is WeaponGrip.BOTH else {item.grip}
            if stow_other_weapons or item_hands & occupied:
                if item.id in trapped:
                    return None
                item=replace(item,location=WeaponItemLocation.CARRIED,grip=None)
        items.append(item)
    result=replace_pc_member(raw_member,weapon_inventory=WeaponInventoryState(tuple(items),item_id,
        None if shield is None or shield.location is PcShieldLocation.DROPPED else pc_grip(shield.hand)),shield=shield)
    validate_pc_weapon_inventory(result,state.source.participant(actor_id))
    return result


def pc_weapon_inventory_view(state,actor_id,item_id,*,for_reload=False,future_turn=False):
    """Prepared carry→held view for advice; no history, resource or RNG mutation."""
    member=state.participant(actor_id)
    inventory=getattr(member,'weapon_inventory',None)
    if inventory is None:
        return None
    if inventory.active_item_id==item_id and not for_reload:
        return state
    if item_id is not None and not future_turn and pc_weapon_swap_used(state,actor_id) and inventory.item(item_id).location is not WeaponItemLocation.HELD:
        return None
    view=_swapped_member(state,actor_id,item_id,forecast=True,for_reload=for_reload)
    if view is None:
        return None
    physical=any((a.location,a.grip)!=(b.location,b.grip) for a,b in zip(inventory.items,view.weapon_inventory.items,strict=True))
    if physical and not future_turn and pc_weapon_swap_used(state,actor_id):
        return None
    party=tuple(view if m.actor_id==actor_id else m for m in state.party)
    base=state.base if type(state) is _PcInventoryAdviceView else state
    return _PcInventoryAdviceView(base,party)


@dataclass(frozen=True,slots=True)
class _PcInventoryAdviceView:
    base: object
    party: tuple

    def __getattr__(self,name):
        return getattr(self.base,name)

    def participant(self,actor_id):
        return next(member for member in self.party if member.actor_id==actor_id)

    @property
    def live_party(self):
        return tuple(member for member in self.party if not member.injury.dead)


def pc_weapon_pickup_view(state,actor_id,item_id):
    """Prepared *after Recover* view; callers must charge the real action.

    Unlike a free carry swap this explicitly values a dropped item. It never
    supplies a swap proof and cannot make that item eligible for free draw.
    """
    member=state.participant(actor_id)
    from towr.domain.pc_briarroot_weapon_models import can_pickup_pc_weapon
    if not can_pickup_pc_weapon(state,actor_id,item_id):
        return None
    inventory=getattr(member,'weapon_inventory',None)
    if inventory is None or not any(item.id==item_id and item.location is WeaponItemLocation.DROPPED
            for item in inventory.items):
        return None
    view=_swapped_member(state,actor_id,item_id,forecast=True,allow_dropped=True)
    if view is None:
        return None
    party = tuple(view if m.actor_id == actor_id else m for m in state.party)
    base = state.base if type(state) is _PcInventoryAdviceView else state
    return _PcInventoryAdviceView(base, party)


def pc_weapon_pickup_member(state,actor_id,item_id,*,injury=None):
    """Actual after-Recover item interaction, called by its validated owner.

    Drawing the item from the ground costs the caller's Recover action. If a
    different held weapon must first be stowed, that incidental hand use still
    has the ordinary W12/14/15 consequences. No stow price exists if none was
    actually held; ordinary Recover hand effects remain the caller's job.
    """
    from towr.domain.pc_heavy_wound_models import critical_for_incidental_hand_use,merge_effective_critical_consequences
    from towr.domain.pc_medical_models import medical_effective_body
    member=state.participant(actor_id)
    from towr.domain.pc_briarroot_weapon_models import can_pickup_pc_weapon
    if not can_pickup_pc_weapon(state,actor_id,item_id):
        return None
    inventory=getattr(member,'weapon_inventory',None)
    if inventory is None or not any(item.id==item_id and item.location is WeaponItemLocation.DROPPED
            for item in inventory.items):
        return None
    updated=_swapped_member(state,actor_id,item_id,forecast=False,allow_dropped=True)
    if updated is None:
        return None
    if injury is not None:
        updated=replace(updated,injury=injury)
    if any(item.location is WeaponItemLocation.HELD and item.id!=item_id for item in inventory.items):
        effective=medical_effective_body(state,actor_id)
        after=critical_for_incidental_hand_use(effective,updated.weapon_hand)
        updated=replace(updated,injury=merge_effective_critical_consequences(updated.injury,after))
    return updated


def expected_pc_weapon_swap(state):
    from towr.domain.pc_medical_tactics import committed_medical_intent
    if committed_medical_intent(state) is not None:return None
    from towr.domain.pc_bash_attack_models import expected_bash_pc_swap
    bash=expected_bash_pc_swap(state)
    if bash is not None:return bash
    from towr.domain.pc_melee_models import PcMeleePolicy,PC_RANGED_WEAPONS,PC_THROWING_WEAPONS
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    from towr.domain.pc_tactical_models import select_pc_tactic
    turn=state.round_state.active_turn
    if (turn is None or turn.actor_id not in state.source.pc_activation_order or turn.action_slots
            or state.pending or state.pending_wound is not None or state.magic_pending is not None
            or not state.live_enemies):
        return None
    actor=turn.actor_id
    source=state.source.participant(actor)
    from towr.domain.pc_medical_models import medical_effective_body
    member=medical_effective_body(state,actor)
    inventory=getattr(member,'weapon_inventory',None)
    if inventory is None or member.injury.dead or any(member.injury.conditions.has(c)
            for c in (Condition.DEFENCELESS,Condition.BROKEN)):
        return None
    if source.policy is PcMeleePolicy.AUTOMATIC_COMBAT:
        intent=select_pc_tactic(state,actor)
    else:
        from towr.domain.pc_melee_result_models import _pc_recover_needed
        from towr.domain.pc_tactical_models import PcTacticalChoice
        from towr.domain.reload_models import ReloadableWeaponState
        from towr.domain.turn_models import CombatActionKind
        from towr.domain.pc_heavy_wound_models import usable_hands
        item=inventory.active
        # A fixed Shoot/Reload policy still owns a real inventory. Preparing
        # its already-selected Reload may stow another held implement; it does
        # not choose a different weapon or invent a second action.
        if (item is None or item.location is not WeaponItemLocation.HELD
                or type(item.reload) is not ReloadableWeaponState or item.reload.loaded
                or len(usable_hands(member))!=2 or _pc_recover_needed(member)
                or not any(other.id!=item.id and other.location is WeaponItemLocation.HELD
                    for other in inventory.items)):
            return None
        intent=PcTacticalChoice(actor,CombatActionKind.IMPROVISE,actor,None,0.0,
            'prepare_fixed_reload_hands',weapon_item_id=item.id,ranged_reload=True)
    item=getattr(intent,'weapon_item_id',None)
    if item is None:
        if not intent.unarmed_attack or inventory.active_item_id is None:
            return None
        swapped=_swapped_member(state,actor,None,forecast=False)
        return None if swapped is None else PcWeaponSwapProof(actor,pc_melee_action_id(state,actor),inventory,
            swapped.weapon_inventory,intent,round_number=state.round_state.round_number)
    if pc_weapon_swap_used(state,actor) and inventory.item(item).location is not WeaponItemLocation.HELD:
        return None
    swapped=_swapped_member(state,actor,item,forecast=False,for_reload=intent.ranged_reload)
    return None if swapped is None or swapped.weapon_inventory==inventory else PcWeaponSwapProof(actor,pc_melee_action_id(state,actor),inventory,
        swapped.weapon_inventory,intent,round_number=state.round_state.round_number)


def apply_pc_weapon_swap(state,proof):
    from towr.domain.pc_heavy_wound_models import critical_for_incidental_hand_use,merge_effective_critical_consequences
    from towr.domain.pc_medical_models import medical_effective_body
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    if type(proof) is not PcWeaponSwapProof:
        raise TypeError('weapon swap requires its exact proof type')
    replace(proof)
    expected=expected_pc_weapon_swap(state)
    if expected is None or proof!=expected:
        raise ValueError('weapon swap changed its actual source, item, hand or committed intent')
    validate_pc_melee_source_types(proof,expected)
    if proof.intent.reason=='bash_immediate':
        from towr.domain.pc_bash_attack_models import apply_bash_pc_swap
        return apply_bash_pc_swap(state,proof)
    member=_swapped_member(state,proof.actor_id,proof.state.active_item_id,forecast=False,for_reload=proof.intent.ranged_reload)
    if not proof.changes_equipment:
        return member
    touched={hand for before,after in zip(proof.previous.items,proof.state.items,strict=True)
        if (before.location,before.grip)!=(after.location,after.grip)
        for grip in (before.grip,after.grip) if grip is not None
        for hand in ((WeaponGrip.LEFT,WeaponGrip.RIGHT) if grip is WeaponGrip.BOTH else (grip,))}
    used=pc_hand(WeaponGrip.BOTH if len(touched)==2 else next(iter(touched)))
    effective=medical_effective_body(state,proof.actor_id)
    injury=merge_effective_critical_consequences(member.injury,critical_for_incidental_hand_use(effective,used))
    return replace(member,injury=injury)
