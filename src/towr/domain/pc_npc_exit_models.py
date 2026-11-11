"""One explicit clear adjacent exit for the Broken Official's actual own turn."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition
from towr.domain.movement_models import FreeMovementRequest,FreeMovementResult,MovementSpeed
from towr.domain.pc_npc_wound_models import OFFICIAL_DEFINITION_IDS
from towr.domain.spatial_models import SpatialBattleState,SpatialEntityPlacement,ZoneGraph,ZoneConnection
from towr.domain.turn_models import CombatSide

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcMeleeState


def _exit_result(request: FreeMovementRequest) -> FreeMovementResult:
    previous = request.state
    placements = tuple(replace(p,zone_id=request.destination_zone_id) if p.entity_id==request.actor_id else p
        for p in previous.placements)
    moved = replace(previous,placements=placements,
        free_move_used_entity_ids=(*previous.free_move_used_entity_ids,request.actor_id))
    return FreeMovementResult(request.id,request.rule_id,request.round_state,request.actor_id,request.speed,
        previous.placement_for(request.actor_id).zone_id,request.traversed_zone_ids,previous,moved,
        (request.rule_id,'RULE-COMBAT-012:speed','RULE-COMBAT-011:zones-and-ranges'))


@dataclass(frozen=True, slots=True)
class PcNpcExitProof:
    request: FreeMovementRequest
    result: FreeMovementResult

    def __post_init__(self):
        if type(self.request) is not FreeMovementRequest or type(self.result) is not FreeMovementResult:
            raise TypeError('NPC exit requires its exact FreeMovement request and result')
        replace(self.request)
        replace(self.result)
        if (self.request.actor_conditions.has(Condition.PRONE)
                or self.request.actor_conditions.has(Condition.DEFENCELESS)
                or self.request.crosses_obstacle or self.request.crosses_difficult_terrain):
            raise ValueError('NPC adjacent exit requires executable ordinary free movement')
        actor_side = self.request.state.placement_for(self.request.actor_id).side_id
        if any(self.request.state.placement_for(actor).side_id!=actor_side for actor in self.request.path_entity_ids):
            raise ValueError('NPC adjacent exit cannot pass through an enemy')
        expected = _exit_result(self.request)
        if self.result!=expected:
            raise ValueError('NPC exit movement result changed its exact request or spatial transition')
        from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
        validate_pc_melee_source_types(self.result,expected)


def pc_npc_exit_supported(state: PcMeleeState, actor_id: str) -> bool:
    policy = state.source.npc_broken_exit_policy
    combat = state.round_state
    if (policy is None or state.pending or state.pending_wound is not None or not state.live_party
            or actor_id in state.exited_npc_ids or actor_id not in state.source.enemy_activation_order):
        return False
    if combat.active_turn is None:
        if combat.round_complete or not state.live_enemies:
            return False
        from towr.domain.pc_melee_result_models import pc_melee_next_actor
        if pc_melee_next_actor(state)!=actor_id:
            return False
    elif combat.active_turn.actor_id!=actor_id or combat.active_turn.action_slots:
        return False
    enemy = state.enemy(actor_id)
    return (enemy.definition.id in OFFICIAL_DEFINITION_IDS and not enemy.state.injury.defeated
        and enemy.state.injury.wounds==1 and enemy.state.injury.conditions.has(Condition.BROKEN)
        and not enemy.state.injury.conditions.has(Condition.PRONE)
        and not enemy.state.injury.conditions.has(Condition.DEFENCELESS))


def build_pc_npc_exit(state: PcMeleeState, actor_id: str) -> FreeMovementRequest | None:
    if state.round_state.active_turn is None or not pc_npc_exit_supported(state,actor_id):
        return None
    policy = state.source.npc_broken_exit_policy
    arena,destination = state.source.facts.zone_id,policy.destination_zone_id
    exited = state.exited_npc_ids
    placements = (*(SpatialEntityPlacement(member.actor_id,CombatSide.PLAYERS_AND_ALLIES.value,arena)
        for member in state.source.party),
        *(SpatialEntityPlacement(enemy.state.actor_id,CombatSide.OPPOSITION.value,
            destination if enemy.state.actor_id in exited else arena) for enemy in state.source.enemies))
    used = tuple(proof.request.actor_id for proof in state.history if type(proof) is PcNpcExitProof
        and proof.request.round_state.round_number==state.round_state.round_number)
    spatial = SpatialBattleState(ZoneGraph((arena,destination),(ZoneConnection(arena,destination),)),
        placements,state.round_state.round_number,free_move_used_entity_ids=used)
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    return FreeMovementRequest(pc_melee_action_id(state,actor_id)+':broken-exit:free-movement',
        state.round_state,spatial,actor_id,MovementSpeed.NORMAL,state.enemy(actor_id).state.injury.conditions,
        (destination,))


def expected_pc_npc_exit(state: PcMeleeState, actor_id: str) -> PcNpcExitProof | None:
    request = build_pc_npc_exit(state,actor_id)
    return None if request is None else PcNpcExitProof(request,_exit_result(request))
