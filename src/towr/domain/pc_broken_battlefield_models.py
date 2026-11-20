"""PG122 mandatory Broken movement in the actual PC/generated battlefield.

Safety is a Zone containing no living enemy actor. Ground-object markers do
not count as enemies. Reaching safety is not an exit, defeat or recovery from
Broken; the fixed policy then uses standard Recover, without invented Willpower.
"""
from __future__ import annotations
from towr.domain.pc_acrobatic_models import actor_acrobatic_source
from towr.domain.pc_movement_block_models import pc_enemy_path_blockers

from collections import deque
from dataclasses import dataclass
from enum import Enum

from towr.domain.condition_models import Condition
from towr.domain.movement_models import (
    FreeMovementRequest,FreeMovementResult,RunActionExecutionRequest,RunActionExecutionResult,MovementSpeed,
)
from towr.domain.pc_battlefield_models import PcBattlefieldState,with_actor_placement
from towr.domain.pc_battlefield_movement_models import _conditions,_enemies,battlefield_path_available
from towr.domain.turn_models import CombatRoundState,CombatActionKind,ManoeuvreKind
from towr.rules.free_movement_resolution import resolve_free_movement
from towr.rules.run_action_execution import execute_run_action


class PcBrokenBlockReason(str,Enum):
    PRONE='prone'
    DEFENCELESS='defenceless'
    NO_LEGAL_ROUTE='no_legal_route'
    ACTION_UNAVAILABLE='action_unavailable'
    SLOW='slow'
    BURDENED='burdened'


@dataclass(frozen=True,slots=True)
class PcBrokenMoveProof:
    actor_id: str
    source_round: CombatRoundState
    previous: PcBattlefieldState
    state: PcBattlefieldState
    enemy_ids: tuple[str,...]
    safe_zone_id: str
    request: FreeMovementRequest
    result: FreeMovementResult


@dataclass(frozen=True,slots=True)
class PcBrokenRunProof:
    actor_id: str
    source_round: CombatRoundState
    previous: PcBattlefieldState
    state: PcBattlefieldState
    enemy_ids: tuple[str,...]
    safe_zone_id: str
    request: RunActionExecutionRequest
    result: RunActionExecutionResult


@dataclass(frozen=True,slots=True)
class PcBrokenBlockedProof:
    actor_id: str
    source_round: CombatRoundState
    previous: PcBattlefieldState
    enemy_ids: tuple[str,...]
    reason: PcBrokenBlockReason


PC_BROKEN_BATTLEFIELD_PROOFS=(PcBrokenMoveProof,PcBrokenRunProof,PcBrokenBlockedProof)


def _actor(state):
    if state.source.battlefield is None or state.battlefield is None:return None
    turn=state.round_state.active_turn
    if turn is None:return None
    actor=turn.actor_id
    from towr.domain.pc_actor_models import pc_actor_side,pc_actor_injury,pc_active_actor_ids
    side=pc_actor_side(state,actor)
    if turn.side is not side:
        raise ValueError('Broken turn differs from the actual actor side')
    if actor not in pc_active_actor_ids(state,side):return None
    if not pc_actor_injury(state,actor).conditions.has(Condition.BROKEN):return None
    return actor


def pc_broken_has_enemy_in_zone(state,actor):
    spatial=state.battlefield.spatial
    zone=spatial.placement_for(actor).zone_id
    return any(spatial.placement_for(enemy).zone_id==zone for enemy in _enemies(state,actor))


def pc_broken_turn_blocked(state):
    actor=_actor(state)
    return actor is not None and any(type(proof) is PcBrokenBlockedProof and proof.actor_id==actor
        and proof.source_round.round_number==state.round_state.round_number for proof in state.history)


def pc_broken_standard_recover_selected(state):
    if state.pending or state.pending_wound is not None or state.magic_pending is not None:return False
    actor=_actor(state)
    if actor is None or pc_broken_turn_blocked(state) or pc_broken_has_enemy_in_zone(state,actor):return False
    if _conditions(state,actor).has(Condition.DEFENCELESS):return False
    turn=state.round_state.active_turn
    return not turn.action_slots or not turn.action_slots[-1].executed


def _route(state,actor,limit):
    """Shortest safe destination, with the fastest legal current movement prefix."""
    spatial=state.battlefield.spatial
    origin=spatial.placement_for(actor).zone_id
    unsafe={spatial.placement_for(enemy).zone_id for enemy in _enemies(state,actor)}
    pending=deque(((origin,()),));visited={origin}
    while pending:
        current,path=pending.popleft()
        if path and current not in unsafe:
            return path[:limit],current
        for zone in spatial.graph.adjacent_zone_ids(current):
            if zone in visited:continue
            route=(*path,zone)
            # Future phases will recheck their own source. An origin's Close
            # restriction cannot be bypassed by pretending takeoff occurred.
            if not battlefield_path_available(state,actor,route[:limit]):continue
            visited.add(zone);pending.append((zone,route))
    return None


