"""Full-owner self-stand and scoped end-turn, without automatic policy.

PG1.4 Rules / Free Actions p116, Conditions p122, Prone p123. ADR-0046.
Wounds Table / Stomach Blow p190. Only standalone Prone is admitted here;
ongoing Prone Wound causes remain blocked.
"""
from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    CharacterInjuryState, WoundConditionEffect, WoundConditionSourceSnapshot, WoundEffectDuration,
)
from towr.domain.movement_models import FreeMoveProneRemovalRequest, FreeMoveProneRemovalResult, ProneRemovalTargetKind
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_roster_turn_models import _identifier, _validate_phase_source
from towr.domain.npc_wound_turn_end_models import _project_wound_turn_end
from towr.domain.npc_wound_turn_models import NpcStomachBlowExpiry
from towr.domain.turn_models import ActionSlotGrant, CombatTurnEndResult


@dataclass(frozen=True, slots=True)
class NpcRosterProneStandRequest:
    id: str
    state: NpcRosterCastingState
    actor_id: str
    actor_has_enemy_in_close_range: bool
    underlying_cause_allows_removal: bool

    def __post_init__(self) -> None:
        _identifier(self.id)
        _identifier(self.actor_id)
        # Reuse full-owner pending/expiry admission, without scheduling a turn.
        _validate_phase_source(self.state)
        for name in ('actor_has_enemy_in_close_range', 'underlying_cause_allows_removal'):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f'{name} must be an explicit boolean')
        if self.actor_has_enemy_in_close_range:
            raise ValueError('an enemy in Close Range prevents self-stand')
        if not self.underlying_cause_allows_removal:
            raise ValueError('the underlying Prone cause must allow removal')
        state = self.state
        turn = state.round_state.active_turn
        if (turn is None or turn.actor_id != self.actor_id or len(turn.action_slots) != 1
                or turn.action_slots[0].grant is not ActionSlotGrant.STANDARD
                or turn.action_slots[0].executed):
            raise ValueError('self-stand requires the active actor and one unexecuted standard slot')
        injury = state.roster.participant(self.actor_id).state.injury
        champion = isinstance(injury, CharacterInjuryState)
        dead = injury.dead if champion else injury.defeated
        supported = {Condition.PRONE, Condition.STAGGERED, Condition.DRAINED, Condition.BROKEN}
        if dead or not injury.conditions.has(Condition.PRONE) or not injury.conditions.conditions <= supported:
            raise ValueError('self-stand requires a living Prone actor with supported Conditions')
        if self.actor_id in state.spatial_state.free_move_used_entity_ids:
            raise ValueError('self-stand requires unused free movement')
        # Deliberately separate the Wound whitelist: Prone/Broken from ongoing
        # Wounds and restrictions cannot be overridden by a caller confirmation.
        if champion and (any(not w.effect_resolved for w in injury.wounds) or any(
                not isinstance(e, WoundConditionEffect)
                or e.condition not in {Condition.STAGGERED, Condition.DRAINED}
                or not injury.conditions.has(e.condition)
                or e.duration not in (WoundEffectDuration.END_OF_NEXT_TURN, WoundEffectDuration.UNTIL_REMOVED,
                                      WoundEffectDuration.UNTIL_TREATED, WoundEffectDuration.UNTIL_HEALED)
                for e in injury.active_wound_effects)):
            raise ValueError('self-stand excludes unresolved or unsupported ongoing Wound effects')
        for expiry in state.wound_expiries:
            if (expiry.actor_id in expiry.source.source.state.round_state.excluded_turn_entity_ids
                    or expiry.actor_id == self.actor_id
                    and expiry.deadline_round_number != state.round_state.round_number):
                raise ValueError('self-stand requires valid target-turn Wound chronology')

    @property
    def stand_request(self) -> FreeMoveProneRemovalRequest:
        return FreeMoveProneRemovalRequest(
            self.id, self.state.round_state, self.state.spatial_state, self.actor_id,
            ProneRemovalTargetKind.SELF, self.actor_id,
            self.state.roster.participant(self.actor_id).state.injury.conditions,
            None, self.actor_has_enemy_in_close_range)


@dataclass(frozen=True, slots=True)
class NpcRosterProneStandResult:
    source: NpcRosterProneStandRequest
    stand: FreeMoveProneRemovalResult

    def __post_init__(self) -> None:
        if not isinstance(self.source, NpcRosterProneStandRequest) or not isinstance(self.stand, FreeMoveProneRemovalResult):
            raise TypeError('self-stand result requires its typed full source and K1 result')
        request, stand = self.source.stand_request, self.stand
        expected = FreeMoveProneRemovalResult(
            request.id, request.rule_id, request.round_state, request.actor_id,
            ProneRemovalTargetKind.SELF, request.target_id, None, False,
            request.target_conditions, request.target_conditions.without_condition(Condition.PRONE),
            request.state, replace(request.state, free_move_used_entity_ids=(
                *request.state.free_move_used_entity_ids, request.actor_id)),
            (request.rule_id, 'RULE-COMBAT-014:free-movement'))
        if (stand != expected or stand.target_kind is not ProneRemovalTargetKind.SELF
                or stand.target_in_close_range is not None or stand.actor_has_enemy_in_close_range is not False):
            raise ValueError('self-stand result differs from the complete bound source/transition')

    @property
    def state(self) -> NpcRosterCastingState:
        old = self.source.state
        actor = old.roster.participant(self.source.actor_id)
        injury = replace(actor.state.injury, conditions=self.stand.target_conditions)
        roster = NpcRoster(tuple(replace(p, state=replace(p.state, injury=injury))
                                 if p is actor else p for p in old.roster.participants))
        return replace(old, roster=roster, spatial_state=self.stand.state,
            champion_attack=(None if old.champion_attack is None else replace(old.champion_attack, roster=roster)),
            minion_attack=(None if old.minion_attack is None else replace(old.minion_attack, roster=roster)))


