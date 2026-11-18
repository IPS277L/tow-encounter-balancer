"""Finite physical Weighted Nets shared by PC, generated and canonical NPCs.

A thrown Net remains the same item. Dynamic scenes use a real object marker;
the explicitly stationary all-Close scene uses a virtual position in its one
Zone. Neither representation adds a combat actor or a free replacement item.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import TYPE_CHECKING

from towr.domain.attack_models import AttackOutcome, ConditionImpactSpec
from towr.domain.condition_models import Condition
from towr.domain.fate_models import FateGloriousSpendResult
from towr.domain.magic_models import WizardMagicState
from towr.domain.movement_models import FreeMovementRequest, FreeMovementResult
from towr.domain.pc_battlefield_models import PcBattlefieldState, battlefield_range, with_actor_placement
from towr.domain.pc_net_models import PcNetConditionSource, is_net_impact, net_condition_sources_from_attack
from towr.domain.pc_npc_net_policy_models import NET_DEFINITION_ID, NET_RULE_ID
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.recover_models import (
    RecoverActionExecutionRequest, RecoverActionExecutionResult, RecoverConditionRemovalChoice,
    RecoverConditionTarget, RecoverMode, RecoverObjectInteractionFollowUp, RecoverStandardChoice,
    _expected_recover_execution,
)
from towr.domain.spatial_models import SpatialEntityPlacement
from towr.domain.test_models import InlineProfile, Skill, TestRequest
from towr.domain.turn_models import CombatActionKind, CombatRoundState
from towr.rules.free_movement_resolution import resolve_free_movement
from towr.rules.recover_resolution import _complete_condition_removal_after_test, _resolve_standard

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcFateDecline,PcMeleeState


class PcNetLocation(str,Enum):
    HELD = 'held'
    CARRIED = 'carried'
    FREE = 'free'
    BOUND = 'bound'


def _identifier(value):
    if type(value) is not str or not value.strip():
        raise TypeError('Net identity requires an exact nonempty string')


@dataclass(frozen=True,slots=True)
class PcNetGroundPosition:
    zone_id: str
    initial_close_actor_ids: tuple[str,...]

    def __post_init__(self):
        _identifier(self.zone_id)
        if (type(self.initial_close_actor_ids) is not tuple
                or len(set(self.initial_close_actor_ids)) != len(self.initial_close_actor_ids)):
            raise TypeError('Net position requires its exact distinct Close actor tuple')
        for actor in self.initial_close_actor_ids:
            _identifier(actor)


@dataclass(frozen=True,slots=True)
class PcWeightedNetState:
    item_id: str
    owner_id: str
    location: PcNetLocation
    bound_target_id: str | None = field(default=None,kw_only=True)
    binding: PcNetConditionSource | None = field(default=None,kw_only=True)
    ground: PcNetGroundPosition | None = field(default=None,kw_only=True)

    def __post_init__(self):
        _identifier(self.item_id); _identifier(self.owner_id)
        if type(self.location) is not PcNetLocation:
            raise TypeError('Net item requires its exact physical location enum')
        if self.location is PcNetLocation.BOUND:
            _identifier(self.bound_target_id)
            if type(self.binding) is not PcNetConditionSource or self.ground is not None:
                raise TypeError('a bound Net requires its exact Condition cause and no ground marker')
            replace(self.binding)
            if self.binding.target_id != self.bound_target_id or self.binding.attacker_id != self.owner_id:
                raise ValueError('Net binding is detached from its actual owner or target')
        elif self.bound_target_id is not None or self.binding is not None:
            raise ValueError('only a bound physical Net retains a target Condition cause')
        if self.location is PcNetLocation.FREE:
            if type(self.ground) is not PcNetGroundPosition:
                raise TypeError('a free Net requires its exact static ground position')
            replace(self.ground)
        elif self.ground is not None:
            raise ValueError('a held, carried or bound Net has no ground position')

    @property
    def marker_id(self):
        return self.item_id+':ground'


def weighted_net_profile(ballistic_skill: int,throwing: int,strength: int):
    """PG68 uses BS/Throwing; PG96 uses Strength only to extend Optimum."""
    from towr.domain.npc_attack_preparation_models import NpcAttackProfile
    for value,name in ((ballistic_skill,'Ballistic Skill'),(strength,'Strength')):
        if type(value) is not int or value < 1:
            raise ValueError(f'Net {name} must be a positive exact integer')
    if type(throwing) is not int or not 1 <= throwing <= 10:
        raise ValueError('Net Throwing must be an explicit Skill rating')
    return NpcAttackProfile('primary','RULE-EQUIPMENT-005:weighted-net',Skill.THROWING,
        InlineProfile(ballistic_skill,throwing),None,RangedWeaponRange.CLOSE,
        RangedWeaponRange.MEDIUM if strength >= 4 else RangedWeaponRange.SHORT,
        RangedWeaponHands.TWO_HANDED,condition_impact=ConditionImpactSpec(Condition.BURDENED,NET_RULE_ID))


def initial_weighted_nets(source):
    from towr.domain.pc_melee_models import PcMeleeWeapon
    from towr.domain.pc_combat_equipment_models import PcItemLocation
    result = []
    for member in source.party:
        if member.pc.weapon is not PcMeleeWeapon.WEIGHTED_NET:
            continue
        if member.combat_equipment is None:
            raise ValueError('PC Net requires its actual concrete equipment item')
        for item in member.combat_equipment:
            if item.weapon is PcMeleeWeapon.WEIGHTED_NET:
                location = PcNetLocation.HELD if item.location is PcItemLocation.HELD else PcNetLocation.CARRIED
                result.append(PcWeightedNetState(member.actor_id+':weapon:'+item.id,member.actor_id,location))
    for enemy in source.enemies:
        components = enemy.definition.generated_components
        if enemy.definition.id == NET_DEFINITION_ID or components is not None and components.weapon.value == 'weighted_net':
            result.append(PcWeightedNetState(enemy.state.actor_id+':weapon',enemy.state.actor_id,PcNetLocation.HELD))
    if len({item.item_id for item in result}) != len(result):
        raise ValueError('physical Net instances must have distinct source-bound identities')
    if {item.marker_id for item in result} & {*source.pc_activation_order,*source.enemy_activation_order}:
        raise ValueError('Net marker identities must not collide with combat participants')
    return tuple(result)


def weighted_net_item(state,item_id):
    return next((item for item in state.weighted_nets if item.item_id == item_id),None)


def weighted_net_for_actor(state,actor):
    if actor in state.source.pc_activation_order:
        member = state.participant(actor)
        if member.weapon_inventory is not None:
            active = member.weapon_inventory.active_item_id
            found = weighted_net_item(state,actor+':weapon:'+active)
            if found is not None:
                return found
    return next((item for item in state.weighted_nets if item.owner_id == actor),None)


def weighted_net_condition_sources(state,target_id,*,bank=None):
    return tuple(item.binding for item in (state.weighted_nets if bank is None else bank)
        if item.location is PcNetLocation.BOUND and item.bound_target_id == target_id)


def _actors(state):
    return (*state.source.pc_activation_order,
        *(actor for actor in state.source.enemy_activation_order if actor not in state.exited_npc_ids))


def _ground_position(state,anchor):
    actors = _actors(state)
    if state.battlefield is None:
        if not state.source.facts.all_opponents_close:
            raise ValueError('stationary Net geometry requires the explicit all-Close scene')
        return PcNetGroundPosition(state.source.facts.zone_id,actors)
    zone = state.battlefield.spatial.placement_for(anchor).zone_id
    close = tuple(actor for actor in actors if actor == anchor or
        battlefield_range(state.battlefield,anchor,actor) is RangedWeaponRange.CLOSE)
    return PcNetGroundPosition(zone,close)


def _add_marker(battlefield,item):
    if battlefield is None:
        return None
    if any(placement.entity_id == item.marker_id for placement in battlefield.spatial.placements):
        raise ValueError('the same physical Net already has a ground marker')
    placement = SpatialEntityPlacement(item.marker_id,'objects',item.ground.zone_id)
    spatial = replace(battlefield.spatial,placements=(*battlefield.spatial.placements,placement))
    pairs = (*battlefield.close_pairs,*(tuple(sorted((item.marker_id,actor)))
        for actor in item.ground.initial_close_actor_ids))
    return PcBattlefieldState(spatial,pairs)


def _remove_marker(battlefield,item):
    if battlefield is None:
        return None
    marker = battlefield.spatial.placement_for(item.marker_id)
    if marker.side_id != 'objects' or marker.zone_id != item.ground.zone_id:
        raise ValueError('Net ground marker changed its static item identity or location')
    return PcBattlefieldState(replace(battlefield.spatial,placements=tuple(
        placement for placement in battlefield.spatial.placements if placement.entity_id != item.marker_id)),
        tuple(pair for pair in battlefield.close_pairs if item.marker_id not in pair))


def weighted_net_item_close(state,actor,item_id):
    item = weighted_net_item(state,item_id)
    if item is None or item.location is not PcNetLocation.FREE or actor not in _actors(state):
        return False
    return (actor in item.ground.initial_close_actor_ids if state.battlefield is None else
        battlefield_range(state.battlefield,actor,item.marker_id) is RangedWeaponRange.CLOSE)


def _replace_item(bank,item):
    if not any(current.item_id == item.item_id for current in bank):
        raise ValueError('Net transition cannot create a source-less physical item')
    return tuple(item if current.item_id == item.item_id else current for current in bank)


def _same(actual,expected):
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    if actual != expected:
        raise ValueError('Net proof changed its complete physical item, action or spatial source')
    validate_pc_melee_source_types(actual,expected)


@dataclass(frozen=True,slots=True)
class PcNetThrowLanding:
    attack_id: str
    item_id: str
    actor_id: str
    target_id: str
    previous_item: PcWeightedNetState
    item: PcWeightedNetState
    previous: PcBattlefieldState | None
    state: PcBattlefieldState | None


def complete_weighted_net_throw(state,request,execution):
    if not is_net_impact(request.kernel_request.attack.impact_spec):
        return None
    item = weighted_net_for_actor(state,request.actor_id)
    if item is None or item.location is not PcNetLocation.HELD:
        raise ValueError('Net throw requires its same actual held physical item')
    if request.target_id not in _actors(state) or request.actor_id not in _actors(state):
        raise ValueError('Net throw must retain actual encounter participants')
    if execution.request_id != request.id or execution.target_id != request.target_id:
        raise ValueError('Net landing belongs to another actual Attack execution')
    causes = net_condition_sources_from_attack(request,execution.resolution)
    if execution.resolution.attack.outcome is AttackOutcome.HIT:
        if len(causes) != 1:
            raise ValueError('successful Net must retain its one actual Burdened application')
        after = replace(item,location=PcNetLocation.BOUND,bound_target_id=request.target_id,binding=causes[0])
        battlefield = state.battlefield
    else:
        after = replace(item,location=PcNetLocation.FREE,ground=_ground_position(state,request.target_id))
        battlefield = _add_marker(state.battlefield,after)
    return PcNetThrowLanding(request.id,item.item_id,request.actor_id,request.target_id,
        item,after,state.battlefield,battlefield)


def weighted_net_updates_from_attack(state,request,execution,landing):
    expected = complete_weighted_net_throw(state,request,execution)
    _same(landing,expected)
    return {} if expected is None else dict(weighted_nets=_replace_item(state.weighted_nets,expected.item),
        battlefield=expected.state)


def _injury(state,actor):
    return state.participant(actor).injury if actor in state.source.pc_activation_order else state.enemy(actor).state.injury


def _conditions(state,actor):
    return _injury(state,actor).conditions


def _allied(state,first,second):
    return (first in state.source.pc_activation_order) == (second in state.source.pc_activation_order)


def _close_actors(state,first,second):
    return (first in _actors(state) and second in _actors(state) and
        (state.source.facts.all_opponents_close if state.battlefield is None else
            battlefield_range(state.battlefield,first,second) is RangedWeaponRange.CLOSE))


def _recover_actor(state):
    turn = state.round_state.active_turn
    if (turn is None or not turn.action_slots or turn.action_slots[-1].executed
            or turn.action_slots[-1].declaration.kind is not CombatActionKind.RECOVER
            or state.pending or state.pending_wound is not None or state.magic_pending is not None):
        raise ValueError('Net recovery requires the actual unused Recover action after mandatory work')
    if _conditions(state,turn.actor_id).has(Condition.DEFENCELESS):
        raise ValueError('Defenceless actors cannot perform a Net Recover')
    return turn.actor_id,len(turn.action_slots)


def _has_close_enemy(state,actor):
    other = state.live_enemies if actor in state.source.pc_activation_order else state.live_party
    return any(_close_actors(state,actor,
        member.state.actor_id if actor in state.source.pc_activation_order else member.actor_id) for member in other)


def _brawn_test(state,actor,test_id):
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_melee_result_models import _pc_test
        if state.source.participant(actor).pc.brawn is None:
            raise ValueError('Net release requires the actor\'s actual Brawn source')
        return _pc_test(state,actor,test_id,Skill.BRAWN)
    enemy = state.enemy(actor)
    components = enemy.definition.generated_components
    if components is None or components.brawn is None:
        raise ValueError('NPC Net release requires its explicit Brawn source')
    from towr.domain.pc_magic_models import magic_test_modifiers
    from towr.domain.pc_npc_distraction_models import pc_npc_distraction_test_modifiers
    modifiers = pc_npc_distraction_test_modifiers(state,actor,None)
    if enemy.state.injury.conditions.has(Condition.DRAINED):
        modifiers = tuple(modifier for modifier in modifiers if modifier.amount <= 0)
    magic,quality = magic_test_modifiers(state,actor,Skill.BRAWN)
    return TestRequest(test_id,InlineProfile(components.strength,components.brawn),(*modifiers,*magic),quality)


def build_weighted_net_release(state,target_id,item_id):
    actor,slot = _recover_actor(state)
    item = weighted_net_item(state,item_id)
    if (item is None or item.location is not PcNetLocation.BOUND or item.bound_target_id != target_id
            or not _allied(state,actor,target_id) or actor != target_id and not _close_actors(state,actor,target_id)):
        raise ValueError('Net release requires one actual bound self/Close ally item')
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    action = pc_melee_action_id(state,actor)+':net:release:'+item_id
    target = RecoverConditionTarget(target_id,_conditions(state,target_id),None if actor == target_id else True)
    choice = RecoverConditionRemovalChoice(target,Condition.BURDENED,
        _brawn_test(state,actor,action+':brawn'),Skill.BRAWN,True)
    return RecoverActionExecutionRequest(action,state.round_state,actor,_conditions(state,actor),
        _has_close_enemy(state,actor),slot,RecoverMode.REMOVE_CONDITION,choice)


def _pickup_hands(state,actor):
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_heavy_wound_models import usable_hands
        return len(usable_hands(state.participant(actor))) == 2
    return not _conditions(state,actor).has(Condition.DEFENCELESS)


def build_weighted_net_pickup(state,item_id):
    actor,slot = _recover_actor(state)
    item = weighted_net_item(state,item_id)
    if (item is None or item.owner_id != actor or not weighted_net_item_close(state,actor,item_id)
            or not _pickup_hands(state,actor)):
        raise ValueError('Net pickup requires its actual Close free item and available two-handed grip')
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    from towr.domain.pc_heavy_wound_models import has_ongoing_condition
    action = pc_melee_action_id(state,actor)+':net:pickup:'+item_id
    conditions = _conditions(state,actor)
    def self_target(condition):
        return RecoverConditionTarget(actor,conditions,None) if conditions.has(condition) and not (
            actor in state.source.pc_activation_order and has_ongoing_condition(_injury(state,actor),condition)) else None
    magic = state.participant(actor).magic if actor in state.source.pc_activation_order else None
    choice = RecoverStandardChoice(magic if magic is not None else WizardMagicState(),
        staggered_target=self_target(Condition.STAGGERED),prone_target=self_target(Condition.PRONE),
        object_interaction=RecoverObjectInteractionFollowUp(action+':object',actor,item_id,True))
    return RecoverActionExecutionRequest(action,state.round_state,actor,conditions,
        _has_close_enemy(state,actor),slot,RecoverMode.STANDARD,choice)


@dataclass(frozen=True,slots=True)
class PcNetReleaseProof:
    request: RecoverActionExecutionRequest
    result: RecoverActionExecutionResult
    item_id: str
    previous_item: PcWeightedNetState
    item: PcWeightedNetState
    previous: PcBattlefieldState | None
    state: PcBattlefieldState | None
    fate_decline: PcFateDecline | None = None
    glorious: FateGloriousSpendResult | None = None


@dataclass(frozen=True,slots=True)
class PcNetPickupProof:
    request: RecoverActionExecutionRequest
    result: RecoverActionExecutionResult
    item_id: str
    previous_item: PcWeightedNetState
    item: PcWeightedNetState
    previous: PcBattlefieldState | None
    state: PcBattlefieldState | None


@dataclass(frozen=True,slots=True)
class PcNetIncidentalPickupProof:
    actor_id: str
    item_id: str
    action_id: str
    previous_item: PcWeightedNetState
    item: PcWeightedNetState
    previous: PcBattlefieldState | None
    state: PcBattlefieldState | None


@dataclass(frozen=True,slots=True)
class PcNetApproachProof:
    actor_id: str
    item_id: str
    source_round: CombatRoundState
    previous: PcBattlefieldState | None
    state: PcBattlefieldState | None
    movement_request: FreeMovementRequest | None
    movement_result: FreeMovementResult | None


@dataclass(frozen=True,slots=True)
class PcNetDrop:
    item_id: str
    actor_id: str
    source_id: str
    previous_item: PcWeightedNetState
    item: PcWeightedNetState
    previous: PcBattlefieldState | None
    state: PcBattlefieldState | None


NET_PROOFS = (PcNetReleaseProof,PcNetPickupProof,PcNetApproachProof,PcNetIncidentalPickupProof)


class PcNetRecoverKind(str,Enum):
    RELEASE = 'release'
    PICKUP = 'pickup'


@dataclass(frozen=True,slots=True)
class PcNetRecoveryIntent:
    actor_id: str
    item_id: str
    target_id: str | None
    kind: PcNetRecoverKind
    requires_approach: bool = False


def weighted_net_recovery_options(state,actor):
    """Pure legal alternatives; the owner binds the final automatic intent."""
    turn = state.round_state.active_turn
    if (turn is None or turn.actor_id != actor or state.pending or state.pending_wound is not None
            or state.magic_pending is not None or _conditions(state,actor).has(Condition.DEFENCELESS)):
        return ()
    if actor in state.source.pc_activation_order:
        brawn = state.source.participant(actor).pc.brawn
    else:
        components = state.enemy(actor).definition.generated_components
        brawn = None if components is None else components.brawn
    options = []
    if brawn is not None:
        for item in state.weighted_nets:
            target = item.bound_target_id
            if item.location is PcNetLocation.BOUND and _allied(state,actor,target) and (
                    target == actor or _close_actors(state,actor,target)):
                options.append(PcNetRecoveryIntent(actor,item.item_id,target,PcNetRecoverKind.RELEASE))
    if _pickup_hands(state,actor):
        for item in state.weighted_nets:
            if item.owner_id == actor and item.location is PcNetLocation.FREE:
                options.append(PcNetRecoveryIntent(actor,item.item_id,None,PcNetRecoverKind.PICKUP,
                    not weighted_net_item_close(state,actor,item.item_id)))
    return tuple(options)


def selected_weighted_net_recovery(state,actor):
    """Release a movement-blocking restraint, otherwise recover one's free Net."""
    from towr.domain.pc_battlefield_movement_models import pc_battlefield_attack_available
    options = weighted_net_recovery_options(state,actor)
    for option in options:
        if option.kind is not PcNetRecoverKind.RELEASE or state.battlefield is None:
            continue
        target = option.target_id
        enemies = (tuple(enemy.state.actor_id for enemy in state.live_enemies)
            if target in state.source.pc_activation_order else tuple(member.actor_id for member in state.live_party))
        if not any(pc_battlefield_attack_available(state,target,enemy) for enemy in enemies):
            return option
    if actor in state.source.enemy_activation_order and state.enemy(actor).definition.id == NET_DEFINITION_ID:
        return None  # Keep the explicit printed Throw-once-then-Spear tactic.
    return next((option for option in options if option.kind is PcNetRecoverKind.PICKUP),None)


