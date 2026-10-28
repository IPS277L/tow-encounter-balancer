"""Full free move plus one necessary Broken Run (ADR-0036).

PG1.4 Rules / Speed / Combat Actions pp115-118, Broken p122;
Magic in the Old World / Interrupted Casting pp156-157.
No Athletics extension, automatic route choice, Recover or end-turn.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.action_execution_models import SkippedCastingTestAfterActionResult
from towr.domain.condition_models import Condition
from towr.domain.injury_models import CharacterInjuryState, WoundConditionEffect
from towr.domain.movement_models import (
    FreeMovementRequest, FreeMovementResult, MovementSpeed,
    RunActionExecutionRequest, RunActionExecutionResult,
)
from towr.domain.npc_action_interruption import validate_npc_casting_interruption
from towr.domain.npc_broken_recover_models import _has_enemy
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, ManoeuvreKind,
)


@dataclass(frozen=True, slots=True)
class NpcBrokenRunRequest:
    id: str
    state: NpcRosterCastingState
    actor_id: str
    movement: FreeMovementRequest
    run_destination_zone_id: str
    run_path_entity_ids: tuple[str, ...]
    run_crosses_obstacle: bool
    run_crosses_difficult_terrain: bool
    fastest_route_confirmed: bool

    def __post_init__(self) -> None:
        for name in ('id', 'actor_id', 'run_destination_zone_id'):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise TypeError(f'{name} must be a string')
            if not value.strip():
                raise ValueError(f'{name} must not be blank')
        if not isinstance(self.state, NpcRosterCastingState):
            raise TypeError('state must be an NpcRosterCastingState')
        if not isinstance(self.movement, FreeMovementRequest):
            raise TypeError('movement must be a FreeMovementRequest')
        for name in ('run_crosses_obstacle', 'run_crosses_difficult_terrain', 'fastest_route_confirmed'):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f'{name} must be an explicit boolean')
        if not self.fastest_route_confirmed:
            raise ValueError('fastest route confirmation is required for Broken Run')
        if self.run_crosses_obstacle or self.run_crosses_difficult_terrain:
            raise ValueError('Broken Run does not support obstacle/terrain traversal')
        if not isinstance(self.run_path_entity_ids, (tuple, list)):
            raise TypeError('Run path must be an ordered tuple or list')
        path = tuple(self.run_path_entity_ids)
        if any(not isinstance(i, str) or not i.strip() for i in path):
            raise ValueError('Run path IDs must be nonblank strings')
        if len(set(path)) != len(path) or self.actor_id in path:
            raise ValueError('Run path cannot repeat entities or cross the actor')
        object.__setattr__(self, 'run_path_entity_ids', path)

        state, movement = self.state, self.movement
        if state.pending_miscast_continuation is not None:
            raise ValueError('prepared Miscast blocks Broken Run')
        if state.pending_minion_attack is not None:
            raise ValueError('pending Minion attack blocks Broken Run')
        if (state.pending_miscast is not None or state.pending_movement is not None
                or state.pending_interruption is not None
                or state.champion_attack is not None and state.champion_attack.pending is not None):
            raise ValueError('mandatory pending continuation blocks Broken Run')
        if self.id in state.consumed_execution_ids:
            raise ValueError('Broken Run action was already consumed')
        actor = state.roster.participant(self.actor_id)
        injury = actor.state.injury
        dead = injury.dead if isinstance(injury, CharacterInjuryState) else injury.defeated
        supported = {Condition.BROKEN, Condition.STAGGERED, Condition.DRAINED}
        if dead or not injury.conditions.has(Condition.BROKEN) or not injury.conditions.conditions <= supported:
            raise ValueError('Broken Run requires a living Broken actor with supported Conditions')
        if isinstance(injury, CharacterInjuryState) and (
            any(not w.effect_resolved for w in injury.wounds) or any(
                not isinstance(e, WoundConditionEffect) or e.condition not in supported - {Condition.BROKEN}
                or not injury.conditions.has(e.condition) for e in injury.active_wound_effects)):
            raise ValueError('Broken Run excludes unresolved or unsupported Wound effects')
        turn = state.round_state.active_turn
        if turn is None or turn.actor_id != self.actor_id or len(turn.action_slots) != 1:
            raise ValueError('Broken Run requires the active actor and one reserved slot')
        slot = turn.action_slots[0]
        declaration = CombatActionDeclaration(CombatActionKind.MANOEUVRE, manoeuvre=ManoeuvreKind.RUN)
        if slot.executed or slot.grant is not ActionSlotGrant.STANDARD or slot.declaration != declaration:
            raise ValueError('Broken Run requires an unexecuted standard Run slot')
        if (movement.id != self.id + ':free-move' or movement.actor_id != self.actor_id
                or movement.round_state != state.round_state or movement.state != state.spatial_state
                or movement.actor_conditions != injury.conditions
                or movement.rule_id != 'RULE-COMBAT-014:free-movement'):
            raise ValueError('Broken Run free movement differs from the complete current source')
        if (movement.speed is MovementSpeed.SLOW
                or len(movement.traversed_zone_ids) != movement.speed.free_move_zone_limit):
            raise ValueError('Broken Run requires the full Normal/Fast free movement allowance')
        if (self.actor_id in state.spatial_state.free_move_used_entity_ids
                or movement.crosses_obstacle or movement.crosses_difficult_terrain):
            raise ValueError('Broken Run needs available free movement without obstacle/terrain')
        origin = state.spatial_state.placement_for(self.actor_id).zone_id
        if not _has_enemy(state, self.actor_id, origin):
            raise ValueError('already safe Broken actor does not need this Run')
        previous = origin
        for zone in movement.traversed_zone_ids:
            if not state.spatial_state.graph.are_adjacent(previous, zone):
                raise ValueError('Broken Run free route must follow adjacent Zones')
            if not _has_enemy(state, self.actor_id, zone):
                raise ValueError('free movement already reaches a safe Zone; Run is unnecessary')
            previous = zone
        if not state.spatial_state.graph.are_adjacent(previous, self.run_destination_zone_id):
            raise ValueError('Broken Run must cross exactly one extra adjacent Zone')
        if _has_enemy(state, self.actor_id, self.run_destination_zone_id):
            raise ValueError('Broken Run destination must be a safe Zone')
        for identifier in (*movement.path_entity_ids, *path):
            if state.roster.participant(identifier).state.side is not actor.state.side:
                raise ValueError('Broken Run route cannot cross an enemy')

    @property
    def run_request(self) -> RunActionExecutionRequest:
        old = self.state.spatial_state
        # Pure source projection, not an execution of the free-move resolver.
        spatial = replace(old, placements=tuple(
            replace(p, zone_id=self.movement.destination_zone_id) if p.entity_id == self.actor_id else p
            for p in old.placements), free_move_used_entity_ids=(*old.free_move_used_entity_ids, self.actor_id))
        return RunActionExecutionRequest(self.id, self.state.round_state, spatial, self.actor_id, 1,
            self.movement.speed, self.movement.actor_conditions, self.run_destination_zone_id,
            self.run_path_entity_ids, self.run_crosses_obstacle, self.run_crosses_difficult_terrain)


@dataclass(frozen=True, slots=True)
class NpcBrokenRunResult:
    source: NpcBrokenRunRequest
    movement: FreeMovementResult
    run: RunActionExecutionResult
    interruption: SkippedCastingTestAfterActionResult | None

    def __post_init__(self) -> None:
        if not isinstance(self.source, NpcBrokenRunRequest):
            raise TypeError('source must be an NpcBrokenRunRequest')
        if not isinstance(self.movement, FreeMovementResult) or not isinstance(self.run, RunActionExecutionResult):
            raise TypeError('Broken Run requires typed completed movement and Run results')
        source, actual, run = self.source, self.movement, self.run
        move = source.movement
        expected = source.run_request
        if (actual.request_id != move.id or actual.rule_id != move.rule_id
                or actual.round_state != move.round_state or actual.previous_state != move.state
                or actual.actor_id != move.actor_id or actual.speed != move.speed
                or actual.traversed_zone_ids != move.traversed_zone_ids or actual.state != expected.spatial_state
                or actual.applied_rule_ids != (move.rule_id, 'RULE-COMBAT-012:speed',
                                              'RULE-COMBAT-011:zones-and-ranges')):
            raise ValueError('completed free movement differs from the Broken Run source')
        if (run.request_id != source.id or run.actor_id != source.actor_id or run.slot_index != 1
                or run.speed != expected.speed or run.previous_round_state != expected.round_state
                or run.previous_spatial_state != actual.state or run.destination_zone_id != expected.destination_zone_id
                or run.applied_rule_ids != ('RULE-COMBAT-014:run-action-execution', 'RULE-COMBAT-012:speed',
                                           'RULE-COMBAT-011:zones-and-ranges')
                or run.slot.execution.actor_id != source.actor_id
                or run.slot.execution.round_number != expected.round_state.round_number
                or run.slot.execution.executor_rule_id != 'RULE-COMBAT-014:run-action-execution'):
            raise ValueError('completed Run differs from the bound action/source/receipt')
        validate_npc_casting_interruption(source.state, source.actor_id, source.id,
                                          run.slot.execution, self.interruption)

    @property
    def state(self) -> NpcRosterCastingState:
        source, old = self.source, self.source.state
        champion = old.champion_attack
        if champion is not None:
            champion = replace(champion, round_state=self.run.round_state)
        wizard = old.wizard if self.interruption is None else replace(old.wizard, magic_state=self.interruption.state)
        pending = (self.interruption if self.interruption is not None
                   and self.interruption.miscast_pool.roll_request is not None else None)
        return replace(old, wizard=wizard, champion_attack=champion,
                       round_state=self.run.round_state, spatial_state=self.run.spatial_state,
                       consumed_execution_ids=(*old.consumed_execution_ids, source.id),
                       pending_interruption=pending)
