from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.injury_models import ProfileNpcType, ProfileStateChangeRequest
from towr.domain.minion_defeat_models import MinionDefeatDecision
from towr.domain.npc_blunderbuss_models import NpcBlunderbussAttackExecutionResult
from towr.domain.npc_nearby_completion_models import NpcNearbyCompletionResult
from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.reload_models import ReloadableWeaponState
from towr.domain.spatial_models import SpatialBattleState


@dataclass(frozen=True, slots=True)
class NpcBlunderbussDefeatAcknowledgementRequest:
    id: str
    current: NpcRoundRequest
    spatial_state: SpatialBattleState
    attack: NpcBlunderbussAttackExecutionResult
    completion: NpcNearbyCompletionResult
    decision: MinionDefeatDecision

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Blunderbuss defeat acknowledgement requires an ID")
        if not isinstance(self.current, NpcRoundRequest) or not isinstance(self.spatial_state, SpatialBattleState):
            raise TypeError("Blunderbuss defeat requires typed current round and spatial snapshots")
        if (not isinstance(self.attack, NpcBlunderbussAttackExecutionResult)
                or not isinstance(self.completion, NpcNearbyCompletionResult)):
            raise TypeError("Blunderbuss defeat requires full primary Attack and secondary completion results")
        if not isinstance(self.decision, MinionDefeatDecision):
            raise TypeError("Blunderbuss defeat requires a typed decision")
        if not self.decision.gm_approved:
            raise ValueError("Blunderbuss defeat disposition requires GM approval")
        primary = self.attack.primary_attack.attack
        if primary.request_id in self.current.state.acknowledged_defeat_execution_ids:
            raise ValueError("Blunderbuss primary defeat was already acknowledged")
        if self.decision.attacker_id != primary.actor_id or self.decision.target_id != primary.target_id:
            raise ValueError("Blunderbuss defeat decision belongs to another attacker/primary target")
        batch_source = self.completion.source_request.chain.batch.source_request
        post_primary = self.attack.continuation
        if (batch_source.primary_attack != self.attack.primary_attack or batch_source.state != post_primary.state):
            raise ValueError("secondary completion belongs to another primary Attack or post-primary roster/history")
        completed_round = self.completion.source_request.current
        if completed_round.id != post_primary.id or completed_round.actor_order != post_primary.actor_order:
            raise ValueError("secondary completion differs from the primary round request/order")
        if self.current != self.completion.continuation or self.spatial_state != self.completion.spatial_state:
            raise ValueError("Blunderbuss defeat requires exact post-completion round/roster/history/pending/spatial")
        previous = self.attack.source_request.preparation.execution.attack.kernel_request.target_state
        target = primary.resolution.target_state
        changes = tuple(f for f in primary.resolution.follow_ups if isinstance(f, ProfileStateChangeRequest))
        expected = ProfileStateChangeRequest(ProfileNpcType.MINION, previous.wounds, target.wounds, True)
        wound = primary.resolution.profile_wound
        if (previous.defeated or not target.defeated or target.wounds != previous.wounds + 1
                or changes != (expected,) or wound is None or wound.state != target
                or wound.state_change != expected or wound.wounds_inflicted != 1
                or self.current.state.roster.participant(primary.target_id).state.injury != target):
            raise ValueError("Blunderbuss primary target requires a new Minion Wound and its defeat proof")
        if self.current.pending_follow_ups.count(expected) != 1:
            raise ValueError("Blunderbuss defeat queue requires exactly one matching primary defeat follow-up")

    @property
    def follow_up(self) -> ProfileStateChangeRequest:
        return next(f for f in self.attack.primary_attack.attack.resolution.follow_ups if isinstance(f, ProfileStateChangeRequest))


@dataclass(frozen=True, slots=True)
class NpcBlunderbussDefeatAcknowledgementResult:
    source_request: NpcBlunderbussDefeatAcknowledgementRequest

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcBlunderbussDefeatAcknowledgementRequest):
            raise TypeError("Blunderbuss defeat result requires its typed source request")

    @property
    def continuation(self) -> NpcRoundRequest:
        source = self.source_request
        current = source.current
        state = replace(current.state, acknowledged_defeat_execution_ids=(
            *current.state.acknowledged_defeat_execution_ids, source.attack.primary_attack.attack.request_id,
        ))
        index = current.pending_follow_ups.index(source.follow_up)
        return replace(current, state=state,
                       pending_follow_ups=current.pending_follow_ups[:index] + current.pending_follow_ups[index + 1:])

    @property
    def spatial_state(self) -> SpatialBattleState:
        return self.source_request.spatial_state

    @property
    def weapon_state(self) -> ReloadableWeaponState:
        return self.source_request.attack.weapon_state

    @property
    def applied_rule_ids(self) -> tuple[str, ...]:
        return ("RULE-NPC-002",)