def weighted_net_has_usable_attack(state,actor):
    """Only Net availability is answered; other weapon/actor rules stay owned."""
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_backup_weapon_models import pc_active_weapon
        from towr.domain.pc_melee_models import PcMeleeWeapon,PcTwoHandedGrip
        from towr.domain.pc_heavy_wound_models import usable_weapon_hand
        if pc_active_weapon(state,actor) is not PcMeleeWeapon.WEIGHTED_NET:
            return True
        held = usable_weapon_hand(state.participant(actor)) is PcTwoHandedGrip.BOTH
    elif actor in state.source.enemy_activation_order:
        from towr.domain.pc_melee_result_models import pc_selected_npc_attack_profile
        profile = pc_selected_npc_attack_profile(state,actor)
        if not is_net_impact(profile.condition_impact):
            return True
        held = state.enemy(actor).state.wields_weapon and bool(state.enemy(actor).state.available_attack_ids)
    else:
        raise ValueError('Net availability requires an actual encounter actor')
    item = weighted_net_for_actor(state,actor)
    if (actor in state.source.enemy_activation_order and item is not None
            and item.location is PcNetLocation.CARRIED
            and state.enemy(actor).definition.id == NET_DEFINITION_ID
            and 'weighted_net' in state.enemy(actor).state.available_attack_ids):
        # The printed policy owns an explicit free draw after reserving Attack.
        # A retained carried item may reach that draw; FREE/BOUND items cannot.
        return True
    return bool(held and item is not None and item.location is PcNetLocation.HELD)


