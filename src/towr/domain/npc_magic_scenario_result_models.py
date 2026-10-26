"""Validated finite M8 journal/result; no runner, reducer dispatch or RNG.

Terminal order is an experimental contract (ADR-0037), not a victory rule.
PG1.4 Combat p112, Broken p122, Magic pp156-157,162; GM1.1 pp91-92.
"""
from dataclasses import dataclass, field

from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundConditionEffect, WoundEffectDuration
from towr.domain.npc_magic_journal_policy import (
    magic_live_ids, magic_scene_key, magic_next_actor, magic_target,
    magic_movement_prefix, validate_magic_step_policy,
)
from towr.domain.npc_magic_scenario_models import NpcMagicScenario
from towr.domain.npc_magic_scene_models import _ordered, _identifier
from towr.domain.npc_magic_step_models import (
    NpcMagicStep, NpcMagicScenarioOutcome, NpcMagicPhase, NpcMagicUnsupported, NpcMagicUnsupportedReason,
)
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartResult
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndResult
from towr.domain.resolution_models import GiveGroundRequest, CowardlyFlightMovementCompletion


def _pending(state: NpcRosterCastingState) -> bool:
    return (state.pending_minion_attack is not None or state.pending_miscast is not None
            or state.pending_movement is not None or state.pending_interruption is not None
            or state.champion_attack is not None and state.champion_attack.pending is not None)


def npc_magic_terminal_outcome(scenario: NpcMagicScenario, state: NpcRosterCastingState) -> NpcMagicScenarioOutcome | None:
    if not isinstance(scenario, NpcMagicScenario) or not isinstance(state, NpcRosterCastingState):
        raise TypeError('terminal check requires typed scenario and full owner')
    if _pending(state) or state.round_state.active_turn is not None:
        return None
    live = magic_live_ids(state)
    if not any(i in live for i in scenario.objective.target_actor_ids):
        return NpcMagicScenarioOutcome.OBJECTIVE_ACHIEVED
    if not any(p.state.actor_id in live and p.state.side is scenario.perspective_side for p in state.roster.participants):
        return NpcMagicScenarioOutcome.PERSPECTIVE_DEFEATED
    if state.round_state.round_complete and state.round_state.round_number == scenario.max_rounds:
        return NpcMagicScenarioOutcome.ROUND_LIMIT_REACHED
    return None


def _injury_supported(state: NpcRosterCastingState, actor_id: str,
                      conditions: set[Condition], *, champion_attack: bool = False) -> bool:
    injury = state.roster.participant(actor_id).state.injury
    if not injury.conditions.conditions <= conditions:
        return False
    if actor_id != state.wizard.actor_id:
        return True
    if any(not w.effect_resolved for w in injury.wounds):
        return False
    if champion_attack:
        return not injury.active_wound_effects
    return all(isinstance(e, WoundConditionEffect) and e.condition in conditions - {Condition.BROKEN}
               and injury.conditions.has(e.condition) for e in injury.active_wound_effects)


def _bad_clock(state: NpcRosterCastingState) -> bool:
    wizard = state.roster.participant(state.wizard.actor_id)
    if wizard.state.injury.dead:
        return False
    timed = {e for e in wizard.state.injury.active_wound_effects if e.duration is WoundEffectDuration.END_OF_NEXT_TURN}
    if timed != {e.effect for e in state.wound_expiries}:
        return True
    for expiry in state.wound_expiries:
        source = expiry.source.source.state.round_state
        if expiry.actor_id in source.excluded_turn_entity_ids:
            return True
        deadline = expiry.deadline_round_number
        if deadline < state.round_state.round_number or (deadline == state.round_state.round_number
                and expiry.actor_id in state.round_state.completed_turn_entity_ids):
            return True
    return False


