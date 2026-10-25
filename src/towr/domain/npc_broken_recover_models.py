"""One supported Broken transition: optional free move, then self Recover.

PG1.4 Rules / Combat Actions pp116-118, Broken p122;
Magic in the Old World / Interrupted Casting p156. ADR-0036.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.action_execution_models import SkippedCastingTestAfterActionResult
from towr.domain.condition_models import Condition
from towr.domain.injury_models import CharacterInjuryState, WoundConditionEffect
from towr.domain.npc_action_interruption import validate_npc_casting_interruption
from towr.domain.movement_models import FreeMovementRequest, FreeMovementResult
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.recover_models import (
    RecoverActionExecutionRequest, RecoverActionExecutionResult, RecoverConditionRemovalChoice,
    RecoverConditionTarget, RecoverMode,
)
from towr.domain.test_models import InlineProfile, RollTrace, Skill, TestQuality, TestRequest
from towr.domain.turn_models import ActionSlotGrant, CombatActionDeclaration, CombatActionKind


@dataclass(frozen=True, slots=True)
class NpcBrokenRecoverRequest:
    id: str
    state: NpcRosterCastingState
    actor_id: str
    willpower_profile: InlineProfile
    movement: FreeMovementRequest | None
    fastest_route_confirmed: bool
    underlying_cause_allows_removal: bool

    def __post_init__(self) -> None:
        for name in ('id', 'actor_id'):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise TypeError(f'{name} must be a string')
            if not value.strip():
                raise ValueError(f'{name} must not be blank')
        if not isinstance(self.state, NpcRosterCastingState):
            raise TypeError('state must be an NpcRosterCastingState')
        if not isinstance(self.willpower_profile, InlineProfile):
            raise TypeError('Broken recovery requires an InlineProfile')
        if self.willpower_profile.pool_cap is not None:
            raise ValueError('Broken recovery excludes custom pool caps')
        for name in ('fastest_route_confirmed', 'underlying_cause_allows_removal'):
            value = getattr(self, name)
            if not isinstance(value, bool):
                raise TypeError(f'{name} must be an explicit boolean')
            if not value:
                raise ValueError(f'{name} is required by this Broken recovery boundary')
        state = self.state
        if (state.pending_miscast is not None or state.pending_movement is not None
                or state.pending_interruption is not None
                or state.champion_attack is not None and state.champion_attack.pending is not None):
            raise ValueError('mandatory pending continuation blocks Broken recovery')
        if self.id in state.consumed_execution_ids:
            raise ValueError('Broken recovery action was already consumed')
        actor = state.roster.participant(self.actor_id)
        injury = actor.state.injury
        dead = injury.dead if isinstance(injury, CharacterInjuryState) else injury.defeated
        supported = {Condition.BROKEN, Condition.STAGGERED, Condition.DRAINED}
        if dead or not injury.conditions.has(Condition.BROKEN) or not injury.conditions.conditions <= supported:
            raise ValueError('Broken recovery requires a living Broken actor with supported Conditions')
        if isinstance(injury, CharacterInjuryState) and (
            any(not w.effect_resolved for w in injury.wounds) or any(
                not isinstance(e, WoundConditionEffect) or e.condition not in supported - {Condition.BROKEN}
                or not injury.conditions.has(e.condition) for e in injury.active_wound_effects)):
            raise ValueError('Broken recovery excludes unresolved or unsupported Wound effects')
        turn = state.round_state.active_turn
        if turn is None or turn.actor_id != self.actor_id or len(turn.action_slots) != 1:
            raise ValueError('Broken recovery requires the active actor and one reserved slot')
        slot = turn.action_slots[0]
        if (slot.executed or slot.grant is not ActionSlotGrant.STANDARD
                or slot.declaration != CombatActionDeclaration(CombatActionKind.RECOVER)):
            raise ValueError('Broken recovery requires an unexecuted standard Recover slot')
        origin = state.spatial_state.placement_for(self.actor_id).zone_id
        unsafe = _has_enemy(state, self.actor_id, origin)
        movement = self.movement
        if movement is None:
            if unsafe:
                raise ValueError('Broken actor must reach a safe Zone before Recover')
        else:
            if not isinstance(movement, FreeMovementRequest):
                raise TypeError('movement must be a FreeMovementRequest or None')
            if not unsafe:
                raise ValueError('already safe Broken actor must Recover without further movement here')
            if (movement.round_state != state.round_state or movement.state != state.spatial_state
                    or movement.actor_id != self.actor_id or movement.actor_conditions != injury.conditions
                    or movement.rule_id != 'RULE-COMBAT-014:free-movement'
                    or movement.id != self.id + ':free-move'):
                raise ValueError('Broken free movement differs from the complete current source')
            if (self.actor_id in state.spatial_state.free_move_used_entity_ids
                    or movement.crosses_obstacle or movement.crosses_difficult_terrain):
                raise ValueError('Broken route needs unavailable free movement or unsupported terrain')
            previous = origin
            for zone in movement.traversed_zone_ids:
                if not state.spatial_state.graph.are_adjacent(previous, zone):
                    raise ValueError('Broken free movement must follow adjacent Zones')
                previous = zone
            if (_has_enemy(state, self.actor_id, movement.destination_zone_id)
                    or any(not _has_enemy(state, self.actor_id, zone)
                           for zone in movement.traversed_zone_ids[:-1])):
                raise ValueError('Broken route must stop at its first safe Zone')
            for identifier in movement.path_entity_ids:
                crossed = state.roster.participant(identifier)
                if crossed.state.side is not actor.state.side:
                    raise ValueError('Broken free movement cannot cross an enemy')

    @property
    def recover_request(self) -> RecoverActionExecutionRequest:
        conditions = self.state.roster.participant(self.actor_id).state.injury.conditions
        return RecoverActionExecutionRequest(
            self.id, self.state.round_state, self.actor_id, conditions, False, 1,
            RecoverMode.REMOVE_CONDITION, RecoverConditionRemovalChoice(
                RecoverConditionTarget(self.actor_id, conditions, None), Condition.BROKEN,
                TestRequest(self.id + ':willpower', self.willpower_profile), Skill.WILLPOWER,
                self.underlying_cause_allows_removal,
            ),
        )


@dataclass(frozen=True, slots=True)
class NpcBrokenRecoverResult:
    source: NpcBrokenRecoverRequest
    movement: FreeMovementResult | None
    recover: RecoverActionExecutionResult
    interruption: SkippedCastingTestAfterActionResult | None

    def __post_init__(self) -> None:
        if not isinstance(self.source, NpcBrokenRecoverRequest):
            raise TypeError('source must be an NpcBrokenRecoverRequest')
        if not isinstance(self.recover, RecoverActionExecutionResult):
            raise TypeError('recover must be a RecoverActionExecutionResult')
        source = self.source
        if self.recover.source_request != source.recover_request:
            raise ValueError('Recover result differs from the complete Broken request')
        movement = source.movement
        if movement is None:
            if self.movement is not None:
                raise ValueError('already safe recovery cannot contain movement')
        else:
            if not isinstance(self.movement, FreeMovementResult):
                raise TypeError('Broken route requires a completed FreeMovementResult')
            actual = self.movement
            if (actual.request_id != movement.id or actual.rule_id != movement.rule_id
                    or actual.round_state != movement.round_state or actual.previous_state != movement.state
                    or actual.actor_id != movement.actor_id or actual.speed != movement.speed
                    or actual.traversed_zone_ids != movement.traversed_zone_ids
                    or actual.applied_rule_ids != (movement.rule_id, 'RULE-COMBAT-012:speed',
                                                  'RULE-COMBAT-011:zones-and-ranges')):
                raise ValueError('completed movement differs from the Broken route/source')
        test = self.recover.resolution.test_result
        profile = source.willpower_profile
        values = test.trace.initial_values
        if (not isinstance(values, tuple) or len(values) != profile.dice
                or any(type(v) is not int or not 1 <= v <= 10 for v in values)):
            raise ValueError('Broken recovery requires the exact normal d10 pool')
        successes = sum(v <= profile.threshold for v in values)
        if test.trace != RollTrace(
            source.id + ':willpower', profile.dice, profile.maximum_dice, 0, 0, profile.dice, profile.dice,
            profile.threshold, False, TestQuality.NORMAL, values, (), values, successes, 0, successes, (),
        ):
            raise ValueError('Broken recovery Test trace differs from its normal profile')
        validate_npc_casting_interruption(source.state, source.actor_id, source.id,
                                          self.recover.slot.execution, self.interruption)

    @property
    def state(self) -> NpcRosterCastingState:
        source, old = self.source, self.source.state
        conditions = self.recover.resolution.conditions
        roster = NpcRoster(tuple(replace(p, state=replace(p.state, injury=replace(
            p.state.injury, conditions=conditions))) if p.state.actor_id == source.actor_id else p
            for p in old.roster.participants))
        champion = old.champion_attack
        if champion is not None:
            champion = replace(champion, roster=roster, round_state=self.recover.round_state)
        wizard = old.wizard if self.interruption is None else replace(old.wizard, magic_state=self.interruption.state)
        pending = (self.interruption if self.interruption is not None
                   and self.interruption.miscast_pool.roll_request is not None else None)
        return replace(old, roster=roster, wizard=wizard, champion_attack=champion,
                       round_state=self.recover.round_state,
                       spatial_state=old.spatial_state if self.movement is None else self.movement.state,
                       consumed_execution_ids=(*old.consumed_execution_ids, source.id),
                       pending_interruption=pending)


def _has_enemy(state: NpcRosterCastingState, actor_id: str, zone: str) -> bool:
    actor = state.roster.participant(actor_id)
    for participant in state.roster.participants:
        injury = participant.state.injury
        dead = injury.dead if isinstance(injury, CharacterInjuryState) else injury.defeated
        if (not dead and participant.state.side is not actor.state.side
                and state.spatial_state.placement_for(participant.state.actor_id).zone_id == zone):
            return True
    return False
