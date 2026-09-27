from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.injury_models import ProfileNpcType, ProfileStateChangeRequest
from towr.domain.minion_defeat_models import MinionDefeatDecision
from towr.domain.npc_nearby_stagger_models import NpcNearbyStaggerExecutionResult
from towr.domain.npc_roster_attack_models import NpcNearbyDefeatKey, NpcNearbyGiveGroundKey, NpcRosterAttackState
from towr.domain.resolution_models import NearbyTargetStaggerResult

if TYPE_CHECKING:
    from towr.domain.npc_nearby_consequence_models import NpcNearbyConsequenceChain


def _defeated_target_ids(batch: NpcNearbyStaggerExecutionResult) -> tuple[str, ...]:
    targets = []
    for source, result in zip(batch.source_request.resolution.targets, batch.resolution.targets):
        before, after = source.impact.target_state, result.impact.state
        expected = ProfileStateChangeRequest(ProfileNpcType.MINION, before.wounds, after.wounds, True)
        wound = result.impact.profile_wound
        if (not before.defeated and after.defeated and after.wounds == before.wounds + 1
                and result.impact.follow_ups == (expected,) and wound is not None
                and wound.state == after and wound.state_change == expected and wound.wounds_inflicted == 1):
            targets.append(result.target_id)
    return tuple(targets)


def validate_nearby_post_batch_state(current: NpcRosterAttackState, batch: NpcNearbyStaggerExecutionResult) -> None:
    """Only scoped defeat acknowledgements may extend the exact post-batch snapshot."""
    expected = batch.state
    history, prefix = current.acknowledged_nearby_defeats, expected.acknowledged_nearby_defeats
    if (history[:len(prefix)] != prefix
            or replace(current, acknowledged_nearby_defeats=prefix) != expected):
        raise ValueError("nearby consequence requires the exact post-batch roster/history")
    eligible = _defeated_target_ids(batch)
    if any(key.source != batch.source_request.resolution.source or key.target_id not in eligible
           for key in history[len(prefix):]):
        raise ValueError("nearby defeat history extension belongs to another batch/target")


@dataclass(frozen=True, slots=True)
class NpcNearbyDefeatAcknowledgementRequest:
    id: str
    current: NpcRosterAttackState
    batch: NpcNearbyStaggerExecutionResult
    decision: MinionDefeatDecision
    continuation: NpcNearbyConsequenceChain | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("nearby defeat acknowledgement requires an ID")
        if not isinstance(self.current, NpcRosterAttackState) or not isinstance(self.batch, NpcNearbyStaggerExecutionResult):
            raise TypeError("nearby defeat acknowledgement requires typed current state and batch")
        if not isinstance(self.decision, MinionDefeatDecision):
            raise TypeError("nearby defeat acknowledgement requires a typed decision")
        if not self.decision.gm_approved:
            raise ValueError("nearby defeat disposition requires GM approval")
        primary = self.batch.source_request.primary_attack
        if primary is None:
            raise ValueError("nearby defeat requires a batch bound to the full primary Attack")
        if self.decision.attacker_id != primary.attack.actor_id:
            raise ValueError("nearby defeat decision belongs to another attacker")
        if self.key in self.current.acknowledged_nearby_defeats:
            raise ValueError("nearby defeat was already acknowledged")
        eligible = _defeated_target_ids(self.batch)
        if self.decision.target_id not in eligible:
            raise ValueError("nearby defeat target must have a new Minion Wound and scoped defeat follow-up")
        if self.continuation is None:
            validate_nearby_post_batch_state(self.current, self.batch)
        else:
            from towr.domain.npc_nearby_consequence_models import validate_nearby_consequence_context

            validate_nearby_consequence_context(self.continuation, self.current, self.batch)

    @property
    def key(self) -> NpcNearbyDefeatKey:
        return NpcNearbyDefeatKey(self.batch.source_request.resolution.source, self.decision.target_id)


@dataclass(frozen=True, slots=True)
class NpcNearbyDefeatAcknowledgementResult:
    source_request: NpcNearbyDefeatAcknowledgementRequest

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcNearbyDefeatAcknowledgementRequest):
            raise TypeError("nearby defeat result requires its typed source request")

    @property
    def state(self) -> NpcRosterAttackState:
        source = self.source_request
        return replace(source.current, acknowledged_nearby_defeats=(
            *source.current.acknowledged_nearby_defeats, source.key,
        ))

    @property
    def pending_targets(self) -> tuple[NearbyTargetStaggerResult, ...]:
        source = self.source_request
        state = self.state
        return tuple(target for target in source.batch.pending_targets
                     if NpcNearbyDefeatKey(source.key.source, target.target_id) not in state.acknowledged_nearby_defeats
                     and NpcNearbyGiveGroundKey(source.key.source, target.target_id) not in state.consumed_nearby_give_ground)

    @property
    def applied_rule_ids(self) -> tuple[str, ...]:
        return ("RULE-NPC-002",)
