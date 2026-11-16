"""Actual PC weapon locations and source-bound reversible incidental swaps."""
from __future__ import annotations

from dataclasses import dataclass,replace
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition
from towr.domain.pc_combat_equipment_models import (
    PcItemLocation,PcWeaponItem,PcWeaponInventoryState,validate_pc_weapon_inventory,
    validate_pc_combat_equipment,
)

if TYPE_CHECKING:
    from towr.domain.pc_tactical_models import PcTacticalChoice


@dataclass(frozen=True,slots=True)
class PcWeaponSwapProof:
    actor_id: str
    action_id: str
    previous: PcWeaponInventoryState
    state: PcWeaponInventoryState
    intent: PcTacticalChoice

    def __post_init__(self):
        from towr.domain.pc_tactical_models import PcTacticalChoice
        if any(type(v) is not str or not v.strip() for v in (self.actor_id,self.action_id)):
            raise TypeError('weapon swap needs exact actor/action identifiers')
        if type(self.previous) is not PcWeaponInventoryState or type(self.state) is not PcWeaponInventoryState:
            raise TypeError('weapon swap needs its actual typed before/after inventories')
        replace(self.previous);replace(self.state)
        if type(self.intent) is not PcTacticalChoice or self.intent.actor_id!=self.actor_id:
            raise TypeError('weapon swap must commit the actual actor tactical choice')
        if getattr(self.intent,'weapon_item_id',None)!=self.state.active_item_id:
            raise ValueError('weapon swap must commit its actual next weapon item')
        if self.previous.active_item_id==self.state.active_item_id:
            raise ValueError('weapon swap must change the active item')
        if tuple((i.id,i.weapon) for i in self.previous.items)!=tuple((i.id,i.weapon) for i in self.state.items):
            raise ValueError('weapon swap cannot change source item membership')
        incoming=next(i for i in self.previous.items if i.id==self.state.active_item_id)
        if incoming.location is not PcItemLocation.CARRIED or self.state.active.location is not PcItemLocation.HELD:
            raise ValueError('free swap only draws an actually carried item')
        for before,after in zip(self.previous.items,self.state.items,strict=True):
            if before.id==incoming.id:
                continue
            expected=(replace(before,location=PcItemLocation.CARRIED,hand=None)
                if before.location is PcItemLocation.HELD else before)
            if after!=expected:
                raise ValueError('weapon swap may only stow an actually held previous weapon')


def initial_pc_weapon_inventory(source):
    validate_pc_combat_equipment(source)
    items=getattr(source,'combat_equipment',None)
    return None if items is None else PcWeaponInventoryState(items,items[0].id)


def sync_pc_weapon_inventory(before_member,after_member,source):
    """Mirror actual drop/recover/legacy draw updates without inventing pickup.

    Called by the owning projection after it has validated the actual action.
    An explicit inventory transition is checked, rather than overwritten.
    """
    inventory=getattr(before_member,'weapon_inventory',None)
    if inventory is None:
        if getattr(after_member,'weapon_inventory',None) is not None:
            validate_pc_weapon_inventory(after_member,source)
        return after_member
    if after_member.weapon_inventory!=inventory:
        validate_pc_weapon_inventory(after_member,source)
        return after_member
    initial=source.combat_equipment
    if type(after_member.using_backup_weapon) is not bool or (after_member.using_backup_weapon and len(initial)!=2):
        raise ValueError('backup mirror requires its actual second source item')
    active=initial[1].id if after_member.using_backup_weapon else initial[0].id
    items=[]
    for item in inventory.items:
        if item.id==active:
            if after_member.weapon_hand is not None:
                item=replace(item,location=PcItemLocation.HELD,hand=after_member.weapon_hand)
            elif item.location is PcItemLocation.HELD:
                item=replace(item,location=PcItemLocation.DROPPED,hand=None)
        elif item.location is PcItemLocation.HELD:
            item=replace(item,location=PcItemLocation.CARRIED,hand=None)
        items.append(item)
    result=replace(after_member,weapon_inventory=PcWeaponInventoryState(tuple(items),active))
    validate_pc_weapon_inventory(result,source)
    return result


def pc_weapon_swap_used(state,actor_id):
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    action=pc_melee_action_id(state,actor_id)
    return any(type(proof) is PcWeaponSwapProof and proof.actor_id==actor_id
        and proof.action_id==action for proof in state.history)


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
    from towr.domain.pc_weapon_models import pc_weapon_requires_two_hands
    member=state.participant(actor_id)
    inventory=getattr(member,'weapon_inventory',None)
    if inventory is None:
        return None
    item=next((item for item in inventory.items if item.id==item_id),None)
    if item is None:
        return None
    hands=usable_hands(member)
    if pc_weapon_requires_two_hands(item.weapon):
        return PcTwoHandedGrip.BOTH if len(hands)==2 else None
    source=state.source.participant(actor_id)
    preferred=(source.initial_weapon_hand if item.id==source.combat_equipment[0].id
        else source.backup_weapon_policy.preferred_hand)
    order=(preferred,*(side for side in PcWeaponHand if side is not preferred))
    shield=(member.shield.hand if member.shield is not None
        and member.shield.location is PcShieldLocation.HELD else None)
    injured=injured_hands(member)
    return next((side for occupied,hurt in ((False,False),(True,False),(False,True),(True,True))
        for side in order if side in hands and (side==shield)==occupied and (side in injured)==hurt),None)


