"""Full-source Minion attack handoff for ADR-0037.

PG1.4 Rules / Attack Tests pp118-119; Conditions pp122-123.
GM1.1 Allies and Antagonists / Minions p91. No defeat decision or movement.
"""
from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionRequest, NpcRosterAttackExecutionResult
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.turn_models import ActionSlotGrant, CombatActionDeclaration, CombatActionKind


@dataclass(frozen=True, slots=True)
class NpcRosterMinionAttackRequest:
    state: NpcRosterCastingState
    attack: NpcRosterAttackExecutionRequest

    def __post_init__(self) -> None:
        if not isinstance(self.state, NpcRosterCastingState) or not isinstance(self.attack, NpcRosterAttackExecutionRequest):
            raise TypeError('Minion handoff requires typed full state and M2 request')
        state = self.state
        if (state.pending_minion_attack is not None or state.pending_miscast is not None
                or state.pending_movement is not None or state.pending_interruption is not None
                or state.champion_attack is not None and state.champion_attack.pending is not None):
            raise ValueError('mandatory pending continuation blocks Minion attack')
        if state.minion_attack is None or self.attack.state != state.minion_attack:
            raise ValueError('Minion attack must match the complete bound owner')
        execution = self.attack.execution
        if execution.id in state.consumed_execution_ids:
            raise ValueError('action execution has already been consumed')
        if execution.state != state.round_state:
            raise ValueError('Minion attack must use the full current round')
        turn = state.round_state.active_turn
        if (turn is None or turn.actor_id != execution.actor_id or execution.slot_index != 1
                or len(turn.action_slots) != 1 or turn.action_slots[0].grant is not ActionSlotGrant.STANDARD
                or turn.action_slots[0].executed
                or turn.action_slots[0].declaration != CombatActionDeclaration(CombatActionKind.ATTACK)):
            raise ValueError('Minion handoff requires one unexecuted standard Attack slot for the active actor')
        actor = state.roster.participant(execution.actor_id)
        target = state.roster.participant(execution.target_id)
        if actor.state.side is target.state.side:
            raise ValueError('Minion handoff requires hostile actors')
        if (not actor.state.injury.conditions.conditions <= {Condition.STAGGERED}
                or not target.state.injury.conditions.conditions <= {Condition.STAGGERED, Condition.BROKEN}):
            raise ValueError('Minion handoff has unsupported actor/target Conditions')
        kernel = execution.kernel_request
        if kernel.target_has_given_ground_this_round != (execution.target_id in state.spatial_state.gave_ground_entity_ids):
            raise ValueError('Minion attack has stale Give Ground usage')
        origin = state.spatial_state.placement_for(execution.target_id).zone_id
        if kernel.can_target_leave_zone and not state.spatial_state.graph.adjacent_zone_ids(origin):
            raise ValueError('can_target_leave_zone requires an adjacent Zone')


@dataclass(frozen=True, slots=True)
class NpcRosterMinionAttackResult:
    source: NpcRosterMinionAttackRequest
    attack: NpcRosterAttackExecutionResult

    def __post_init__(self) -> None:
        if not isinstance(self.source, NpcRosterMinionAttackRequest) or not isinstance(self.attack, NpcRosterAttackExecutionResult):
            raise TypeError('Minion handoff result requires typed source and M2 result')
        if self.attack.source_request != self.source.attack:
            raise ValueError('Minion attack result differs from the complete bound source')

    @property
    def state(self) -> NpcRosterCastingState:
        old, updated, combat = self.source.state, self.attack.state, self.attack.execution.state
        champion = old.champion_attack
        if champion is not None:
            champion = replace(champion, roster=updated.roster, round_state=combat)
        return replace(old, roster=updated.roster, round_state=combat, champion_attack=champion,
                       minion_attack=updated,
                       consumed_execution_ids=(*old.consumed_execution_ids, self.attack.execution.request_id),
                       pending_minion_attack=self.attack if self.attack.pending_follow_ups else None)
