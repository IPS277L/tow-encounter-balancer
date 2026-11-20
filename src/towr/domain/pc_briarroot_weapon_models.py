"""Finite ordinary weapon drops and Briarroot abandonment, with real positions.

The binding remains a separate cause bank. Dropping a held weapon records its
actual inventory transition and a static ground marker; the binding owner then
settles its mandatory release. Natural weapons never enter this item bank.
"""
from __future__ import annotations
from towr.domain.pc_acrobatic_models import actor_acrobatic_source
from towr.domain.pc_movement_block_models import pc_enemy_path_blockers

from dataclasses import dataclass,field,replace
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition
from towr.domain.magic_models import WizardMagicState
from towr.domain.movement_models import FreeMovementRequest,FreeMovementResult
from towr.domain.pc_battlefield_models import (
    PcBattlefieldState,battlefield_range,with_actor_placement,battlefield_ground_below,
)
from towr.domain.pc_briarroot_models import BriarrootWeaponKind,briarroot_movement_keeps_close
from towr.domain.weapon_inventory_models import WeaponItemLocation as PcItemLocation, WeaponInventoryState,WeaponGrip
from towr.domain.weapon_catalog import weapon_profile
from towr.domain.ranged_weapon_profiles import RangedWeaponHands
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.recover_models import (
    RecoverActionExecutionRequest,RecoverActionExecutionResult,RecoverConditionTarget,
    RecoverMode,RecoverObjectInteractionFollowUp,RecoverStandardChoice,RecoverStandardResult,
    _expected_recover_execution,
)
from towr.domain.spatial_models import SpatialEntityPlacement
from towr.domain.turn_models import CombatActionKind,CombatRoundState
from towr.rules.free_movement_resolution import resolve_free_movement

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcMeleeParticipantState
    from towr.domain.npc_roster_models import NpcParticipantSnapshot


def _id(value):
    if type(value) is not str or not value.strip():
        raise TypeError('physical Briarroot weapon requires exact nonempty identifiers')


@dataclass(frozen=True,slots=True)
class PcBriarrootWeaponGround:
    zone_id: str
    initial_close_actor_ids: tuple[str,...]

    def __post_init__(self):
        _id(self.zone_id)
        if type(self.initial_close_actor_ids) is not tuple:
            raise TypeError('ground position requires its exact ordered Close actor tuple')
        for actor in self.initial_close_actor_ids:
            _id(actor)
        if len(set(self.initial_close_actor_ids))!=len(self.initial_close_actor_ids):
            raise ValueError('ground position cannot duplicate a Close actor')


@dataclass(frozen=True,slots=True)
class PcBriarrootDroppedWeapon:
    owner_id: str
    weapon_id: str
    ground: PcBriarrootWeaponGround | None
    available_attack_ids: tuple[str,...] = ()

    def __post_init__(self):
        _id(self.owner_id); _id(self.weapon_id)
        if self.ground is not None:
            if type(self.ground) is not PcBriarrootWeaponGround:
                raise TypeError('dropped weapon requires its actual typed ground position')
            replace(self.ground)
        if type(self.available_attack_ids) is not tuple:
            raise TypeError('a weapon retains its exact ordered pre-drop attack tuple')
        for identifier in self.available_attack_ids:
            _id(identifier)
        if len(set(self.available_attack_ids))!=len(self.available_attack_ids):
            raise ValueError('a dropped weapon cannot duplicate its actual available attacks')

    @property
    def marker_id(self):
        return (f'object:briarroot-weapon:{len(self.owner_id)}:{self.owner_id}:'
            f'{len(self.weapon_id)}:{self.weapon_id}')


