"""One mandatory K1 Athletics Test after a real Difficult Terrain crossing.

The source movement already paid its own movement/action. This owner adds no
action and never reruns that movement. Completed-crossing K1 checks preserve
the frozen movement prefix and its resource usage.
"""
from __future__ import annotations

from dataclasses import dataclass,replace
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition
from towr.domain.fate_models import FateGloriousSpendResult
from towr.domain.movement_models import DifficultTerrainTraversalRequest,DifficultTerrainTraversalResult
from towr.domain.pc_battlefield_models import PcBattlefieldState,battlefield_is_midair
from towr.domain.pc_scene_feature_models import difficult_terrain_crossed
from towr.domain.test_models import Skill,TestRequest,QualityModifier,TestQuality
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_inventory_models import WeaponGrip,WeaponItemLocation
from towr.domain.weapon_use_models import WeaponUse,build_weapon_use

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcFateDecline
    from towr.domain.pc_battlefield_movement_models import PcBattlefieldMoveProof
    from towr.domain.pc_battlefield_manoeuvre_models import PcBattlefieldChargeProof,PcBattlefieldRunProof,PcBattlefieldCarefulProof
    from towr.domain.pc_shield_models import PcShieldApproachProof
    from towr.domain.pc_briarroot_weapon_models import PcBriarrootWeaponApproachProof
    from towr.domain.pc_weighted_net_models import PcNetApproachProof
    from towr.domain.pc_broken_battlefield_models import PcBrokenMoveProof,PcBrokenRunProof



def _movement_parts(proof):
    from towr.domain.pc_battlefield_movement_models import PcBattlefieldMoveProof
    from towr.domain.pc_battlefield_manoeuvre_models import PcBattlefieldChargeProof,PcBattlefieldRunProof,PcBattlefieldCarefulProof
    from towr.domain.pc_shield_models import PcShieldApproachProof
    from towr.domain.pc_briarroot_weapon_models import PcBriarrootWeaponApproachProof
    from towr.domain.pc_weighted_net_models import PcNetApproachProof
    from towr.domain.pc_broken_battlefield_models import PcBrokenMoveProof,PcBrokenRunProof
    kinds=(PcBattlefieldMoveProof,PcBattlefieldChargeProof,PcBattlefieldRunProof,PcBattlefieldCarefulProof,
        PcShieldApproachProof,PcBriarrootWeaponApproachProof,PcNetApproachProof,PcBrokenMoveProof,PcBrokenRunProof)
    if type(proof) not in kinds:return None
    replace(proof)
    before,after=proof.previous,proof.state
    if before is None or after is None:return None
    actor=proof.actor_id
    if type(proof) is PcBattlefieldCarefulProof:
        clock=proof.result.round_state
        route=proof.request.free_movement.traversed_zone_ids
    elif type(proof) is PcBattlefieldChargeProof:
        clock=proof.result.round_state
        origin=before.spatial.placement_for(actor).zone_id
        destination=after.spatial.placement_for(actor).zone_id
        middle=proof.request.intermediate_zone_id
        route=(() if origin==destination else (destination,) if middle is None
            or middle==destination else (middle,destination))
    elif type(proof) in (PcBattlefieldRunProof,PcBrokenRunProof):
        clock=proof.result.round_state
        route=(proof.request.destination_zone_id,)
        actual=after.spatial.placement_for(actor).zone_id
        if actual!=route[-1]:route=(*route,actual)
    else:
        clock=proof.source_round
        request=(proof.request if type(proof) in (PcBriarrootWeaponApproachProof,PcBrokenMoveProof) else proof.movement_request)
        route=() if request is None else request.traversed_zone_ids
    return actor,clock,before,after,route


