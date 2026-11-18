"""Role-independent finite weapon sources and per-battle item states.

The immutable origin identifies an item; it is not a current-owner permission.
Ground positions, paid interactions and their journal proofs belong to their
respective owners. These models do not move items or apply Conditions.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from towr.domain.exacting_test_models import (
    ExactingOpposedTestContribution, ExactingTestContribution, ExactingTestProgress,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponId
from towr.domain.reload_models import (
    ReloadableWeaponState, begin_reload_cycle, create_initial_ranged_weapon_reload_state,
)
from towr.domain.weapon_catalog import WeaponGroup, WeaponKind, WeaponTrait, weapon_profile


WEAPON_COUNT_BURDEN_RULE_ID = 'RULE-EQUIPMENT-002:weapon-count-burden'
TWO_HANDED_COUNT_BURDEN_RULE_ID = 'RULE-EQUIPMENT-002:two-handed-count-burden'


class WeaponHand(str, Enum):
    LEFT = 'left'
    RIGHT = 'right'


class WeaponTwoHandedGrip(str, Enum):
    BOTH = 'both'


class WeaponGrip(str, Enum):
    LEFT = 'left'
    RIGHT = 'right'
    BOTH = 'both'


class WeaponItemLocation(str, Enum):
    HELD = 'held'
    CARRIED = 'carried'
    DROPPED = 'dropped'
    DEPLOYED = 'deployed'
    STUCK = 'stuck'
    SPENT = 'spent'


def _identifier(value, label):
    if type(value) is not str or not value.strip():
        raise TypeError(label+' requires an exact nonempty identifier')


def _integer(value, label, minimum=0):
    if type(value) is not int:
        raise TypeError(label+' requires an exact integer')
    if value < minimum:
        raise ValueError(label+' is below its permitted minimum')


def _grip(kind, location, grip):
    if type(location) is not WeaponItemLocation:
        raise TypeError('item location requires its exact typed value')
    if grip is not None and type(grip) is not WeaponGrip:
        raise TypeError('item grip requires its exact typed value or None')
    if location is not WeaponItemLocation.HELD:
        if grip is not None:
            raise ValueError('a non-held item has no occupied weapon hand')
        return
    if grip is None:
        raise ValueError('a held physical weapon requires its actual grip')
    profile = weapon_profile(kind)
    if profile.hands is RangedWeaponHands.TWO_HANDED:
        if grip is not WeaponGrip.BOTH:
            raise ValueError('a held printed 2H item occupies both hands')
    elif grip is WeaponGrip.BOTH and not profile.variable_grip:
        # Rock's printed n/a is preserved in the catalogue; ADR-0140 explicitly
        # requires one usable hand to throw it, rather than inventing printed 1H.
        raise ValueError('this physical weapon has no two-handed grip')


def weapon_reload_target(kind: WeaponKind) -> int | None:
    """Only the printed Exacting target, without a RangedWeaponId dependency."""
    traits = weapon_profile(kind).trait_codes
    targets = tuple(value for trait, value in (
        (WeaponTrait.RELOAD_TWO_SUCCESSES, 2),
        (WeaponTrait.RELOAD_THREE_SUCCESSES, 3),
        (WeaponTrait.RELOAD_FOUR_SUCCESSES, 4),
        (WeaponTrait.RELOAD_THREE_AFTER_BONUS, 3),
        (WeaponTrait.RELOAD_FIVE_AFTER_BONUS, 5),
    ) if trait in traits)
    if len(set(targets)) > 1:
        raise ValueError('weapon catalogue has conflicting Exacting targets')
    return targets[0] if targets else None


@dataclass(frozen=True, slots=True)
class WeaponItemSource:
    id: str
    kind: WeaponKind
    initial_location: WeaponItemLocation
    initial_grip: WeaponGrip | None
    quantity: int = 1
    initially_loaded: bool | None = None
    initial_charges: int = 0
    gm_fit_confirmed: bool | None = None

    def __post_init__(self):
        _identifier(self.id, 'source item')
        profile = weapon_profile(self.kind)
        if not profile.physical:
            raise ValueError('Unarmed is an external attack mode, not an inventory item')
        if type(self.initial_location) is not WeaponItemLocation:
            raise TypeError('initial item location must be its exact typed value')
        if self.initial_location not in (WeaponItemLocation.HELD, WeaponItemLocation.CARRIED):
            raise ValueError('a source item begins held or carried')
        _grip(self.kind, self.initial_location, self.initial_grip)
        _integer(self.quantity, 'source quantity', 1)
        if self.quantity != 1 and profile.group is not WeaponGroup.THROWING:
            raise ValueError('separate melee weapons and guns require separate source instances')
        if self.initially_loaded is not None and type(self.initially_loaded) is not bool:
            raise TypeError('initially_loaded must be an exact bool or None')
        if weapon_reload_target(self.kind) is not None:
            if self.initially_loaded is None:
                raise ValueError('an Exacting or Repeater weapon requires its actual initial charge')
        elif self.initially_loaded is not None:
            raise ValueError('free-reload and non-Shooting weapons have no initial loaded flag')
        _integer(self.initial_charges, 'initial Scarab charges')
        if self.kind is not WeaponKind.SCARAB_KNIFE and self.initial_charges:
            raise ValueError('initial charges belong only to the actual Scarab Knife')
        if self.gm_fit_confirmed is not None and type(self.gm_fit_confirmed) is not bool:
            raise TypeError('GM weapon fit must be an exact bool or None')
        if self.kind is WeaponKind.OGRE_PISTOL:
            if self.gm_fit_confirmed is not True:
                raise ValueError('Ogre Pistol requires explicit GM confirmation of fit')
        elif self.gm_fit_confirmed is not None:
            raise ValueError('this source has no Ogre Pistol fit confirmation')


def weapon_unit_id(initial_actor_id: str, source_item_id: str, unit_index: int) -> str:
    """An injective origin namespace, including IDs that themselves contain ':'."""
    _identifier(initial_actor_id, 'initial item actor')
    _identifier(source_item_id, 'source item')
    _integer(unit_index, 'unit index')
    return ('weapon-unit:'+str(len(initial_actor_id))+':'+initial_actor_id+':'
        +str(len(source_item_id))+':'+source_item_id+':'+str(unit_index))


def weapon_reload_cycle_id(unit_id: str, cycle_index: int) -> str:
    """A deterministic, injective cycle ID for the same actual physical unit."""
    _identifier(unit_id, 'reload weapon unit')
    _integer(cycle_index, 'reload cycle index', 1)
    return 'weapon-reload-cycle:'+str(len(unit_id))+':'+unit_id+':'+str(cycle_index)


def _readmit_reload(reload: ReloadableWeaponState) -> None:
    """Validate the full K1 state and its retained contributions, without a mirror."""
    if type(reload) is not ReloadableWeaponState:
        raise TypeError('an Exacting weapon requires its actual K1 reload state')
    if type(reload.weapon_id) is not RangedWeaponId or type(reload.loaded) is not bool:
        raise TypeError('reload weapon kind and loaded flag require exact typed values')
    _integer(reload.required_successes, 'reload target', 1)
    if type(reload.reload_cycle_ids) is not tuple:
        raise TypeError('reload cycle history requires its exact tuple')
    for cycle_id in reload.reload_cycle_ids:
        _identifier(cycle_id, 'reload cycle history')
    if reload.exacting is not None:
        if type(reload.exacting) is not ExactingTestProgress:
            raise TypeError('reload progress requires its exact K1 Exacting state')
        if type(reload.exacting.contributions) is not tuple:
            raise TypeError('reload contributions require their exact tuple')
        for contribution in reload.exacting.contributions:
            if type(contribution) not in (ExactingTestContribution, ExactingOpposedTestContribution):
                raise TypeError('reload contribution requires its exact K1 source')
            replace(contribution)
        replace(reload.exacting)
    replace(reload)


@dataclass(frozen=True, slots=True)
class WeaponUnitState:
    source: WeaponItemSource
    id: str
    initial_actor_id: str
    source_item_id: str
    unit_index: int
    location: WeaponItemLocation
    grip: WeaponGrip | None
    reload: ReloadableWeaponState | None = None
    charges: int = 0
    dragon_arrow_used: bool = False

    def __post_init__(self):
        if type(self.source) is not WeaponItemSource:
            raise TypeError('weapon unit requires its exact immutable source')
        replace(self.source)
        _identifier(self.id, 'physical unit')
        _identifier(self.initial_actor_id, 'initial item actor')
        _identifier(self.source_item_id, 'source item')
        _integer(self.unit_index, 'unit index')
        if (self.source_item_id != self.source.id or self.unit_index >= self.source.quantity
                or self.id != weapon_unit_id(self.initial_actor_id, self.source.id, self.unit_index)):
            raise ValueError('physical unit ID, index and source must retain the same initial origin')
        _grip(self.source.kind, self.location, self.grip)
        target = weapon_reload_target(self.source.kind)
        if target is None:
            if self.reload is not None:
                raise ValueError('this weapon has no persistent Exacting state')
        else:
            _readmit_reload(self.reload)
            if (self.reload.weapon_instance_id != self.id
                    or self.reload.weapon_id.value != self.source.kind.value
                    or self.reload.required_successes != target):
                raise ValueError('K1 reload must retain this actual unit, weapon kind and target')
            expected_cycles = tuple(weapon_reload_cycle_id(self.id, index)
                for index in range(1, len(self.reload.reload_cycle_ids)+1))
            if self.reload.reload_cycle_ids != expected_cycles:
                raise ValueError('K1 reload cycle IDs must retain this unit and actual cycle order')
            if not self.reload.reload_cycle_ids and self.source.initially_loaded is not True:
                raise ValueError('an initially empty source has no initially loaded cycle zero')
        _integer(self.charges, 'Scarab charges')
        if self.source.kind is not WeaponKind.SCARAB_KNIFE and self.charges:
            raise ValueError('a different weapon cannot acquire Scarab charges')
        if type(self.dragon_arrow_used) is not bool:
            raise TypeError('Dragon Bow use requires an exact bool')
        if self.source.kind is not WeaponKind.DRAGON_BOW and self.dragon_arrow_used:
            raise ValueError('a different weapon cannot consume the Dragon Bow activation')

    @property
    def kind(self):
        return self.source.kind


    @property
    def weapon(self):
        return self.kind

    @property
    def hand(self):
        if self.grip is None:
            return None
        return WeaponTwoHandedGrip.BOTH if self.grip is WeaponGrip.BOTH else WeaponHand(self.grip.value)


def _same_unit_transition(previous, following):
    if (following.source != previous.source or following.id != previous.id
            or following.initial_actor_id != previous.initial_actor_id
            or following.source_item_id != previous.source_item_id
            or following.unit_index != previous.unit_index):
        raise ValueError('updating an item cannot replace its immutable source or origin')
    if previous.location is WeaponItemLocation.SPENT and following.location is not WeaponItemLocation.SPENT:
        raise ValueError('a spent unit cannot be refilled by an inventory update')
    if previous.dragon_arrow_used and not following.dragon_arrow_used:
        raise ValueError('an inventory update cannot restore a spent Dragon Bow activation')
    before, after = previous.reload, following.reload
    if before is None:
        return
    if before.loaded:
        if after.loaded:
            if after != before:
                raise ValueError('moving a loaded weapon cannot rewrite its reload history')
        else:
            next_cycle = weapon_reload_cycle_id(previous.id, len(before.reload_cycle_ids)+1)
            if after != begin_reload_cycle(before, next_cycle):
                raise ValueError('firing a loaded item opens exactly its next empty K1 cycle')
    else:
        if (after.reload_cycle_ids != before.reload_cycle_ids
                or after.reload_cycle_id != before.reload_cycle_id):
            raise ValueError('a partial reload cannot move to a different cycle')
        old_contributions = before.exacting.contributions
        new_contributions = after.exacting.contributions
        if new_contributions[:len(old_contributions)] != old_contributions:
            raise ValueError('an inventory update cannot remove or rewrite actual Reload work')


@dataclass(frozen=True, slots=True)
class WeaponInventoryState:
    """Actual items and an optional selected unit, which need not still be held.

    Selection preserves Recover/drop context; WeaponUse separately proves that
    a selected implement is actually held and usable before granting effects.
    """
    items: tuple[WeaponUnitState, ...] = ()
    active_item_id: str | None = None
    shield_hand: WeaponGrip | None = None

    def __post_init__(self):
        if type(self.items) is not tuple or any(type(item) is not WeaponUnitState for item in self.items):
            raise TypeError('inventory items require an exact tuple of typed physical units')
        for item in self.items:
            replace(item)
        ids = tuple(item.id for item in self.items)
        if len(set(ids)) != len(ids):
            raise ValueError('the same physical unit cannot occupy two inventory entries')
        if self.active_item_id is not None:
            _identifier(self.active_item_id, 'selected weapon unit')
            if self.active_item_id not in ids:
                raise ValueError('a selected weapon must be an actual existing unit')
        if self.shield_hand is not None:
            if type(self.shield_hand) is not WeaponGrip:
                raise TypeError('Shield hand requires its exact typed grip or None')
            if self.shield_hand is WeaponGrip.BOTH:
                raise ValueError('a Shield occupies one actual hand')
        occupied = set(() if self.shield_hand is None else (self.shield_hand,))
        for item in self.items:
            if item.location is not WeaponItemLocation.HELD:
                continue
            hands = (WeaponGrip.LEFT, WeaponGrip.RIGHT) if item.grip is WeaponGrip.BOTH else (item.grip,)
            if any(hand in occupied for hand in hands):
                raise ValueError('held weapons and Shield cannot share an occupied hand')
            occupied.update(hands)

    def item(self, item_id: str) -> WeaponUnitState:
        _identifier(item_id, 'weapon unit lookup')
        try:
            return next(item for item in self.items if item.id == item_id)
        except StopIteration:
            raise KeyError(item_id) from None

    @property
    def active(self) -> WeaponUnitState | None:
        return None if self.active_item_id is None else self.item(self.active_item_id)

    def with_item(self, item: WeaponUnitState) -> WeaponInventoryState:
        """Replace one existing unit; never reconstruct stock from its source."""
        replace(self)
        if type(item) is not WeaponUnitState:
            raise TypeError('inventory update requires its exact typed physical unit')
        replace(item)
        previous = self.item(item.id)
        _same_unit_transition(previous, item)
        return replace(self, items=tuple(item if old.id == item.id else old for old in self.items))


def initial_weapon_inventory(initial_actor_id: str, sources: tuple[WeaponItemSource, ...], *,
        active_item_id: str | None = None, shield_hand: WeaponGrip | None = None) -> WeaponInventoryState:
    """Expand finite stacks once: the first unit may be held, all others carried."""
    _identifier(initial_actor_id, 'initial inventory actor')
    if type(sources) is not tuple or any(type(source) is not WeaponItemSource for source in sources):
        raise TypeError('initial inventory requires an exact tuple of typed sources')
    if len({source.id for source in sources}) != len(sources):
        raise ValueError('initial inventory source IDs must be distinct')
    items = []
    for source in sources:
        replace(source)
        target = weapon_reload_target(source.kind)
        for index in range(source.quantity):
            unit_id = weapon_unit_id(initial_actor_id, source.id, index)
            reload = None
            if target is not None:
                reload = create_initial_ranged_weapon_reload_state(unit_id, RangedWeaponId(source.kind.value))
                if not source.initially_loaded:
                    reload = begin_reload_cycle(reload, weapon_reload_cycle_id(unit_id, 1))
            location = source.initial_location if index == 0 else WeaponItemLocation.CARRIED
            grip = source.initial_grip if location is WeaponItemLocation.HELD else None
            items.append(WeaponUnitState(source, unit_id,
                initial_actor_id, source.id, index, location, grip, reload, source.initial_charges))
    inventory = WeaponInventoryState(tuple(items), active_item_id, shield_hand)
    if active_item_id is not None and inventory.active.location is not WeaponItemLocation.HELD:
        raise ValueError('an initially selected weapon must actually begin held')
    return inventory


def carrying_burden_rule_ids(inventory: WeaponInventoryState, strength: int) -> tuple[str, ...]:
    """Return only independent PG92 carrying causes, without changing Conditions."""
    if type(inventory) is not WeaponInventoryState:
        raise TypeError('carrying requires the actual typed inventory state')
    replace(inventory)
    _integer(strength, 'Strength', 1)
    carried = tuple(item for item in inventory.items
        if item.location in (WeaponItemLocation.HELD, WeaponItemLocation.CARRIED))
    sources = []
    if len(carried) > strength:
        sources.append(WEAPON_COUNT_BURDEN_RULE_ID)
    if sum(weapon_profile(item.kind).hands is RangedWeaponHands.TWO_HANDED for item in carried) > 1:
        sources.append(TWO_HANDED_COUNT_BURDEN_RULE_ID)
    return tuple(sources)