def weighted_net_actor_waits(state,actor):
    if weighted_net_has_usable_attack(state,actor):
        return False
    selected = selected_weighted_net_recovery(state,actor)
    return selected is None or selected.requires_approach


def weighted_net_release_item(state,item_id,result):
    """Only an actually successful Brawn Recover releases this one physical Net."""
    item = weighted_net_item(state,item_id)
    if item is None or item.location is not PcNetLocation.BOUND:
        raise ValueError('Net release requires an actual binding')
    if not result.resolution.removed:
        return item,state.battlefield
    after = replace(item,location=PcNetLocation.FREE,bound_target_id=None,binding=None,
        ground=_ground_position(state,item.bound_target_id))
    return after,_add_marker(state.battlefield,after)


def weighted_net_pickup_item(state,item_id):
    item = weighted_net_item(state,item_id)
    if item is None or item.location is not PcNetLocation.FREE:
        raise ValueError('Net pickup cannot remove a bound or unavailable item')
    return replace(item,location=PcNetLocation.HELD,ground=None),_remove_marker(state.battlefield,item)


def expected_weighted_net_incidental_pickup(state):
    turn = state.round_state.active_turn
    if (turn is None or turn.action_slots or state.pending or state.pending_wound is not None
            or state.magic_pending is not None):
        return None
    actor = turn.actor_id
    if (any(_conditions(state,actor).has(condition) for condition in (Condition.DEFENCELESS,Condition.BROKEN))
            or _has_close_enemy(state,actor) or not _pickup_hands(state,actor)
            or actor in state.source.enemy_activation_order and state.enemy(actor).definition.id == NET_DEFINITION_ID):
        return None
    item = next((item for item in state.weighted_nets if item.owner_id == actor
        and weighted_net_item_close(state,actor,item.item_id)),None)
    if item is None:
        return None
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    after,battlefield = weighted_net_pickup_item(state,item.item_id)
    return PcNetIncidentalPickupProof(actor,item.item_id,
        pc_melee_action_id(state,actor)+':net:incidental-pickup:'+item.item_id,
        item,after,state.battlefield,battlefield)


