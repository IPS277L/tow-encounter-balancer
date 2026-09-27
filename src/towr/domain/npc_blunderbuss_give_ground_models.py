from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition, StaggerChoice, StaggerOutcome
from towr.domain.npc_blunderbuss_models import NpcBlunderbussAttackExecutionResult
from towr.domain.npc_nearby_completion_models import NpcNearbyCompletionResult
from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.reload_models import ReloadableWeaponState
from towr.domain.resolution_models import GiveGroundRequest, GiveGroundResolutionRequest, GiveGroundResolutionResult
from towr.domain.spatial_models import SpatialBattleState


@dataclass(frozen=True, slots=True)
class NpcBlunderbussGiveGroundExecutionRequest:
    id: str
    current: NpcRoundRequest
    spatial_state: SpatialBattleState
    attack: NpcBlunderbussAttackExecutionResult
    completion: NpcNearbyCompletionResult
    movement: GiveGroundResolutionRequest

    def __post_init__(self) -> None:
        if not isinstance(self.movement, GiveGroundResolutionRequest):
            raise TypeError("Blunderbuss Give Ground execution requires a pending movement request")
        validate_blunderbuss_give_ground_context(self)


@dataclass(frozen=True, slots=True)
class NpcBlunderbussGiveGroundConsumptionRequest:
    id: str
    current: NpcRoundRequest
    spatial_state: SpatialBattleState
    attack: NpcBlunderbussAttackExecutionResult
    completion: NpcNearbyCompletionResult
    movement: GiveGroundResolutionResult

    def __post_init__(self) -> None:
        if not isinstance(self.movement, GiveGroundResolutionResult):
            raise TypeError("Blunderbuss Give Ground consumption requires a completed movement result")
        validate_blunderbuss_give_ground_context(self)


def validate_blunderbuss_give_ground_context(
    request: NpcBlunderbussGiveGroundExecutionRequest | NpcBlunderbussGiveGroundConsumptionRequest,
) -> None:
    if not isinstance(request.id, str) or not request.id.strip():
        raise ValueError("Blunderbuss Give Ground requires an ID")
    current, spatial, attack, completion = request.current, request.spatial_state, request.attack, request.completion
    if not isinstance(current, NpcRoundRequest) or not isinstance(spatial, SpatialBattleState):
        raise TypeError("Blunderbuss Give Ground requires typed current round and spatial snapshots")
    if not isinstance(attack, NpcBlunderbussAttackExecutionResult) or not isinstance(completion, NpcNearbyCompletionResult):
        raise TypeError("Blunderbuss Give Ground requires full primary Attack and secondary completion results")
    primary = attack.primary_attack.attack
    if primary.request_id in current.state.consumed_give_ground_execution_ids:
        raise ValueError("Blunderbuss primary Give Ground was already consumed")
    batch_source = completion.source_request.chain.batch.source_request
    post_primary = attack.continuation
    if batch_source.primary_attack != attack.primary_attack or batch_source.state != post_primary.state:
        raise ValueError("secondary completion belongs to another primary Attack or post-primary roster/history")
    completed_round = completion.source_request.current
    if completed_round.id != post_primary.id or completed_round.actor_order != post_primary.actor_order:
        raise ValueError("secondary completion differs from the primary round request/order")
    if current != completion.continuation or spatial != completion.spatial_state:
        raise ValueError("Blunderbuss Give Ground requires exact post-completion round/roster/history/pending/spatial")
    movement = request.movement
    source = movement.source_request if isinstance(movement, GiveGroundResolutionResult) else movement
    if source is None:
        raise ValueError("Blunderbuss Give Ground requires the complete movement source request")
    movements = tuple(f for f in primary.resolution.follow_ups if isinstance(f, GiveGroundRequest))
    if movements != (source.source,):
        raise ValueError("movement does not match the sole primary Give Ground follow-up")
    if current.pending_follow_ups.count(source.source) != 1:
        raise ValueError("Blunderbuss queue requires exactly one matching primary Give Ground")
    kernel = attack.source_request.preparation.execution.attack.kernel_request
    stagger = primary.resolution.stagger
    target = current.state.roster.participant(primary.target_id).state.injury
    if (stagger is None or not stagger.gave_ground or stagger.wound_requested
            or stagger.selected_choice is not StaggerChoice.GIVE_GROUND
            or stagger.outcome is not StaggerOutcome.GAVE_GROUND
            or StaggerChoice.GIVE_GROUND not in stagger.allowed_choices
            or not kernel.target_state.conditions.has(Condition.STAGGERED)
            or primary.resolution.target_state != kernel.target_state or target != primary.resolution.target_state
            or stagger.state != target.conditions or primary.resolution.profile_wound is not None):
        raise ValueError("Blunderbuss primary Give Ground requires its completed Stagger choice")
    if (source.mover_id != primary.target_id or source.away_from_entity_id != primary.actor_id
            or source.mover_conditions != target.conditions):
        raise ValueError("Blunderbuss Give Ground has a different target/attacker/Conditions")
    if source.state != spatial:
        raise ValueError("Blunderbuss Give Ground uses a stale spatial snapshot")
    if spatial.round_number != current.round_state.round_number:
        raise ValueError("Blunderbuss Give Ground spatial and combat rounds differ")
    for participant in current.state.roster.participants:
        if spatial.placement_for(participant.state.actor_id).side_id != participant.turn_participant.side.value:
            raise ValueError("Blunderbuss Give Ground spatial sides differ from roster")
    if (not kernel.can_target_leave_zone or kernel.target_has_given_ground_this_round
            or primary.target_id in spatial.gave_ground_entity_ids):
        raise ValueError("Blunderbuss Give Ground availability differs from Attack context")
    if isinstance(movement, GiveGroundResolutionResult) and "RULE-COMBAT-015:give-ground" not in movement.applied_rule_ids:
        raise ValueError("Blunderbuss Give Ground movement trace is incomplete")


@dataclass(frozen=True, slots=True)
class NpcBlunderbussGiveGroundConsumptionResult:
    source_request: NpcBlunderbussGiveGroundConsumptionRequest

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcBlunderbussGiveGroundConsumptionRequest):
            raise TypeError("Blunderbuss Give Ground result requires its typed source request")

    @property
    def continuation(self) -> NpcRoundRequest:
        source = self.source_request
        current = source.current
        participants = tuple(
            replace(p, state=replace(p.state, injury=replace(p.state.injury, conditions=source.movement.conditions)))
            if p.state.actor_id == source.movement.mover_id else p for p in current.state.roster.participants
        )
        state = replace(current.state, roster=replace(current.state.roster, participants=participants),
                        consumed_give_ground_execution_ids=(
                            *current.state.consumed_give_ground_execution_ids, source.attack.primary_attack.attack.request_id,
                        ))
        index = current.pending_follow_ups.index(source.movement.source)
        return replace(current, state=state,
                       pending_follow_ups=current.pending_follow_ups[:index] + current.pending_follow_ups[index + 1:])

    @property
    def spatial_state(self) -> SpatialBattleState:
        return self.source_request.movement.state

    @property
    def weapon_state(self) -> ReloadableWeaponState:
        return self.source_request.attack.weapon_state

    @property
    def applied_rule_ids(self) -> tuple[str, ...]:
        return self.source_request.movement.applied_rule_ids
