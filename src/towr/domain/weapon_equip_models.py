"""One completed incidental weapon equip, independent of participant role.

Only held/carried locations and grips change here. The combat owner must
match ``before`` to the actor's actual inventory and recheck usable hands,
binding restrictions and the chosen action context before admitting a proof.
Ground pickup, Shield release and paid Recover retain their separate owners.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.weapon_inventory_models import (
    WeaponGrip, WeaponInventoryState, WeaponItemLocation,
)


def _actor(value):
    if type(value) is not str or not value.strip():
        raise TypeError('weapon equip requires its exact nonempty actor identifier')


def _round(value):
    if type(value) is not int:
        raise TypeError('weapon equip round must be an exact integer')
    if value < 1:
        raise ValueError('weapon equip round must be positive')


def _inventory(value):
    if type(value) is not WeaponInventoryState:
        raise TypeError('weapon equip requires its exact full inventory state')
    replace(value)


@dataclass(frozen=True, slots=True)
class WeaponEquipTransition:
    actor_id: str
    round_number: int
    before: WeaponInventoryState
    after: WeaponInventoryState

    def __post_init__(self):
        _actor(self.actor_id)
        _round(self.round_number)
        _inventory(self.before)
        _inventory(self.after)
        if self.before.shield_hand is not self.after.shield_hand:
            raise ValueError('weapon equip cannot move or release the actual Shield')
        if tuple(item.id for item in self.before.items) != tuple(item.id for item in self.after.items):
            raise ValueError('weapon equip cannot create, remove or reorder physical units')
        movable = (WeaponItemLocation.HELD, WeaponItemLocation.CARRIED)
        for previous, following in zip(self.before.items, self.after.items, strict=True):
            if previous.location not in movable:
                if following != previous:
                    raise ValueError('free equip cannot change a dropped, deployed, stuck or spent item')
                continue
            if following.location not in movable:
                raise ValueError('free equip can only hold or carry an available physical item')
            expected = replace(previous, location=following.location, grip=following.grip)
            if following != expected:
                raise ValueError('weapon equip cannot alter source, origin, reload, charges or Dragon Bow use')

    @property
    def changes_equipment(self) -> bool:
        """Selecting another already held weapon is not an object interaction."""
        return any((previous.location, previous.grip) != (following.location, following.grip)
            for previous, following in zip(self.before.items, self.after.items, strict=True))


def plan_weapon_equip(actor_id: str, round_number: int, inventory: WeaponInventoryState, *,
        held_items: tuple[tuple[str, WeaponGrip], ...], active_item_id: str | None,
        usable_hands: tuple[WeaponGrip, ...]) -> WeaponEquipTransition:
    """Plan one complete legal hand arrangement without spending its budget.

    Only actual carried units can be drawn; omitted held units are stowed.
    Every resulting held weapon must fit the supplied current usable hands.
    The eventual combat owner must obtain those facts from the actual body
    state and compare the complete ``before`` snapshot before application.
    """
    _actor(actor_id)
    _round(round_number)
    _inventory(inventory)
    if type(held_items) is not tuple:
        raise TypeError('held weapon choices require an exact ordered tuple')
    selected = {}
    for choice in held_items:
        if type(choice) is not tuple or len(choice) != 2:
            raise TypeError('each held choice requires its exact unit ID and grip tuple')
        identifier, grip = choice
        if type(identifier) is not str or not identifier.strip() or type(grip) is not WeaponGrip:
            raise TypeError('held weapon choices require exact unit identifiers and typed grips')
        if identifier in selected:
            raise ValueError('one physical unit cannot be selected twice')
        if identifier not in {item.id for item in inventory.items}:
            raise ValueError('held weapon choice is absent from the actual inventory')
        if inventory.item(identifier).location not in (WeaponItemLocation.HELD, WeaponItemLocation.CARRIED):
            raise ValueError('only actually held or carried units are available to free equip')
        selected[identifier] = grip
    if (type(usable_hands) is not tuple
            or any(type(hand) is not WeaponGrip or hand is WeaponGrip.BOTH for hand in usable_hands)):
        raise TypeError('usable hands require an exact tuple of actual left/right hands')
    if len(set(usable_hands)) != len(usable_hands):
        raise ValueError('usable hands cannot duplicate an actual hand')
    for grip in selected.values():
        needed = (WeaponGrip.LEFT, WeaponGrip.RIGHT) if grip is WeaponGrip.BOTH else (grip,)
        if any(hand not in usable_hands for hand in needed):
            raise ValueError('held weapon arrangement requires its actual usable hands')
    items = []
    for item in inventory.items:
        if item.id in selected:
            item = replace(item, location=WeaponItemLocation.HELD, grip=selected[item.id])
        elif item.location is WeaponItemLocation.HELD:
            item = replace(item, location=WeaponItemLocation.CARRIED, grip=None)
        items.append(item)
    after = WeaponInventoryState(tuple(items), active_item_id, inventory.shield_hand)
    if after == inventory:
        raise ValueError('unchanged weapon arrangement does not need an equip interaction')
    return WeaponEquipTransition(actor_id, round_number, inventory, after)


@dataclass(frozen=True, slots=True)
class WeaponEquipTurnState:
    round_number: int
    actor_id: str
    incidental_used: bool = False

    def __post_init__(self):
        _round(self.round_number)
        _actor(self.actor_id)
        if type(self.incidental_used) is not bool:
            raise TypeError('weapon equip usage requires an exact bool')


def apply_incidental_equip(state: WeaponEquipTurnState,
        transition: WeaponEquipTransition) -> WeaponEquipTurnState:
    """Spend only the actual equip allowance, never a paid combat action.

    This pure owner does not assert that the global actor still has ``before``;
    full inventory membership, current hands and journal admission remain the
    responsibility of the combat state owner.
    """
    if type(state) is not WeaponEquipTurnState or type(transition) is not WeaponEquipTransition:
        raise TypeError('weapon equip application requires its exact turn and transition types')
    replace(state)
    replace(transition)
    if (state.actor_id, state.round_number) != (transition.actor_id, transition.round_number):
        raise ValueError('weapon equip transition belongs to another actor or round')
    if not transition.changes_equipment:
        return state
    if state.incidental_used:
        raise ValueError('the incidental weapon equip allowance was already used this turn')
    return replace(state, incidental_used=True)
