from __future__ import annotations

from dataclasses import dataclass

from towr.domain.npc_nearby_defeat_models import NpcNearbyDefeatAcknowledgementResult
from towr.domain.npc_nearby_give_ground_models import NpcNearbyGiveGroundConsumptionResult
from towr.domain.npc_nearby_stagger_models import NpcNearbyStaggerExecutionResult
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.resolution_models import NearbyTargetStaggerResult
from towr.domain.spatial_models import SpatialBattleState


NpcNearbyConsequenceStep = NpcNearbyDefeatAcknowledgementResult | NpcNearbyGiveGroundConsumptionResult


@dataclass(frozen=True, slots=True)
class NpcNearbyConsequenceChain:
    """Explicit completed consequences of one batch; never executes rules or chooses order."""

    batch: NpcNearbyStaggerExecutionResult
    initial_spatial_state: SpatialBattleState
    steps: tuple[NpcNearbyConsequenceStep, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.batch, NpcNearbyStaggerExecutionResult):
            raise TypeError("nearby consequence chain requires a typed batch")
        if not isinstance(self.initial_spatial_state, SpatialBattleState):
            raise TypeError("nearby consequence chain requires a typed spatial snapshot")
        primary = self.batch.source_request.primary_attack
        if primary is None:
            raise ValueError("nearby consequence chain requires a full primary-bound batch")
        spatial, current = self.initial_spatial_state, self.batch.state
        if spatial.round_number != primary.attack.state.round_number:
            raise ValueError("nearby consequence chain spatial and primary rounds differ")
        for participant in current.roster.participants:
            if spatial.placement_for(participant.state.actor_id).side_id != participant.turn_participant.side.value:
                raise ValueError("nearby consequence chain spatial sides differ from roster")
        steps = tuple(self.steps)
        for index, step in enumerate(steps):
            if not isinstance(step, (NpcNearbyDefeatAcknowledgementResult, NpcNearbyGiveGroundConsumptionResult)):
                raise TypeError("nearby consequence chain requires typed completed steps")
            source = step.source_request
            if source.batch != self.batch or source.current != current:
                raise ValueError("nearby consequence step differs from current batch/roster/history")
            continuation = source.continuation
            if continuation is not None and (
                continuation.batch != self.batch or continuation.initial_spatial_state != self.initial_spatial_state
                or continuation.steps != steps[:index]
            ):
                raise ValueError("nearby consequence step continuation differs from the exact chain prefix")
            if isinstance(step, NpcNearbyGiveGroundConsumptionResult):
                if source.spatial_state != spatial:
                    raise ValueError("nearby consequence movement uses a stale spatial snapshot")
                if source.previous is not None and (index == 0 or source.previous != steps[index - 1]):
                    raise ValueError("nearby consequence previous movement differs from the chain prefix")
                spatial = step.spatial_state
            current = step.state
        object.__setattr__(self, "steps", steps)

    @property
    def state(self) -> NpcRosterAttackState:
        return self.steps[-1].state if self.steps else self.batch.state

    @property
    def spatial_state(self) -> SpatialBattleState:
        for step in reversed(self.steps):
            if isinstance(step, NpcNearbyGiveGroundConsumptionResult):
                return step.spatial_state
        return self.initial_spatial_state

    @property
    def pending_targets(self) -> tuple[NearbyTargetStaggerResult, ...]:
        return self.steps[-1].pending_targets if self.steps else self.batch.pending_targets

    @property
    def acknowledgements(self) -> tuple[NpcNearbyDefeatAcknowledgementResult, ...]:
        return tuple(step for step in self.steps if isinstance(step, NpcNearbyDefeatAcknowledgementResult))


def validate_nearby_consequence_context(
    continuation: NpcNearbyConsequenceChain, current: NpcRosterAttackState,
    batch: NpcNearbyStaggerExecutionResult, spatial_state: SpatialBattleState | None = None,
) -> None:
    if not isinstance(continuation, NpcNearbyConsequenceChain):
        raise TypeError("nearby consequence continuation must be a typed chain")
    if continuation.batch != batch or continuation.state != current:
        raise ValueError("nearby consequence continuation differs from current batch/roster/history")
    if spatial_state is not None and continuation.spatial_state != spatial_state:
        raise ValueError("nearby consequence continuation differs from current spatial snapshot")
