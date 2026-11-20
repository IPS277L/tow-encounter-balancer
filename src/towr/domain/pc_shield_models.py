"""Actual one-handed shield equipment and the fixed M53 fighting policy."""
from __future__ import annotations
from towr.domain.pc_acrobatic_models import actor_acrobatic_source
from towr.domain.pc_movement_block_models import pc_enemy_path_blockers

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import TYPE_CHECKING

from towr.domain.attack_models import ResilienceProfile
from towr.domain.armour_models import BodyArmour
from towr.domain.condition_models import Condition
from towr.domain.pc_heavy_wound_models import injured_hands, usable_hands, usable_weapon_hand
from towr.domain.pc_melee_models import PcShieldLoadout, PcTwoHandedGrip, PcWeaponHand
from towr.domain.reload_models import ReloadableWeaponState
from towr.domain.test_models import Skill
from towr.domain.pc_battlefield_models import PcBattlefieldState
from towr.domain.movement_models import FreeMovementRequest, FreeMovementResult
from towr.domain.turn_models import CombatRoundState

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcMeleeParticipantState, PcMeleeState
    from towr.domain.pc_tactical_models import PcTacticalChoice


class PcShieldLocation(str, Enum):
    HELD = 'held'
    DROPPED = 'dropped'
    UNAVAILABLE = 'unavailable'


@dataclass(frozen=True, slots=True)
class PcShieldGroundPosition:
    zone_id: str
    initial_close_actor_ids: tuple[str, ...]

    def __post_init__(self):
        if type(self.zone_id) is not str or not self.zone_id.strip():
            raise TypeError('Shield ground position requires its actual Zone')
        if (type(self.initial_close_actor_ids) is not tuple
                or len(set(self.initial_close_actor_ids)) != len(self.initial_close_actor_ids)
                or any(type(actor) is not str or not actor.strip() for actor in self.initial_close_actor_ids)):
            raise TypeError('Shield ground position requires its distinct Close actors')


@dataclass(frozen=True, slots=True)
class PcShieldState:
    location: PcShieldLocation
    hand: PcWeaponHand | None
    ground: PcShieldGroundPosition | None = field(default=None, kw_only=True)

    def __post_init__(self):
        if type(self.location) is not PcShieldLocation:
            raise TypeError('shield location requires its exact typed value')
        if self.location is PcShieldLocation.DROPPED:
            if self.hand is not None:
                raise ValueError('a dropped shield has no held hand')
        elif type(self.hand) is not PcWeaponHand:
            raise TypeError('held/unavailable shield retains its actual typed hand')
        if self.ground is not None:
            if self.location is not PcShieldLocation.DROPPED or type(self.ground) is not PcShieldGroundPosition:
                raise TypeError('only a dropped Shield can retain its exact ground position')
            replace(self.ground)


@dataclass(frozen=True, slots=True)
class PcShieldReleaseProof:
    actor_id: str
    action_id: str
    hand: PcWeaponHand
    intent: PcTacticalChoice | None = field(default=None, kw_only=True)

    def __post_init__(self):
        if any(type(value) is not str or not value.strip() for value in (self.actor_id,self.action_id)):
            raise TypeError('shield release requires exact nonempty source IDs')
        if type(self.hand) is not PcWeaponHand:
            raise TypeError('shield release requires its actual typed hand')
        if self.intent is not None:
            from towr.domain.pc_tactical_models import PcTacticalChoice
            if type(self.intent) is not PcTacticalChoice or self.intent.actor_id != self.actor_id:
                raise TypeError('shield release must retain its actual actor tactical intent')


def initial_pc_shield(loadout: PcShieldLoadout | None) -> PcShieldState | None:
    if loadout is None:
        return None
    if type(loadout) is not PcShieldLoadout:
        raise TypeError('initial shield requires its exact loadout')
    replace(loadout)
    return PcShieldState(PcShieldLocation.HELD,loadout.initial_hand)


def pc_has_working_shield(member: PcMeleeParticipantState) -> bool:
    shield = member.shield
    return (shield is not None and shield.location is PcShieldLocation.HELD
        and shield.hand in usable_hands(member)
        and member.weapon_hand not in (shield.hand,PcTwoHandedGrip.BOTH))


