"""Physical Trade Tools and their role-independent per-battle locations.

ADR-0141 C17 requires a real Musician's Gear item and caller-supplied hand
requirements. These primitives prove physical use and one-item transitions;
Lore, hearing, action costs, Wounds and cross-equipment hands have other owners.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from towr.domain.weapon_inventory_models import WeaponGrip, WeaponInventoryState, WeaponItemLocation


_BOTH_HANDS = (WeaponGrip.LEFT, WeaponGrip.RIGHT)


class ToolKind(str, Enum):
    MUSICIANS_GEAR = 'musicians_gear'


def _identifier(value, label):
    if type(value) is not str or not value.strip():
        raise TypeError(label + ' requires an exact nonempty identifier')


def _grip(hands_required, location, grip):
    if type(location) is not WeaponItemLocation:
        raise TypeError('tool location requires its exact typed value')
    if location not in (WeaponItemLocation.HELD, WeaponItemLocation.CARRIED,
            WeaponItemLocation.DROPPED):
        raise ValueError('a physical tool can only be held, carried or dropped')
    if grip is not None and type(grip) is not WeaponGrip:
        raise TypeError('tool grip requires its exact typed value or None')
    if location is not WeaponItemLocation.HELD:
        if grip is not None:
            raise ValueError('a non-held tool occupies no hand')
    elif hands_required == 2:
        if grip is not WeaponGrip.BOTH:
            raise ValueError('a two-handed tool requires its actual Both grip')
    elif grip not in _BOTH_HANDS:
        raise ValueError('a one-handed tool requires its actual Left or Right grip')


def _usable_hands(hands):
    if type(hands) is not tuple or any(type(hand) is not WeaponGrip for hand in hands):
        raise TypeError('usable tool hands require an exact tuple of typed hands')
    if len(set(hands)) != len(hands) or WeaponGrip.BOTH in hands:
        raise ValueError('usable tool hands are distinct Left/Right hands')


def _hands(item):
    if item.location is not WeaponItemLocation.HELD:
        return ()
    return _BOTH_HANDS if item.grip is WeaponGrip.BOTH else (item.grip,)


@dataclass(frozen=True, slots=True)
class ToolItemSource:
    id: str
    kind: ToolKind
    hands_required: int
    initial_location: WeaponItemLocation
    initial_grip: WeaponGrip | None
    instrument_name: str | None = None

    def __post_init__(self):
        _identifier(self.id, 'tool source')
        if type(self.kind) is not ToolKind:
            raise TypeError('tool source requires its exact typed kind')
        if type(self.hands_required) is not int:
            raise TypeError('tool hands_required requires an exact integer')
        if self.hands_required not in (1, 2):
            raise ValueError('tool hands_required must be one or two')
        _grip(self.hands_required, self.initial_location, self.initial_grip)
        if self.initial_location not in (WeaponItemLocation.HELD, WeaponItemLocation.CARRIED):
            raise ValueError('a tool source begins held or carried')
        if self.instrument_name is not None:
            _identifier(self.instrument_name, 'instrument name')


def tool_item_id(initial_actor_id: str, source_item_id: str) -> str:
    """An injective origin namespace, independent of the current holder."""
    _identifier(initial_actor_id, 'initial tool actor')
    _identifier(source_item_id, 'tool source')
    return ('tool-item:' + str(len(initial_actor_id)) + ':' + initial_actor_id
        + ':' + str(len(source_item_id)) + ':' + source_item_id)


@dataclass(frozen=True, slots=True)
class ToolItemState:
    source: ToolItemSource
    id: str
    initial_actor_id: str
    source_item_id: str
    location: WeaponItemLocation
    grip: WeaponGrip | None
    dropped_zone_id: str | None = None

    def __post_init__(self):
        if type(self.source) is not ToolItemSource:
            raise TypeError('tool item requires its exact immutable source')
        replace(self.source)
        _identifier(self.id, 'physical tool')
        _identifier(self.initial_actor_id, 'initial tool actor')
        _identifier(self.source_item_id, 'tool source')
        if (self.source_item_id != self.source.id
                or self.id != tool_item_id(self.initial_actor_id, self.source.id)):
            raise ValueError('tool ID and source must retain their initial origin')
        _grip(self.source.hands_required, self.location, self.grip)
        if self.location is WeaponItemLocation.DROPPED:
            _identifier(self.dropped_zone_id, 'dropped tool Zone')
        elif self.dropped_zone_id is not None:
            raise ValueError('only a dropped tool retains a ground Zone')

    @property
    def kind(self) -> ToolKind:
        return self.source.kind

    @property
    def hands_required(self) -> int:
        return self.source.hands_required

    @property
    def occupied_hands(self) -> tuple[WeaponGrip, ...]:
        return _hands(self)


@dataclass(frozen=True, slots=True)
class ToolInventoryState:
    """Ordered physical tools; current hands shared with other tools only."""
    items: tuple[ToolItemState, ...] = ()

    def __post_init__(self):
        if type(self.items) is not tuple or any(type(item) is not ToolItemState for item in self.items):
            raise TypeError('tool inventory requires an exact tuple of typed items')
        for item in self.items:
            replace(item)
        if len({item.id for item in self.items}) != len(self.items):
            raise ValueError('a physical tool cannot occupy two inventory entries')
        occupied = set()
        for item in self.items:
            if any(hand in occupied for hand in _hands(item)):
                raise ValueError('held tools cannot share an occupied hand')
            occupied.update(_hands(item))

    def item(self, item_id: str) -> ToolItemState:
        _identifier(item_id, 'tool lookup')
        try:
            return next(item for item in self.items if item.id == item_id)
        except StopIteration:
            raise KeyError(item_id) from None

    @property
    def occupied_hands(self) -> tuple[WeaponGrip, ...]:
        used = {hand for item in self.items for hand in _hands(item)}
        return tuple(hand for hand in _BOTH_HANDS if hand in used)

    def with_item(self, item: ToolItemState) -> ToolInventoryState:
        """Replace one item in place, preserving its full source and origin."""
        replace(self)
        if type(item) is not ToolItemState:
            raise TypeError('tool update requires its exact typed item')
        replace(item)
        previous = self.item(item.id)
        if (item.source != previous.source or item.initial_actor_id != previous.initial_actor_id
                or item.source_item_id != previous.source_item_id):
            raise ValueError('a tool update cannot rewrite its immutable source or origin')
        return replace(self, items=tuple(item if old.id == item.id else old for old in self.items))


def initial_tool_inventory(initial_actor_id: str,
        sources: tuple[ToolItemSource, ...]) -> ToolInventoryState:
    """Create exactly one physical item per distinct source, once per battle."""
    _identifier(initial_actor_id, 'initial tool inventory actor')
    if type(sources) is not tuple or any(type(source) is not ToolItemSource for source in sources):
        raise TypeError('initial tool inventory requires an exact tuple of typed sources')
    for source in sources:
        replace(source)
    if len({source.id for source in sources}) != len(sources):
        raise ValueError('initial tool source IDs must be distinct')
    return ToolInventoryState(tuple(ToolItemState(source,
        tool_item_id(initial_actor_id, source.id), initial_actor_id, source.id,
        source.initial_location, source.initial_grip) for source in sources))


def validate_tool_equipment_hands(tools: ToolInventoryState, weapons: WeaponInventoryState) -> None:
    """Check actual shared hand occupancy without stowing or choosing an item."""
    if type(tools) is not ToolInventoryState or type(weapons) is not WeaponInventoryState:
        raise TypeError('shared equipment hands require exact tool and weapon inventories')
    replace(tools)
    replace(weapons)
    occupied = set(() if weapons.shield_hand is None else (weapons.shield_hand,))
    for item in weapons.items:
        occupied.update(_hands(item))
    if any(hand in occupied for hand in tools.occupied_hands):
        raise ValueError('held tools, weapons and Shield cannot share an occupied hand')


def _facts(actor_id, inventory, usable_hands):
    _identifier(actor_id, 'tool actor')
    if type(inventory) is not ToolInventoryState:
        raise TypeError('tool use requires its exact typed inventory snapshot')
    replace(inventory)
    _usable_hands(usable_hands)


def _item(inventory, item_id):
    _identifier(item_id, 'tool item')
    try:
        return inventory.item(item_id)
    except KeyError:
        raise ValueError('tool source must be an actual inventory item') from None


def _require_usable(item, usable_hands):
    if any(hand not in usable_hands for hand in _hands(item)):
        raise ValueError('every occupied tool hand must be currently usable')


@dataclass(frozen=True, slots=True)
class ToolUse:
    actor_id: str
    inventory: ToolInventoryState
    item_id: str
    usable_hands: tuple[WeaponGrip, ...] = _BOTH_HANDS

    def __post_init__(self):
        _facts(self.actor_id, self.inventory, self.usable_hands)
        item = _item(self.inventory, self.item_id)
        if item.location is not WeaponItemLocation.HELD:
            raise ValueError('only an actually held tool can supply its use')
        _require_usable(item, self.usable_hands)

    @property
    def item(self) -> ToolItemState:
        return self.inventory.item(self.item_id)

    @property
    def kind(self) -> ToolKind:
        return self.item.kind

    @property
    def used_hands(self) -> tuple[WeaponGrip, ...]:
        return self.item.occupied_hands


def build_tool_use(actor_id: str, inventory: ToolInventoryState, item_id: str,
        usable_hands: tuple[WeaponGrip, ...] = _BOTH_HANDS) -> ToolUse:
    return ToolUse(actor_id, inventory, item_id, usable_hands)


class ToolInventoryTransitionKind(str, Enum):
    DROP = 'drop'
    STOW = 'stow'
    EQUIP = 'equip'
    PICKUP = 'pickup'


@dataclass(frozen=True, slots=True)
class ToolInventoryTransition:
    """One physical change, with source snapshots for a higher owner's replay."""
    kind: ToolInventoryTransitionKind
    actor_id: str
    item_id: str
    before: ToolInventoryState
    after: ToolInventoryState
    zone_id: str | None = None
    usable_hands: tuple[WeaponGrip, ...] = _BOTH_HANDS

    def __post_init__(self):
        if type(self.kind) is not ToolInventoryTransitionKind:
            raise TypeError('tool transition requires its exact typed kind')
        _facts(self.actor_id, self.before, self.usable_hands)
        _facts(self.actor_id, self.after, self.usable_hands)
        previous = _item(self.before, self.item_id)
        following = _item(self.after, self.item_id)
        if self.before == self.after or self.after != self.before.with_item(following):
            raise ValueError('a tool transition changes exactly one existing item in source order')
        if self.kind in (ToolInventoryTransitionKind.DROP, ToolInventoryTransitionKind.PICKUP):
            _identifier(self.zone_id, 'tool transition actor Zone')
        elif self.zone_id is not None:
            raise ValueError('a held/carried tool transition has no ground Zone')
        if self.kind is ToolInventoryTransitionKind.DROP:
            if (previous.location is not WeaponItemLocation.HELD
                    or following != replace(previous, location=WeaponItemLocation.DROPPED,
                        grip=None, dropped_zone_id=self.zone_id)):
                raise ValueError('Drop moves one held tool to the actual actor Zone')
        elif self.kind is ToolInventoryTransitionKind.STOW:
            if (previous.location is not WeaponItemLocation.HELD
                    or following != replace(previous, location=WeaponItemLocation.CARRIED, grip=None)):
                raise ValueError('Stow moves one held tool to carried')
        else:
            expected = (WeaponItemLocation.CARRIED if self.kind is ToolInventoryTransitionKind.EQUIP
                else WeaponItemLocation.DROPPED)
            if (previous.location is not expected or following.location is not WeaponItemLocation.HELD
                    or following != replace(previous, location=WeaponItemLocation.HELD,
                        grip=following.grip, dropped_zone_id=None)):
                raise ValueError('Equip/Pickup moves one actual carried/dropped tool to held')
            if (self.kind is ToolInventoryTransitionKind.PICKUP
                    and previous.dropped_zone_id != self.zone_id):
                raise ValueError('Pickup requires the actor at the actual dropped tool Zone')
            _require_usable(following, self.usable_hands)


