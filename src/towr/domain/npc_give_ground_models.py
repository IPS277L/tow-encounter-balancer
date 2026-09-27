from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult
from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.resolution_models import GiveGroundRequest, GiveGroundResolutionRequest, GiveGroundResolutionResult
from towr.domain.spatial_models import SpatialBattleState


@dataclass(frozen=True, slots=True)
class NpcGiveGroundExecutionRequest:
    id: str
    current: NpcRoundRequest
    spatial_state: SpatialBattleState
    attack: NpcRosterAttackExecutionResult
    movement: GiveGroundResolutionRequest

    def __post_init__(self) -> None:
        if not isinstance(self.movement, GiveGroundResolutionRequest):
            raise TypeError("NPC Give Ground execution requires a pending movement request")
        validate_npc_give_ground_context(self)


@dataclass(frozen=True, slots=True)
class NpcGiveGroundConsumptionRequest:
    id: str
    current: NpcRoundRequest
    spatial_state: SpatialBattleState
    attack: NpcRosterAttackExecutionResult
    movement: GiveGroundResolutionResult

    def __post_init__(self) -> None:
        if not isinstance(self.movement, GiveGroundResolutionResult):
            raise TypeError("NPC Give Ground requires a completed movement result")
        validate_npc_give_ground_context(self)


def validate_npc_give_ground_context(
    request: NpcGiveGroundExecutionRequest | NpcGiveGroundConsumptionRequest,
) -> None:
    if not isinstance(request.id, str) or not request.id.strip():
        raise ValueError("NPC Give Ground consumption requires a non-empty id")
    current, spatial_state, attack, movement = request.current, request.spatial_state, request.attack, request.movement
    if not isinstance(current, NpcRoundRequest) or not isinstance(spatial_state, SpatialBattleState):
        raise TypeError("NPC Give Ground requires typed current round and spatial snapshots")
    if not isinstance(attack, NpcRosterAttackExecutionResult):
        raise TypeError("NPC Give Ground requires the full roster Attack result")
    execution = attack.execution
    if execution.request_id in current.state.consumed_give_ground_execution_ids:
        raise ValueError("NPC Give Ground execution was already consumed")
    if current.state != attack.state or current.round_state != execution.state:
        raise ValueError("NPC Give Ground requires exact post-Attack roster/history/round")
    movements = tuple(item for item in attack.pending_follow_ups if isinstance(item, GiveGroundRequest))
    if movements != (movement.source,):
        raise ValueError("movement does not match the sole Attack Give Ground follow-up")
    if current.pending_follow_ups.count(movement.source) != 1:
        raise ValueError("current queue requires exactly one matching Give Ground")
    pending = iter(current.pending_follow_ups)
    for item in attack.pending_follow_ups:
        if not any(queued == item for queued in pending):
            raise ValueError("current queue omits or reorders source Attack follow-ups")
    source = movement.source_request if isinstance(movement, GiveGroundResolutionResult) else movement
    if source is None:
        raise ValueError("NPC Give Ground requires the complete movement source request")
    if (movement.mover_id != execution.target_id or source.away_from_entity_id != execution.actor_id
            or source.mover_conditions != current.state.roster.participant(execution.target_id).state.injury.conditions):
        raise ValueError("Give Ground has a different target/attacker/source Conditions")
    if source.state != spatial_state:
        raise ValueError("Give Ground uses a stale spatial snapshot")
    if spatial_state.round_number != current.round_state.round_number:
        raise ValueError("Give Ground spatial and combat rounds differ")
    for participant in current.round_state.participants:
        if spatial_state.placement_for(participant.entity_id).side_id != participant.side.value:
            raise ValueError("Give Ground spatial sides differ from round participants")
    kernel = attack.source_request.execution.kernel_request
    if (not kernel.can_target_leave_zone or kernel.target_has_given_ground_this_round
            or execution.target_id in spatial_state.gave_ground_entity_ids):
        raise ValueError("Give Ground availability differs from Attack context")
    if isinstance(movement, GiveGroundResolutionResult) and "RULE-COMBAT-015:give-ground" not in movement.applied_rule_ids:
        raise ValueError("Give Ground movement trace is incomplete")


@dataclass(frozen=True, slots=True)
class NpcGiveGroundConsumptionResult:
    source_request: NpcGiveGroundConsumptionRequest

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcGiveGroundConsumptionRequest):
            raise TypeError("NPC Give Ground result requires its typed source request")

    @property
    def continuation(self) -> NpcRoundRequest:
        source = self.source_request
        current = source.current
        participants = tuple(
            replace(p, state=replace(p.state, injury=replace(p.state.injury, conditions=source.movement.conditions)))
            if p.state.actor_id == source.movement.mover_id else p
            for p in current.state.roster.participants
        )
        state = replace(current.state, roster=replace(current.state.roster, participants=participants),
                        consumed_give_ground_execution_ids=(
                            *current.state.consumed_give_ground_execution_ids, source.attack.execution.request_id,
                        ))
        index = current.pending_follow_ups.index(source.movement.source)
        return replace(current, state=state,
                       pending_follow_ups=current.pending_follow_ups[:index] + current.pending_follow_ups[index + 1:])

    @property
    def spatial_state(self) -> SpatialBattleState:
        return self.source_request.movement.state

    @property
    def applied_rule_ids(self) -> tuple[str, ...]:
        return self.source_request.movement.applied_rule_ids
