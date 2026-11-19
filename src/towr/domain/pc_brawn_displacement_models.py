"""Battle-owned PG69 Unarmed shove/drag choices and physical consequences.

The frozen Attack commits an alternative before its opposed Test. A shove
changes actual Close relations in the same Zone; dragging removes a real mount
through the existing forced-dismount owner, without inventing Prone.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.attack_models import AttackOutcome
from towr.domain.brawn_impact_models import (
    BrawnAttackEffect, BrawnDisplacementImpactResult, BrawnDisplacementRequest,
    prepare_brawn_displacement_impact,
)
from towr.domain.condition_models import Condition
from towr.domain.pc_battlefield_models import PcBattlefieldState, battlefield_range
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.test_models import Skill
from towr.domain.weapon_catalog import WeaponGroup, WeaponKind, WeaponTrait, weapon_profile
from towr.domain.weapon_inventory_models import WeaponGrip, WeaponItemLocation
from towr.domain.weapon_use_models import WeaponUse

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcAttackProof


def _alive(state, actor):
    if actor in state.source.pc_activation_order:
        return not state.participant(actor).injury.dead
    if actor in state.source.enemy_activation_order:
        return not state.enemy(actor).state.injury.defeated and actor not in state.exited_npc_ids
    raise ValueError('Brawn effect requires a participant of the actual source battle')


def _shove_battlefield(state, actor, target):
    before = state.battlefield
    if type(before) is not PcBattlefieldState:
        return None
    if (before.spatial.placement_for(actor).zone_id != before.spatial.placement_for(target).zone_id
            or battlefield_range(before, actor, target) is not RangedWeaponRange.CLOSE):
        return None
    after = replace(before, close_pairs=tuple(pair for pair in before.close_pairs if target not in pair))
    if battlefield_range(after, actor, target) is not RangedWeaponRange.SHORT:
        raise ValueError('a same-Zone shove must retain a genuine Short destination')
    from towr.domain.pc_briarroot_models import briarroot_movement_keeps_close
    if not briarroot_movement_keeps_close(state, target, after):
        return None
    return after


def _ready_later_shooter(state, actor, target, after):
    """Current held/loaded resources of an ally who still owns a later turn."""
    from towr.domain.pc_magic_weapon_models import actor_inventory, actor_injury
    from towr.domain.weapon_use_models import build_weapon_use
    from towr.domain.pc_heavy_wound_models import usable_hands
    order = (state.source.pc_activation_order if actor in state.source.pc_activation_order
        else state.source.enemy_activation_order)
    opposite = (tuple(enemy.state.actor_id for enemy in state.live_enemies)
        if actor in state.source.pc_activation_order else tuple(member.actor_id for member in state.live_party))
    unavailable = (*state.round_state.completed_turn_entity_ids, *state.round_state.excluded_turn_entity_ids)
    for ally in order[order.index(actor)+1:]:
        if ally in unavailable or not _alive(state, ally):
            continue
        injury = actor_injury(state, ally)
        if injury.conditions.has(Condition.DEFENCELESS) or injury.conditions.has(Condition.BROKEN):
            continue
        inventory = actor_inventory(state, ally)
        if inventory is None:
            continue
        from towr.domain.pc_armour_models import actor_bound_to_chivalric_combat
        from towr.domain.pc_scene_feature_models import scene_attack_visibility
        if (actor_bound_to_chivalric_combat(state, ally)
                or not scene_attack_visibility(state, ally, target, Skill.SHOOTING).visible):
            continue
        hands = (tuple(WeaponGrip(hand.value) for hand in usable_hands(state.participant(ally)))
            if ally in state.source.pc_activation_order else (WeaponGrip.LEFT, WeaponGrip.RIGHT))
        if not any(battlefield_range(state.battlefield, ally, foe) is RangedWeaponRange.CLOSE for foe in opposite):
            continue
        if any(battlefield_range(after, ally, foe) is RangedWeaponRange.CLOSE for foe in opposite):
            continue
        for item in inventory.items:
            profile = weapon_profile(item.kind)
            if (item.location is not WeaponItemLocation.HELD or profile.group is not WeaponGroup.SHOOTING
                    or profile.optimum_range_min is RangedWeaponRange.CLOSE
                    or WeaponTrait.AIM_REQUIRED in profile.trait_codes
                    or item.reload is not None and not item.reload.loaded):
                continue
            try:
                use = build_weapon_use(ally, inventory, item.id, usable_hands=hands)
            except ValueError:
                continue
            # The ally must actually be able to reach the same newly separated
            # target with this weapon; a distant ready gun is not a free shot.
            from towr.domain.weapon_range_models import WeaponRangeContext, assess_weapon_attack_range
            band = battlefield_range(after, ally, target)
            strength = (state.source.participant(ally).pc.strength if ally in state.source.pc_activation_order
                else state.enemy(ally).definition.generated_components.strength)
            try:
                prepared = assess_weapon_attack_range(use.kind, WeaponRangeContext(band, strength,
                    has_enemy_in_close_range=False,
                    gm_shooting_maximum=state.source.battlefield.two_handed_max_range))
            except (ValueError, TypeError):
                continue
            if prepared.allowed:
                return True
    return False


def selected_brawn_effect(state, actor, target, use):
    """Choose only a supported actual benefit; manual PC keeps Staggered."""
    if type(use) is not WeaponUse:
        return BrawnAttackEffect.STAGGER
    replace(use)
    if use.actor_id != actor:
        raise ValueError('Brawn alternative belongs to a different actual actor')
    if use.kind is not WeaponKind.UNARMED or use.skill is not Skill.BRAWN or use.item_ids:
        return BrawnAttackEffect.STAGGER
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_melee_models import PcMeleePolicy
        if state.source.participant(actor).policy is not PcMeleePolicy.AUTOMATIC_COMBAT:
            return BrawnAttackEffect.STAGGER
        if state.source.participant(actor).pc.brawn is None:
            return BrawnAttackEffect.STAGGER
    else:
        components = state.enemy(actor).definition.generated_components
        if components is None or components.brawn is None:
            return BrawnAttackEffect.STAGGER
    if not _alive(state, actor) or not _alive(state, target):
        return BrawnAttackEffect.STAGGER
    from towr.domain.pc_mount_models import pc_is_mounted
    if pc_is_mounted(state, target):
        return BrawnAttackEffect.DISMOUNT
    after = _shove_battlefield(state, actor, target)
    if after is not None and _ready_later_shooter(state, actor, target, after):
        return BrawnAttackEffect.SHOVE
    return BrawnAttackEffect.STAGGER


def _pending(state):
    requests = tuple(item for item in state.pending if type(item) is BrawnDisplacementRequest)
    if len(requests) > 1:
        raise ValueError('one actual Brawn Attack cannot have multiple unresolved displacement alternatives')
    return requests[0] if requests else None


def _bound_displacement(state, request):
    from towr.domain.pc_melee_result_models import PcAttackProof, validate_pc_melee_source_types
    from towr.domain.pc_demigryph_models import pc_kernel_resolution
    if type(request) is not BrawnDisplacementRequest:
        raise TypeError('Brawn consequence requires its exact successful Attack pending source')
    replace(request)
    if state.pending.count(request) != 1:
        raise ValueError('Brawn consequence lacks its one actual pending request')
    for index in range(len(state.history)-1, -1, -1):
        attack = state.history[index]
        if type(attack) is not PcAttackProof or attack.request.kernel_request.id != request.resolution_id:
            continue
        intent = attack.weapon_intent
        result = pc_kernel_resolution(attack)
        expected = BrawnDisplacementRequest(attack.request.kernel_request.id,
            attack.request.kernel_request.attack.id,
            prepare_brawn_displacement_impact(intent.attack_use, intent.brawn_effect), attack.request.target_id)
        if (request != expected or request.actor_id != attack.request.actor_id
                or result.attack.outcome is not AttackOutcome.HIT
                or type(result.replacement_impact) is not BrawnDisplacementImpactResult
                or result.replacement_impact.request != request or request not in result.follow_ups):
            raise ValueError('Brawn consequence changed its actual Attack, actor, target or frozen choice')
        validate_pc_melee_source_types(request, expected)
        return index, attack
    raise ValueError('Brawn consequence has no actual source Attack in this battle history')


def brawn_displacement_pending_actor(state):
    request = _pending(state)
    if request is None:
        return None
    _bound_displacement(state, request)
    return request.target_id


@dataclass(frozen=True, slots=True)
class PcBrawnShoveProof:
    request: BrawnDisplacementRequest
    attack_history_index: int
    attack: PcAttackProof
    previous: PcBattlefieldState
    state: PcBattlefieldState


def expected_pc_brawn_shove(state):
    request = _pending(state)
    if request is None or request.kind is not BrawnAttackEffect.SHOVE or state.pending_wound is not None:
        return None
    index, attack = _bound_displacement(state, request)
    after = _shove_battlefield(state, request.actor_id, request.target_id)
    if after is None:
        raise ValueError('the actual Brawn shove has no legal Short destination in this source scene')
    return PcBrawnShoveProof(request, index, attack, state.battlefield, after)


def project_pc_brawn_shove(state, proof):
    if type(proof) is not PcBrawnShoveProof:
        raise TypeError('Brawn shove requires its exact physical source proof')
    expected = expected_pc_brawn_shove(state)
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    if expected is None or proof != expected:
        raise ValueError('Brawn shove changed its Attack, pending request, actual placement or applied twice')
    validate_pc_melee_source_types(proof, expected)
    pending = tuple(item for item in state.pending if item != proof.request)
    updates = dict(battlefield=expected.state, pending=pending)
    if not pending and state.pending_wound is None:
        updates['pending_actor_id'] = None
    return updates