@dataclass(frozen=True,slots=True)
class PcBriarrootWeaponDropProof:
    id: str
    history_index: int
    actor_id: str
    weapon_id: str
    binding_ids: tuple[str,...]
    previous_item: PcBriarrootDroppedWeapon | None
    item: PcBriarrootDroppedWeapon
    previous: PcBattlefieldState | None
    state: PcBattlefieldState | None
    previous_actor: PcMeleeParticipantState | NpcParticipantSnapshot = field(repr=False)
    actor: PcMeleeParticipantState | NpcParticipantSnapshot = field(repr=False)
    loss_witness_history_index: int | None = None
    loss_witness: object | None = field(default=None,repr=False)

    def __post_init__(self):
        for value in (self.id,self.actor_id,self.weapon_id):
            _id(value)
        if type(self.history_index) is not int or self.history_index<0:
            raise ValueError('weapon drop requires its exact source history position')
        if type(self.binding_ids) is not tuple or len(set(self.binding_ids))!=len(self.binding_ids):
            raise TypeError('weapon drop requires its exact distinct binding tuple')
        for binding in self.binding_ids:
            _id(binding)
        if type(self.item) is not PcBriarrootDroppedWeapon or self.item.ground is None:
            raise TypeError('weapon drop must produce one actual finite ground item')
        replace(self.item)
        if self.previous_item is not None:
            if type(self.previous_item) is not PcBriarrootDroppedWeapon:
                raise TypeError('weapon drop previous item must retain its exact type')
            replace(self.previous_item)
            if self.previous_item.ground is not None:
                raise ValueError('a weapon already on the ground cannot be dropped again')
        if (self.item.owner_id,self.item.weapon_id)!=(self.actor_id,self.weapon_id):
            raise ValueError('weapon drop changed its physical source identity')
        for actor in (self.previous_actor,self.actor):
            from towr.domain.pc_melee_result_models import PcMeleeParticipantState
            from towr.domain.npc_roster_models import NpcParticipantSnapshot
            if type(actor) not in (PcMeleeParticipantState,NpcParticipantSnapshot):
                raise TypeError('weapon drop requires its exact before/after combat actor snapshots')
            replace(actor)
        if type(self.previous_actor) is not type(self.actor):
            raise TypeError('weapon abandonment cannot change the kind of its source owner')
        if type(self.previous_actor) is NpcParticipantSnapshot:
            if (self.previous_actor.state.actor_id!=self.actor_id or self.actor.state.actor_id!=self.actor_id
                    or self.item.available_attack_ids!=self.previous_actor.state.available_attack_ids
                    or self.actor.definition!=self.previous_actor.definition):
                raise ValueError('NPC weapon abandonment changed its actual source attacks or identity')
            if self.loss_witness is None and self.actor != _npc_drop_snapshot(self.previous_actor,self.weapon_id):
                raise ValueError('NPC abandonment must drop only its actual physical unit')
        else:
            if (self.previous_actor.actor_id!=self.actor_id or self.actor.actor_id!=self.actor_id
                    or self.item.available_attack_ids):
                raise ValueError('PC weapon abandonment changed its actual source identity')
            if (self.actor.ranged!=self.previous_actor.ranged or self.actor.magic!=self.previous_actor.magic
                    or self.actor.fate!=self.previous_actor.fate):
                raise ValueError('abandoning a weapon cannot refill charges, magic or Fate')
        if self.loss_witness is None:
            if self.loss_witness_history_index is not None:
                raise ValueError('voluntary abandonment cannot invent a forced-loss witness')
        elif (type(self.loss_witness_history_index) is not int
                or not 0<=self.loss_witness_history_index<self.history_index
                or self.previous_actor!=self.actor):
            raise ValueError('forced-loss acknowledgement must retain its actual settled actor')


@dataclass(frozen=True,slots=True)
class PcBriarrootWeaponPickup:
    action_id: str
    actor_id: str
    weapon_id: str
    previous_item: PcBriarrootDroppedWeapon
    item: PcBriarrootDroppedWeapon
    previous: PcBattlefieldState | None
    state: PcBattlefieldState | None

    def __post_init__(self):
        for value in (self.action_id,self.actor_id,self.weapon_id):
            _id(value)
        for item in (self.previous_item,self.item):
            if type(item) is not PcBriarrootDroppedWeapon:
                raise TypeError('weapon pickup retains its exact finite item states')
            replace(item)
        if (self.previous_item.ground is None or self.item.ground is not None
                or self.item!=replace(self.previous_item,ground=None)
                or (self.item.owner_id,self.item.weapon_id)!=(self.actor_id,self.weapon_id)):
            raise ValueError('weapon pickup must recover the same one actual ground item')


@dataclass(frozen=True,slots=True)
class PcBriarrootWeaponPickupProof:
    request: RecoverActionExecutionRequest
    result: RecoverActionExecutionResult
    pickup: PcBriarrootWeaponPickup
    previous_actor: NpcParticipantSnapshot = field(repr=False)
    actor: NpcParticipantSnapshot = field(repr=False)

    def __post_init__(self):
        from towr.domain.npc_roster_models import NpcParticipantSnapshot
        if (type(self.request) is not RecoverActionExecutionRequest
                or type(self.result) is not RecoverActionExecutionResult
                or type(self.pickup) is not PcBriarrootWeaponPickup
                or type(self.previous_actor) is not NpcParticipantSnapshot
                or type(self.actor) is not NpcParticipantSnapshot):
            raise TypeError('NPC weapon pickup requires its exact Recover/item/actor source types')
        for value in (self.request,self.result,self.pickup,self.previous_actor,self.actor):
            replace(value)
        if self.request.actor_id!=self.pickup.actor_id or self.request.id!=self.pickup.action_id:
            raise ValueError('NPC weapon pickup changed its actual action owner or source ID')
        if (self.result.source_request!=self.request or self.request.mode is not RecoverMode.STANDARD
                or type(self.result.resolution) is not RecoverStandardResult
                or self.actor.definition!=self.previous_actor.definition
                or self.previous_actor.state.actor_id != self.actor_id
                or self.actor.state.actor_id != self.actor_id
                or not self.actor.state.wields_weapon):
            raise ValueError('NPC weapon pickup must restore only its actual retained source attacks')
        if self.actor != _npc_pickup_snapshot(self.previous_actor,self.pickup,self.result):
            raise ValueError('NPC weapon pickup changed another physical item, grip or resource')

    @property
    def actor_id(self):
        return self.request.actor_id

    @property
    def previous(self):
        return self.pickup.previous

    @property
    def state(self):
        return self.pickup.state


