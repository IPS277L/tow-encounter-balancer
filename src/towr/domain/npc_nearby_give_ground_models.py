from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition, StaggerChoice, StaggerOutcome
from towr.domain.npc_nearby_defeat_models import validate_nearby_post_batch_state
from towr.domain.npc_nearby_stagger_models import NpcNearbyStaggerExecutionResult
from towr.domain.npc_roster_attack_models import NpcNearbyDefeatKey, NpcNearbyGiveGroundKey, NpcRosterAttackState
from towr.domain.resolution_models import (
    GiveGroundRequest, GiveGroundResolutionRequest, GiveGroundResolutionResult, NearbyTargetStaggerResult,
)
from towr.domain.spatial_models import SpatialBattleState


@dataclass(frozen=True, slots=True)
class NpcNearbyGiveGroundExecutionRequest:
    id: str
    current: NpcRosterAttackState
    spatial_state: SpatialBattleState
    batch: NpcNearbyStaggerExecutionResult
    target_id: str
    movement: GiveGroundResolutionRequest
    previous: NpcNearbyGiveGroundConsumptionResult | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.movement, GiveGroundResolutionRequest):
            raise TypeError("nearby Give Ground execution requires a pending movement request")
        validate_nearby_give_ground_context(self)

    @property
    def key(self) -> NpcNearbyGiveGroundKey:
        return NpcNearbyGiveGroundKey(self.batch.source_request.resolution.source, self.target_id)


@dataclass(frozen=True, slots=True)
class NpcNearbyGiveGroundConsumptionRequest:
    id: str
    current: NpcRosterAttackState
    spatial_state: SpatialBattleState
    batch: NpcNearbyStaggerExecutionResult
    target_id: str
    movement: GiveGroundResolutionResult
    previous: NpcNearbyGiveGroundConsumptionResult | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.movement, GiveGroundResolutionResult):
            raise TypeError("nearby Give Ground consumption requires a completed movement result")
        validate_nearby_give_ground_context(self)

    @property
    def key(self) -> NpcNearbyGiveGroundKey:
        return NpcNearbyGiveGroundKey(self.batch.source_request.resolution.source, self.target_id)


def validate_nearby_give_ground_context(
    request: NpcNearbyGiveGroundExecutionRequest | NpcNearbyGiveGroundConsumptionRequest,
) -> None:
    if not isinstance(request.id, str) or not request.id.strip():
        raise ValueError("nearby Give Ground requires an ID")
    current, spatial, batch = request.current, request.spatial_state, request.batch
    if not isinstance(current, NpcRosterAttackState) or not isinstance(spatial, SpatialBattleState):
        raise TypeError("nearby Give Ground requires typed current roster and spatial snapshots")
    if not isinstance(batch, NpcNearbyStaggerExecutionResult):
        raise TypeError("nearby Give Ground requires a full secondary batch result")
    if request.key in current.consumed_nearby_give_ground:
        raise ValueError("nearby Give Ground was already consumed")
    primary = batch.source_request.primary_attack
    if primary is None:
        raise ValueError("nearby Give Ground requires a batch bound to the full primary Attack")
    if request.previous is None:
        validate_nearby_post_batch_state(current, batch)
    else:
        previous = request.previous
        if not isinstance(previous, NpcNearbyGiveGroundConsumptionResult):
            raise TypeError("previous nearby Give Ground must be a completed consumption result")
        if (previous.source_request.batch != batch or previous.state != current
                or previous.spatial_state != spatial):
            raise ValueError("previous nearby Give Ground differs from current batch/roster/history/spatial")
    pairs = tuple((source.impact, target.impact) for source, target in zip(
        batch.source_request.resolution.targets, batch.resolution.targets,
    ) if target.target_id == request.target_id)
    if len(pairs) != 1:
        raise ValueError("nearby Give Ground target is not a secondary target of this batch")
    impact_source, impact = pairs[0]
    stagger = impact.stagger
    if (impact.follow_ups != (GiveGroundRequest(impact_source.id),)
            or not stagger.gave_ground or stagger.wound_requested
            or stagger.selected_choice is not StaggerChoice.GIVE_GROUND
            or stagger.outcome is not StaggerOutcome.GAVE_GROUND
            or StaggerChoice.GIVE_GROUND not in stagger.allowed_choices
            or impact.state != impact_source.target_state or stagger.state != impact.state.conditions
            or not impact_source.target_state.conditions.has(Condition.STAGGERED)
            or impact.profile_wound is not None):
        raise ValueError("nearby Give Ground requires its scoped completed Stagger choice")
    movement = request.movement
    source = movement.source_request if isinstance(movement, GiveGroundResolutionResult) else movement
    if source is None:
        raise ValueError("nearby Give Ground requires the complete movement source request")
    if (source.source != impact.follow_ups[0] or source.mover_id != request.target_id
            or source.away_from_entity_id != primary.attack.actor_id
            or source.mover_conditions != current.roster.participant(request.target_id).state.injury.conditions):
        raise ValueError("nearby Give Ground has a different target/attacker/source/Conditions")
    if source.state != spatial:
        raise ValueError("nearby Give Ground uses a stale spatial snapshot")
    if spatial.round_number != primary.attack.state.round_number:
        raise ValueError("nearby Give Ground spatial and primary combat rounds differ")
    for participant in current.roster.participants:
        if spatial.placement_for(participant.state.actor_id).side_id != participant.turn_participant.side.value:
            raise ValueError("nearby Give Ground spatial sides differ from roster")
    if (not impact_source.can_target_leave_zone or impact_source.target_has_given_ground_this_round
            or request.target_id in spatial.gave_ground_entity_ids):
        raise ValueError("nearby Give Ground availability differs from secondary context")
    if isinstance(movement, GiveGroundResolutionResult) and "RULE-COMBAT-015:give-ground" not in movement.applied_rule_ids:
        raise ValueError("nearby Give Ground movement trace is incomplete")


@dataclass(frozen=True, slots=True)
class NpcNearbyGiveGroundConsumptionResult:
    source_request: NpcNearbyGiveGroundConsumptionRequest

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcNearbyGiveGroundConsumptionRequest):
            raise TypeError("nearby Give Ground result requires its typed source request")

    @property
    def state(self) -> NpcRosterAttackState:
        source = self.source_request
        participants = tuple(
            replace(p, state=replace(p.state, injury=replace(p.state.injury, conditions=source.movement.conditions)))
            if p.state.actor_id == source.target_id else p for p in source.current.roster.participants
        )
        return replace(source.current, roster=replace(source.current.roster, participants=participants),
                       consumed_nearby_give_ground=(*source.current.consumed_nearby_give_ground, source.key))

    @property
    def spatial_state(self) -> SpatialBattleState:
        return self.source_request.movement.state

    @property
    def pending_targets(self) -> tuple[NearbyTargetStaggerResult, ...]:
        source, state = self.source_request, self.state
        effect = source.key.source
        return tuple(target for target in source.batch.pending_targets
                     if NpcNearbyDefeatKey(effect, target.target_id) not in state.acknowledged_nearby_defeats
                     and NpcNearbyGiveGroundKey(effect, target.target_id) not in state.consumed_nearby_give_ground)

    @property
    def applied_rule_ids(self) -> tuple[str, ...]:
        return self.source_request.movement.applied_rule_ids
