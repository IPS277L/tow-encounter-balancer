"""Source-bound Charge and Run phases in the explicit open encounter arena.

Only positioning and Athletics live here. A successful Charge keeps its real
Manoeuvre slot unused for the ordinary native Attack/Fate/Help/kernel owner.
"""
from __future__ import annotations
from towr.domain.pc_acrobatic_models import actor_acrobatic_source
from towr.domain.pc_movement_block_models import pc_enemy_path_blockers

from dataclasses import dataclass, field, replace
from collections import deque
from typing import TYPE_CHECKING

from towr.domain.charge_models import ChargeMovementRequest, ChargeMovementResult
from towr.domain.condition_models import Condition
from towr.domain.fate_models import FateGloriousSpendResult
from towr.domain.injury_models import WoundRestriction
from towr.domain.movement_models import (
    MovementSpeed, RunActionExecutionRequest, RunActionExecutionResult,
    RunAthleticsExtensionRequest, RunAthleticsExtensionResult, FreeMovementRequest,
    MoveCarefullyActionExecutionRequest,MoveCarefullyActionExecutionResult,MoveCarefullySearchChoice,
)
from towr.domain.pc_battlefield_models import PcBattlefieldState, battlefield_range, with_actor_placement, battlefield_is_midair
from towr.domain.pc_battlefield_movement_models import (
    PcBattlefieldMoveProof, _conditions, _enemies, _has_close_enemy, _ranges, _rank, _zone_distance,
    pc_battlefield_attack_available,
    aerialmovement_permission, battlefield_path_available, _ranged_flight_preference,
)
from towr.domain.reload_models import ranged_weapon_is_loaded
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.test_models import DiceModifier, Skill, TestRequest
from towr.domain.turn_models import CombatActionKind, ManoeuvreKind
from towr.rules.charge_action_execution import _complete_charge_movement_after_test, CHARGE_MELEE_BONUS_RULE_ID
from towr.rules.run_action_execution import execute_run_action, _complete_run_athletics_extension_after_test
from towr.rules.move_carefully_resolution import execute_move_carefully_action

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcFateDecline, PcMeleeState


@dataclass(frozen=True, slots=True)
class PcBattlefieldManoeuvreProposal:
    actor_id: str
    target_id: str
    kind: ManoeuvreKind

    def __post_init__(self):
        if (any(type(value) is not str or not value.strip() for value in (self.actor_id,self.target_id))
                or self.actor_id == self.target_id or type(self.kind) is not ManoeuvreKind
                or self.kind not in (ManoeuvreKind.CHARGE,ManoeuvreKind.RUN,ManoeuvreKind.MOVE_CAREFULLY)):
            raise ValueError('battlefield proposal requires an actual actor, target and supported Manoeuvre')


def pc_battlefield_actor_speed(state: PcMeleeState, actor: str) -> MovementSpeed:
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_heavy_wound_models import restriction_sources
        if restriction_sources(state.participant(actor).injury,WoundRestriction.SPEED_IS_SLOW):
            return MovementSpeed.SLOW
    elif actor not in state.source.enemy_activation_order:
        from towr.domain.pc_companion_effect_models import companion_profile
        return companion_profile(state,actor).speed
    from towr.domain.pc_mount_models import pc_mount_speed
    return pc_mount_speed(state,actor,MovementSpeed.NORMAL)


def _speed(state,actor,speed):
    actual = pc_battlefield_actor_speed(state,actor)
    if speed is not None and (type(speed) is not MovementSpeed or speed is not actual):
        raise ValueError('Manoeuvre Speed must match the actual source, not a caller override')
    return actual


def _began_close(state,actor):
    # An incidental move cannot erase the beginning-of-turn prohibition. The
    # native policy has one turn per actor/round; no other actor moves mid-turn.
    previous = next((proof.previous for proof in state.history
        if type(proof) is PcBattlefieldMoveProof and proof.actor_id == actor
        and proof.source_round.round_number == state.round_state.round_number),state.battlefield)
    return any(battlefield_range(previous,actor,target) is RangedWeaponRange.CLOSE
        for target in _enemies(state,actor))


def _attack_skill(state,actor):
    from towr.domain.pc_mount_attack_models import pc_mount_primary_needed
    if pc_mount_primary_needed(state, actor):
        return Skill.MELEE
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_melee_result_models import pc_attack_skill
        return pc_attack_skill(state,actor)
    from towr.domain.pc_melee_result_models import pc_selected_npc_attack_profile
    return pc_selected_npc_attack_profile(state,actor).skill