@dataclass(frozen=True,slots=True)
class PcBriarrootWeaponApproachProof:
    actor_id: str
    weapon_id: str
    source_round: CombatRoundState
    previous: PcBattlefieldState
    state: PcBattlefieldState
    request: FreeMovementRequest | None
    result: FreeMovementResult | None

    def __post_init__(self):
        _id(self.actor_id); _id(self.weapon_id)
        if (type(self.source_round) is not CombatRoundState
                or type(self.previous) is not PcBattlefieldState or type(self.state) is not PcBattlefieldState):
            raise TypeError('weapon approach retains its exact clock and battlefield snapshots')
        if (self.request is None)!=(self.result is None):
            raise ValueError('weapon approach must retain both actual movement witnesses')
        if self.request is not None and (type(self.request) is not FreeMovementRequest
                or type(self.result) is not FreeMovementResult):
            raise TypeError('weapon approach requires its exact free-movement source/result')
        for value in (self.source_round,self.previous,self.state,self.request,self.result):
            if value is not None:
                replace(value)


BRIARROOT_WEAPON_PROOFS=(PcBriarrootWeaponDropProof,PcBriarrootWeaponPickupProof,PcBriarrootWeaponApproachProof)


def _actors(state):
    return (*state.source.pc_activation_order,*state.source.enemy_activation_order)


def _member(state,actor):
    return state.participant(actor) if actor in state.source.pc_activation_order else state.enemy(actor)


def _injury(state,actor):
    member=_member(state,actor)
    return member.injury if actor in state.source.pc_activation_order else member.state.injury


def _alive(state,actor):
    return (not _injury(state,actor).dead if actor in state.source.pc_activation_order
        else not _injury(state,actor).defeated and actor not in state.exited_npc_ids)


def _bank(state):
    bank=state.briarroot_dropped_weapons
    if type(bank) is not tuple or any(type(item) is not PcBriarrootDroppedWeapon for item in bank):
        raise TypeError('dropped weapons require the exact ordered finite item bank')
    for item in bank:
        replace(item)
    if len({(item.owner_id,item.weapon_id) for item in bank})!=len(bank):
        raise ValueError('a finite dropped weapon cannot be duplicated')
    return bank


def _item(state,actor,weapon_id):
    return next((item for item in _bank(state) if (item.owner_id,item.weapon_id)==(actor,weapon_id)),None)


def _set_item(bank,item):
    key=item.owner_id,item.weapon_id
    return (tuple(item if (previous.owner_id,previous.weapon_id)==key else previous for previous in bank)
        if any((previous.owner_id,previous.weapon_id)==key for previous in bank) else (*bank,item))


def _binding_ids(state,actor,weapon_id):
    return tuple(binding.id for binding in state.briarroot_bindings
        if binding.attacker_id==actor and binding.weapon_id==weapon_id and binding.kind is BriarrootWeaponKind.HELD)


def _ground(state,actor):
    if state.battlefield is None:
        return PcBriarrootWeaponGround(state.source.facts.zone_id,_actors(state))
    zone=state.battlefield.spatial.placement_for(actor).zone_id
    shadow=battlefield_ground_below(state.battlefield,zone)
    if shadow!=zone:
        return PcBriarrootWeaponGround(shadow,())
    return PcBriarrootWeaponGround(zone,tuple(other for other in _actors(state) if other==actor
        or battlefield_range(state.battlefield,actor,other) is RangedWeaponRange.CLOSE))


def _add_marker(battlefield,item):
    if battlefield is None:
        return None
    if any(placement.entity_id==item.marker_id for placement in battlefield.spatial.placements):
        raise ValueError('the finite weapon already has a physical ground marker')
    placement=SpatialEntityPlacement(item.marker_id,'objects',item.ground.zone_id)
    return replace(battlefield,spatial=replace(battlefield.spatial,
        placements=(*battlefield.spatial.placements,placement)),close_pairs=(*battlefield.close_pairs,
            *(tuple(sorted((item.marker_id,actor))) for actor in item.ground.initial_close_actor_ids)))


def _remove_marker(battlefield,item):
    if battlefield is None:
        return None
    marker=battlefield.spatial.placement_for(item.marker_id)
    if marker.zone_id!=item.ground.zone_id or marker.side_id!='objects':
        raise ValueError('weapon pickup changed the actual static ground marker')
    return replace(battlefield,spatial=replace(battlefield.spatial,placements=tuple(
        placement for placement in battlefield.spatial.placements if placement.entity_id!=item.marker_id)),
        close_pairs=tuple(pair for pair in battlefield.close_pairs if item.marker_id not in pair))


def _own_turn(state,actor,*,unreserved=False):
    if actor not in _actors(state) or not _alive(state,actor):
        raise ValueError('weapon interaction requires an actual live source owner')
    turn=state.round_state.active_turn
    if (turn is None or turn.actor_id!=actor or unreserved and turn.action_slots
            or state.pending or state.pending_wound is not None or state.magic_pending is not None
            or _injury(state,actor).conditions.has(Condition.DEFENCELESS)):
        raise ValueError('weapon interaction must follow mandatory work in its actual active turn')
    return turn


def _physical_weapon_id(state,actor):
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_backup_weapon_models import pc_active_weapon_item_id
        return pc_active_weapon_item_id(state,actor)
    enemy=state.enemy(actor)
    if enemy.state.weapon_inventory is not None:
        selected=enemy.state.weapon_inventory.active
        return None if selected is None else selected.id
    from towr.domain.pc_melee_result_models import pc_selected_npc_attack_profile
    profile=pc_selected_npc_attack_profile(state,actor)
    return None if profile.hands is None else actor+':weapon:'+profile.id