def drop_tool(actor_id: str, inventory: ToolInventoryState, item_id: str, *,
        actor_zone_id: str, usable_hands: tuple[WeaponGrip, ...] = _BOTH_HANDS
        ) -> ToolInventoryTransition:
    _facts(actor_id, inventory, usable_hands)
    item = _item(inventory, item_id)
    following = replace(item, location=WeaponItemLocation.DROPPED,
        grip=None, dropped_zone_id=actor_zone_id)
    return ToolInventoryTransition(ToolInventoryTransitionKind.DROP, actor_id, item_id,
        inventory, inventory.with_item(following), actor_zone_id, usable_hands)


def stow_tool(actor_id: str, inventory: ToolInventoryState, item_id: str, *,
        usable_hands: tuple[WeaponGrip, ...] = _BOTH_HANDS) -> ToolInventoryTransition:
    _facts(actor_id, inventory, usable_hands)
    item = _item(inventory, item_id)
    following = replace(item, location=WeaponItemLocation.CARRIED, grip=None, dropped_zone_id=None)
    return ToolInventoryTransition(ToolInventoryTransitionKind.STOW, actor_id, item_id,
        inventory, inventory.with_item(following), usable_hands=usable_hands)


def equip_tool(actor_id: str, inventory: ToolInventoryState, item_id: str, grip: WeaponGrip, *,
        usable_hands: tuple[WeaponGrip, ...] = _BOTH_HANDS) -> ToolInventoryTransition:
    _facts(actor_id, inventory, usable_hands)
    item = _item(inventory, item_id)
    following = replace(item, location=WeaponItemLocation.HELD, grip=grip, dropped_zone_id=None)
    return ToolInventoryTransition(ToolInventoryTransitionKind.EQUIP, actor_id, item_id,
        inventory, inventory.with_item(following), usable_hands=usable_hands)


def pickup_tool(actor_id: str, inventory: ToolInventoryState, item_id: str, grip: WeaponGrip, *,
        actor_zone_id: str, usable_hands: tuple[WeaponGrip, ...] = _BOTH_HANDS
        ) -> ToolInventoryTransition:
    _facts(actor_id, inventory, usable_hands)
    item = _item(inventory, item_id)
    following = replace(item, location=WeaponItemLocation.HELD, grip=grip, dropped_zone_id=None)
    return ToolInventoryTransition(ToolInventoryTransitionKind.PICKUP, actor_id, item_id,
        inventory, inventory.with_item(following), actor_zone_id, usable_hands)
