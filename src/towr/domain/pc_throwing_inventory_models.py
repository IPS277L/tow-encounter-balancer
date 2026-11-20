"""One real Throwing Attack spends or lands its own finite physical unit.

The Attack owner validates the Test and consequences. This owner authenticates
the completed action and retains the same item, its pre-attack target position
and resources. Weighted Nets keep their existing binding-specific owner.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.action_execution_models import AttackActionExecutionRequest, AttackActionExecutionResult
from towr.domain.pc_battlefield_models import PcBattlefieldState
from towr.domain.pc_briarroot_weapon_models import (
    PcBriarrootDroppedWeapon, _add_marker, _bank, _ground, _item, _set_item,
)
from towr.domain.test_models import Skill
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_inventory_models import WeaponInventoryState, WeaponItemLocation
from towr.domain.weapon_use_models import WeaponUse


RECOVERABLE_THROWING_WEAPONS = (
    WeaponKind.ROCK, WeaponKind.THROWING_SPEAR, WeaponKind.THROWING_AXE,
)
VOLATILE_THROWING_WEAPONS = (WeaponKind.OIL_FLASK, WeaponKind.BLASTING_CHARGE)
FINITE_THROWING_WEAPONS = (*RECOVERABLE_THROWING_WEAPONS, *VOLATILE_THROWING_WEAPONS)
_THROWING_WEAPONS = (*FINITE_THROWING_WEAPONS, WeaponKind.THROWING_KNIVES)


def _identifier(value):
    if type(value) is not str or not value.strip():
        raise TypeError('Throwing inventory requires exact nonempty action/actor identifiers')


def _after_inventory(use):
    if type(use) is not WeaponUse:
        raise TypeError('Throwing inventory requires the frozen typed WeaponUse')
    replace(use)
    if use.skill is not Skill.THROWING or use.kind not in _THROWING_WEAPONS:
        raise ValueError('this receipt owns only ordinary physical Throwing, excluding Weighted Net')
    item = use.primary
    if item is None or item.location is not WeaponItemLocation.HELD:
        raise ValueError('Throwing requires its actual held finite item')
    if use.kind is WeaponKind.THROWING_KNIVES:
        # The printed source is a whole-battle set, not one finite blade.
        return use.inventory
    location = (WeaponItemLocation.DROPPED if use.kind in RECOVERABLE_THROWING_WEAPONS
        else WeaponItemLocation.SPENT)
    return use.inventory.with_item(replace(item, location=location, grip=None))


@dataclass(frozen=True, slots=True)
class PcThrowingInventoryReceipt:
    request_id: str
    actor_id: str
    target_id: str
    weapon_use: WeaponUse
    after_inventory: WeaponInventoryState
    previous_item: PcBriarrootDroppedWeapon | None
    item: PcBriarrootDroppedWeapon | None
    previous: PcBattlefieldState | None
    state: PcBattlefieldState | None

    def __post_init__(self):
        for value in (self.request_id, self.actor_id, self.target_id):
            _identifier(value)
        expected = _after_inventory(self.weapon_use)
        if self.actor_id == self.target_id or self.weapon_use.actor_id != self.actor_id:
            raise ValueError('Throwing receipt changed its actual actor or target')
        if type(self.after_inventory) is not WeaponInventoryState:
            raise TypeError('Throwing receipt requires its actual whole resulting inventory')
        replace(self.after_inventory)
        if self.after_inventory != expected:
            raise ValueError('Throwing changed another unit, grip, charge, Shield or finite source')
        for battlefield in (self.previous, self.state):
            if battlefield is not None:
                if type(battlefield) is not PcBattlefieldState:
                    raise TypeError('Throwing retains exact before/after battlefield snapshots')
                replace(battlefield)
        if self.weapon_use.kind in RECOVERABLE_THROWING_WEAPONS:
            if type(self.item) is not PcBriarrootDroppedWeapon or self.item.ground is None:
                raise TypeError('recoverable Throwing must retain its actual static ground item')
            replace(self.item)
            if (self.item.owner_id, self.item.weapon_id) != (self.actor_id, self.weapon_use.primary_item_id):
                raise ValueError('Throwing landing changed its exact item source or owner')
            if self.previous_item is not None:
                if type(self.previous_item) is not PcBriarrootDroppedWeapon:
                    raise TypeError('Throwing retains the exact previous finite ground-bank record')
                replace(self.previous_item)
                if (self.previous_item.owner_id, self.previous_item.weapon_id) != (
                        self.item.owner_id, self.item.weapon_id) or self.previous_item.ground is not None:
                    raise ValueError('a grounded item cannot be thrown again without actual pickup')
            if self.state != _add_marker(self.previous, self.item):
                raise ValueError('Throwing changed the frozen battlefield beyond its actual ground marker')
        elif self.item is not None or self.previous_item is not None or self.state != self.previous:
            raise ValueError('volatile items and a whole-battle knife set do not create a ground item')


def _action_source(state, request, execution, use):
    if type(request) is not AttackActionExecutionRequest or type(execution) is not AttackActionExecutionResult:
        raise TypeError('Throwing receipt requires its completed typed K1 Attack action')
    replace(request)
    replace(execution)
    if (execution.request_id, execution.actor_id, execution.target_id, execution.slot_index,
            execution.previous_state, execution.resolution.request_id,
            execution.resolution.attack.request_id) != (
            request.id, request.actor_id, request.target_id, request.slot_index,
            request.state, request.kernel_request.id, request.kernel_request.attack.id):
        raise ValueError('Throwing receipt is detached from its actual K1 Attack action')
    if request.state != state.round_state:
        raise ValueError('Throwing cannot reuse a completed or stale action clock')
    if use.actor_id != request.actor_id:
        raise ValueError('Throwing source belongs to a different actor')
    actor = request.actor_id
    if actor in state.source.pc_activation_order:
        inventory = state.participant(actor).weapon_inventory
    elif actor in state.source.npc_activation_order:
        inventory = state.enemy(actor).state.weapon_inventory
    else:
        raise ValueError('Throwing actor does not belong to the source encounter')
    if request.target_id not in (*state.source.pc_activation_order, *state.source.npc_activation_order):
        raise ValueError('Throwing target does not belong to the source encounter')
    if use.inventory != inventory:
        raise ValueError('Throwing source changed the actual current physical inventory')


def prepare_throwing_inventory(state, request, execution, weapon_use):
    """Freeze physical expenditure after a real Attack, on HIT and MISS alike."""
    if weapon_use is None:
        return None
    if type(weapon_use) is not WeaponUse:
        raise TypeError('Throwing requires the exact pre-Test WeaponUse or no physical use')
    replace(weapon_use)
    if weapon_use.kind not in _THROWING_WEAPONS:
        return None
    after = _after_inventory(weapon_use)
    _action_source(state, request, execution, weapon_use)
    actor = request.actor_id
    previous_item = item = None
    battlefield = state.battlefield
    if weapon_use.kind in RECOVERABLE_THROWING_WEAPONS:
        previous_item = _item(state, actor, weapon_use.primary_item_id)
        available = (() if actor in state.source.pc_activation_order
            else state.enemy(actor).state.available_attack_ids)
        # ADR-0140 fixes the landing to the target's position before the Attack,
        # irrespective of HIT/MISS, Give Ground, death or later movement.
        item = PcBriarrootDroppedWeapon(actor, weapon_use.primary_item_id,
            _ground(state, request.target_id), available)
        battlefield = _add_marker(state.battlefield, item)
    return PcThrowingInventoryReceipt(request.id, actor, request.target_id, weapon_use,
        after, previous_item, item, state.battlefield, battlefield)


def throwing_inventory_updates(state, request, execution, weapon_use, receipt, updates):
    """Apply exactly the source-bound inventory transition over health updates."""
    expected = prepare_throwing_inventory(state, request, execution, weapon_use)
    if receipt != expected or type(receipt) is not type(expected):
        raise ValueError('Throwing changed or omitted its actual physical inventory receipt')
    if expected is None:
        return updates
    replace(receipt)
    updates = dict(updates)
    actor = receipt.actor_id
    inventory = receipt.after_inventory
    if actor in state.source.pc_activation_order:
        updates['party'] = tuple(replace(member, weapon_inventory=inventory)
            if member.actor_id == actor else member for member in updates.get('party', state.party))
    else:
        from towr.domain.pc_npc_weapon_inventory import npc_inventory_attack_ids
        armed = any(item.location is WeaponItemLocation.HELD for item in inventory.items)
        updates['enemies'] = tuple(replace(enemy, state=replace(enemy.state,
            weapon_inventory=inventory, wields_weapon=armed,
            available_attack_ids=npc_inventory_attack_ids(enemy.definition, inventory)))
            if enemy.state.actor_id == actor else enemy for enemy in updates.get('enemies', state.enemies))
    if receipt.item is not None:
        updates['briarroot_dropped_weapons'] = _set_item(_bank(state), receipt.item)
        updates['battlefield'] = receipt.state
    return updates