def expected_weighted_net_approach(state,actor,item_id):
    item = weighted_net_item(state,item_id)
    turn = state.round_state.active_turn
    if (item is None or item.owner_id != actor or item.location is not PcNetLocation.FREE
            or state.battlefield is None or turn is None or turn.actor_id != actor or turn.action_slots
            or weighted_net_item_close(state,actor,item_id) or state.pending
            or state.pending_wound is not None or state.magic_pending is not None
            or any(_conditions(state,actor).has(condition) for condition in (
                Condition.PRONE,Condition.DEFENCELESS,Condition.BROKEN))):
        return None
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    from towr.domain.pc_battlefield_manoeuvre_models import pc_battlefield_actor_speed
    from towr.domain.pc_battlefield_movement_models import _zone_distance
    previous = state.battlefield
    spatial = previous.spatial
    origin = spatial.placement_for(actor).zone_id
    destination = item.ground.zone_id
    # This is an explicit approach to the item's local position. It does not
    # make Close globally transitive or reconnect a creature that moved away.
    close = (item.marker_id,*(other for other in _actors(state) if other != actor
        and battlefield_range(previous,item.marker_id,other) is RangedWeaponRange.CLOSE))
    if origin == destination:
        after = with_actor_placement(previous,actor,destination,close_to_ids=close)
        return PcNetApproachProof(actor,item_id,state.round_state,previous,after,None,None)
    if actor in spatial.free_move_used_entity_ids:
        return None
    speed = pc_battlefield_actor_speed(state,actor)
    route = []
    current = origin
    for _ in range(speed.free_move_zone_limit):
        following = min(spatial.graph.adjacent_zone_ids(current),
            key=lambda zone:_zone_distance(spatial.graph,zone,destination))
        if _zone_distance(spatial.graph,following,destination) >= _zone_distance(spatial.graph,current,destination):
            break
        route.append(following); current = following
        if current == destination:
            break
    if not route:
        return None
    request = FreeMovementRequest(pc_melee_action_id(state,actor)+':net:approach:'+item_id,
        state.round_state,spatial,actor,speed,_conditions(state,actor),tuple(route))
    result = resolve_free_movement(request)
    after = with_actor_placement(replace(previous,spatial=result.state),actor,current,
        close_to_ids=close if current == destination else ())
    return PcNetApproachProof(actor,item_id,state.round_state,previous,after,request,result)