def _is_dropped(state,actor,weapon_id):
    if actor in state.source.pc_activation_order:
        member=state.participant(actor)
        if member.weapon_inventory is not None:
            item=next((item for item in member.weapon_inventory.items if item.id==weapon_id),None)
            return item is not None and item.location is PcItemLocation.DROPPED
        return member.weapon_hand is None and _physical_weapon_id(state,actor)==weapon_id
    enemy = state.enemy(actor)
    inventory = enemy.state.weapon_inventory
    if inventory is not None:
        item = next((item for item in inventory.items if item.id == weapon_id),None)
        return item is not None and item.location is PcItemLocation.DROPPED
    return not enemy.state.wields_weapon


def _npc_drop_snapshot(enemy,weapon_id):
    inventory = enemy.state.weapon_inventory
    if inventory is None:
        if not enemy.state.wields_weapon:
            raise ValueError('NPC cannot abandon an already unwielded weapon')
        return replace(enemy,state=replace(enemy.state,wields_weapon=False,available_attack_ids=()))
    try:
        unit = inventory.item(weapon_id)
    except KeyError as error:
        raise ValueError('NPC cannot abandon a foreign physical unit') from error
    if unit.location is not PcItemLocation.HELD:
        raise ValueError('NPC abandonment requires its actual held physical unit')
    inventory = inventory.with_item(replace(unit,location=PcItemLocation.DROPPED,grip=None))
    armed = any(item.location is PcItemLocation.HELD for item in inventory.items)
    from towr.domain.pc_npc_weapon_inventory import npc_inventory_attack_ids
    return replace(enemy,state=replace(enemy.state,weapon_inventory=inventory,wields_weapon=armed,
        available_attack_ids=npc_inventory_attack_ids(enemy.definition,inventory)))


def _npc_pickup_inventory(enemy,weapon_id):
    inventory = enemy.state.weapon_inventory
    if inventory is None:
        return None
    try:
        unit = inventory.item(weapon_id)
    except KeyError as error:
        raise ValueError('NPC cannot recover a foreign physical unit') from error
    if unit.location is not PcItemLocation.DROPPED:
        raise ValueError('NPC can recover only its actual dropped unit')
    profile = weapon_profile(unit.kind)
    if profile.hands is RangedWeaponHands.TWO_HANDED:
        grips = (WeaponGrip.BOTH,)
    else:
        grips = tuple(dict.fromkeys((unit.source.initial_grip,WeaponGrip.LEFT,WeaponGrip.RIGHT,
            *((WeaponGrip.BOTH,) if profile.variable_grip else ()))))
    for grip in grips:
        if grip is None:
            continue
        try:
            return inventory.with_item(replace(unit,location=PcItemLocation.HELD,grip=grip))
        except ValueError:
            continue
    raise ValueError('NPC weapon pickup has no free legal grip without stowing another item')


def _npc_pickup_snapshot(enemy,pickup,result):
    inventory = _npc_pickup_inventory(enemy,pickup.weapon_id)
    if inventory is None and enemy.state.wields_weapon:
        raise ValueError('opaque NPC weapon pickup requires its actual disarmed source')
    conditions = enemy.state.injury.conditions
    for change in result.resolution.condition_changes:
        conditions = change.conditions
    available = (enemy.state.available_attack_ids if enemy.state.wields_weapon
        else pickup.item.available_attack_ids)
    return replace(enemy,state=replace(enemy.state,weapon_inventory=inventory,
        injury=replace(enemy.state.injury,conditions=conditions),wields_weapon=True,available_attack_ids=available))


def _drop_actor(state,actor,weapon_id):
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_heavy_wound_models import critical_for_incidental_hand_use
        member=state.participant(actor)
        if member.weapon_hand is None or _physical_weapon_id(state,actor)!=weapon_id:
            raise ValueError('only the actual held source weapon can be abandoned')
        inventory=member.weapon_inventory
        if inventory is not None:
            if inventory.active.location is not PcItemLocation.HELD:
                raise ValueError('a carried/deployed weapon is not a caught held weapon')
            inventory=WeaponInventoryState(tuple(replace(item,location=PcItemLocation.DROPPED,grip=None)
                if item.id==weapon_id else item for item in inventory.items),inventory.active_item_id,inventory.shield_hand)
        return replace(member,weapon_inventory=inventory,
            injury=critical_for_incidental_hand_use(member,member.weapon_hand))
    enemy=state.enemy(actor)
    if enemy.state.weapon_inventory is None and _physical_weapon_id(state,actor)!=weapon_id:
        raise ValueError('only the actual opaque NPC weapon can be abandoned')
    return _npc_drop_snapshot(enemy,weapon_id)