def _has_athletics_source(state,actor):
    return actor in state.source.pc_activation_order or any(
        profile.skill is Skill.ATHLETICS for profile in state.enemy(actor).definition.protection)


def _careful_route(state,actor,target,speed):
    if actor in state.battlefield.spatial.free_move_used_entity_ids:return None
    spatial=state.battlefield.spatial
    origin=spatial.placement_for(actor).zone_id
    target_zone=spatial.placement_for(target).zone_id
    low,high,_,_=_ranges(state,actor)
    def deviation(zone):
        rank=_zone_distance(spatial.graph,zone,target_zone)+1
        if zone==target_zone and high is RangedWeaponRange.CLOSE:rank=0
        return max(_rank(low)-rank,0,rank-_rank(high))
    from towr.domain.pc_terrain_models import terrain_test_required_for_route
    queue=deque(((origin,()),));options=[]
    while queue:
        current,path=queue.popleft()
        if len(path)>=speed.free_move_zone_limit:continue
        for zone in spatial.graph.adjacent_zone_ids(current):
            if zone==origin or zone in path:continue
            route=(*path,zone)
            close=(target,) if zone==target_zone and high is RangedWeaponRange.CLOSE else ()
            if not battlefield_path_available(state,actor,route,close_to_ids=close):continue
            queue.append((zone,route))
            if deviation(zone)<deviation(origin) and terrain_test_required_for_route(state,actor,route):
                options.append(route)
    return min(options,key=lambda path:(deviation(path[-1]),len(path))) if options else None


def _careful_is_useful(state,actor):
    from towr.domain.pc_terrain_models import _terrain_test,_staff_support
    test=_terrain_test(state,actor,'tactics:terrain:'+actor,_staff_support(state,actor))
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_talent_advice import pc_test_distribution
        chance=pc_test_distribution(state,actor,Skill.ATHLETICS,test,include_policy=True)[0]
    else:
        from towr.domain.pc_tactical_models import _distribution
        chance=_distribution(test)[0]
    return chance>=.5


def proposed_pc_battlefield_manoeuvre(state: PcMeleeState, *,
        speed: MovementSpeed | None = None) -> PcBattlefieldManoeuvreProposal | None:
    """Conservative deterministic positioning; never call the tactical solver.

    Long prefers an unused free move. Once that move is spent, Long Charge is
    available with its actual Athletics risk. Existing legal attacks win here.
    """
    if (state.source.battlefield is None or state.battlefield is None or state.pending
            or state.pending_wound is not None or state.magic_pending is not None
            or not state.live_party or not state.live_enemies):
        return None
    turn = state.round_state.active_turn
    if turn is None or len(turn.action_slots) > 1 or any(slot.executed for slot in turn.action_slots):
        return None
    actor = turn.actor_id
    from towr.domain.pc_mount_attack_models import pc_mount_primary_needed
    mount_attack = pc_mount_primary_needed(state, actor)
    conditions = _conditions(state,actor)
    actual_speed = _speed(state,actor,speed)
    if actual_speed is MovementSpeed.SLOW or any(conditions.has(condition) for condition in (
            Condition.BURDENED,Condition.PRONE,Condition.DEFENCELESS,Condition.BROKEN)):
        return None
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_heavy_wound_models import usable_weapon_hand
        from towr.domain.pc_melee_result_models import _pc_recover_needed
        from towr.domain.pc_backup_weapon_models import pc_preferred_weapon_hand
        member = state.participant(actor)
        from towr.domain.pc_weapon_inventory import pc_attack_weapon_use
        use=pc_attack_weapon_use(state,actor)
        if not mount_attack and (_pc_recover_needed(member,
                unarmed_available=state.source.participant(actor).pc.brawn is not None) or use is None
                or use.primary is not None and pc_preferred_weapon_hand(state,actor) != member.weapon_hand):
            return None
        from towr.domain.pc_backup_weapon_models import pc_active_weapon
        from towr.domain.pc_melee_models import PC_RANGED_WEAPONS
        if (not mount_attack and pc_active_weapon(state,actor) in PC_RANGED_WEAPONS
                and member.ranged is not None and not ranged_weapon_is_loaded(member.ranged)):
            return None
    else:
        from towr.domain.pc_npc_ranged_models import pc_npc_ranged_weapon
        weapon = pc_npc_ranged_weapon(state,actor)
        if not mount_attack and weapon is not None and not ranged_weapon_is_loaded(weapon):
            return None
    targets = _enemies(state,actor)
    if not targets or any(pc_battlefield_attack_available(state,actor,target) for target in targets):
        return None
    free_available = actor not in state.battlefield.spatial.free_move_used_entity_ids
    if free_available and state.source.battlefield.zone_features:
        for target in targets:
            if _careful_route(state,actor,target,actual_speed) is not None and _careful_is_useful(state,actor):
                return PcBattlefieldManoeuvreProposal(actor,target,ManoeuvreKind.MOVE_CAREFULLY)
    can_charge = _attack_skill(state,actor) in (Skill.MELEE,Skill.BRAWN,Skill.THROWING) and not _began_close(state,actor)
    if can_charge:
        for target in targets:
            distance = battlefield_range(state.battlefield,actor,target)
            if distance in (RangedWeaponRange.SHORT,RangedWeaponRange.MEDIUM) or (
                    distance is RangedWeaponRange.LONG and not free_available
                    and _has_athletics_source(state,actor)):
                if _charge_route(state, actor, target) is not None:
                    return PcBattlefieldManoeuvreProposal(actor,target,ManoeuvreKind.CHARGE)
    if free_available:
        return None
    target = targets[0]
    if _run_destination(state,actor,target,state.battlefield.spatial) is not None:
        return PcBattlefieldManoeuvreProposal(actor,target,ManoeuvreKind.RUN)
    return None