def _swapped_member(state,actor_id,item_id,*,forecast,allow_dropped=False):
    from towr.domain.pc_shield_models import PcShieldLocation,PcShieldState
    from towr.domain.pc_melee_models import PcTwoHandedGrip
    member=state.participant(actor_id)
    inventory=getattr(member,'weapon_inventory',None)
    if inventory is None:
        return None
    target=next((item for item in inventory.items if item.id==item_id),None)
    if target is None or (target.location is PcItemLocation.DROPPED and not allow_dropped):
        return None
    hand=pc_weapon_swap_hand(state,actor_id,item_id)
    if hand is None:
        return None
    shield=member.shield
    if shield is not None and shield.location is PcShieldLocation.HELD and (hand is PcTwoHandedGrip.BOTH or hand is shield.hand):
        if not forecast:
            return None
        shield=PcShieldState(PcShieldLocation.DROPPED,None)
    items=tuple(replace(item,location=PcItemLocation.HELD,hand=hand) if item.id==item_id else
        replace(item,location=PcItemLocation.CARRIED,hand=None) if item.location is PcItemLocation.HELD else item
        for item in inventory.items)
    result=replace(member,weapon_hand=hand,using_backup_weapon=item_id!=state.source.participant(actor_id).combat_equipment[0].id,
        weapon_inventory=PcWeaponInventoryState(items,item_id),shield=shield)
    validate_pc_weapon_inventory(result,state.source.participant(actor_id))
    return result


def pc_weapon_inventory_view(state,actor_id,item_id):
    """Prepared carry→held view for advice; no history, resource or RNG mutation."""
    member=state.participant(actor_id)
    inventory=getattr(member,'weapon_inventory',None)
    if inventory is None:
        return None
    if inventory.active_item_id==item_id:
        return state
    if pc_weapon_swap_used(state,actor_id):
        return None
    view=_swapped_member(state,actor_id,item_id,forecast=True)
    return None if view is None else replace(state,party=tuple(view if m.actor_id==actor_id else m for m in state.party))


def pc_weapon_pickup_view(state,actor_id,item_id):
    """Prepared *after Recover* view; callers must charge the real action.

    Unlike a free carry swap this explicitly values a dropped item. It never
    supplies a swap proof and cannot make that item eligible for free draw.
    """
    member=state.participant(actor_id)
    inventory=getattr(member,'weapon_inventory',None)
    if inventory is None or not any(item.id==item_id and item.location is PcItemLocation.DROPPED
            for item in inventory.items):
        return None
    view=_swapped_member(state,actor_id,item_id,forecast=True,allow_dropped=True)
    return None if view is None else replace(state,party=tuple(view if m.actor_id==actor_id else m for m in state.party))


def pc_weapon_pickup_member(state,actor_id,item_id,*,injury=None):
    """Actual after-Recover item interaction, called by its validated owner.

    Drawing the item from the ground costs the caller's Recover action. If a
    different held weapon must first be stowed, that incidental hand use still
    has the ordinary W12/14/15 consequences. No stow price exists if none was
    actually held; ordinary Recover hand effects remain the caller's job.
    """
    from towr.domain.pc_heavy_wound_models import critical_for_incidental_hand_use
    member=state.participant(actor_id)
    inventory=getattr(member,'weapon_inventory',None)
    if inventory is None or not any(item.id==item_id and item.location is PcItemLocation.DROPPED
            for item in inventory.items):
        return None
    updated=_swapped_member(state,actor_id,item_id,forecast=False,allow_dropped=True)
    if updated is None:
        return None
    if injury is not None:
        updated=replace(updated,injury=injury)
    if any(item.location is PcItemLocation.HELD and item.id!=item_id for item in inventory.items):
        updated=replace(updated,injury=critical_for_incidental_hand_use(
            replace(member,injury=updated.injury),updated.weapon_hand))
    return updated


def expected_pc_weapon_swap(state):
    from towr.domain.pc_melee_models import PcMeleePolicy,PC_RANGED_WEAPONS
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    from towr.domain.pc_tactical_models import select_pc_tactic
    turn=state.round_state.active_turn
    if (turn is None or turn.actor_id not in state.source.pc_activation_order or turn.action_slots
            or state.pending or state.pending_wound is not None or state.magic_pending is not None
            or not state.live_enemies):
        return None
    actor=turn.actor_id
    source=state.source.participant(actor)
    member=state.participant(actor)
    inventory=getattr(member,'weapon_inventory',None)
    if (source.policy is not PcMeleePolicy.AUTOMATIC_COMBAT or source.pc.weapon not in PC_RANGED_WEAPONS
            or inventory is None or member.injury.dead or member.injury.conditions.has(Condition.DEFENCELESS)
            or pc_weapon_swap_used(state,actor)):
        return None
    intent=select_pc_tactic(state,actor)
    item=getattr(intent,'weapon_item_id',None)
    if item is None or item==inventory.active_item_id:
        return None
    swapped=_swapped_member(state,actor,item,forecast=False)
    return None if swapped is None else PcWeaponSwapProof(actor,pc_melee_action_id(state,actor),inventory,
        swapped.weapon_inventory,intent)


def apply_pc_weapon_swap(state,proof):
    from towr.domain.pc_heavy_wound_models import critical_for_incidental_hand_use
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    if type(proof) is not PcWeaponSwapProof:
        raise TypeError('weapon swap requires its exact proof type')
    replace(proof)
    expected=expected_pc_weapon_swap(state)
    if expected is None or proof!=expected:
        raise ValueError('weapon swap changed its actual source, item, hand or committed intent')
    validate_pc_melee_source_types(proof,expected)
    member=_swapped_member(state,proof.actor_id,proof.state.active_item_id,forecast=False)
    injury=critical_for_incidental_hand_use(member,member.weapon_hand)
    return replace(member,injury=injury)