def build_briarroot_weapon_drop(state,actor,weapon_id=None):
    _own_turn(state,actor,unreserved=True)
    weapon_id=_physical_weapon_id(state,actor) if weapon_id is None else weapon_id
    bindings=_binding_ids(state,actor,weapon_id)
    before=_member(state,actor)
    after=_drop_actor(state,actor,weapon_id)
    item=PcBriarrootDroppedWeapon(actor,weapon_id,_ground(state,actor),
        () if actor in state.source.pc_activation_order else before.state.available_attack_ids)
    index=len(state.history)
    return PcBriarrootWeaponDropProof(state.source.id+':briarroot:weapon-drop:'+str(index),index,
        actor,weapon_id,bindings,_item(state,actor,weapon_id),item,state.battlefield,
        _add_marker(state.battlefield,item),before,after)


def _latest_wound_loss_witness(state,actor,weapon_id):
    from towr.domain.pc_melee_result_models import (PcHandDropProof,PcBodyConsequenceProof,
        PcWoundCompletionProof,PcRecoverProof,PcAttackProof)
    after = -1
    for index, proof in enumerate(state.history):
        if (type(proof) is PcBriarrootWeaponDropProof
                and (proof.actor_id,proof.weapon_id)==(actor,weapon_id)):
            after = index
        pickup = proof.briarroot_weapon_pickup if type(proof) is PcRecoverProof else None
        if pickup is not None and (pickup.actor_id,pickup.weapon_id)==(actor,weapon_id):
            after = index
        thrown = getattr(proof,'throwing_inventory',None) if type(proof) is PcAttackProof else None
        if (thrown is not None and thrown.item is not None
                and (thrown.actor_id,thrown.item.weapon_id)==(actor,weapon_id)):
            after = index
    for index in range(len(state.history)-1,after,-1):
        proof = state.history[index]
        if type(proof) not in (PcHandDropProof,PcBodyConsequenceProof):
            continue
        completion = next((item.completion for item in reversed(state.history[:index])
            if type(item) is PcWoundCompletionProof),None)
        if completion is not None and completion.source_request.roll.source_request.target_id==actor:
            return index,proof
    return None


def expected_briarroot_weapon_loss(state):
    """Ground every actually lost PC item before any ordinary continuation.

    A preceding Shield/weapon acknowledgement is not a new loss and does not
    hide another item dropped by the same Wound. Each item keeps the original
    typed consequence witness and consumes no additional action.
    """
    for current in state.party:
        actor = current.actor_id
        inventory = current.weapon_inventory
        candidates = (tuple(item.id for item in inventory.items if item.location is PcItemLocation.DROPPED)
            if inventory is not None else ((_physical_weapon_id(state,actor),)
                if current.weapon_hand is None else ()))
        for weapon_id in candidates:
            previous = _item(state,actor,weapon_id)
            if previous is not None and previous.ground is not None or not _is_dropped(state,actor,weapon_id):
                continue
            witness = _latest_wound_loss_witness(state,actor,weapon_id)
            if witness is None:
                continue
            item = PcBriarrootDroppedWeapon(actor,weapon_id,_ground(state,actor))
            index = len(state.history)
            return PcBriarrootWeaponDropProof(state.source.id+':briarroot:weapon-drop:'+str(index),index,
                actor,weapon_id,_binding_ids(state,actor,weapon_id),previous,item,state.battlefield,
                _add_marker(state.battlefield,item),current,current,*witness)
    return None


def apply_briarroot_weapon_drop(state,proof):
    if type(proof) is not PcBriarrootWeaponDropProof:
        raise TypeError('physical abandonment requires its exact typed receipt')
    replace(proof)
    expected=(build_briarroot_weapon_drop(state,proof.actor_id,proof.weapon_id)
        if proof.loss_witness is None else expected_briarroot_weapon_loss(state))
    if proof!=expected:
        raise ValueError('weapon drop changed its actual item, actor, bindings or ground position')
    updates=dict(briarroot_dropped_weapons=_set_item(_bank(state),proof.item),battlefield=proof.state)
    if proof.actor_id in state.source.pc_activation_order:
        updates['party']=tuple(proof.actor if member.actor_id==proof.actor_id else member for member in state.party)
    else:
        updates['enemies']=tuple(proof.actor if enemy.state.actor_id==proof.actor_id else enemy for enemy in state.enemies)
    return updates


def briarroot_weapon_on_ground(state,actor,weapon_id=None):
    if weapon_id is None:
        weapon_id=_physical_weapon_id(state,actor)
    return next((item for item in _bank(state) if item.owner_id==actor
        and (weapon_id is None or item.weapon_id==weapon_id) and item.ground is not None),None)


def _ground_weapon_close(state,actor,item):
    return (actor in item.ground.initial_close_actor_ids if state.battlefield is None else
        battlefield_range(state.battlefield,actor,item.marker_id) is RangedWeaponRange.CLOSE)


def can_pickup_briarroot_weapon(state,actor,weapon_id=None):
    item=briarroot_weapon_on_ground(state,actor,weapon_id)
    if (item is None or not _alive(state,actor)
            or _injury(state,actor).conditions.has(Condition.DEFENCELESS)
            or not _ground_weapon_close(state,actor,item)):
        return False
    if actor in state.source.enemy_activation_order:
        enemy=state.enemy(actor)
        if enemy.state.weapon_inventory is not None:
            try:
                _npc_pickup_inventory(enemy,item.weapon_id)
            except ValueError:
                return False
        elif enemy.state.wields_weapon:
            return False
    return True