def pc_shield_recover_hand(member: PcMeleeParticipantState, *, state=None) -> PcWeaponHand | None:
    if state is not None:
        from towr.domain.pc_medical_models import medical_effective_body
        member=medical_effective_body(state,member.actor_id)
    from towr.domain.pc_weapon_inventory import equipment_usable_hands
    if member.shield is None or member.shield.location is not PcShieldLocation.DROPPED:
        return None
    if state is not None and not pc_shield_is_close(state, member.actor_id):
        return None
    # Keep the second hand free through the whole Exacting reload cycle,
    # including an incidental object interaction in a necessary Recover.
    from towr.domain.pc_melee_models import PC_RANGED_WEAPONS
    active=member.weapon_inventory.active
    if (active is not None and active.kind in PC_RANGED_WEAPONS
            and type(member.ranged) is ReloadableWeaponState and not member.ranged.loaded):
        return None
    if member.injury.dead or member.injury.conditions.has(Condition.DEFENCELESS):
        return None
    if member.weapon_hand is PcTwoHandedGrip.BOTH:
        return None
    return next((side for side in equipment_usable_hands(member)
        if side is not member.weapon_hand and side not in injured_hands(member)),None)


def pc_shield_recover_needed(member: PcMeleeParticipantState, *, state=None) -> bool:
    if state is not None:
        from towr.domain.pc_medical_models import medical_effective_body
        member=medical_effective_body(state,member.actor_id)
    return usable_weapon_hand(member) is not None and pc_shield_recover_hand(member,state=state) is not None


def pc_shield_resilience(state: PcMeleeState, actor: str) -> ResilienceProfile:
    from towr.domain.pc_potion_models import pc_effective_definition
    pc = pc_effective_definition(state, actor)
    source = state.source.participant(actor)
    from towr.domain.pc_medical_models import medical_effective_body
    shield = pc_has_working_shield(medical_effective_body(state,actor))
    from towr.domain.pc_mount_models import mount_resilience_bonus
    bonus = pc.armour_bonus+int(shield)+mount_resilience_bonus(state,actor)
    # Positive Resilience bonuses already imply armour. Preserve a zero-bonus
    # worn item (e.g. Helmet) without adding imaginary Resilience.
    from towr.domain.armour_models import armour_is_worn
    worn=(armour_is_worn(source.armour) if source.armour is not None else source.armour_worn is True)
    base=ResilienceProfile(pc.toughness,bonus,
        armoured=True if worn and bonus == 0 else None,
        mundane_armour_ward=(source.armour is not None
            and source.armour.benefit is BodyArmour.METEORIC_IRON))
    from towr.domain.pc_armour_bane_models import armour_bane_resilience
    return armour_bane_resilience(state,actor,base)


def pc_defence_hand(member: PcMeleeParticipantState, attack_skill: Skill) -> PcWeaponHand | PcTwoHandedGrip | None:
    if attack_skill in (Skill.SHOOTING,Skill.THROWING):
        return member.shield.hand if pc_has_working_shield(member) else None
    if attack_skill is Skill.MELEE:
        return usable_weapon_hand(member) or (member.shield.hand if pc_has_working_shield(member) else None)
    return None


def pc_protection_hand(member: PcMeleeParticipantState, attack_skill: Skill,
        selected_skill: Skill) -> PcWeaponHand | PcTwoHandedGrip | None:
    from towr.domain.pc_weapon_inventory import pc_protection_weapon_use,pc_hand
    from towr.domain.weapon_inventory_models import WeaponGrip
    use=pc_protection_weapon_use(member,selected_skill,attack_skill)
    if use is None or not use.used_hands:
        return None
    return pc_hand(WeaponGrip.BOTH if len(use.used_hands)==2 else use.used_hands[0])