def _independent_burden(state,target):
    from towr.domain.injury_models import WoundConditionEffect
    injury = _injury(state,target)
    if target in state.source.pc_activation_order:
        return any(type(effect) is WoundConditionEffect and effect.condition is Condition.BURDENED
            for effect in injury.active_wound_effects)
    return state.source.enemy(target).state.injury.conditions.has(Condition.BURDENED)


def _release_target_injury(state,target,bank):
    injury = _injury(state,target)
    conditions = injury.conditions
    if weighted_net_condition_sources(state,target,bank=bank) or _independent_burden(state,target):
        conditions = conditions.with_condition(Condition.BURDENED)
    else:
        conditions = conditions.without_condition(Condition.BURDENED)
    return replace(injury,conditions=conditions)


def _pc_pickup_member(state,member,item_id,injury,*,incidental=False):
    """The one paid object interaction also stows the actual held backup."""
    from towr.domain.pc_melee_models import PcTwoHandedGrip
    from towr.domain.pc_combat_equipment_models import PcItemLocation,PcWeaponInventoryState
    from towr.domain.pc_heavy_wound_models import critical_for_incidental_hand_use,critical_for_hand
    source = state.source.participant(member.actor_id)
    actual_id = next(item.id for item in source.combat_equipment
        if member.actor_id+':weapon:'+item.id == item_id)
    inventory = member.weapon_inventory
    if any(item.location is PcItemLocation.HELD and item.id != actual_id for item in inventory.items):
        injury = critical_for_incidental_hand_use(replace(member,injury=injury),member.weapon_hand)
    injury = (critical_for_incidental_hand_use(replace(member,injury=injury),PcTwoHandedGrip.BOTH)
        if incidental else critical_for_hand(replace(member,injury=injury),PcTwoHandedGrip.BOTH))
    items = tuple(replace(item,location=PcItemLocation.HELD,hand=PcTwoHandedGrip.BOTH)
        if item.id == actual_id else replace(item,location=PcItemLocation.CARRIED,hand=None)
        if item.location is PcItemLocation.HELD else item for item in inventory.items)
    return replace(member,injury=injury,weapon_hand=PcTwoHandedGrip.BOTH,
        using_backup_weapon=actual_id != source.combat_equipment[0].id,
        weapon_inventory=PcWeaponInventoryState(items,actual_id))