def _ready(state,target,kind,speed):
    if state.source.battlefield is None or state.battlefield is None:
        raise ValueError('Manoeuvre requires the complete actual battlefield')
    turn = state.round_state.active_turn
    if (turn is None or not turn.action_slots or turn.action_slots[-1].executed
            or turn.action_slots[-1].declaration.kind is not CombatActionKind.MANOEUVRE
            or turn.action_slots[-1].declaration.manoeuvre is not kind
            or target not in _enemies(state,turn.actor_id)):
        raise ValueError('Manoeuvre requires its actual unused reserved action and living target')
    if state.pending or state.pending_wound is not None or state.magic_pending is not None:
        raise ValueError('mandatory consequences must finish before a Manoeuvre')
    return turn.actor_id,_speed(state,turn.actor_id,speed)


def _athletics(state,actor,test_id):
    if actor not in (*state.source.pc_activation_order,*state.source.enemy_activation_order):
        from towr.domain.pc_companion_effect_models import companion_test_request
        return companion_test_request(state,actor,test_id,Skill.ATHLETICS)
    from towr.domain.pc_mount_models import pc_is_mounted
    mounted = pc_is_mounted(state, actor)
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_melee_result_models import _pc_test
        return _pc_test(state,actor,test_id,Skill.ATHLETICS,control_mount=mounted)
    from towr.domain.pc_magic_models import magic_test_modifiers
    from towr.domain.pc_npc_distraction_models import pc_npc_distraction_test_modifiers
    enemy = state.enemy(actor)
    option = next((profile for profile in enemy.definition.protection if profile.skill is Skill.ATHLETICS),None)
    if option is None:
        raise ValueError('NPC Athletics requires its actual explicit profile source')
    modifiers = pc_npc_distraction_test_modifiers(state,actor,None)
    if _conditions(state,actor).has(Condition.DRAINED):
        modifiers = tuple(item for item in modifiers if item.amount <= 0)
    magic_dice,qualities = magic_test_modifiers(state,actor,Skill.ATHLETICS)
    from towr.domain.pc_armour_models import actor_armour_test_modifiers
    return TestRequest(test_id,option.test_profile,(*modifiers,*magic_dice,
        *actor_armour_test_modifiers(state,actor,Skill.ATHLETICS,control_mount=mounted)),qualities)