def expected_pc_shield_release(state: PcMeleeState) -> PcShieldReleaseProof | None:
    from towr.domain.pc_bash_attack_models import expected_bash_pc_shield_release
    bash=expected_bash_pc_shield_release(state)
    if bash is not None:return bash
    if state.pending or state.pending_wound is not None:
        return None
    turn = state.round_state.active_turn
    if turn is None or turn.actor_id not in state.source.pc_activation_order or turn.action_slots:
        return None
    actor = turn.actor_id
    from towr.domain.pc_medical_models import medical_effective_body
    member = medical_effective_body(state,actor)
    if (member.injury.dead or member.injury.conditions.has(Condition.DEFENCELESS)
            or not pc_has_working_shield(member)):
        return None
    from towr.domain.pc_potion_models import selected_pc_potion
    if member.potions and selected_pc_potion(state) is not None:
        return None
    if state.source.participant(actor).wizard is not None:
        from towr.domain.pc_melee_result_models import pc_is_casting_action
        if pc_is_casting_action(state):
            return None
    from towr.domain.pc_mount_attack_models import pc_uses_mount_attack
    if pc_uses_mount_attack(state, actor):
        return None  # The mount's Attack needs no incidental rider weapon hand.
    from towr.domain.pc_backup_weapon_models import pc_preferred_weapon_hand, pc_backup_candidate_hand,pc_active_weapon
    from towr.domain.pc_melee_result_models import pc_melee_action_id, _pc_recover_needed
    needs_weapon_hand = (pc_preferred_weapon_hand(state,actor) is member.shield.hand
        or pc_backup_candidate_hand(state,actor) is member.shield.hand)
    from towr.domain.pc_melee_models import PC_RANGED_WEAPONS
    needs_reload_hands = (pc_active_weapon(state,actor) in PC_RANGED_WEAPONS
        and type(member.ranged) is ReloadableWeaponState and not member.ranged.loaded
        and len(usable_hands(member)) == 2 and usable_weapon_hand(member) is not None
        and bool(state.live_enemies) and not _pc_recover_needed(member))
    from towr.domain.pc_melee_models import PcMeleePolicy
    source = state.source.participant(actor)
    intent = None
    if source.policy is PcMeleePolicy.AUTOMATIC_COMBAT and source.pc.ranged is not None:
        from towr.domain.pc_tactical_models import select_pc_tactic
        from towr.domain.pc_weapon_inventory import pc_weapon_swap_hand
        selected=select_pc_tactic(state,actor)
        intent=selected
        item_id=selected.pickup_item_id or selected.weapon_item_id
        needs_weapon_hand=bool(item_id is not None and member.weapon_inventory is not None
            and pc_weapon_swap_hand(state,actor,item_id) is member.shield.hand)
        needs_reload_hands=selected.ranged_reload and len(usable_hands(member))==2
    if not needs_weapon_hand and not needs_reload_hands:
        return None
    return PcShieldReleaseProof(actor,pc_melee_action_id(state,actor)+':shield:release',member.shield.hand,
        intent=intent)


@dataclass(frozen=True, slots=True)
class PcShieldDropProof:
    actor_id: str
    history_index: int
    loss_witness_history_index: int
    loss_witness: object = field(repr=False)
    previous_shield: PcShieldState
    shield: PcShieldState
    previous: PcBattlefieldState
    state: PcBattlefieldState

    def __post_init__(self):
        _validate_shield_actor(self.actor_id)
        if (type(self.history_index) is not int or type(self.loss_witness_history_index) is not int
                or not 0 <= self.loss_witness_history_index < self.history_index):
            raise ValueError('Shield drop requires its actual causal history positions')
        if (type(self.previous_shield) is not PcShieldState or type(self.shield) is not PcShieldState
                or self.previous_shield != PcShieldState(PcShieldLocation.DROPPED, None)
                or self.shield.location is not PcShieldLocation.DROPPED or self.shield.ground is None):
            raise ValueError('Shield drop must ground exactly the actually lost source item')
        for item in (self.previous, self.state):
            if type(item) is not PcBattlefieldState:
                raise TypeError('Shield drop requires its exact before/after battlefield')
            replace(item)