@dataclass(frozen=True, slots=True)
class NpcRosterProneTurnEndRequest:
    """One completed Prone turn; PG1.4 Rules p123, Wounds Table p190."""

    id: str
    state: NpcRosterCastingState
    actor_id: str
    condition_sources: tuple[WoundConditionSourceSnapshot, ...] = ()

    def __post_init__(self) -> None:
        _identifier(self.id)
        _identifier(self.actor_id)
        _validate_phase_source(self.state)
        if (not isinstance(self.condition_sources, (tuple, list))
                or not all(isinstance(s, WoundConditionSourceSnapshot) for s in self.condition_sources)):
            raise TypeError('condition sources require ordered WoundConditionSourceSnapshot values')
        object.__setattr__(self, 'condition_sources', tuple(self.condition_sources))
        state = self.state
        if any(r.id == self.id or (r.actor_id, r.round_number) == (
                self.actor_id, state.round_state.round_number) for r in state.wound_turn_end_receipts):
            raise ValueError('turn end was already consumed')
        turn = state.round_state.active_turn
        if (turn is None or turn.actor_id != self.actor_id or len(turn.action_slots) != 1
                or turn.action_slots[0].grant is not ActionSlotGrant.STANDARD
                or not turn.action_slots[0].executed):
            raise ValueError('Prone turn end requires the active actor and one executed standard slot')
        if (self.actor_id == state.wizard.actor_id
                and turn.action_slots[0].execution.id not in state.consumed_execution_ids):
            raise ValueError('Wizard action must be applied through its bound consumer first')
        injury = state.roster.participant(self.actor_id).state.injury
        champion = isinstance(injury, CharacterInjuryState)
        dead = injury.dead if champion else injury.defeated
        supported = {Condition.PRONE, Condition.STAGGERED, Condition.DRAINED, Condition.BROKEN}
        if dead or not injury.conditions.has(Condition.PRONE) or not injury.conditions.conditions <= supported:
            raise ValueError('Prone turn end requires a living Prone actor with supported Conditions')
        # Standalone Prone admission does not admit ongoing Prone Wounds.
        if champion and (any(not w.effect_resolved for w in injury.wounds) or any(
                not isinstance(e, WoundConditionEffect)
                or e.condition not in {Condition.STAGGERED, Condition.DRAINED}
                or not injury.conditions.has(e.condition)
                or e.duration not in (WoundEffectDuration.END_OF_NEXT_TURN, WoundEffectDuration.UNTIL_REMOVED,
                                      WoundEffectDuration.UNTIL_TREATED, WoundEffectDuration.UNTIL_HEALED)
                for e in injury.active_wound_effects)):
            raise ValueError('Prone turn end excludes unresolved or unsupported ongoing Wound effects')
        for expiry in self.expiries:
            if expiry.deadline_round_number != state.round_state.round_number:
                raise ValueError('Wound expiry belongs to another target turn')
        conditions = tuple(s.condition for s in self.condition_sources)
        if len(set(conditions)) != len(conditions) or set(conditions) != {e.effect.condition for e in self.expiries}:
            raise ValueError('condition sources must match exactly the expiring Conditions')
        if champion:
            removed = {e.effect for e in self.expiries}
            for snapshot in self.condition_sources:
                if not snapshot.has_other_active_source and any(
                    e not in removed and e.condition is snapshot.condition for e in injury.active_wound_effects
                ):
                    raise ValueError('another active Wound source cannot be denied')

    @property
    def expiries(self) -> tuple[NpcStomachBlowExpiry, ...]:
        return tuple(e for e in self.state.wound_expiries if e.actor_id == self.actor_id)


@dataclass(frozen=True, slots=True)
class NpcRosterProneTurnEndResult:
    source: NpcRosterProneTurnEndRequest
    turn_end: CombatTurnEndResult

    def __post_init__(self) -> None:
        if (not isinstance(self.source, NpcRosterProneTurnEndRequest)
                or not isinstance(self.turn_end, CombatTurnEndResult)):
            raise TypeError('Prone turn end requires typed source and scheduler result')
        source, result = self.source, self.turn_end
        combat = source.state.round_state
        expected = replace(combat, active_turn=None,
                           completed_turn_entity_ids=(*combat.completed_turn_entity_ids, source.actor_id))
        if (result.request_id != source.id or result.state != expected
                or result.completed_turn != combat.active_turn or result.next_side is not expected.next_side
                or result.round_complete is not expected.round_complete
                or result.applied_rule_ids != ('RULE-COMBAT-001:rounds-sides-turns',)):
            raise ValueError('scheduler result differs from the complete bound Prone turn transition')

    @property
    def state(self) -> NpcRosterCastingState:
        source = self.source
        return _project_wound_turn_end(source.state, source.id, source.actor_id,
                                      source.condition_sources, source.expiries, self.turn_end.state)