def _charge_route(state, actor, target):
    battlefield = state.battlefield
    graph = battlefield.spatial.graph
    origin, destination = (battlefield.spatial.placement_for(item).zone_id for item in (actor, target))
    distance = battlefield_range(battlefield, actor, target)
    if distance is RangedWeaponRange.SHORT:
        options = ((),)
    elif distance is RangedWeaponRange.MEDIUM:
        options = ((destination,),)
    elif distance is RangedWeaponRange.LONG:
        options = tuple((middle, destination) for middle in graph.adjacent_zone_ids(origin)
            if graph.are_adjacent(middle, destination))
    else:
        return None
    from towr.domain.pc_terrain_models import terrain_test_required_for_route
    terrain_used=actor in battlefield.spatial.difficult_terrain_tested_entity_ids
    return next((path for path in options if battlefield_path_available(state, actor, path,
        close_to_ids=(target,)) and (distance is not RangedWeaponRange.LONG or not terrain_used
            and not terrain_test_required_for_route(state,actor,path))), None)


def build_pc_battlefield_careful(state: PcMeleeState,target_id: str, *, speed=None):
    actor,speed=_ready(state,target_id,ManoeuvreKind.MOVE_CAREFULLY,speed)
    route=_careful_route(state,actor,target_id,speed)
    if route is None:raise ValueError('Move Carefully needs actual reachable Difficult Terrain')
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    identifier=pc_melee_action_id(state,actor)+':battlefield:careful'
    movement=FreeMovementRequest(identifier+':movement',state.round_state,state.battlefield.spatial,
        actor,speed,_conditions(state,actor),route,crosses_difficult_terrain=True,acrobatic=actor_acrobatic_source(state,actor),path_entity_ids=pc_enemy_path_blockers(state,actor,route))
    return MoveCarefullyActionExecutionRequest(identifier,movement,len(state.round_state.active_turn.action_slots),
        MoveCarefullySearchChoice.DECLINE,None,None,state.round_state,state.battlefield.spatial)


def build_pc_battlefield_charge(state: PcMeleeState,target_id: str, *, speed=None) -> ChargeMovementRequest:
    actor,speed = _ready(state,target_id,ManoeuvreKind.CHARGE,speed)
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    action = pc_melee_action_id(state,actor)+':battlefield:charge'
    distance = battlefield_range(state.battlefield,actor,target_id)
    spatial = state.battlefield.spatial
    route = _charge_route(state, actor, target_id)
    if route is None:
        raise ValueError('Charge route violates actual flight or bound Close restrictions')
    intermediate = None
    test = None
    if distance is RangedWeaponRange.LONG:
        intermediate = route[0]
        test = _athletics(state,actor,action+':athletics')
    from towr.domain.pc_terrain_models import terrain_test_required_for_route
    terrain=terrain_test_required_for_route(state,actor,route)
    return ChargeMovementRequest(action,state.round_state,spatial,actor,target_id,
        len(state.round_state.active_turn.action_slots),speed,_conditions(state,actor),distance,
        _began_close(state,actor),test,intermediate,crosses_difficult_terrain=terrain,
        terrain_resolution_deferred=terrain,acrobatic=actor_acrobatic_source(state,actor),path_entity_ids=pc_enemy_path_blockers(state,actor,route))


def current_pc_charge(state: PcMeleeState,actor: str) -> ChargeMovementResult | None:
    turn = state.round_state.active_turn
    if (turn is None or turn.actor_id != actor or not turn.action_slots
            or turn.action_slots[-1].executed
            or turn.action_slots[-1].declaration.kind is not CombatActionKind.MANOEUVRE
            or turn.action_slots[-1].declaration.manoeuvre is not ManoeuvreKind.CHARGE):
        return None
    for proof in reversed(state.history):
        if type(proof) is PcBattlefieldChargeProof and proof.actor_id == actor:
            result = proof.result
            return result if result.attack_allowed and result.round_state == state.round_state else None
    return None


def pc_charge_attack_modifiers(state: PcMeleeState,actor: str,target: str) -> tuple[DiceModifier,...]:
    grant = current_pc_charge(state,actor)
    return ((DiceModifier(CHARGE_MELEE_BONUS_RULE_ID,1),) if grant is not None
        and grant.target_id == target and _attack_skill(state,actor) is Skill.MELEE else ())