@dataclass(frozen=True, slots=True)
class PcShieldPickup:
    actor_id: str
    action_id: str
    previous_shield: PcShieldState
    shield: PcShieldState
    previous: PcBattlefieldState | None
    state: PcBattlefieldState | None

    def __post_init__(self):
        _validate_shield_actor(self.actor_id)
        _validate_shield_actor(self.action_id)
        if (type(self.previous_shield) is not PcShieldState or type(self.shield) is not PcShieldState
                or self.previous_shield.location is not PcShieldLocation.DROPPED
                or self.shield.location is not PcShieldLocation.HELD or self.shield.ground is not None):
            raise ValueError('Shield pickup requires one actual ground-to-held item transition')
        if self.previous is None:
            if self.state is not None or self.previous_shield.ground is not None:
                raise ValueError('stationary Shield pickup cannot invent a spatial item')
        else:
            if (type(self.previous) is not PcBattlefieldState or type(self.state) is not PcBattlefieldState
                    or self.previous_shield.ground is None):
                raise TypeError('spatial Shield pickup requires its full ground and battlefield source')
            replace(self.previous); replace(self.state)


@dataclass(frozen=True, slots=True)
class PcShieldApproachProof:
    actor_id: str
    source_round: CombatRoundState
    previous: PcBattlefieldState
    state: PcBattlefieldState
    movement_request: FreeMovementRequest | None
    movement_result: FreeMovementResult | None

    def __post_init__(self):
        _validate_shield_actor(self.actor_id)
        for item, kind in ((self.source_round, CombatRoundState),
                (self.previous, PcBattlefieldState), (self.state, PcBattlefieldState)):
            if type(item) is not kind:
                raise TypeError('Shield approach requires its exact clock and battlefield sources')
            replace(item)
        if self.movement_request is None:
            if self.movement_result is not None:
                raise ValueError('within-Zone Shield approach cannot invent a movement result')
        else:
            if type(self.movement_request) is not FreeMovementRequest or type(self.movement_result) is not FreeMovementResult:
                raise TypeError('Shield approach requires its exact K1 move request and result')
            replace(self.movement_request); replace(self.movement_result)


def _validate_shield_actor(value):
    if type(value) is not str or not value.strip():
        raise TypeError('physical Shield requires exact nonempty source identifiers')


def _shield_marker_id(actor):
    return actor+':shield:ground'


def _shield_actors(state):
    return (*state.source.pc_activation_order,
        *(actor for actor in state.source.npc_activation_order if actor not in state.exited_npc_ids))


def _shield_ground(state, actor):
    from towr.domain.pc_battlefield_models import (
        battlefield_is_midair, battlefield_ground_below, battlefield_range,
    )
    from towr.domain.ranged_weapon_profiles import RangedWeaponRange
    battlefield = state.battlefield
    zone = battlefield.spatial.placement_for(actor).zone_id
    if battlefield_is_midair(battlefield, actor):
        return PcShieldGroundPosition(battlefield_ground_below(battlefield, zone), ())
    return PcShieldGroundPosition(zone, tuple(other for other in _shield_actors(state)
        if other == actor or battlefield_range(battlefield, actor, other) is RangedWeaponRange.CLOSE))


def _add_shield_marker(battlefield, actor, shield):
    from towr.domain.spatial_models import SpatialEntityPlacement
    if battlefield is None:
        return None
    marker = _shield_marker_id(actor)
    if any(item.entity_id == marker for item in battlefield.spatial.placements):
        raise ValueError('the same physical PC Shield already has a ground marker')
    spatial = replace(battlefield.spatial, placements=(*battlefield.spatial.placements,
        SpatialEntityPlacement(marker, 'object:pc-shield', shield.ground.zone_id)))
    return replace(battlefield, spatial=spatial, close_pairs=(*battlefield.close_pairs,
        *(tuple(sorted((marker, other))) for other in shield.ground.initial_close_actor_ids)))


def _remove_shield_marker(battlefield, actor):
    if battlefield is None:
        return None
    marker = _shield_marker_id(actor)
    if not any(item.entity_id == marker for item in battlefield.spatial.placements):
        raise ValueError('PC Shield pickup lacks its actual physical marker')
    return replace(battlefield, spatial=replace(battlefield.spatial,
        placements=tuple(item for item in battlefield.spatial.placements if item.entity_id != marker)),
        close_pairs=tuple(pair for pair in battlefield.close_pairs if marker not in pair))


