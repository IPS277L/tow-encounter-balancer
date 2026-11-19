"""Finite Magic Weapon consequences, GM1.1 VI83–84 / ADR-0140.

These helpers preserve actual physical units and consume no RNG. The encounter
owner supplies the completed Attack/Wound/Test, validates its action clock and
geometry, and consumes that receipt once. A HIT alone never charges a Scarab
Knife; character charges wait until the actual Near Miss window has closed.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.attack_models import AttackOutcome
from towr.domain.injury_models import ProfileWoundRequest, ProfileWoundResult
from towr.domain.test_models import (
    DiceModifier, InitialTestRoll, RerollTrace, RollTrace, TestQuality,
    TestRequest, TestResult, _expected_initial_roll_parameters,
)
from towr.domain.weapon_catalog import WeaponKind, weapon_profile
from towr.domain.weapon_inventory_models import (
    WeaponGrip, WeaponInventoryState, WeaponItemLocation,
)
from towr.domain.weapon_use_models import WeaponUse
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleCompletionResult, CharacterWoundLifecycleOutcome,
)


GROTARGG_RETRIEVE_RULE_ID = 'RULE-MAGIC-ITEM-003:grotargg-retrieve'
SCARAB_CHARGE_RULE_ID = 'RULE-MAGIC-ITEM-003:scarab-actual-wound-charge'
SCARAB_HEAL_RULE_ID = 'RULE-MAGIC-ITEM-003:scarab-three-charges-heal'


def _inventory(value):
    if type(value) is not WeaponInventoryState:
        raise TypeError('Magic Weapon consequences require the exact full inventory')
    replace(value)


def _use(value):
    if type(value) is not WeaponUse:
        raise TypeError('Magic Weapon consequences require the frozen actual WeaponUse')
    replace(value)


def _source_item_ids(use, kind):
    return tuple(item_id for item_id in use.item_ids
        if use.inventory.item(item_id).kind is kind)


def _attack_inventories(use, outcome, higher_ground, target_inventory, disarmed_item_id):
    _use(use)
    if type(outcome) is not AttackOutcome or type(higher_ground) is not bool:
        raise TypeError('Magic Weapon consequences require exact Attack/context facts')
    if target_inventory is not None:
        _inventory(target_inventory)
    if disarmed_item_id is not None and (
            type(disarmed_item_id) is not str or not disarmed_item_id.strip()):
        raise TypeError('Fracasse must select one exact existing physical unit ID')
    actor_after, target_after = use.inventory, target_inventory
    if higher_ground and outcome is AttackOutcome.MISS:
        for item_id in _source_item_ids(use, WeaponKind.GROTARGGS_HAMMER):
            item = actor_after.item(item_id)
            actor_after = actor_after.with_item(replace(item,
                location=WeaponItemLocation.STUCK, grip=None))
    eligible = (() if target_inventory is None else tuple(item.id
        for item in target_inventory.items if item.location is WeaponItemLocation.HELD
        and weapon_profile(item.kind).magical))
    disarm = bool(_source_item_ids(use, WeaponKind.MORNING_STAR_OF_FRACASSE)
        and outcome is AttackOutcome.HIT and eligible)
    if not disarm:
        if disarmed_item_id is not None:
            raise ValueError('only an actual Fracasse HIT disarms a held magic weapon')
    elif disarmed_item_id not in eligible:
        raise ValueError('Fracasse HIT must disarm exactly one actual held Magic Weapon')
    else:
        item = target_inventory.item(disarmed_item_id)
        target_after = target_inventory.with_item(replace(item,
            location=WeaponItemLocation.DROPPED, grip=None))
    return actor_after, target_after


@dataclass(frozen=True, slots=True)
class WeaponMagicAttackTransition:
    use: WeaponUse
    outcome: AttackOutcome
    higher_ground: bool
    target_inventory: WeaponInventoryState | None
    disarmed_item_id: str | None
    actor_inventory: WeaponInventoryState
    after_target_inventory: WeaponInventoryState | None

    def __post_init__(self):
        expected = _attack_inventories(self.use, self.outcome, self.higher_ground,
            self.target_inventory, self.disarmed_item_id)
        _inventory(self.actor_inventory)
        if self.after_target_inventory is not None:
            _inventory(self.after_target_inventory)
        if (self.actor_inventory, self.after_target_inventory) != expected:
            raise ValueError('Magic Attack consequence changed another item or finite resource')


def prepare_weapon_magic_attack(use: WeaponUse, outcome: AttackOutcome, *,
        higher_ground=False, target_inventory=None, disarmed_item_id=None):
    actor, target = _attack_inventories(use, outcome, higher_ground,
        target_inventory, disarmed_item_id)
    return WeaponMagicAttackTransition(use, outcome, higher_ground,
        target_inventory, disarmed_item_id, actor, target)


def apply_weapon_magic_attack(current_inventory, current_target_inventory, transition):
    if type(transition) is not WeaponMagicAttackTransition:
        raise TypeError('Magic Attack application requires its exact typed transition')
    replace(transition)
    _inventory(current_inventory)
    if current_target_inventory is not None:
        _inventory(current_target_inventory)
    if (current_inventory != transition.use.inventory
            or current_target_inventory != transition.target_inventory):
        raise ValueError('Magic Attack consequence is replayed or detached from its frozen inventories')
    return transition.actor_inventory, transition.after_target_inventory


def _actual_wounds(wound, profile_request):
    if type(wound) is CharacterWoundLifecycleCompletionResult:
        if profile_request is not None:
            raise ValueError('a character lifecycle does not consume a Profile Wound source')
        # Completion includes the original roll/request, accepted Wound and the
        # actual Fate cancellation; re-admit the nested provenance too.
        replace(wound.source_request.roll.source_request.wound)
        replace(wound.source_request.roll.source_request)
        replace(wound.source_request.roll)
        replace(wound.source_request)
        replace(wound)
        return int(wound.outcome is CharacterWoundLifecycleOutcome.ACCEPTED)
    if type(wound) is not ProfileWoundResult or type(profile_request) is not ProfileWoundRequest:
        raise TypeError('Scarab requires actual completed character or full Profile Wound provenance')
    replace(profile_request)
    replace(profile_request.state)
    replace(wound)
    replace(wound.state)
    from towr.rules.injury_resolution import resolve_profile_wound
    expected = resolve_profile_wound(profile_request)
    if (wound != expected or type(wound.wounds_inflicted) is not int
            or type(wound.wounds_requested) is not int):
        raise ValueError('Scarab Profile Wound differs from its actual deterministic source')
    if type(wound.state) is not type(expected.state) or type(wound.state_change) is not type(expected.state_change):
        raise TypeError('Scarab Profile Wound requires exact injury/state-change families')
    if (type(wound.state_change.previous_wounds) is not int
            or type(wound.state_change.current_wounds) is not int
            or type(wound.state_change.defeated) is not bool
            or type(wound.state_change.npc_type) is not type(profile_request.npc_type)):
        raise TypeError('Scarab Profile Wound requires exact state-change counters')
    return wound.wounds_inflicted


def _charge_inventory(use, current_inventory, wound, profile_request):
    _use(use)
    _inventory(current_inventory)
    ids = _source_item_ids(use, WeaponKind.SCARAB_KNIFE)
    if not ids:
        raise ValueError('only an actually contributing Scarab Knife can acquire a Wound charge')
    count = _actual_wounds(wound, profile_request)
    after = current_inventory
    for item_id in ids:
        source = use.inventory.item(item_id)
        item = current_inventory.item(item_id)
        # Injury/mandatory continuation may have dropped the same unit. Never
        # recover it or restore old charges when crediting the actual Wound.
        if (item.source != source.source or item.initial_actor_id != source.initial_actor_id
                or item.source_item_id != source.source_item_id or item.unit_index != source.unit_index):
            raise ValueError('Scarab Wound charge must retain the actual contributing physical source')
        after = after.with_item(replace(item, charges=item.charges + count))
    return after


@dataclass(frozen=True, slots=True)
class WeaponScarabWoundCharge:
    use: WeaponUse
    previous_inventory: WeaponInventoryState
    wound: CharacterWoundLifecycleCompletionResult | ProfileWoundResult
    profile_request: ProfileWoundRequest | None
    after_inventory: WeaponInventoryState

    def __post_init__(self):
        expected = _charge_inventory(self.use, self.previous_inventory, self.wound, self.profile_request)
        _inventory(self.after_inventory)
        if self.after_inventory != expected:
            raise ValueError('Scarab actual Wound charge changed another item or resource')


def prepare_scarab_wound_charge(use, current_inventory, wound, *, profile_request=None):
    return WeaponScarabWoundCharge(use, current_inventory, wound, profile_request,
        _charge_inventory(use, current_inventory, wound, profile_request))


def apply_scarab_wound_charge(current_inventory, transition):
    if type(transition) is not WeaponScarabWoundCharge:
        raise TypeError('Scarab charge application requires its exact actual-Wound transition')
    replace(transition)
    _inventory(current_inventory)
    if current_inventory != transition.previous_inventory:
        raise ValueError('Scarab charge is replayed or detached from the current inventory')
    return transition.after_inventory


def _healing_inventory(use, item_id):
    _use(use)
    if item_id not in _source_item_ids(use, WeaponKind.SCARAB_KNIFE):
        raise ValueError('Scarab healing requires one actual held usable Knife')
    item = use.inventory.item(item_id)
    if item.charges < 3:
        raise ValueError('Scarab healing spends three actual charges of that same Knife')
    return use.inventory.with_item(replace(item, charges=item.charges - 3))


@dataclass(frozen=True, slots=True)
class WeaponScarabHealingResources:
    use: WeaponUse
    item_id: str
    after_inventory: WeaponInventoryState

    def __post_init__(self):
        _inventory(self.after_inventory)
        if self.after_inventory != _healing_inventory(self.use, self.item_id):
            raise ValueError('Scarab healing changed another item or a different charge stock')


def prepare_scarab_healing_resources(use, item_id):
    """Spend resources only; the paid Recover owner heals its actual Wound."""
    return WeaponScarabHealingResources(use, item_id, _healing_inventory(use, item_id))


def apply_scarab_healing_resources(current_inventory, transition):
    if type(transition) is not WeaponScarabHealingResources:
        raise TypeError('Scarab healing requires its exact resource transition')
    replace(transition)
    _inventory(current_inventory)
    if current_inventory != transition.use.inventory:
        raise ValueError('Scarab healing resources are replayed or detached from current inventory')
    return transition.after_inventory


def prepare_hammer_retrieval_test(test: TestRequest) -> TestRequest:
    """Apply the printed Very Difficult Brawn price once to a real Test source."""
    if type(test) is not TestRequest:
        raise TypeError('Hammer retrieval requires its exact Brawn Test source')
    replace(test)
    if any(mod.rule_id == GROTARGG_RETRIEVE_RULE_ID for mod in test.dice_modifiers):
        raise ValueError('Hammer retrieval difficulty cannot be applied twice')
    return replace(test, dice_modifiers=(*test.dice_modifiers,
        DiceModifier(GROTARGG_RETRIEVE_RULE_ID, -2)))


def _validate_retrieval_test(request, result):
    """Validate the full already-owned Test trace, without new rolls."""
    if type(request) is not TestRequest or type(result) is not TestResult or type(result.trace) is not RollTrace:
        raise TypeError('Hammer retrieval requires the complete typed Test and result')
    replace(request)
    mods = tuple(mod for mod in request.dice_modifiers if mod.rule_id == GROTARGG_RETRIEVE_RULE_ID)
    if mods != (DiceModifier(GROTARGG_RETRIEVE_RULE_ID, -2),):
        raise ValueError('Hammer retrieval requires its one actual Very Difficult modifier')
    trace = result.trace
    parameters = _expected_initial_roll_parameters(request)
    InitialTestRoll(request, *parameters, trace.initial_values)
    for name in ('base_dice', 'pool_cap', 'regular_dice_delta', 'cap_bypassing_dice',
            'dice_before_minimum', 'rolled_dice', 'threshold', 'rolled_successes',
            'success_delta', 'successes'):
        if type(getattr(trace, name)) is not int:
            raise TypeError('Hammer Test counters must be exact integers')
    if type(trace.minimum_die_rule_applied) is not bool:
        raise TypeError('Hammer Test minimum flag must be an exact bool')
    if any(type(getattr(trace, name)) is not tuple for name in (
            'initial_values', 'final_values', 'rerolls', 'applied_rule_ids')):
        raise TypeError('Hammer Test trace collections require exact tuples')
    if any(type(value) is not int or not 1 <= value <= 10 for value in trace.initial_values):
        raise TypeError('Hammer Test requires exact d10 values')
    grim = any(mod.quality is TestQuality.GRIM for mod in request.quality_modifiers)
    glorious = any(mod.quality is TestQuality.GLORIOUS for mod in request.quality_modifiers)
    quality = TestQuality.NORMAL if grim == glorious else TestQuality.GRIM if grim else TestQuality.GLORIOUS
    locked = {mod.value for mod in request.reroll_locks}
    eligible = tuple(index for index, value in enumerate(trace.initial_values)
        if value not in locked and (value <= parameters[6] if quality is TestQuality.GRIM else value > parameters[6]))
    if any(type(reroll) is not RerollTrace for reroll in trace.rerolls):
        raise TypeError('Hammer Test rerolls require exact typed traces')
    indices = tuple(reroll.index for reroll in trace.rerolls)
    if (quality is TestQuality.NORMAL and indices or quality is TestQuality.GRIM and indices != eligible
            or quality is TestQuality.GLORIOUS and (indices != tuple(sorted(set(indices)))
                or any(index not in eligible for index in indices))):
        raise ValueError('Hammer Test rerolls differ from its actual quality/source')
    final = list(trace.initial_values)
    for reroll in trace.rerolls:
        if any(type(value) is not int for value in (reroll.index, reroll.original, reroll.replacement)):
            raise TypeError('Hammer Test reroll coordinates require exact integers')
        if reroll.original != final[reroll.index] or not 1 <= reroll.replacement <= 10:
            raise ValueError('Hammer Test reroll changed its source or d10 value')
        final[reroll.index] = reroll.replacement
    successes = sum(value <= parameters[6] for value in final)
    delta = sum(mod.amount for mod in request.success_modifiers)
    rules = tuple(mod.rule_id for mods in (request.dice_modifiers, request.quality_modifiers,
        request.success_modifiers, request.reroll_locks) for mod in mods)
    expected = RollTrace(request.id, *parameters, quality, trace.initial_values,
        trace.rerolls, tuple(final), successes, delta, max(0, successes + delta), rules)
    if trace != expected:
        raise ValueError('Hammer Test trace is not canonical for its actual bound request')


def _hammer_inventory(inventory, item_id, usable_hands, test, result):
    _inventory(inventory)
    if type(item_id) is not str or not item_id:
        raise TypeError('Hammer retrieval requires the exact physical unit ID')
    if (type(usable_hands) is not tuple or any(type(hand) is not WeaponGrip for hand in usable_hands)
            or len(set(usable_hands)) != len(usable_hands)):
        raise TypeError('Hammer retrieval requires an exact tuple of actual usable hands')
    item = inventory.item(item_id)
    if item.kind is not WeaponKind.GROTARGGS_HAMMER or item.location is not WeaponItemLocation.STUCK:
        raise ValueError('Hammer retrieval requires this same actual embedded Grotargg item')
    if set(usable_hands) != {WeaponGrip.LEFT, WeaponGrip.RIGHT} or inventory.shield_hand is not None:
        raise ValueError('Hammer retrieval requires both actual usable free hands')
    if any(other.location is WeaponItemLocation.HELD for other in inventory.items):
        raise ValueError('Hammer retrieval cannot displace another held weapon')
    _validate_retrieval_test(test, result)
    return (inventory.with_item(replace(item, location=WeaponItemLocation.HELD, grip=WeaponGrip.BOTH))
        if result.succeeded else inventory)


@dataclass(frozen=True, slots=True)
class WeaponHammerRetrievalTransition:
    previous_inventory: WeaponInventoryState
    item_id: str
    usable_hands: tuple[WeaponGrip, ...]
    test: TestRequest
    result: TestResult
    after_inventory: WeaponInventoryState

    def __post_init__(self):
        expected = _hammer_inventory(self.previous_inventory, self.item_id,
            self.usable_hands, self.test, self.result)
        _inventory(self.after_inventory)
        if self.after_inventory != expected:
            raise ValueError('Hammer retrieval changed another item, charge or Test outcome')


def prepare_hammer_retrieval(inventory, item_id, usable_hands, test, result):
    """Preserve the paid alternate Recover result; caller proves Brawn/position."""
    return WeaponHammerRetrievalTransition(inventory, item_id, usable_hands, test,
        result, _hammer_inventory(inventory, item_id, usable_hands, test, result))


def apply_hammer_retrieval(current_inventory, transition):
    if type(transition) is not WeaponHammerRetrievalTransition:
        raise TypeError('Hammer retrieval requires its exact completed transition')
    replace(transition)
    _inventory(current_inventory)
    if current_inventory != transition.previous_inventory:
        raise ValueError('Hammer retrieval is replayed or detached from the current inventory')
    return transition.after_inventory