def _run_destination(state,actor,target,spatial):
    low,high,_,_ = _ranges(state,actor)
    origin,target_zone = (spatial.placement_for(entity).zone_id for entity in (actor,target))
    def deviation(zone):
        distance = _zone_distance(spatial.graph,zone,target_zone)+1
        if zone == target_zone and high is RangedWeaponRange.CLOSE:
            distance = 0
        return max(_rank(low)-distance,0,distance-_rank(high))
    current = replace(with_actor_placement(state.battlefield, actor, origin), spatial=spatial)
    options = tuple(zone for zone in spatial.graph.adjacent_zone_ids(origin)
        if battlefield_path_available(state, actor, (zone,), battlefield=current,
            close_to_ids=(target,) if zone == target_zone and high is RangedWeaponRange.CLOSE else ()))
    flight = _ranged_flight_preference(state, actor)
    destination = min(options, key=lambda zone: (deviation(zone), 0 if flight
        and battlefield_is_midair(current, zone, zone=True) else 1)) if options else None
    return destination if destination is not None and deviation(destination) < deviation(origin) else None


def build_pc_battlefield_run(state: PcMeleeState,target_id: str, *, speed=None) -> RunActionExecutionRequest:
    actor,speed = _ready(state,target_id,ManoeuvreKind.RUN,speed)
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    destination = _run_destination(state,actor,target_id,state.battlefield.spatial)
    if destination is None:
        raise ValueError('Run needs an actual adjacent Zone that improves the selected distance')
    from towr.domain.pc_terrain_models import terrain_test_required_for_route
    terrain=terrain_test_required_for_route(state,actor,(destination,))
    return RunActionExecutionRequest(pc_melee_action_id(state,actor)+':battlefield:run',
        state.round_state,state.battlefield.spatial,actor,len(state.round_state.active_turn.action_slots),
        speed,_conditions(state,actor),destination,crosses_difficult_terrain=terrain,
        terrain_resolution_deferred=terrain,acrobatic=actor_acrobatic_source(state,actor),path_entity_ids=pc_enemy_path_blockers(state,actor,(destination,)))


def _run_athletics(state, base_run, destination, target_id):
    if type(base_run) is not RunActionExecutionResult:
        raise TypeError('Run Athletics requires its exact executed base Run')
    test = _athletics(state,base_run.actor_id,base_run.request_id+':extension:athletics')
    spatial = base_run.spatial_state
    origin, target = (spatial.placement_for(actor).zone_id for actor in (base_run.actor_id, target_id))
    if target_id not in _enemies(state,base_run.actor_id) or not spatial.graph.are_adjacent(origin,destination):
        raise ValueError('Run Athletics context requires its actual enemy and adjacent destination')
    pursuing = _zone_distance(spatial.graph,destination,target) < _zone_distance(spatial.graph,origin,target)
    from towr.domain.pc_armour_models import actor_armour_quality_modifiers
    qualities = actor_armour_quality_modifiers(state,base_run.actor_id,tracking_or_pursuit=pursuing)
    test = replace(test,quality_modifiers=(*test.quality_modifiers,*qualities))
    return test


def build_pc_battlefield_run_extension(state: PcMeleeState,base_run: RunActionExecutionResult,
        target_id: str) -> RunAthleticsExtensionRequest | None:
    if not _has_athletics_source(state,base_run.actor_id):
        return None  # The extra Test is optional; do not manufacture a Skill.
    from towr.domain.pc_terrain_models import terrain_test_required_for_route
    actor=base_run.actor_id
    if actor in state.battlefield.spatial.difficult_terrain_tested_entity_ids or terrain_test_required_for_route(
            state,actor,(base_run.destination_zone_id,)):
        return None  # PG115: a terrain crossing excludes optional extra-Zone Athletics.
    destination = _run_destination(state,base_run.actor_id,target_id,base_run.spatial_state)
    if destination is None:
        return None
    current=replace(with_actor_placement(state.battlefield,actor,base_run.destination_zone_id),
        spatial=base_run.spatial_state)
    if terrain_test_required_for_route(state,base_run.actor_id,(destination,),battlefield=current):
        return None
    test = _run_athletics(state,base_run,destination,target_id)
    return RunAthleticsExtensionRequest(base_run.request_id+':extension',base_run,test,
        _conditions(state,base_run.actor_id),destination,
        acrobatic=actor_acrobatic_source(state,actor),
        path_entity_ids=pc_enemy_path_blockers(state,actor,(destination,),battlefield=current))