def can_pickup_pc_weapon(state,actor,weapon_id):
    """Spatial pickup needs the actual finite item, never a missing-marker guess."""
    if actor not in state.source.pc_activation_order or not _is_dropped(state,actor,weapon_id):
        return False
    if briarroot_weapon_on_ground(state,actor,weapon_id) is not None:
        return can_pickup_briarroot_weapon(state,actor,weapon_id)
    # In the admitted legacy scenes PCs are stationary, including the Short
    # opening in which only NPCs approach. There are no hidden PC positions.
    return (state.battlefield is None and _alive(state,actor)
        and not _injury(state,actor).conditions.has(Condition.DEFENCELESS)
        and (state.source.facts.all_opponents_close or state.source.short_range_opening is not None))


def _pickup(state,actor,weapon_id,action_id):
    item=briarroot_weapon_on_ground(state,actor,weapon_id)
    if item is None or not can_pickup_briarroot_weapon(state,actor,weapon_id):
        raise ValueError('weapon pickup requires its actual owned Close ground marker')
    return PcBriarrootWeaponPickup(action_id,actor,weapon_id,item,replace(item,ground=None),
        state.battlefield,_remove_marker(state.battlefield,item))


def complete_briarroot_pc_pickup(state,result):
    if type(result) is not RecoverActionExecutionResult or type(result.resolution) is not RecoverStandardResult:
        return None
    actor=result.source_request.actor_id
    interaction=result.resolution.object_interaction_follow_up
    if actor not in state.source.pc_activation_order or interaction is None:
        return None
    item=_item(state,actor,interaction.object_id)
    if item is None or item.ground is None:
        return None
    return _pickup(state,actor,item.weapon_id,result.request_id)


def briarroot_pc_pickup_updates(state,result,pickup):
    expected=complete_briarroot_pc_pickup(state,result)
    if pickup!=expected:
        raise ValueError('PC weapon Recover changed its actual physical pickup receipt')
    return {} if pickup is None else dict(briarroot_dropped_weapons=_set_item(_bank(state),pickup.item),
        battlefield=pickup.state)


def build_briarroot_weapon_pickup(state,actor,weapon_id):
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    from towr.domain.pc_weighted_net_models import _has_close_enemy
    turn=_own_turn(state,actor)
    if actor in state.source.pc_activation_order:
        raise ValueError('PC weapon pickup uses its ordinary standard Recover owner')
    if not turn.action_slots or turn.action_slots[-1].executed or turn.action_slots[-1].declaration.kind is not CombatActionKind.RECOVER:
        raise ValueError('weapon pickup requires its actual unexecuted Recover slot')
    if not can_pickup_briarroot_weapon(state,actor,weapon_id):
        raise ValueError('NPC weapon Recover requires its actual Close dropped unit and free grip')
    action=pc_melee_action_id(state,actor)+':briarroot:weapon-pickup:'+weapon_id
    conditions=_injury(state,actor).conditions
    target=lambda condition:RecoverConditionTarget(actor,conditions,None) if conditions.has(condition) else None
    return RecoverActionExecutionRequest(action,state.round_state,actor,conditions,_has_close_enemy(state,actor),
        len(turn.action_slots),RecoverMode.STANDARD,RecoverStandardChoice(WizardMagicState(),
            staggered_target=target(Condition.STAGGERED),prone_target=target(Condition.PRONE),
            object_interaction=RecoverObjectInteractionFollowUp(action+':object',actor,weapon_id,True)))


def complete_briarroot_weapon_pickup(state,request,result,weapon_id):
    from towr.rules.recover_resolution import _resolve_standard
    expected=build_briarroot_weapon_pickup(state,request.actor_id,weapon_id)
    if request!=expected or result!=_expected_recover_execution(request,_resolve_standard(request.choice)):
        raise ValueError('NPC weapon pickup changed its actual standard Recover source')
    actor=request.actor_id
    pickup=_pickup(state,actor,weapon_id,request.id)
    before=state.enemy(actor)
    after=_npc_pickup_snapshot(before,pickup,result)
    return PcBriarrootWeaponPickupProof(request,result,pickup,before,after)


def apply_briarroot_weapon_pickup(state,proof):
    if type(proof) is not PcBriarrootWeaponPickupProof:
        raise TypeError('NPC physical pickup requires its exact Recover proof')
    expected=complete_briarroot_weapon_pickup(state,proof.request,proof.result,proof.pickup.weapon_id)
    if proof!=expected:
        raise ValueError('NPC physical pickup changed its item, source actor or available attacks')
    return dict(briarroot_dropped_weapons=_set_item(_bank(state),proof.pickup.item),battlefield=proof.state,
        round_state=proof.result.round_state,enemies=tuple(proof.actor if enemy.state.actor_id==proof.actor_id
            else enemy for enemy in state.enemies))