def _shield_loss_witness(state, actor):
    from towr.domain.pc_melee_result_models import PcHandDropProof, PcBodyConsequenceProof, PcWoundCompletionProof
    # Other mandatory equipment acknowledgements may follow the Wound's hand
    # loss. The current dropped item plus its actual causal journal receipt
    # fixes the source; movement cannot intervene before this acknowledgement.
    for index in range(len(state.history)-1, -1, -1):
        proof = state.history[index]
        if type(proof) is PcShieldDropProof and proof.actor_id == actor:
            return None
        if type(proof) is PcShieldReleaseProof and proof.actor_id == actor:
            return index, proof
        if type(proof) in (PcHandDropProof, PcBodyConsequenceProof):
            completion = next((item.completion for item in reversed(state.history[:index])
                if type(item) is PcWoundCompletionProof), None)
            if completion is not None and completion.source_request.roll.source_request.target_id == actor:
                return index, proof
    return None


def expected_pc_shield_drop(state):
    if state.battlefield is None:
        return None  # The stationary all-Close source has no distinct positions.
    for member in state.party:
        shield = member.shield
        if shield is None or shield.location is not PcShieldLocation.DROPPED or shield.ground is not None:
            continue
        if state.source.participant(member.actor_id).shield is None:
            raise ValueError('a PC cannot invent a dropped Shield outside its source loadout')
        witness = _shield_loss_witness(state, member.actor_id)
        if witness is None:
            raise ValueError('dropped PC Shield lacks its actual equipment loss receipt')
        after = replace(shield, ground=_shield_ground(state, member.actor_id))
        return PcShieldDropProof(member.actor_id, len(state.history), *witness,
            shield, after, state.battlefield, _add_shield_marker(state.battlefield, member.actor_id, after))
    return None


def pc_shield_drop_updates(state, proof):
    if type(proof) is not PcShieldDropProof or proof != expected_pc_shield_drop(state):
        raise ValueError('PC Shield drop changed its actual loss, position or source item')
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    validate_pc_melee_source_types(proof, expected_pc_shield_drop(state))
    return dict(party=tuple(replace(member, shield=proof.shield) if member.actor_id == proof.actor_id
        else member for member in state.party), battlefield=proof.state)


def pc_shield_is_close(state, actor):
    member = state.participant(actor)
    if member.shield is None or member.shield.location is not PcShieldLocation.DROPPED:
        return False
    if state.battlefield is None:
        # In the bounded legacy Short opening only NPCs approach. The PC
        # never changes position, so their own dropped Shield remains Close.
        return (state.source.facts.all_opponents_close
            or state.source.short_range_opening is not None)
    if member.shield.ground is None:
        return False
    from towr.domain.pc_battlefield_models import battlefield_range
    from towr.domain.ranged_weapon_profiles import RangedWeaponRange
    marker = _shield_marker_id(actor)
    return (any(item.entity_id == marker for item in state.battlefield.spatial.placements)
        and battlefield_range(state.battlefield, actor, marker) is RangedWeaponRange.CLOSE)


def complete_pc_shield_pickup(state, result):
    actor = result.source_request.actor_id
    if actor not in state.source.pc_activation_order:
        return None
    interaction = getattr(result.resolution, 'object_interaction_follow_up', None)
    if interaction is None or interaction.object_id != actor+':shield':
        return None
    hand = pc_shield_recover_hand(state.participant(actor), state=state)
    if hand is None:
        raise ValueError('PC Shield Recover requires its actual Close item and usable pickup hand')
    before = state.participant(actor).shield
    return PcShieldPickup(actor, result.request_id, before,
        PcShieldState(PcShieldLocation.HELD, hand), state.battlefield,
        _remove_shield_marker(state.battlefield, actor))


def pc_shield_pickup_updates(state, result, pickup):
    expected = complete_pc_shield_pickup(state, result)
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    if pickup != expected:
        raise ValueError('PC Shield Recover changed its actual physical pickup receipt')
    validate_pc_melee_source_types(pickup, expected)
    return {} if pickup is None else dict(battlefield=pickup.state)


