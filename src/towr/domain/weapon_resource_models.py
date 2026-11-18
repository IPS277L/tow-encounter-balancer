"""Per-item Shooting resources and a bridge from actual K1 Reload receipts.

The Attack owner calls the shot transition only after the Test has genuinely
started: a miss consumes the same resources; a cancelled preflight does not.
The unit retains the complete authoritative K1 Reload state, including zero-
success contributions. The battle owner still proves receipt/clock membership
and single consumption for Tests without a resource change, such as a free bow.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.reload_models import ReloadActionExecutionResult, begin_reload_cycle
from towr.domain.reload_models import ReloadActionExecutionRequest
from towr.domain.exacting_test_models import ExactingTestContributionResult
from towr.domain.test_models import Skill
from towr.domain.weapon_catalog import WeaponKind, WeaponTrait
from towr.domain.weapon_inventory_models import (
    WeaponGrip, WeaponInventoryState, WeaponItemLocation, weapon_reload_cycle_id,
)
from towr.domain.weapon_use_models import WeaponUse


_REPEATER_TRAITS = (WeaponTrait.RELOAD_THREE_AFTER_BONUS, WeaponTrait.RELOAD_FIVE_AFTER_BONUS)


def _shooting_use(use):
    if type(use) is not WeaponUse:
        raise TypeError('weapon resources require the exact frozen WeaponUse')
    replace(use)
    if use.primary is None or use.skill is not Skill.SHOOTING:
        raise ValueError('shot and Reload resources require an actual primary Shooting weapon')
    return use.primary


def _inventory(value):
    if type(value) is not WeaponInventoryState:
        raise TypeError('weapon resources require the exact full inventory state')
    replace(value)


def _shot_inventory(use, uses_repeater_bonus, dragon_fire):
    item = _shooting_use(use)
    for value in (uses_repeater_bonus, dragon_fire):
        if type(value) is not bool:
            raise TypeError('shot resource choices require exact bool values')
    repeater = any(trait in use.primary_profile.trait_codes for trait in _REPEATER_TRAITS)
    if uses_repeater_bonus and not repeater:
        raise ValueError('only an actual Repeater can consume its optional bonus')
    if dragon_fire and item.kind is not WeaponKind.DRAGON_BOW:
        raise ValueError('Dragon fire belongs only to the actual Dragon Bow')
    if dragon_fire and item.dragon_arrow_used:
        raise ValueError('the Dragon Bow activation was already used this battle')
    reload = item.reload
    if reload is not None:
        if not reload.loaded:
            raise ValueError('an empty Shooting weapon cannot begin another shot')
        if not repeater or uses_repeater_bonus:
            reload = begin_reload_cycle(reload,
                weapon_reload_cycle_id(item.id, len(reload.reload_cycle_ids)+1))
    following = replace(item, reload=reload,
        dragon_arrow_used=item.dragon_arrow_used or dragon_fire)
    return use.inventory.with_item(following)


@dataclass(frozen=True, slots=True)
class WeaponShotResourceTransition:
    use: WeaponUse
    uses_repeater_bonus: bool
    dragon_fire: bool
    after_inventory: WeaponInventoryState

    def __post_init__(self):
        expected = _shot_inventory(self.use, self.uses_repeater_bonus, self.dragon_fire)
        _inventory(self.after_inventory)
        if self.after_inventory != expected:
            raise ValueError('shot resources changed another item, source or unrelated resource')


def prepare_weapon_shot_resources(use: WeaponUse, *, uses_repeater_bonus=False,
        dragon_fire=False) -> WeaponShotResourceTransition:
    """Prepare the consequence of a genuinely started Shooting Test, without RNG."""
    return WeaponShotResourceTransition(use, uses_repeater_bonus, dragon_fire,
        _shot_inventory(use, uses_repeater_bonus, dragon_fire))


def apply_weapon_shot_resources(current_inventory: WeaponInventoryState,
        transition: WeaponShotResourceTransition) -> WeaponInventoryState:
    """Require the whole frozen source; the Attack owner guards its Test receipt."""
    _inventory(current_inventory)
    if type(transition) is not WeaponShotResourceTransition:
        raise TypeError('shot application requires its exact resource transition')
    replace(transition)
    if current_inventory != transition.use.inventory:
        raise ValueError('shot resource transition is replayed or detached from the current inventory')
    return transition.after_inventory


def _reload_inventory(use, result):
    item = _shooting_use(use)
    if type(result) is not ReloadActionExecutionResult:
        raise TypeError('Reload bridge requires its exact completed K1 action result')
    # Re-admit the real action, Exacting contribution and executed action slot;
    # do not reconstruct contribution histories or execute another Test.
    replace(result)
    if type(result.source_request) is not ReloadActionExecutionRequest or type(result.exacting) is not ExactingTestContributionResult:
        raise TypeError('Reload bridge requires its exact K1 action and Exacting sources')
    replace(result.source_request)
    replace(result.exacting)
    if item.reload is None:
        raise ValueError('a free-reload weapon has no Exacting action to bridge')
    if set(use.usable_hands) != {WeaponGrip.LEFT, WeaponGrip.RIGHT}:
        raise ValueError('Reload requires both actual usable hands')
    if use.inventory.shield_hand is not None:
        raise ValueError('Reload requires the actual Shield hand to be freed first')
    if any(other.id != item.id and other.location is WeaponItemLocation.HELD for other in use.inventory.items):
        raise ValueError('Reload requires the second hand to be freed from other held weapons')
    source = result.source_request
    if type(source.actor_id) is not str or source.actor_id != use.actor_id:
        raise ValueError('Reload result belongs to another actual actor')
    previous = result.previous_state
    if (type(previous.weapon_instance_id) is not str or previous.weapon_instance_id != item.id
            or previous.weapon_id.value != item.kind.value):
        raise ValueError('Reload result belongs to another physical item or weapon profile')
    if previous != item.reload:
        raise ValueError('Reload result must retain the complete actual previous K1 state')
    return use.inventory.with_item(replace(item, reload=result.state))


@dataclass(frozen=True, slots=True)
class WeaponReloadResourceTransition:
    use: WeaponUse
    result: ReloadActionExecutionResult
    after_inventory: WeaponInventoryState

    def __post_init__(self):
        expected = _reload_inventory(self.use, self.result)
        _inventory(self.after_inventory)
        if self.after_inventory != expected:
            raise ValueError('Reload bridge changed another item, source or unrelated resource')


def apply_weapon_reload_result(use: WeaponUse,
        result: ReloadActionExecutionResult) -> WeaponReloadResourceTransition:
    """Carry actual K1 progress into the same item without rolling or buying an action.

    The unit stores ``result.state`` itself, without reducing progress or
    copying counters. The battle owner retains the action receipt/current clock,
    compares ``use.inventory`` to its actual inventory, and applies any real
    injured-hand consequences. This transition cannot waive those costs.
    """
    return WeaponReloadResourceTransition(use, result, _reload_inventory(use, result))