def expected_briarroot_weapon_approach(state,actor,weapon_id):
    item=briarroot_weapon_on_ground(state,actor,weapon_id)
    turn=state.round_state.active_turn
    if (item is None or not _alive(state,actor) or state.battlefield is None or turn is None or turn.actor_id!=actor
            or turn.action_slots or state.pending or state.pending_wound is not None or state.magic_pending is not None
            or _ground_weapon_close(state,actor,item)
            or any(_injury(state,actor).conditions.has(condition)
                for condition in (Condition.PRONE,Condition.DEFENCELESS,Condition.BROKEN))):
        return None
    from towr.domain.movement_models import FreeMovementRequest
    from towr.domain.pc_battlefield_movement_models import _zone_distance
    from towr.domain.pc_battlefield_manoeuvre_models import pc_battlefield_actor_speed
    from towr.domain.pc_battlefield_movement_models import aerialmovement_permission,battlefield_path_available
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    previous=state.battlefield
    spatial=previous.spatial
    origin=spatial.placement_for(actor).zone_id
    destination=item.ground.zone_id
    close=(item.marker_id,*(other for other in _actors(state) if other!=actor
        and battlefield_range(previous,item.marker_id,other) is RangedWeaponRange.CLOSE))
    request=result=None
    if origin==destination:
        after=with_actor_placement(previous,actor,destination,close_to_ids=close)
    else:
        if actor in spatial.free_move_used_entity_ids:
            return None
        speed=pc_battlefield_actor_speed(state,actor)
        route=[]; current=origin
        for _ in range(speed.free_move_zone_limit):
            choices=tuple(zone for zone in spatial.graph.adjacent_zone_ids(current)
                if aerialmovement_permission(state,actor,(*route,zone)))
            if not choices:
                break
            following=min(choices,key=lambda zone:_zone_distance(spatial.graph,zone,destination))
            if _zone_distance(spatial.graph,following,destination)>=_zone_distance(spatial.graph,current,destination):
                break
            route.append(following); current=following
            if current==destination:
                break
        if not route:
            return None
        if not battlefield_path_available(state,actor,tuple(route),
                close_to_ids=close if current==destination else ()):
            return None
        from towr.domain.pc_terrain_models import terrain_test_required_for_route
        terrain=terrain_test_required_for_route(state,actor,tuple(route))
        request=FreeMovementRequest(pc_melee_action_id(state,actor)+':briarroot:weapon-approach:'+weapon_id,
            state.round_state,spatial,actor,speed,_injury(state,actor).conditions,tuple(route),
            crosses_difficult_terrain=terrain,terrain_resolution_deferred=terrain,acrobatic=actor_acrobatic_source(state,actor),path_entity_ids=pc_enemy_path_blockers(state,actor,tuple(route)))
        result=resolve_free_movement(request)
        after=replace(with_actor_placement(previous,actor,current,
            close_to_ids=close if current==destination else ()),spatial=result.state)
    if not briarroot_movement_keeps_close(state,actor,after):
        return None
    return PcBriarrootWeaponApproachProof(actor,weapon_id,state.round_state,previous,after,request,result)


def apply_briarroot_weapon_approach(state,proof):
    if type(proof) is not PcBriarrootWeaponApproachProof or proof!=expected_briarroot_weapon_approach(
            state,proof.actor_id,proof.weapon_id):
        raise ValueError('weapon approach changed its actual marker, movement or source clock')
    updates=dict(battlefield=proof.state)
    if proof.actor_id in state.source.pc_activation_order:
        from towr.domain.pc_heavy_wound_models import critical_for_action
        member=state.participant(proof.actor_id)
        changed=replace(member,injury=critical_for_action(member,None))
        updates['party']=tuple(changed if previous.actor_id==proof.actor_id else previous for previous in state.party)
    return updates