def expected_pc_shield_approach(state):
    turn = state.round_state.active_turn
    if (state.battlefield is None or turn is None or turn.actor_id not in state.source.pc_activation_order
            or turn.action_slots or state.pending or state.pending_wound is not None or state.magic_pending is not None):
        return None
    actor = turn.actor_id
    from towr.domain.pc_medical_models import medical_effective_body
    member = medical_effective_body(state,actor)
    if not pc_shield_recover_needed(member,state=state) or pc_shield_is_close(state, actor):
        return None
    if member.shield.ground is None or any(member.injury.conditions.has(condition)
            for condition in (Condition.PRONE, Condition.DEFENCELESS, Condition.BROKEN)):
        return None
    # Recover conditions, potions and the actual weapon are handled before a
    # spare Shield approach; a reloading character keeps the second hand free.
    from towr.domain.pc_potion_models import selected_pc_potion
    if member.potions and selected_pc_potion(state) is not None:
        return None
    if any(type(proof) is PcShieldApproachProof and proof.actor_id == actor
            and proof.source_round.round_number == state.round_state.round_number for proof in state.history):
        return None
    from towr.domain.pc_battlefield_models import with_actor_placement, battlefield_range
    from towr.domain.pc_battlefield_movement_models import _zone_distance, battlefield_path_available
    from towr.domain.pc_battlefield_manoeuvre_models import pc_battlefield_actor_speed
    from towr.domain.movement_models import FreeMovementRequest
    from towr.domain.ranged_weapon_profiles import RangedWeaponRange
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    from towr.rules.free_movement_resolution import resolve_free_movement
    previous = state.battlefield
    spatial = previous.spatial
    origin = spatial.placement_for(actor).zone_id
    destination = member.shield.ground.zone_id
    marker = _shield_marker_id(actor)
    close = (marker, *(other for other in _shield_actors(state) if other != actor
        and battlefield_range(previous, marker, other) is RangedWeaponRange.CLOSE))
    request = result = None
    route = ()
    current = origin
    if origin != destination:
        if actor in spatial.free_move_used_entity_ids:
            return None
        speed = pc_battlefield_actor_speed(state, actor)
        for _ in range(speed.free_move_zone_limit):
            candidates = tuple(zone for zone in spatial.graph.adjacent_zone_ids(current)
                if battlefield_path_available(state, actor, (*route, zone),
                    close_to_ids=close if zone == destination else ()))
            if not candidates:
                break
            following = min(candidates, key=lambda zone: _zone_distance(spatial.graph, zone, destination))
            if _zone_distance(spatial.graph, following, destination) >= _zone_distance(spatial.graph, current, destination):
                break
            route = (*route, following)
            current = following
            if current == destination:
                break
        if not route:
            return None
        from towr.domain.pc_terrain_models import terrain_test_required_for_route
        terrain=terrain_test_required_for_route(state,actor,route)
        request = FreeMovementRequest(pc_melee_action_id(state, actor)+':shield:approach',
            state.round_state, spatial, actor, speed, member.injury.conditions, route,
            crosses_difficult_terrain=terrain,terrain_resolution_deferred=terrain,acrobatic=actor_acrobatic_source(state,actor),path_entity_ids=pc_enemy_path_blockers(state,actor,route))
        result = resolve_free_movement(request)
    elif not battlefield_path_available(state, actor, (), close_to_ids=close):
        return None
    after = with_actor_placement(previous, actor, current, close_to_ids=close if current == destination else ())
    if result is not None:
        after = replace(after, spatial=result.state)
    return PcShieldApproachProof(actor, state.round_state, previous, after, request, result)


def pc_shield_approach_updates(state, proof):
    if type(proof) is not PcShieldApproachProof or proof != expected_pc_shield_approach(state):
        raise ValueError('PC Shield approach changed its actual item, movement or source clock')
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    from towr.domain.pc_heavy_wound_models import critical_for_action
    from towr.domain.turn_models import CombatActionKind
    validate_pc_melee_source_types(proof, expected_pc_shield_approach(state))
    from towr.domain.pc_medical_models import medical_effective_body
    member = state.participant(proof.actor_id)
    effective=medical_effective_body(state,proof.actor_id)
    after=critical_for_action(effective, CombatActionKind.MANOEUVRE)
    added=tuple(effect for effect in after.active_wound_effects if effect not in effective.injury.active_wound_effects)
    injury=replace(member.injury,active_wound_effects=tuple(dict.fromkeys((*member.injury.active_wound_effects,*added))),
        conditions=(member.injury.conditions.with_condition(Condition.CRITICALLY_INJURED) if added else member.injury.conditions))
    return dict(battlefield=proof.state, party=tuple(replace(item, injury=injury)
        if item.actor_id == proof.actor_id else item for item in state.party))