@dataclass(frozen=True,slots=True)
class PcTerrainTraversalRequest:
    id: str
    actor_id: str
    movement_index: int
    movement: PcBattlefieldMoveProof | PcBattlefieldChargeProof | PcBattlefieldRunProof | PcBattlefieldCarefulProof | PcShieldApproachProof | PcBriarrootWeaponApproachProof | PcNetApproachProof | PcBrokenMoveProof | PcBrokenRunProof
    previous: PcBattlefieldState
    crossed_zone_ids: tuple[str,...]
    staff_use: WeaponUse | None
    traversal: DifficultTerrainTraversalRequest

    def __post_init__(self):
        if any(type(value) is not str or not value.strip() for value in (self.id,self.actor_id)):
            raise TypeError('terrain resolution needs exact identifiers')
        if type(self.movement_index) is not int or self.movement_index<0:
            raise TypeError('terrain resolution needs its exact movement history index')
        parts=_movement_parts(self.movement)
        if parts is None or parts[0]!=self.actor_id:
            raise ValueError('terrain source must retain its real actor-owned movement proof')
        actor,clock,before,after,route=parts
        if type(self.previous) is not PcBattlefieldState or self.previous!=after:
            raise ValueError('terrain source changed its completed spatial prefix')
        if type(self.traversal) is not DifficultTerrainTraversalRequest:
            raise TypeError('terrain resolution requires the exact K1 source')
        replace(self.traversal)
        if (self.traversal.id!=self.id or self.traversal.actor_id!=actor
                or self.traversal.round_state!=clock or self.traversal.state!=before.spatial
                or self.traversal.completed_crossing!=after.spatial):
            raise ValueError('terrain K1 source changed actual movement, clock or actor')
        if type(self.crossed_zone_ids) is not tuple or not self.crossed_zone_ids or any(
                type(zone) is not str or not before.spatial.graph.contains(zone) for zone in self.crossed_zone_ids):
            raise ValueError('terrain source needs its actual crossed feature Zones')
        if len(set(self.crossed_zone_ids))!=len(self.crossed_zone_ids):
            raise ValueError('terrain source repeats its crossed Zone')
        if self.staff_use is not None:
            if type(self.staff_use) is not WeaponUse:
                raise TypeError('Staff support needs its complete physical use')
            replace(self.staff_use)
            if self.staff_use.actor_id!=actor or self.staff_use.kind is not WeaponKind.STAFF:
                raise ValueError('terrain Staff belongs to another actor or item')

    @property
    def athletics_test(self):return self.traversal.athletics_test

    @property
    def round_state(self):return self.traversal.round_state


@dataclass(frozen=True,slots=True)
class PcTerrainTraversalProof:
    request: PcTerrainTraversalRequest
    result: DifficultTerrainTraversalResult
    fate_decline: PcFateDecline | None = None
    glorious: FateGloriousSpendResult | None = None


def _staff_support(state,actor):
    pc=actor in state.source.pc_activation_order
    member=state.participant(actor) if pc else None
    injury=member.injury if pc else state.enemy(actor).state.injury
    if injury.conditions.has(Condition.DRAINED):return None  # No benefit, hence no optional Staff hand use.
    inventory=member.weapon_inventory if pc else state.enemy(actor).state.weapon_inventory
    if inventory is None:return None
    if pc:
        from towr.domain.pc_heavy_wound_models import usable_hands,injured_hands
        usable=tuple(WeaponGrip(side.value) for side in usable_hands(member))
        injured={WeaponGrip(side.value) for side in injured_hands(member)}
    else:
        usable=(WeaponGrip.LEFT,WeaponGrip.RIGHT);injured=set()
    options=[]
    for item in inventory.items:
        if item.kind is not WeaponKind.STAFF or item.location is not WeaponItemLocation.HELD:continue
        try:use=build_weapon_use(actor,inventory,item.id,usable_hands=usable)
        except ValueError:continue
        options.append(use)
    return min(options,key=lambda use:len(set(use.used_hands)&injured)) if options else None


def _terrain_test(state,actor,test_id,staff):
    from towr.domain.pc_battlefield_manoeuvre_models import _athletics
    test=_athletics(state,actor,test_id)
    injury=(state.participant(actor).injury if actor in state.source.pc_activation_order
        else state.enemy(actor).state.injury)
    modifiers=test.dice_modifiers
    if staff is not None:
        from towr.domain.weapon_effect_preparation import weapon_kind_test_modifiers
        modifiers=(*modifiers,*weapon_kind_test_modifiers(staff.kind,Skill.ATHLETICS,injury.conditions,
            crossing_difficult_terrain=True))
    if injury.conditions.has(Condition.DRAINED):
        modifiers=tuple(modifier for modifier in modifiers if modifier.amount<=0)
    quality=test.quality_modifiers
    if injury.conditions.has(Condition.BLINDED) and not any(
            modifier.rule_id=='RULE-HEALTH-008:blinded' for modifier in quality):
        quality=(*quality,QualityModifier('RULE-HEALTH-008:blinded',TestQuality.GRIM))
    return replace(test,dice_modifiers=modifiers,quality_modifiers=quality)


def terrain_test_required_for_route(state,actor,path,*,battlefield=None,moved=True):
    before=state.battlefield if battlefield is None else battlefield
    flying=any(battlefield_is_midair(before,zone,zone=True) for zone in (
        before.spatial.placement_for(actor).zone_id,*path))
    return bool(difficult_terrain_crossed(state,actor,before,path,moved=moved,flying=flying))