def diagnose_npc_magic_unsupported(
    scenario: NpcMagicScenario, state: NpcRosterCastingState, source_id: str,
    staged: tuple[CowardlyFlightMovementCompletion, ...] = (),
) -> NpcMagicUnsupported | None:
    """Recognize a concrete first-boundary stop; never catches constructor errors."""
    if not isinstance(scenario, NpcMagicScenario) or not isinstance(state, NpcRosterCastingState):
        raise TypeError('diagnosis requires typed scenario and full current owner')
    _identifier(source_id)
    staged = _ordered(staged, CowardlyFlightMovementCompletion, 'staged movements')
    phase = NpcMagicPhase.CONTINUATION
    reason = NpcMagicUnsupportedReason
    turn = state.round_state.active_turn
    actor_id = turn.actor_id if turn else None

    def stop(why, *, actors=(), zones=(), key=None, identifier=source_id, prefix=()):
        return NpcMagicUnsupported(phase, why, actor_id, identifier, actors, zones, key, prefix)

    if staged and state.pending_movement is None:
        raise ValueError('only Curse movement may retain a staged prefix')
    if state.pending_miscast is not None:
        return stop(reason.MISCAST_PREPARATION, identifier=state.pending_miscast.source.id)
    if state.pending_interruption is not None:
        return stop(reason.MISCAST_PREPARATION, identifier=state.pending_interruption.action.id)
    if state.champion_attack is not None and state.champion_attack.pending is not None:
        attack = state.champion_attack.pending
        return stop(reason.WOUND_EFFECT, actors=(attack.execution.target_id,), identifier=attack.execution.request_id)
    if state.pending_minion_attack is not None:
        attack = state.pending_minion_attack
        if any(isinstance(f, GiveGroundRequest) for f in attack.pending_follow_ups):
            return stop(reason.ATTACK_GIVE_GROUND, actors=(attack.execution.target_id,), identifier=attack.execution.request_id)
        # An ordinary single defeat is supported, so cannot be silently stopped.
        return None
    if state.pending_movement is not None:
        pending = state.pending_movement
        key = magic_movement_prefix(scenario, state, staged)
        remaining = pending.zone.movement_follow_ups[len(staged):]
        if not remaining:
            return None  # Willpower completion is required; no post-movement frame needed.
        frame = scenario.frame_for(key)
        mover = remaining[0].target_id
        if frame is None:
            return stop(reason.MISSING_SCENE, actors=(mover,), key=key, identifier=pending.source.id, prefix=staged)
        plan = next(p for p in frame.give_ground_plans if p.actor_id == mover)
        if plan.destination_zone_id is None or not plan.can_leave_zone:
            return stop(reason.MISSING_ROUTE, actors=(mover,), identifier=pending.source.id, prefix=staged)
        return None
    if turn is None:
        phase = NpcMagicPhase.SCHEDULING
        live = set(magic_live_ids(state))
        if (_bad_clock(state) or set(state.round_state.excluded_turn_entity_ids) & live
                or not state.round_state.round_complete and magic_next_actor(scenario, state) is None):
            return stop(reason.CHRONOLOGY)
        return None
    if turn.action_slots[0].executed:
        phase = NpcMagicPhase.END_TURN
        if (_bad_clock(state) or any(e.actor_id == actor_id and e.deadline_round_number != state.round_state.round_number
                                    for e in state.wound_expiries)):
            return stop(reason.CHRONOLOGY)
        conditions = {Condition.STAGGERED, Condition.DRAINED, Condition.BROKEN}
        if not _injury_supported(state, actor_id, conditions):
            return stop(reason.END_TURN, actors=(actor_id,))
        return None
    phase = NpcMagicPhase.ACTION
    injury = state.roster.participant(actor_id).state.injury
    broken = injury.conditions.has(Condition.BROKEN)
    conditions = ({Condition.BROKEN, Condition.STAGGERED, Condition.DRAINED} if broken else
                  {Condition.STAGGERED, Condition.DRAINED} if actor_id == state.wizard.actor_id else {Condition.STAGGERED})
    if not _injury_supported(state, actor_id, conditions):
        return stop(reason.ACTOR_INJURY, actors=(actor_id,))
    frame = scenario.frame_for(magic_scene_key(state))
    if frame is None:
        return stop(reason.MISSING_SCENE, key=magic_scene_key(state))
    if broken:
        if not any(p.actor_id == actor_id for p in frame.broken_plans):
            return stop(reason.BROKEN_ROUTE, actors=(actor_id,))
        return None
    target = magic_target(scenario, state, actor_id, frame)
    if target is None:
        return stop(reason.NO_LEGAL_TARGET)
    if actor_id == state.wizard.actor_id:
        enemies = tuple(i for i in magic_live_ids(state) if state.roster.participant(i).state.side
                        is not state.roster.participant(actor_id).state.side
                        and state.spatial_state.placement_for(i).zone_id == target)
        bad = tuple(i for i in enemies if not _injury_supported(state, i,
                    {Condition.STAGGERED, Condition.DRAINED, Condition.BROKEN}))
    else:
        bad = (() if _injury_supported(state, target,
               {Condition.STAGGERED} if target == state.wizard.actor_id else {Condition.STAGGERED, Condition.BROKEN},
               champion_attack=target == state.wizard.actor_id) else (target,))
    if bad:
        return stop(reason.TARGET_INJURY, actors=bad)
    if actor_id != state.wizard.actor_id and not any(d.actor_id == target for d in frame.attack_departures):
        return stop(reason.MISSING_ROUTE, actors=(target,))
    return None