def _after(state,spatial,actor,target,*,charge=False):
    target_zone = spatial.placement_for(target).zone_id
    destination = spatial.placement_for(actor).zone_id
    _,high,_,_ = _ranges(state,actor)
    close = (target,) if charge or destination == target_zone and high is RangedWeaponRange.CLOSE else ()
    after = replace(with_actor_placement(state.battlefield,actor,destination,close_to_ids=close), spatial=spatial)
    from towr.domain.pc_battlefield_movement_models import movement_keeps_briarroot_close
    if not movement_keeps_briarroot_close(state, actor, after):
        raise ValueError('Manoeuvre cannot move a bound weapon out of Close')
    return after


def battlefield_after_manoeuvre(state: PcMeleeState,result,target_id: str, *, extension_result=None):
    """Project Close links from the one already executed K1 movement result."""
    if type(result) is ChargeMovementResult:
        if result.target_id != target_id or extension_result is not None:
            raise ValueError('Charge battlefield projection must retain its actual target and phase')
        return _after(state,result.spatial_state,result.actor_id,target_id,charge=result.attack_allowed)
    if type(result) is RunActionExecutionResult:
        if extension_result is not None and (type(extension_result) is not RunAthleticsExtensionResult
                or extension_result.base_run != result):
            raise ValueError('Run extension belongs to another actual base Run')
        spatial = result.spatial_state if extension_result is None else extension_result.spatial_state
        return _after(state,spatial,result.actor_id,target_id)
    if type(result) is MoveCarefullyActionExecutionResult:
        if extension_result is not None:raise ValueError('Move Carefully has no optional Run extension')
        return _after(state,result.spatial_state,result.actor_id,target_id)
    raise TypeError('battlefield projection needs its exact Charge, Run or Move Carefully phase result')


@dataclass(frozen=True, slots=True)
class PcBattlefieldChargeProof:
    request: ChargeMovementRequest
    result: ChargeMovementResult
    previous: PcBattlefieldState
    state: PcBattlefieldState
    fate_decline: PcFateDecline | None = None
    glorious: FateGloriousSpendResult | None = None

    @property
    def actor_id(self):
        return self.request.actor_id


@dataclass(frozen=True, slots=True)
class PcBattlefieldRunProof:
    request: RunActionExecutionRequest
    result: RunActionExecutionResult
    previous: PcBattlefieldState
    state: PcBattlefieldState
    target_id: str = field(kw_only=True)
    extension_request: RunAthleticsExtensionRequest | None = None
    extension_result: RunAthleticsExtensionResult | None = None
    fate_decline: PcFateDecline | None = None
    glorious: FateGloriousSpendResult | None = None

    @property
    def actor_id(self):
        return self.request.actor_id


@dataclass(frozen=True,slots=True)
class PcBattlefieldCarefulProof:
    request: MoveCarefullyActionExecutionRequest
    result: MoveCarefullyActionExecutionResult
    previous: PcBattlefieldState
    state: PcBattlefieldState
    target_id: str = field(kw_only=True)

    @property
    def actor_id(self):return self.request.free_movement.actor_id


BATTLEFIELD_MANOEUVRE_PROOFS = (PcBattlefieldChargeProof,PcBattlefieldRunProof,PcBattlefieldCarefulProof)