def _plan(state):
    actor=_actor(state)
    if actor is None or state.pending or state.pending_wound is not None or state.magic_pending is not None:return None
    if pc_broken_turn_blocked(state):return None
    conditions=_conditions(state,actor)
    if conditions.has(Condition.DEFENCELESS):return actor,'blocked',PcBrokenBlockReason.DEFENCELESS
    if not pc_broken_has_enemy_in_zone(state,actor):return None
    if conditions.has(Condition.PRONE):return actor,'blocked',PcBrokenBlockReason.PRONE
    from towr.domain.pc_battlefield_manoeuvre_models import pc_battlefield_actor_speed
    speed=pc_battlefield_actor_speed(state,actor)
    if actor not in state.battlefield.spatial.free_move_used_entity_ids:
        route=_route(state,actor,speed.free_move_zone_limit)
        return (actor,'free',route) if route is not None else (actor,'blocked',PcBrokenBlockReason.NO_LEGAL_ROUTE)
    if speed is MovementSpeed.SLOW:return actor,'blocked',PcBrokenBlockReason.SLOW
    if conditions.has(Condition.BURDENED):return actor,'blocked',PcBrokenBlockReason.BURDENED
    turn=state.round_state.active_turn
    if turn.action_slots:
        slot=turn.action_slots[-1]
        if (slot.executed or slot.declaration.kind is not CombatActionKind.MANOEUVRE
                or slot.declaration.manoeuvre is not ManoeuvreKind.RUN):
            return actor,'blocked',PcBrokenBlockReason.ACTION_UNAVAILABLE
    route=_route(state,actor,1)
    return (actor,'run',route) if route is not None else (actor,'blocked',PcBrokenBlockReason.NO_LEGAL_ROUTE)


def pc_broken_run_selected(state):
    plan=_plan(state)
    return plan is not None and plan[1]=='run'


def build_pc_broken_run(state):
    plan=_plan(state)
    if plan is None or plan[1]!='run':raise ValueError('Broken actor has no required Run phase')
    actor,_,(path,safe)=plan
    turn=state.round_state.active_turn
    if not turn.action_slots:raise ValueError('Broken Run requires its real reserved Manoeuvre slot')
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    from towr.domain.pc_battlefield_manoeuvre_models import pc_battlefield_actor_speed
    from towr.domain.pc_terrain_models import terrain_test_required_for_route
    terrain=terrain_test_required_for_route(state,actor,path)
    return RunActionExecutionRequest(pc_melee_action_id(state,actor)+':broken:run',state.round_state,
        state.battlefield.spatial,actor,len(turn.action_slots),pc_battlefield_actor_speed(state,actor),
        _conditions(state,actor),path[0],crosses_difficult_terrain=terrain,terrain_resolution_deferred=terrain,acrobatic=actor_acrobatic_source(state,actor),path_entity_ids=pc_enemy_path_blockers(state,actor,(path[0],)))


def expected_pc_broken_battlefield_step(state):
    plan=_plan(state)
    if plan is None:return None
    actor,kind,detail=plan
    before=state.battlefield
    enemies=_enemies(state,actor)
    if kind=='blocked':
        return PcBrokenBlockedProof(actor,state.round_state,before,enemies,detail)
    path,safe=detail
    if kind=='free':
        from towr.domain.pc_melee_result_models import pc_melee_action_id
        from towr.domain.pc_battlefield_manoeuvre_models import pc_battlefield_actor_speed
        from towr.domain.pc_terrain_models import terrain_test_required_for_route
        terrain=terrain_test_required_for_route(state,actor,path)
        request=FreeMovementRequest(pc_melee_action_id(state,actor)+':broken:move',state.round_state,
            before.spatial,actor,pc_battlefield_actor_speed(state,actor),_conditions(state,actor),path,
            crosses_difficult_terrain=terrain,terrain_resolution_deferred=terrain,acrobatic=actor_acrobatic_source(state,actor),path_entity_ids=pc_enemy_path_blockers(state,actor,path))
        result=resolve_free_movement(request)
        after=with_actor_placement(before,actor,request.destination_zone_id)
        from dataclasses import replace
        after=replace(after,spatial=result.state)
        return PcBrokenMoveProof(actor,state.round_state,before,after,enemies,safe,request,result)
    if not state.round_state.active_turn.action_slots:return None
    request=build_pc_broken_run(state)
    result=execute_run_action(request)
    from dataclasses import replace
    after=replace(with_actor_placement(before,actor,request.destination_zone_id),spatial=result.spatial_state)
    return PcBrokenRunProof(actor,state.round_state,before,after,enemies,safe,request,result)


def project_pc_broken_battlefield(state,proof):
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types,_party_update
    if type(proof) not in PC_BROKEN_BATTLEFIELD_PROOFS:
        raise TypeError('Broken movement needs its exact typed actual phase')
    expected=expected_pc_broken_battlefield_step(state)
    if expected is None or proof!=expected:
        raise ValueError('Broken movement changed its actor, clock, fastest legal path, safety or actual result')
    validate_pc_melee_source_types(proof,expected)
    if type(proof) is PcBrokenBlockedProof:return {}
    updates=dict(battlefield=proof.state)
    if type(proof) is PcBrokenRunProof:
        updates['round_state']=proof.result.round_state
    if proof.actor_id in state.source.pc_activation_order:
        from towr.domain.pc_heavy_wound_models import critical_for_action
        updates['party']=_party_update(state,proof.actor_id,injury=critical_for_action(
            state.participant(proof.actor_id),CombatActionKind.MANOEUVRE
                if type(proof) is PcBrokenRunProof else None))
    return updates