def project_weighted_net_step(state,proof):
    from towr.domain.pc_melee_result_models import _party_update,_enemy_update,pc_after_test,_test_result
    from towr.domain.pc_heavy_wound_models import critical_for_action
    from towr.domain.pc_fate_test_models import validate_pc_test_fate
    if type(proof) not in NET_PROOFS:
        raise TypeError('Net step requires its exact typed supported proof')
    if type(proof) is PcNetIncidentalPickupProof:
        expected = expected_weighted_net_incidental_pickup(state)
        if expected is None:
            raise ValueError('no legal incidental Net pickup is available in this actual turn')
        _same(proof,expected)
        updates = dict(weighted_nets=_replace_item(state.weighted_nets,proof.item),battlefield=proof.state)
        if proof.actor_id in state.source.pc_activation_order:
            member = state.participant(proof.actor_id)
            picked = _pc_pickup_member(state,member,proof.item_id,member.injury,incidental=True)
            updates['party'] = tuple(picked if current.actor_id == proof.actor_id else current for current in state.party)
        else:
            enemy = state.enemy(proof.actor_id)
            picked = replace(enemy,state=replace(enemy.state,wields_weapon=True,
                available_attack_ids=tuple(profile.id for profile in enemy.definition.attacks)))
            updates['enemies'] = tuple(picked if current.state.actor_id == proof.actor_id else current for current in state.enemies)
        return updates
    if type(proof) is PcNetApproachProof:
        expected = expected_weighted_net_approach(state,proof.actor_id,proof.item_id)
        if expected is None:
            raise ValueError('no actual Net item approach is due')
        _same(proof,expected)
        updates = dict(battlefield=proof.state)
        if proof.actor_id in state.source.pc_activation_order:
            member = state.participant(proof.actor_id)
            updates['party'] = _party_update(state,proof.actor_id,injury=critical_for_action(member,None))
        return updates
    item = weighted_net_item(state,proof.item_id)
    _same(proof.previous_item,item); _same(proof.previous,state.battlefield)
    actor,_ = _recover_actor(state)
    if type(proof) is PcNetReleaseProof:
        target = item.bound_target_id
        request = build_weighted_net_release(state,target,proof.item_id)
        _same(proof.request,request)
        actual_test = proof.result.resolution.test_result
        fate = None
        if actor in state.source.pc_activation_order:
            effective,fate = validate_pc_test_fate(state,actor,Skill.BRAWN,request.choice.test,
                actual_test,proof.fate_decline,proof.glorious)
        else:
            if proof.fate_decline is not None or proof.glorious is not None:
                raise ValueError('NPC Net release cannot invent a PC Fate resource')
            _test_result(request.choice.test,actual_test)
            effective = request.choice.test
        choice = replace(request.choice,test=effective)
        result = _expected_recover_execution(replace(request,choice=choice),
            _complete_condition_removal_after_test(choice,actual_test))
        _same(proof.result,result)
        after,battlefield = weighted_net_release_item(state,item.item_id,result)
        _same((proof.item,proof.state),(after,battlefield))
        bank = _replace_item(state.weighted_nets,after)
        injury = _release_target_injury(state,target,bank)
        updates = dict(weighted_nets=bank,battlefield=battlefield,round_state=result.round_state)
        if target in state.source.pc_activation_order:
            updates['party'] = _party_update(state,target,injury=injury,
                net_condition_sources=weighted_net_condition_sources(state,target,bank=bank))
        else:
            updates['enemies'] = _enemy_update(state,target,injury)
        if actor in state.source.pc_activation_order:
            member = next(member for member in updates.get('party',state.party) if member.actor_id == actor)
            actor_injury = pc_after_test(state,actor,critical_for_action(member,CombatActionKind.RECOVER))
            party = tuple(replace(member,injury=actor_injury,fate=fate) if member.actor_id == actor else member
                for member in updates.get('party',state.party))
            updates['party'] = party
        return updates
    request = build_weighted_net_pickup(state,item.item_id)
    _same(proof.request,request)
    result = _expected_recover_execution(request,_resolve_standard(request.choice))
    _same(proof.result,result)
    after,battlefield = weighted_net_pickup_item(state,item.item_id)
    _same((proof.item,proof.state),(after,battlefield))
    conditions = _conditions(state,actor)
    for change in result.resolution.condition_changes:
        if change.entity_id != actor:
            raise ValueError('Net pickup changed an unselected Recover target')
        conditions = change.conditions
    updates = dict(weighted_nets=_replace_item(state.weighted_nets,after),
        battlefield=battlefield,round_state=result.round_state)
    if actor in state.source.pc_activation_order:
        member = state.participant(actor)
        critical = critical_for_action(member,CombatActionKind.RECOVER,
            removes_prone=member.injury.conditions.has(Condition.PRONE) and not conditions.has(Condition.PRONE))
        if critical.conditions.has(Condition.CRITICALLY_INJURED):
            conditions = conditions.with_condition(Condition.CRITICALLY_INJURED)
        picked = _pc_pickup_member(state,member,item.item_id,replace(critical,conditions=conditions))
        picked = replace(picked,magic=result.resolution.magic_state if member.magic is not None else None)
        updates['party'] = tuple(picked if current.actor_id == actor else current for current in state.party)
    else:
        enemy = state.enemy(actor)
        picked = replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,conditions=conditions),
            wields_weapon=True,available_attack_ids=tuple(profile.id for profile in enemy.definition.attacks)))
        updates['enemies'] = tuple(picked if current.state.actor_id == actor else current for current in state.enemies)
    return updates


def _expected_net_drops(state,proof):
    from towr.domain.pc_melee_result_models import PcHandDropProof,PcBodyConsequenceProof,PcMinionStaggerDefeatProof
    from towr.domain._pc_heavy_wound_projection import body_consequence
    from towr.domain.pc_warped_form_models import PcWarpedFormMinionDefeatProof
    actor = None
    if type(proof) is PcMinionStaggerDefeatProof:
        actor = proof.source.target_id
    elif type(proof) is PcWarpedFormMinionDefeatProof:
        actor = proof.target_id
    elif type(proof) in (PcHandDropProof,PcBodyConsequenceProof):
        actor = state.pending_actor_id
        if actor not in state.source.pc_activation_order:
            return ()
        member = state.participant(actor)
        argument = (PcBodyConsequenceProof(proof.source,proof.die,proof.hand)
            if type(proof) is PcHandDropProof else proof)
        changed = body_consequence(member,argument)
        if member.weapon_hand is None or changed.weapon_hand is not None:
            return ()
    if actor is None:
        return ()
    item = weighted_net_for_actor(state,actor)
    if item is None or item.location is not PcNetLocation.HELD:
        return ()
    after = replace(item,location=PcNetLocation.FREE,ground=_ground_position(state,actor))
    source_id = (proof.source.source_id if type(proof) is PcMinionStaggerDefeatProof else
        proof.activation_id if type(proof) is PcWarpedFormMinionDefeatProof else
        'wound:'+str(proof.source.wound_sequence)+':'+proof.source.consequence.value)
    return (PcNetDrop(item.item_id,actor,source_id,item,after,state.battlefield,_add_marker(state.battlefield,after)),)