def project_pc_battlefield_manoeuvre(state: PcMeleeState,proof) -> dict:
    """Return canonical owner updates; the common projection appends history."""
    from towr.domain.pc_melee_result_models import (
        _party_update,_enemy_update,_test_result,pc_after_test,validate_pc_melee_source_types,
    )
    from towr.domain.pc_fate_test_models import validate_pc_test_fate
    from towr.domain.pc_heavy_wound_models import critical_for_action
    def same(actual,expected):
        if actual != expected:
            raise ValueError('Manoeuvre changed its complete canonical source, phase or spatial result')
        validate_pc_melee_source_types(actual,expected)
    if type(proof) not in BATTLEFIELD_MANOEUVRE_PROOFS:
        raise TypeError('battlefield Manoeuvre requires an exact supported proof')
    if type(proof) is PcBattlefieldCarefulProof:
        actor,target=proof.actor_id,proof.target_id
        same(proposed_pc_battlefield_manoeuvre(state),PcBattlefieldManoeuvreProposal(actor,target,ManoeuvreKind.MOVE_CAREFULLY))
        request=build_pc_battlefield_careful(state,target)
        same(proof.previous,state.battlefield);same(proof.request,request)
        result=execute_move_carefully_action(request)
        same(proof.result,result)
        after=_after(state,result.spatial_state,actor,target)
        same(proof.state,after)
        updates=dict(round_state=result.round_state,battlefield=after)
        if actor in state.source.pc_activation_order:
            injury=critical_for_action(state.participant(actor),CombatActionKind.MANOEUVRE)
            updates['party']=_party_update(state,actor,injury=injury)
        else:
            updates['enemies']=_enemy_update(state,actor,state.enemy(actor).state.injury)
        return updates
    actor = proof.actor_id
    target = proof.request.target_id if type(proof) is PcBattlefieldChargeProof else proof.target_id
    proposal = proposed_pc_battlefield_manoeuvre(state)
    kind = ManoeuvreKind.CHARGE if type(proof) is PcBattlefieldChargeProof else ManoeuvreKind.RUN
    if proposal is None or proposal != PcBattlefieldManoeuvreProposal(actor,target,kind):
        raise ValueError('Manoeuvre must follow the actual deterministic positioning proposal')
    same(proof.previous,state.battlefield)
    request = (build_pc_battlefield_charge(state,target) if kind is ManoeuvreKind.CHARGE
        else build_pc_battlefield_run(state,target))
    same(proof.request,request)
    test_request = request.athletics_test if kind is ManoeuvreKind.CHARGE else None
    test = proof.result.athletics_test_result if kind is ManoeuvreKind.CHARGE else None
    extension = None
    if kind is ManoeuvreKind.RUN:
        canonical_run = execute_run_action(request)
        same(proof.result,canonical_run)
        extension = build_pc_battlefield_run_extension(state,canonical_run,target)
        same(proof.extension_request,extension)
        if extension is not None:
            if type(proof.extension_result) is not RunAthleticsExtensionResult:
                raise TypeError('Run extension must preserve its exact actual Test and result')
            test_request,test = extension.athletics_test,proof.extension_result.athletics_test_result
        elif proof.extension_result is not None:
            raise ValueError('Run cannot invent a second extra Zone or Athletics result')
    fate = None
    effective = test_request
    if test_request is None:
        if proof.fate_decline is not None or proof.glorious is not None:
            raise ValueError('a deterministic Manoeuvre has no Athletics Fate window')
    elif actor in state.source.pc_activation_order:
        effective,fate = validate_pc_test_fate(state,actor,Skill.ATHLETICS,test_request,test,
            proof.fate_decline,proof.glorious)
    else:
        if proof.fate_decline is not None or proof.glorious is not None:
            raise ValueError('NPC Athletics cannot acquire a PC Fate resource')
        _test_result(test_request,test)
    if kind is ManoeuvreKind.CHARGE:
        result = _complete_charge_movement_after_test(replace(request,athletics_test=effective),test)
        same(proof.result,result)
        spatial,conditions,combat = result.spatial_state,result.conditions,result.round_state
        after = battlefield_after_manoeuvre(state,result,target)
    else:
        if extension is not None:
            completed = _complete_run_athletics_extension_after_test(
                replace(extension,athletics_test=effective),test)
            same(proof.extension_result,completed)
            spatial,conditions = completed.spatial_state,completed.conditions
        else:
            spatial,conditions = proof.result.spatial_state,_conditions(state,actor)
        combat = proof.result.round_state
        after = battlefield_after_manoeuvre(state,proof.result,target,
            extension_result=completed if extension is not None else None)
    same(proof.state,after)
    updates = dict(round_state=combat,battlefield=after)
    if actor in state.source.pc_activation_order:
        member = state.participant(actor)
        critical = critical_for_action(member,CombatActionKind.MANOEUVRE)
        # Preserve newly caused Critically Injured while incorporating a failed
        # Athletics Staggered, then apply the ordinary after-Test wound rules.
        if critical.conditions.has(Condition.CRITICALLY_INJURED):
            conditions = conditions.with_condition(Condition.CRITICALLY_INJURED)
        injury = replace(critical,conditions=conditions)
        if test_request is not None:
            injury = pc_after_test(state,actor,injury)
        changes = dict(injury=injury)
        if fate is not None:
            changes['fate'] = fate
        updates['party'] = _party_update(state,actor,**changes)
    else:
        injury = replace(state.enemy(actor).state.injury,conditions=conditions)
        updates['enemies'] = _enemy_update(state,actor,injury)
    return updates
