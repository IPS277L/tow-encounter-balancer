"""One source-bound M8 end-turn; PG1.4 Rules pp121-123, Wounds Table p190."""
from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundConditionEffect, WoundConditionSourceSnapshot, WoundEffectDuration
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_wound_turn_models import NpcStomachBlowExpiry, NpcWoundTurnEndReceipt
from towr.domain.turn_models import ActionSlotGrant, CombatRoundState, CombatTurnEndResult


@dataclass(frozen=True, slots=True)
class NpcWoundTurnEndRequest:
    id: str
    state: NpcRosterCastingState
    actor_id: str
    condition_sources: tuple[WoundConditionSourceSnapshot, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.state, NpcRosterCastingState):
            raise TypeError('turn end requires a full roster state')
        for identifier in (self.id, self.actor_id):
            if not isinstance(identifier, str):
                raise TypeError('turn end IDs must be strings')
            if not identifier.strip():
                raise ValueError('turn end IDs must not be blank')
        if (not isinstance(self.condition_sources, (tuple, list))
                or not all(isinstance(s, WoundConditionSourceSnapshot) for s in self.condition_sources)):
            raise TypeError('condition sources require ordered WoundConditionSourceSnapshot values')
        object.__setattr__(self, 'condition_sources', tuple(self.condition_sources))
        state = self.state
        if state.pending_miscast_continuation is not None:
            raise ValueError('prepared Miscast blocks turn end')
        if state.pending_minion_attack is not None:
            raise ValueError('pending Minion attack blocks turn end')
        if (state.pending_miscast is not None or state.pending_movement is not None
                or state.pending_interruption is not None
                or state.champion_attack is not None and state.champion_attack.pending is not None):
            raise ValueError('mandatory pending continuation blocks turn end')
        if any(r.id == self.id or (r.actor_id, r.round_number) == (
                self.actor_id, state.round_state.round_number) for r in state.wound_turn_end_receipts):
            raise ValueError('turn end was already consumed')
        turn = state.round_state.active_turn
        if turn is None or turn.actor_id != self.actor_id:
            raise ValueError('only the active actor may end its turn')
        if (len(turn.action_slots) != 1 or turn.action_slots[0].grant is not ActionSlotGrant.STANDARD
                or not turn.action_slots[0].executed):
            raise ValueError('this boundary requires one executed standard action')
        action = turn.action_slots[0].execution
        if self.actor_id == state.wizard.actor_id and action.id not in state.consumed_execution_ids:
            raise ValueError('Wizard action must be applied through its bound consumer first')
        injury = state.roster.participant(self.actor_id).state.injury
        champion = self.actor_id == state.wizard.actor_id
        if (injury.dead if champion else injury.defeated):
            raise ValueError('dead or defeated actor cannot end a live turn')
        supported = {Condition.STAGGERED, Condition.DRAINED, Condition.BROKEN}
        if not injury.conditions.conditions <= supported:
            raise ValueError('unsupported end-turn Condition requires a separate consumer')
        if champion:
            if any(not w.effect_resolved for w in injury.wounds) or any(
                not isinstance(e, WoundConditionEffect) or e.condition not in supported - {Condition.BROKEN}
                or not injury.conditions.has(e.condition)
                or e.duration not in (WoundEffectDuration.END_OF_NEXT_TURN, WoundEffectDuration.UNTIL_REMOVED,
                                      WoundEffectDuration.UNTIL_TREATED, WoundEffectDuration.UNTIL_HEALED)
                for e in injury.active_wound_effects
            ):
                raise ValueError('unresolved or unsupported end-turn Wound effects')
            timed = tuple(e for e in injury.active_wound_effects
                          if e.duration is WoundEffectDuration.END_OF_NEXT_TURN)
            if set(timed) != {e.effect for e in self.expiries}:
                raise ValueError('timed Wound effects require their bound attack chronology')
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
class NpcWoundTurnEndResult:
    source: NpcWoundTurnEndRequest
    turn_end: CombatTurnEndResult

    def __post_init__(self) -> None:
        if not isinstance(self.source, NpcWoundTurnEndRequest) or not isinstance(self.turn_end, CombatTurnEndResult):
            raise TypeError('turn end result requires typed source and scheduler result')
        source, result = self.source, self.turn_end
        combat = source.state.round_state
        expected = replace(combat, active_turn=None,
                           completed_turn_entity_ids=(*combat.completed_turn_entity_ids, source.actor_id))
        if (result.request_id != source.id or result.state != expected
                or result.completed_turn != combat.active_turn or result.next_side is not expected.next_side
                or result.round_complete is not expected.round_complete
                or result.applied_rule_ids != ('RULE-COMBAT-001:rounds-sides-turns',)):
            raise ValueError('scheduler result differs from the complete bound turn transition')

    @property
    def state(self) -> NpcRosterCastingState:
        source = self.source
        return _project_wound_turn_end(source.state, source.id, source.actor_id,
                                      source.condition_sources, source.expiries, self.turn_end.state)


def _project_wound_turn_end(
    old: NpcRosterCastingState, request_id: str, actor_id: str,
    condition_sources: tuple[WoundConditionSourceSnapshot, ...],
    expiries: tuple[NpcStomachBlowExpiry, ...], combat: CombatRoundState,
) -> NpcRosterCastingState:
    """Project an already validated end transition; never schedule or strip Prone."""
    roster = old.roster
    if expiries:
        actor = roster.participant(actor_id)
        injury = actor.state.injury
        conditions = injury.conditions
        for snapshot in condition_sources:
            if not snapshot.has_other_active_source:
                conditions = conditions.without_condition(snapshot.condition)
        removed = {e.effect for e in expiries}
        injury = replace(injury, conditions=conditions, active_wound_effects=tuple(
            e for e in injury.active_wound_effects if e not in removed))
        roster = NpcRoster(tuple(replace(p, state=replace(p.state, injury=injury))
                                 if p is actor else p for p in roster.participants))
    champion = old.champion_attack
    if champion is not None:
        champion = replace(champion, roster=roster, round_state=combat)
    receipt = NpcWoundTurnEndReceipt(request_id, actor_id, old.round_state.round_number,
                                   tuple(e.attack_id for e in expiries))
    return replace(old, roster=roster, round_state=combat, champion_attack=champion,
                   minion_attack=(None if old.minion_attack is None else replace(old.minion_attack, roster=roster)),
                   wound_expiries=tuple(e for e in old.wound_expiries if e not in expiries),
                   wound_turn_end_receipts=(*old.wound_turn_end_receipts, receipt))