def validate_pc_shields(state):
    """A ground Shield is the source-owned item witnessed by its journal."""
    from towr.domain.pc_melee_result_models import PcRecoverProof
    from towr.domain.pc_musician_equipment_models import PcMusicianEquipmentProof
    from towr.domain.pc_battlefield_musician_models import PcMusicianRecoverProof
    from towr.domain.pc_medical_equipment_models import PcMedicalEquipmentProof,PcMedicalToolRecoverProof
    expected = {actor: None for actor in state.source.pc_activation_order}
    for index, proof in enumerate(state.history):
        if type(proof) in (PcMusicianRecoverProof,PcMedicalEquipmentProof,PcMedicalToolRecoverProof):
            replace(proof)
            proof=proof.equipment
        if type(proof) is PcMusicianEquipmentProof and proof.actor_id in expected:
            replace(proof)
            previous,current=proof.previous.shield,proof.state.shield
            if previous!=current:
                if (proof.history_index!=index or previous is None or current is None
                        or previous.location is not PcShieldLocation.HELD
                        or previous.ground!=expected[proof.actor_id]
                        or current.location is not PcShieldLocation.DROPPED
                        or current.ground is None or expected[proof.actor_id] is not None):
                    raise ValueError('music Shield release changed its actual source or drop position')
                expected[proof.actor_id]=current.ground
        if type(proof) is PcShieldDropProof:
            if (proof.history_index != index or not 0 <= proof.loss_witness_history_index < index
                    or state.history[proof.loss_witness_history_index] != proof.loss_witness
                    or state.source.participant(proof.actor_id).shield is None
                    or proof.previous_shield != PcShieldState(PcShieldLocation.DROPPED, None)
                    or proof.shield.location is not PcShieldLocation.DROPPED
                    or proof.shield.ground is None or expected[proof.actor_id] is not None):
                raise ValueError('PC Shield ground history lost its one actual equipment source')
            expected[proof.actor_id] = proof.shield.ground
        if type(proof) is PcRecoverProof and proof.pc_shield_pickup is not None:
            pickup = proof.pc_shield_pickup
            if (type(pickup) is not PcShieldPickup or pickup.action_id != proof.result.request_id
                    or pickup.actor_id != proof.result.source_request.actor_id
                    or expected[pickup.actor_id] != pickup.previous_shield.ground
                    or pickup.shield.location is not PcShieldLocation.HELD or pickup.shield.ground is not None):
                raise ValueError('PC Shield pickup detached or repeated its physical item')
            expected[pickup.actor_id] = None
    for member in state.party:
        source = state.source.participant(member.actor_id)
        if (source.shield is None) != (member.shield is None):
            raise ValueError('PC Shield presence differs from its complete source')
        if member.shield is None:
            continue
        if member.shield.ground != expected[member.actor_id]:
            raise ValueError('PC Shield ground position differs from its actual drop/pickup history')
        if state.battlefield is not None:
            marker = _shield_marker_id(member.actor_id)
            present = any(item.entity_id == marker for item in state.battlefield.spatial.placements)
            if present != (member.shield.ground is not None):
                raise ValueError('PC Shield marker differs from its actual dropped item')
            if present and state.battlefield.spatial.placement_for(marker).zone_id != member.shield.ground.zone_id:
                raise ValueError('PC Shield marker moved away from its frozen landing position')
            if member.shield.location is PcShieldLocation.DROPPED and member.shield.ground is None:
                if _shield_loss_witness(state, member.actor_id) is None:
                    raise ValueError('ungrounded PC Shield requires its pending actual drop acknowledgement')