def complete_weighted_net_equipment_proof(state,proof):
    if not hasattr(proof,'weighted_net_drops'):
        return proof
    expected = _expected_net_drops(state,proof)
    if proof.weighted_net_drops:
        _same(proof.weighted_net_drops,expected)
    return replace(proof,weighted_net_drops=expected)


def weighted_nets_after_equipment(state,proof,updates):
    """Atomic final inventory/bank synchronisation after a validated owner step."""
    from towr.domain.pc_net_models import PcNpcNetDrawProof
    from towr.domain.pc_combat_equipment_models import PcItemLocation
    from towr.domain.pc_melee_models import PcMeleeWeapon
    values = dict(updates)
    bank = values.get('weighted_nets',state.weighted_nets)
    if hasattr(proof,'weighted_net_drops'):
        expected = _expected_net_drops(state,proof)
        _same(proof.weighted_net_drops,expected)
        for drop in expected:
            bank = _replace_item(bank,drop.item)
            values['battlefield'] = drop.state
    if type(proof) is PcNpcNetDrawProof:
        item = next((item for item in bank if item.owner_id == proof.actor_id),None)
        if item is not None:
            if proof.attack_id == 'weighted_net':
                if item.location not in (PcNetLocation.CARRIED,PcNetLocation.HELD):
                    raise ValueError('free draw cannot recover a thrown or bound Net')
                item = replace(item,location=PcNetLocation.HELD)
            elif item.location is PcNetLocation.HELD:
                item = replace(item,location=PcNetLocation.CARRIED)
            bank = _replace_item(bank,item)
    party = list(values.get('party',state.party))
    for index,member in enumerate(party):
        inventory = member.weapon_inventory
        if inventory is None:
            party[index] = replace(member,net_condition_sources=weighted_net_condition_sources(state,
                member.actor_id,bank=bank))
            continue
        items = list(inventory.items)
        for item_index,weapon_item in enumerate(items):
            if weapon_item.weapon is not PcMeleeWeapon.WEIGHTED_NET:
                continue
            physical = next(item for item in bank if item.item_id == member.actor_id+':weapon:'+weapon_item.id)
            if physical.location in (PcNetLocation.FREE,PcNetLocation.BOUND):
                if weapon_item.location is PcItemLocation.HELD:
                    original = weighted_net_item(state,physical.item_id)
                    if original.location in (PcNetLocation.FREE,PcNetLocation.BOUND):
                        raise ValueError('generic equipment changes cannot silently retrieve a deployed Net')
                    member = replace(member,weapon_hand=None)
                items[item_index] = replace(weapon_item,location=PcItemLocation.DEPLOYED,hand=None)
            elif weapon_item.location in (PcItemLocation.HELD,PcItemLocation.CARRIED):
                physical = replace(physical,location=PcNetLocation.HELD if weapon_item.location is PcItemLocation.HELD else PcNetLocation.CARRIED)
                bank = _replace_item(bank,physical)
            else:
                raise ValueError('Net cannot leave inventory without its actual throw/drop proof')
        inventory = replace(inventory,items=tuple(items))
        party[index] = replace(member,weapon_inventory=inventory,
            net_condition_sources=tuple(item.binding for item in bank
                if item.location is PcNetLocation.BOUND and item.bound_target_id == member.actor_id))
    enemies = []
    for enemy in values.get('enemies',state.enemies):
        physical = next((item for item in bank if item.owner_id == enemy.state.actor_id),None)
        if physical is not None and enemy.definition.generated_components is not None:
            available = physical.location is PcNetLocation.HELD
            enemy = replace(enemy,state=replace(enemy.state,wields_weapon=available,
                available_attack_ids=tuple(profile.id for profile in enemy.definition.attacks) if available else ()))
        elif physical is not None and enemy.definition.id == NET_DEFINITION_ID:
            from towr.domain.pc_net_models import net_stock_and_held
            # The existing printed Spear draw remains a distinct validated
            # equipment change. A throw itself leaves no weapon in the hands.
            landed = getattr(proof,'weighted_net_landing',None)
            if landed is not None and landed.actor_id == enemy.state.actor_id:
                enemy = replace(enemy,state=replace(enemy.state,wields_weapon=False,
                    available_attack_ids=('jagged_spear',)))
            elif type(proof) is PcNetPickupProof and physical.location is PcNetLocation.HELD:
                enemy = replace(enemy,state=replace(enemy.state,wields_weapon=True,
                    available_attack_ids=tuple(profile.id for profile in enemy.definition.attacks)))
        enemies.append(enemy)
    values['weighted_nets'] = bank
    if tuple(party) != state.party or 'party' in values:
        values['party'] = tuple(party)
    if tuple(enemies) != state.enemies or 'enemies' in values:
        values['enemies'] = tuple(enemies)
    return values


weighted_nets_after_drop = weighted_nets_after_equipment


def validate_weighted_net_bank(state):
    """Retain each physical item and the complete ordered receipt prefix."""
    from towr.domain.pc_combat_equipment_models import PcItemLocation,PcWeaponInventoryState
    source = initial_weighted_nets(state.source)
    if type(state.weighted_nets) is not tuple or len(source) != len(state.weighted_nets):
        raise TypeError('Net bank must retain its exact source-ordered physical item tuple')
    for actual,original in zip(state.weighted_nets,source,strict=True):
        if type(actual) is not PcWeightedNetState:
            raise TypeError('Net bank requires exact physical item states')
        replace(actual)
        if (actual.item_id,actual.owner_id) != (original.item_id,original.owner_id):
            raise ValueError('Net bank changed physical source membership or ownership')
        if actual.location is PcNetLocation.BOUND and actual.bound_target_id not in (
                *state.source.pc_activation_order,*state.source.enemy_activation_order):
            raise ValueError('Net binding targets a source-less actor')
        if actual.owner_id in state.source.pc_activation_order:
            inventory = state.participant(actual.owner_id).weapon_inventory
            if type(inventory) is not PcWeaponInventoryState:
                raise TypeError('PC physical Net requires its actual source inventory state')
            weapon = next((item for item in inventory.items
                if actual.owner_id+':weapon:'+item.id == actual.item_id),None)
            expected_location = (PcItemLocation.HELD if actual.location is PcNetLocation.HELD else
                PcItemLocation.CARRIED if actual.location is PcNetLocation.CARRIED else PcItemLocation.DEPLOYED)
            if weapon is None or weapon.location is not expected_location:
                raise ValueError('PC equipment changed the location of its actual physical Net')
        if state.battlefield is not None:
            markers = tuple(placement for placement in state.battlefield.spatial.placements
                if placement.entity_id == actual.marker_id)
            if actual.location is PcNetLocation.FREE:
                if len(markers) != 1 or markers[0].side_id != 'objects' or markers[0].zone_id != actual.ground.zone_id:
                    raise ValueError('free physical Net lost or moved its actual static object marker')
            elif markers:
                raise ValueError('a non-free Net cannot keep a ground marker')
    if source:
        _same(state.weighted_nets,_weighted_net_history_bank(state,source))