@dataclass(frozen=True, slots=True)
class NpcMagicScenarioResult:
    source: NpcMagicScenario
    steps: tuple[NpcMagicStep, ...]
    unsupported: NpcMagicUnsupported | None = None
    _current: NpcRosterCastingState = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source, NpcMagicScenario):
            raise TypeError('magic journal requires its complete typed scenario')
        steps = _ordered(self.steps, NpcMagicStep, 'magic steps')
        object.__setattr__(self, 'steps', steps)
        if self.unsupported is not None and not isinstance(self.unsupported, NpcMagicUnsupported):
            raise TypeError('unsupported diagnosis must be typed')
        current = self.source.initial_runtime_state
        seen: set[str] = set()
        for step in steps:
            if npc_magic_terminal_outcome(self.source, current) is not None:
                raise ValueError('journal cannot continue after a terminal outcome')
            if step.before != current:
                raise ValueError('journal must form an exact continuous full-owner source chain')
            if not step.id.startswith(self.source.id + ':'):
                raise ValueError('journal IDs must use the scenario namespace')
            identifiers = ((step.id, step.id + ':start', step.id + ':slot')
                           if isinstance(step.result, NpcRosterTurnStartResult) else (step.id,))
            if seen.intersection(identifiers):
                raise ValueError('journal phase/action IDs must not repeat or collide')
            seen.update(identifiers)
            validate_magic_step_policy(self.source, step)
            current = step.after
            if current.round_state.round_number > self.source.max_rounds:
                raise ValueError('journal exceeds the global round budget')
        object.__setattr__(self, '_current', current)
        terminal = npc_magic_terminal_outcome(self.source, current)
        if terminal is not None:
            if self.unsupported is not None:
                raise ValueError('terminal journal cannot claim an unsupported stop')
        else:
            last_id = steps[-1].id if steps else self.source.id
            staged = self.unsupported.staged_movements if self.unsupported is not None else ()
            expected = diagnose_npc_magic_unsupported(self.source, current, last_id, staged)
            if self.unsupported is None or expected is None or self.unsupported != expected:
                raise ValueError('journal requires the exact currently unsupported phase/source/diagnosis')

    @property
    def current(self) -> NpcRosterCastingState:
        return self._current

    @property
    def outcome(self) -> NpcMagicScenarioOutcome:
        return npc_magic_terminal_outcome(self.source, self.current) or NpcMagicScenarioOutcome.UNSUPPORTED_PATH

    @property
    def started_rounds(self) -> int:
        return len({s.before.round_state.round_number for s in self.steps if isinstance(s.result, NpcRosterTurnStartResult)})

    @property
    def completed_rounds(self) -> int:
        return sum(isinstance(s.result, NpcWoundTurnEndResult) and s.after.round_state.round_complete for s in self.steps)

    @property
    def executed_actions(self) -> int:
        return len(self.current.consumed_execution_ids)