def validate_briarroot_dropped_weapons(state):
    """Fold finite item receipts independently from combat/RNG execution."""
    from towr.domain.pc_melee_result_models import PcRecoverProof,PcAttackProof
    from towr.domain.pc_briarroot_models import PcBriarrootProof,PcBriarrootReleaseProof
    from towr.domain.pc_throwing_inventory_models import PcThrowingInventoryReceipt
    bank=(); bindings=()
    for index,proof in enumerate(state.history):
        from towr.domain.pc_hammer_recover_models import PcHammerRetrievalProof
        if type(proof) is PcHammerRetrievalProof:
            previous=next((item for item in bank if (item.owner_id,item.weapon_id)==(proof.actor_id,proof.weapon_id)),None)
            if previous!=proof.previous_item:
                raise ValueError('Hammer extraction lost its actual embedded item prefix')
            bank=_set_item(bank,proof.item)
        from towr.domain.pc_demigryph_models import pc_kernel_attack_types
        magical=getattr(proof,'magic_weapon',None) if type(proof) in pc_kernel_attack_types() else None
        if magical is not None:
            for previous,item in magical.drops:
                actual=next((row for row in bank if (row.owner_id,row.weapon_id)==(item.owner_id,item.weapon_id)),None)
                if previous!=actual:
                    raise ValueError('Magic disarm/stuck changed its finite ground-item prefix')
                bank=_set_item(bank,item)
        if type(proof) is PcAttackProof and getattr(proof,'throwing_inventory',None) is not None:
            receipt = proof.throwing_inventory
            if type(receipt) is not PcThrowingInventoryReceipt:
                raise TypeError('Throwing must retain its exact source-bound inventory receipt')
            replace(receipt)
            if (receipt.request_id,receipt.actor_id,receipt.target_id,receipt.weapon_use) != (
                    proof.request.id,proof.request.actor_id,proof.request.target_id,proof.weapon_intent.attack_use):
                raise ValueError('Throwing physical history changed its actual Attack or weapon source')
            if receipt.item is not None:
                previous = next((item for item in bank if (item.owner_id,item.weapon_id) == (
                    receipt.actor_id,receipt.item.weapon_id)),None)
                if previous != receipt.previous_item:
                    raise ValueError('Throwing landing changed or duplicated its finite item prefix')
                bank = _set_item(bank,receipt.item)
            continue
        if type(proof) in (PcBriarrootProof,PcBriarrootReleaseProof):
            if proof.previous!=bindings:
                raise ValueError('physical weapon history lost its binding-source prefix')
            bindings=proof.bindings
        if type(proof) is PcBriarrootWeaponDropProof:
            replace(proof)
            if proof.history_index!=index or proof.id!=state.source.id+':briarroot:weapon-drop:'+str(index):
                raise ValueError('weapon drop lost its exact source history position')
            previous=next((item for item in bank if (item.owner_id,item.weapon_id)==(proof.actor_id,proof.weapon_id)),None)
            if previous!=proof.previous_item:
                raise ValueError('weapon drop changed or duplicated its finite item prefix')
            actual_bindings=tuple(binding.id for binding in bindings
                if binding.attacker_id==proof.actor_id and binding.weapon_id==proof.weapon_id
                    and binding.kind is BriarrootWeaponKind.HELD)
            if proof.binding_ids!=actual_bindings:
                raise ValueError('weapon drop changed its actual full Briarroot binding source')
            if proof.loss_witness is not None and state.history[proof.loss_witness_history_index]!=proof.loss_witness:
                raise ValueError('weapon loss acknowledgement lost its actual Wound consequence')
            bank=_set_item(bank,proof.item)
        else:
            pickup=(proof.pickup if type(proof) is PcBriarrootWeaponPickupProof else
                getattr(proof,'briarroot_weapon_pickup',None) if type(proof) is PcRecoverProof else None)
            if pickup is None:
                continue
            if type(pickup) is not PcBriarrootWeaponPickup:
                raise TypeError('PC Recover must retain its exact finite weapon pickup receipt')
            replace(pickup)
            result=proof.result
            if (type(result.resolution) is not RecoverStandardResult
                    or result.request_id!=pickup.action_id
                    or result.source_request.actor_id!=pickup.actor_id
                    or result.resolution.object_interaction_follow_up is None
                    or result.resolution.object_interaction_follow_up.object_id!=pickup.weapon_id):
                raise ValueError('physical pickup lost its actual ordinary Recover object interaction')
            previous=next((item for item in bank if (item.owner_id,item.weapon_id)==(pickup.actor_id,pickup.weapon_id)),None)
            if previous!=pickup.previous_item:
                raise ValueError('weapon pickup lost its one actual prior ground item')
            bank=_set_item(bank,pickup.item)
    if _bank(state)!=bank:
        raise ValueError('physical weapon bank differs from its complete source receipt history')
    for item in bank:
        if item.owner_id not in _actors(state):
            raise ValueError('physical weapon owner must belong to the source encounter')
        if item.owner_id in state.source.pc_activation_order:
            source=state.source.participant(item.owner_id)
            from towr.domain.pc_weapon_inventory import initial_pc_weapon_inventory
            identifiers=tuple(unit.id for unit in initial_pc_weapon_inventory(source).items)
            if item.weapon_id not in identifiers or item.available_attack_ids:
                raise ValueError('physical PC weapon changed its actual finite source inventory')
            inventory=state.participant(item.owner_id).weapon_inventory
            if inventory is not None:
                actual=next(weapon for weapon in inventory.items if weapon.id==item.weapon_id)
                if item.ground is not None and actual.location not in (PcItemLocation.DROPPED,PcItemLocation.STUCK):
                    raise ValueError('a grounded physical PC weapon cannot also be held or carried')
        else:
            source=next(enemy for enemy in state.source.enemies if enemy.state.actor_id==item.owner_id)
            inventory=state.enemy(item.owner_id).state.weapon_inventory
            identifiers=(tuple(unit.id for unit in inventory.items) if inventory is not None else
                tuple(item.owner_id+':weapon:'+profile.id for profile in source.definition.attacks if profile.hands is not None))
            if item.weapon_id not in identifiers or not set(item.available_attack_ids)<={profile.id for profile in source.definition.attacks}:
                raise ValueError('physical NPC weapon changed its actual source attack membership')
            if inventory is not None:
                actual=inventory.item(item.weapon_id)
                if item.ground is not None and actual.location not in (PcItemLocation.DROPPED,PcItemLocation.STUCK):
                    raise ValueError('a grounded physical NPC unit cannot also be held or carried')
            elif item.ground is not None and state.enemy(item.owner_id).state.wields_weapon:
                raise ValueError('a grounded opaque NPC weapon cannot remain wielded')
        if state.battlefield is not None:
            markers=tuple(placement for placement in state.battlefield.spatial.placements
                if placement.entity_id==item.marker_id)
            if item.ground is not None:
                if len(markers)!=1 or markers[0].zone_id!=item.ground.zone_id or markers[0].side_id!='objects':
                    raise ValueError('dropped weapon lost or moved its actual static ground marker')
            elif markers:
                raise ValueError('a recovered weapon cannot keep a duplicate ground marker')