def _weighted_net_history_bank(state,source):
    """Fold physical receipts without rerunning combat, dice or action choices.

    The action owner proves each receipt when it is created. This independent
    prefix check prevents a later state from erasing/reordering that receipt
    while keeping its physical item, binding or restored equipment.
    """
    from towr.domain.pc_melee_result_models import PcAttackProof
    from towr.domain.pc_net_models import PcNpcNetDrawProof
    from towr.domain.pc_weapon_inventory import PcWeaponSwapProof
    from towr.domain.pc_combat_equipment_models import PcItemLocation
    from towr.domain.pc_melee_models import PcMeleeWeapon
    bank = source

    def current(item_id):
        item = next((item for item in bank if item.item_id == item_id),None)
        if item is None:
            raise ValueError('Net receipt invented a physical item outside its source')
        return item

    def physical_transition(proof,*,before,after):
        item = current(proof.item_id)
        _same(proof.previous_item,item)
        if item.location not in before:
            raise ValueError('Net receipt does not follow its actual physical item prefix')
        _same(proof.item,after(item))
        return _replace_item(bank,proof.item)

    for proof in state.history:
        for drop in getattr(proof,'weighted_net_drops',()):
            if type(drop) is not PcNetDrop:
                raise TypeError('Net drop history requires its exact physical receipt')
            if drop.actor_id != current(drop.item_id).owner_id:
                raise ValueError('Net drop changed its physical owner')
            bank = physical_transition(drop,before=(PcNetLocation.HELD,),after=lambda item:
                replace(item,location=PcNetLocation.FREE,ground=drop.item.ground))
        if type(proof) is PcAttackProof:
            landing = proof.weighted_net_landing
            if not is_net_impact(proof.request.kernel_request.attack.impact_spec):
                if landing is not None:
                    raise ValueError('ordinary Attack cannot invent a physical Net landing')
                continue
            if type(landing) is not PcNetThrowLanding:
                raise TypeError('Net Attack history lost its actual physical landing receipt')
            _same((landing.attack_id,landing.actor_id,landing.target_id),
                (proof.request.id,proof.request.actor_id,proof.request.target_id))
            if landing.actor_id != current(landing.item_id).owner_id:
                raise ValueError('Net throw changed its physical owner')
            causes = net_condition_sources_from_attack(proof.request,proof.execution.resolution)
            if proof.execution.resolution.attack.outcome is AttackOutcome.HIT:
                if len(causes) != 1:
                    raise ValueError('Net hit history lost its one actual Burdened source')
                after = lambda item:replace(item,location=PcNetLocation.BOUND,
                    bound_target_id=landing.target_id,binding=causes[0])
            else:
                after = lambda item:replace(item,location=PcNetLocation.FREE,ground=landing.item.ground)
            bank = physical_transition(landing,before=(PcNetLocation.HELD,),after=after)
        elif type(proof) is PcNetReleaseProof:
            released = proof.result.resolution.removed
            bank = physical_transition(proof,before=(PcNetLocation.BOUND,),after=lambda item:
                replace(item,location=PcNetLocation.FREE,bound_target_id=None,binding=None,
                    ground=proof.item.ground) if released else item)
        elif type(proof) in (PcNetPickupProof,PcNetIncidentalPickupProof):
            bank = physical_transition(proof,before=(PcNetLocation.FREE,),after=lambda item:
                replace(item,location=PcNetLocation.HELD,ground=None))
        elif type(proof) is PcNpcNetDrawProof:
            item = next((item for item in bank if item.owner_id == proof.actor_id),None)
            if item is None:
                raise ValueError('Net draw history lost its physical source item')
            if proof.attack_id == 'weighted_net':
                if item.location not in (PcNetLocation.HELD,PcNetLocation.CARRIED):
                    raise ValueError('free draw cannot restore a deployed physical Net')
                bank = _replace_item(bank,replace(item,location=PcNetLocation.HELD))
            elif item.location is PcNetLocation.HELD:
                bank = _replace_item(bank,replace(item,location=PcNetLocation.CARRIED))
        elif type(proof) is PcWeaponSwapProof:
            for before,after in zip(proof.previous.items,proof.state.items,strict=True):
                if before.weapon is not PcMeleeWeapon.WEIGHTED_NET:
                    continue
                item = current(proof.actor_id+':weapon:'+before.id)
                if before.location in (PcItemLocation.HELD,PcItemLocation.CARRIED):
                    _same(item.location,PcNetLocation(before.location.value))
                elif item.location not in (PcNetLocation.FREE,PcNetLocation.BOUND):
                    raise ValueError('weapon swap changed its deployed physical Net prefix')
                if after.location in (PcItemLocation.HELD,PcItemLocation.CARRIED):
                    if item.location not in (PcNetLocation.HELD,PcNetLocation.CARRIED):
                        raise ValueError('weapon swap cannot retrieve a deployed physical Net')
                    bank = _replace_item(bank,replace(item,location=PcNetLocation(after.location.value)))
    return bank