def expected_pc_terrain_traversal(state):
    if state.source.battlefield is None or state.battlefield is None:return None
    turn=state.round_state.active_turn
    if turn is None or state.pending or state.pending_wound is not None or state.magic_pending is not None:return None
    actor=turn.actor_id
    for index in range(len(state.history)-1,-1,-1):
        move=state.history[index]
        parts=_movement_parts(move)
        if parts is None:continue
        owner,clock,before,after,path=parts
        if owner!=actor or clock.round_number!=state.round_state.round_number:continue
        if any(type(proof) is PcTerrainTraversalProof and proof.request.movement_index==index
                for proof in state.history[index+1:]):return None
        moved=(before.spatial.placement_for(actor)!=after.spatial.placement_for(actor)
            or tuple(pair for pair in before.close_pairs if actor in pair)!=tuple(
                pair for pair in after.close_pairs if actor in pair))
        flying=any(battlefield_is_midair(before,zone,zone=True) for zone in (
            before.spatial.placement_for(actor).zone_id,*path))
        from towr.domain.pc_battlefield_manoeuvre_models import PcBattlefieldCarefulProof
        crossed=difficult_terrain_crossed(state,actor,before,path,moved=moved,flying=flying,
            move_carefully=type(move) is PcBattlefieldCarefulProof)
        if not crossed:return None
        if after!=state.battlefield or clock!=state.round_state:
            raise ValueError('terrain must resolve immediately after its actual movement prefix')
        from towr.domain.pc_melee_result_models import pc_melee_action_id
        identifier=pc_melee_action_id(state,actor)+':terrain:move:'+str(index)
        staff=_staff_support(state,actor)
        injury=(state.participant(actor).injury if actor in state.source.pc_activation_order
            else state.enemy(actor).state.injury)
        test=_terrain_test(state,actor,identifier+':athletics',staff)
        traversal=DifficultTerrainTraversalRequest(identifier,state.round_state,before.spatial,actor,
            injury.conditions,test,after.spatial.placement_for(actor).zone_id,
            completed_crossing=after.spatial)
        return PcTerrainTraversalRequest(identifier,actor,index,move,after,crossed,staff,traversal)
    return None


def project_pc_terrain(state,proof):
    from towr.domain.pc_melee_result_models import (
        _party_update,_enemy_update,_test_result,pc_after_test,validate_pc_melee_source_types,
    )
    from towr.rules.difficult_terrain_resolution import _complete_difficult_terrain_after_test
    if type(proof) is not PcTerrainTraversalProof or type(proof.request) is not PcTerrainTraversalRequest:
        raise TypeError('terrain resolution requires its exact source and proof')
    if type(proof.result) is not DifficultTerrainTraversalResult:
        raise TypeError('terrain resolution requires its complete K1 result')
    def same(actual,expected):
        if actual!=expected:raise ValueError('terrain proof changed actual source, Test, resource or complete result')
        validate_pc_melee_source_types(actual,expected)
    expected=expected_pc_terrain_traversal(state)
    if expected is None:raise ValueError('there is no unresolved real terrain crossing')
    same(proof.request,expected)
    actor=expected.actor_id
    pc=actor in state.source.pc_activation_order
    test=proof.result.athletics_test_result
    if pc:
        from towr.domain.pc_fate_test_models import validate_pc_test_fate
        effective,fate=validate_pc_test_fate(state,actor,Skill.ATHLETICS,expected.athletics_test,
            test,proof.fate_decline,proof.glorious)
    else:
        if proof.fate_decline is not None or proof.glorious is not None:
            raise ValueError('NPC terrain crossing cannot acquire PC Fate')
        _test_result(expected.athletics_test,test);effective=expected.athletics_test
    canonical=_complete_difficult_terrain_after_test(replace(expected.traversal,athletics_test=effective),test)
    same(proof.result,canonical)
    updates=dict(battlefield=replace(state.battlefield,spatial=canonical.state))
    if pc:
        from towr.domain.pc_heavy_wound_models import critical_for_hand
        from towr.domain.pc_weapon_intent_models import weapon_use_hand
        injury=pc_after_test(state,actor,critical_for_hand(state.participant(actor),weapon_use_hand(expected.staff_use)))
        conditions=canonical.conditions
        if injury.conditions.has(Condition.CRITICALLY_INJURED):
            conditions=conditions.with_condition(Condition.CRITICALLY_INJURED)
        updates['party']=_party_update(state,actor,injury=replace(injury,conditions=conditions),fate=fate)
    else:
        injury=state.enemy(actor).state.injury
        updates['enemies']=_enemy_update(state,actor,replace(injury,conditions=canonical.conditions))
    return updates
