"""Actual alternate Recover/Brawn extraction of a stuck Grotargg unit, GM83.

Selection belongs to tactics. This owner admits the real held/ground/hand facts,
completes one already-owned Test, and retains the same finite item on failure.
It never substitutes a fictitious Condition or standard Recover benefits.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition
from towr.domain.fate_models import FateGloriousSpendResult
from towr.domain.pc_battlefield_models import PcBattlefieldState
from towr.domain.recover_models import (
    RecoverActionExecutionRequest, RecoverActionExecutionResult,
    RecoverConditionTarget, RecoverHammerRetrievalChoice, RecoverHammerRetrievalResult,
    RecoverMode, _expected_recover_execution,
)
from towr.domain.test_models import Skill, QualityModifier, TestQuality
from towr.domain.turn_models import CombatActionKind
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_inventory_models import WeaponGrip, WeaponItemLocation
from towr.domain.weapon_magic_lifecycle import (
    WeaponHammerRetrievalTransition, prepare_hammer_retrieval,
    prepare_hammer_retrieval_test,
)
from towr.rules.recover_resolution import _complete_hammer_retrieval_after_test

if TYPE_CHECKING:
    from towr.domain.pc_briarroot_weapon_models import PcBriarrootDroppedWeapon
    from towr.domain.pc_melee_result_models import PcFateDecline


def _hands(state, actor):
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_heavy_wound_models import usable_hands
        return tuple(WeaponGrip(hand.value) for hand in usable_hands(state.participant(actor)))
    return WeaponGrip.LEFT, WeaponGrip.RIGHT


def hammer_retrieval_option(state, actor):
    """One actual active STUCK unit in Close; never call the tactic selector."""
    from towr.domain.pc_magic_weapon_models import actor_inventory, actor_injury
    from towr.domain.pc_briarroot_weapon_models import (
        briarroot_weapon_on_ground, _ground_weapon_close,
    )
    from towr.domain.pc_extinguish_models import _enemy_in_zone
    if actor not in (*state.source.pc_activation_order, *state.source.enemy_activation_order):
        raise ValueError('Hammer retrieval requires an actual source participant')
    turn = state.round_state.active_turn
    if (turn is None or turn.actor_id != actor or state.pending
            or state.pending_wound is not None or state.magic_pending is not None
            or turn.action_slots and turn.action_slots[-1].executed):
        return None
    injury = actor_injury(state, actor)
    if (getattr(injury, 'dead', False) or getattr(injury, 'defeated', False)
            or actor in state.exited_npc_ids or injury.conditions.has(Condition.DEFENCELESS)
            or injury.conditions.has(Condition.BROKEN) and _enemy_in_zone(state, actor)):
        return None
    inventory = actor_inventory(state, actor)
    if inventory is None:
        return None
    selected = inventory.active
    if (selected is None or selected.kind is not WeaponKind.GROTARGGS_HAMMER
            or selected.location is not WeaponItemLocation.STUCK
            or inventory.shield_hand is not None
            or any(item.location is WeaponItemLocation.HELD for item in inventory.items)
            or set(_hands(state, actor)) != {WeaponGrip.LEFT, WeaponGrip.RIGHT}):
        return None
    brawn = (state.source.participant(actor).pc.brawn if actor in state.source.pc_activation_order
        else getattr(state.enemy(actor).definition.generated_components, 'brawn', None))
    if brawn is None:
        return None
    item = briarroot_weapon_on_ground(state, actor, selected.id)
    if item is None:
        return None
    try:
        close = _ground_weapon_close(state, actor, item)
    except (KeyError, ValueError):
        return None
    return selected.id if close else None


def _test(state, actor, test_id):
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_melee_result_models import _pc_test
        test = _pc_test(state, actor, test_id, Skill.BRAWN, weapon_use=None)
    else:
        from towr.domain.pc_weighted_net_models import _brawn_test
        from towr.domain.pc_armour_models import actor_armour_test_modifiers
        from towr.domain.pc_magic_weapon_models import actor_injury
        test = _brawn_test(state, actor, test_id)
        conditions = actor_injury(state, actor).conditions
        modifiers = (*test.dice_modifiers, *actor_armour_test_modifiers(state, actor, Skill.BRAWN))
        if conditions.has(Condition.DRAINED):
            modifiers = tuple(mod for mod in modifiers if mod.amount <= 0)
        quality = test.quality_modifiers
        if conditions.has(Condition.BLINDED):
            quality = (*quality, QualityModifier('RULE-HEALTH-008:blinded', TestQuality.GRIM))
        test = replace(test, dice_modifiers=modifiers, quality_modifiers=quality)
    return prepare_hammer_retrieval_test(test)


def build_pc_hammer_retrieval(state):
    turn = state.round_state.active_turn
    if (turn is None or not turn.action_slots or turn.action_slots[-1].executed
            or turn.action_slots[-1].declaration.kind is not CombatActionKind.RECOVER):
        raise ValueError('Hammer extraction requires its actual reserved unused Recover slot')
    actor = turn.actor_id
    item_id = hammer_retrieval_option(state, actor)
    if item_id is None:
        raise ValueError('Hammer extraction requires the actual Close stuck unit and usable two-handed grip')
    from towr.domain.pc_magic_weapon_models import actor_injury
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    from towr.domain.pc_extinguish_models import _enemy_in_zone
    action = pc_melee_action_id(state, actor) + ':hammer-retrieval'
    conditions = actor_injury(state, actor).conditions
    choice = RecoverHammerRetrievalChoice(RecoverConditionTarget(actor, conditions, None),
        item_id, _test(state, actor, action + ':brawn'))
    return RecoverActionExecutionRequest(action, state.round_state, actor, conditions,
        _enemy_in_zone(state, actor), len(turn.action_slots), RecoverMode.RETRIEVE_HAMMER, choice)


@dataclass(frozen=True, slots=True)
class PcHammerRetrievalProof:
    request: RecoverActionExecutionRequest
    effective: RecoverActionExecutionRequest
    result: RecoverActionExecutionResult
    resources: WeaponHammerRetrievalTransition
    previous_item: PcBriarrootDroppedWeapon
    item: PcBriarrootDroppedWeapon
    previous: PcBattlefieldState | None
    state: PcBattlefieldState | None
    fate_decline: PcFateDecline | None = None
    glorious: FateGloriousSpendResult | None = None

    @property
    def actor_id(self):
        return self.request.actor_id

    @property
    def weapon_id(self):
        return self.request.choice.item_id


def complete_pc_hammer_retrieval(state, request, effective, result,
        fate_decline=None, glorious=None):
    """Bind one actual completed Brawn Test to this paid action and ground item."""
    from towr.domain.pc_magic_weapon_models import actor_inventory
    from towr.domain.pc_briarroot_weapon_models import briarroot_weapon_on_ground, _remove_marker
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    expected = build_pc_hammer_retrieval(state)
    if request != expected:
        raise ValueError('Hammer Recover changed its actual original action/item/Test source')
    validate_pc_melee_source_types(request, expected)
    if type(effective) is not RecoverActionExecutionRequest or type(result) is not RecoverActionExecutionResult:
        raise TypeError('Hammer Recover requires its exact effective request and completed action')
    if (effective.mode is not RecoverMode.RETRIEVE_HAMMER
            or type(effective.choice) is not RecoverHammerRetrievalChoice):
        raise TypeError('Hammer Recover requires its actual alternative effective choice')
    if type(result.resolution) is not RecoverHammerRetrievalResult:
        raise TypeError('Hammer Recover cannot claim standard benefits or Condition removal')
    after_fate = replace(request, choice=replace(request.choice, test=effective.choice.test))
    if effective != after_fate:
        raise ValueError('Hammer Fate window changed facts other than its actual Test')
    validate_pc_melee_source_types(effective, after_fate)
    canonical = _expected_recover_execution(effective,
        _complete_hammer_retrieval_after_test(effective.choice, result.resolution.test_result))
    if result != canonical:
        raise ValueError('Hammer Recover changed its actual execution, Test or action clock')
    validate_pc_melee_source_types(result, canonical)
    actor = request.actor_id
    resources = prepare_hammer_retrieval(actor_inventory(state, actor), request.choice.item_id,
        _hands(state, actor), effective.choice.test, result.resolution.test_result)
    previous_item = briarroot_weapon_on_ground(state, actor, request.choice.item_id)
    item = replace(previous_item, ground=None) if result.resolution.succeeded else previous_item
    after = _remove_marker(state.battlefield, previous_item) if result.resolution.succeeded else state.battlefield
    return PcHammerRetrievalProof(request, effective, result, resources, previous_item, item,
        state.battlefield, after, fate_decline, glorious)


def project_pc_hammer_retrieval(state, proof):
    if type(proof) is not PcHammerRetrievalProof:
        raise TypeError('Hammer Recover requires its exact source-bound proof')
    if (type(proof.result) is not RecoverActionExecutionResult
            or type(proof.result.resolution) is not RecoverHammerRetrievalResult):
        raise TypeError('Hammer Recover requires its actual completed alternative result')
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types, _test_result, pc_after_test
    from towr.domain.pc_magic_weapon_models import replace_actor_inventory
    from towr.domain.pc_briarroot_weapon_models import _bank, _set_item
    original = build_pc_hammer_retrieval(state)
    actor = original.actor_id
    actual = proof.result.resolution.test_result
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_fate_test_models import validate_pc_test_fate
        effective_test, fate = validate_pc_test_fate(state, actor, Skill.BRAWN,
            original.choice.test, actual, proof.fate_decline, proof.glorious)
    else:
        if proof.fate_decline is not None or proof.glorious is not None:
            raise ValueError('NPC Hammer retrieval cannot invent PC Fate')
        _test_result(original.choice.test, actual)
        effective_test, fate = original.choice.test, None
    effective = replace(original, choice=replace(original.choice, test=effective_test))
    result = _expected_recover_execution(effective,
        _complete_hammer_retrieval_after_test(effective.choice, actual))
    expected = complete_pc_hammer_retrieval(state, original, effective, result,
        proof.fate_decline, proof.glorious)
    if proof != expected:
        raise ValueError('Hammer Recover changed its complete item, inventory, Test, ground or clock source')
    validate_pc_melee_source_types(proof, expected)
    updates = dict(round_state=result.round_state, battlefield=expected.state,
        briarroot_dropped_weapons=_set_item(_bank(state), expected.item))
    updates = replace_actor_inventory(state, actor, expected.resources.after_inventory, updates)
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_heavy_wound_models import critical_for_action
        from towr.domain.pc_melee_models import PcTwoHandedGrip
        from towr.domain.pc_weapon_inventory import replace_pc_member
        injury = critical_for_action(state.participant(actor), CombatActionKind.RECOVER,
            used_hand=PcTwoHandedGrip.BOTH)
        injury = pc_after_test(state, actor, injury)
        updates['party'] = tuple(replace_pc_member(member, injury=injury, fate=fate)
            if member.actor_id == actor else member for member in updates['party'])
    return updates
