"""Source-bound handoff between the two narrow ADR-0036 action owners."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition

from towr.domain.npc_champion_attack_models import NpcChampionAttackRequest, NpcChampionAttackResult
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_wound_turn_models import NpcStomachBlowExpiry
from towr.domain.injury_models import WoundEntryId

if TYPE_CHECKING:
    from towr.domain.npc_crushed_rib_models import NpcCrushedRibContext


@dataclass(frozen=True, slots=True)
class NpcRosterChampionAttackRequest:
    """Bind magic/spatial and attack ownership before any Attack RNG."""

    state: NpcRosterCastingState
    attack: NpcChampionAttackRequest
    crushed_rib_context: NpcCrushedRibContext | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        if not isinstance(self.state, NpcRosterCastingState) or not isinstance(self.attack, NpcChampionAttackRequest):
            raise TypeError('handoff requires typed Casting state and Champion attack request')
        if self.state.pending_miscast_continuation is not None:
            raise ValueError('prepared Miscast blocks Champion attack dispatch')
        if self.state.pending_minion_attack is not None:
            raise ValueError('pending Minion attack blocks Champion attack dispatch')
        if self.state.pending_miscast is not None:
            raise ValueError('pending Miscast blocks Champion attack dispatch')
        if self.state.pending_interruption is not None:
            raise ValueError('pending interruption Miscast blocks Champion attack dispatch')
        if self.state.pending_movement is not None:
            raise ValueError('pending movement blocks Champion attack dispatch')
        if self.state.champion_attack is None or self.state.champion_attack != self.attack.state:
            raise ValueError('Champion attack must match the current bound owner')
        if self.attack.execution.id in self.state.consumed_execution_ids:
            raise ValueError('action execution has already been consumed')
        execution = self.attack.execution
        context = self.crushed_rib_context
        pending = self.attack.crushed_rib_preparation
        consumed = self.attack.crushed_rib_consumption
        if context is None:
            if pending is not None or consumed is not None:
                raise ValueError('lower Crushed Rib witnesses require their full-owner context')
        else:
            from towr.domain.npc_crushed_rib_models import NpcCrushedRibContext
            if not isinstance(context, NpcCrushedRibContext):
                raise TypeError('Champion handoff requires a typed Crushed Rib context')
            if self.attack.stationary_wounds is not None:
                raise ValueError('Crushed Rib and stationary contexts are mutually exclusive')
            context.validate_source(self.state, execution.target_id)
            replace(self.attack)
            if context.consumption is None:
                if pending is None or consumed is not None:
                    raise ValueError('pending Crushed Rib context requires its lower preparation')
                source = pending.source_request
                if source.actor_id != context.actor_id or source.state != context.injury:
                    raise ValueError('Protection preparation differs from full Crushed Rib source')
            elif pending is not None or consumed != context.consumption.consumption:
                raise ValueError('consumed Crushed Rib context requires its exact first receipt')
            if execution.kernel_request.target_has_given_ground_this_round is not (
                    execution.target_id in self.state.spatial_state.gave_ground_entity_ids):
                raise ValueError('Crushed Rib Protection has stale Give Ground usage')
            origin = self.state.spatial_state.placement_for(execution.target_id).zone_id
            if (execution.kernel_request.can_target_leave_zone
                    and not self.state.spatial_state.graph.adjacent_zone_ids(origin)):
                raise ValueError('can_target_leave_zone requires an adjacent Zone')
        if self.attack.stationary_wounds is not None:
            self.attack.stationary_wounds.validate_source(self.state, execution.target_id)
        if any(self.state.roster.participant(i).state.injury.conditions.has(Condition.PRONE)
               for i in (execution.actor_id, execution.target_id)):
            from towr.domain.npc_roster_turn_models import _validate_phase_source
            _validate_phase_source(self.state)
            if execution.kernel_request.target_has_given_ground_this_round != (
                    execution.target_id in self.state.spatial_state.gave_ground_entity_ids):
                raise ValueError('Prone Champion handoff has stale Give Ground usage')
            origin = self.state.spatial_state.placement_for(execution.target_id).zone_id
            if (execution.kernel_request.can_target_leave_zone
                    and not self.state.spatial_state.graph.adjacent_zone_ids(origin)):
                raise ValueError('can_target_leave_zone requires an adjacent Zone')


@dataclass(frozen=True, slots=True)
class NpcRosterChampionAttackResult:
    source: NpcRosterChampionAttackRequest
    attack: NpcChampionAttackResult

    def __post_init__(self) -> None:
        if not isinstance(self.source, NpcRosterChampionAttackRequest) or not isinstance(self.attack, NpcChampionAttackResult):
            raise TypeError('handoff requires typed source and Champion attack result')
        if self.attack.source != self.source.attack:
            raise ValueError('Champion attack result differs from the bound source')
        if (self.source.crushed_rib_context is not None
                or self.source.attack.crushed_rib_preparation is not None
                or self.source.attack.crushed_rib_consumption is not None
                or self.attack.crushed_rib is not None):
            replace(self.source)
            replace(self.attack)

    @property
    def state(self) -> NpcRosterCastingState:
        previous, updated = self.source.state, self.attack.state
        expiries = previous.wound_expiries
        completion = self.attack.completion
        if (completion is not None and completion.wound_effect is not None
                and completion.wound_effect.request.entry_id is WoundEntryId.STOMACH_BLOW):
            expiries = (*expiries, NpcStomachBlowExpiry(self.attack))
        return replace(previous, roster=updated.roster, round_state=updated.round_state,
                       minion_attack=(None if previous.minion_attack is None else
                                      replace(previous.minion_attack, roster=updated.roster)),
                       champion_attack=updated, consumed_execution_ids=(
                           *previous.consumed_execution_ids, self.attack.execution.request_id),
                       wound_expiries=expiries)
