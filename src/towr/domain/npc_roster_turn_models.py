"""Full-owner scheduling phases, not action execution (ADR-0037).

PG1.4 Rules / Combat p112, Combat Actions p116, Giving Ground p119;
Wounds & Conditions pp121-123; Wounds Table / Stomach Blow p190.
"""
from dataclasses import dataclass, replace

from towr.domain.injury_models import WoundEffectDuration
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.spatial_models import SpatialBattleState
from towr.domain.turn_models import (
    ACTION_BUDGET_RULE_ID, ActionSlotGrant, CombatActionDeclaration, CombatActionKind,
    CombatActionSlot, CombatActionSlotResult, CombatRoundAdvanceResult, CombatRoundState,
    CombatSide, CombatTurnStartResult, CombatTurnState, ImproviseKind, ManoeuvreKind,
)


_TURN_RULES = ('RULE-COMBAT-001:rounds-sides-turns',)


def _identifier(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError('phase IDs must be strings')
    if not value.strip():
        raise ValueError('phase IDs must not be blank')


def _inactive_ids(state: NpcRosterCastingState) -> tuple[str, ...]:
    return tuple(p.state.actor_id for p in state.roster.participants
                 if (p.state.injury.dead if p.state.actor_id == state.wizard.actor_id else p.state.injury.defeated))


def _validate_phase_source(state: NpcRosterCastingState) -> None:
    if not isinstance(state, NpcRosterCastingState):
        raise TypeError('phase requires the complete roster state')
    if state.pending_miscast_continuation is not None:
        raise ValueError('prepared Miscast blocks scheduling')
    if (state.pending_minion_attack is not None or state.pending_miscast is not None
            or state.pending_movement is not None or state.pending_interruption is not None
            or state.champion_attack is not None and state.champion_attack.pending is not None):
        raise ValueError('mandatory pending continuation blocks scheduling')
    if not all(isinstance(s, CombatSide) for s in state.round_state.side_order):
        raise TypeError('side order must contain CombatSide values')
    inactive = set(_inactive_ids(state))
    if not set(state.round_state.excluded_turn_entity_ids) <= inactive:
        raise ValueError('live excluded actors require a separate scheduling contract')
    wizard = state.roster.participant(state.wizard.actor_id)
    if not wizard.state.injury.dead:
        timed = {e for e in wizard.state.injury.active_wound_effects
                 if e.duration is WoundEffectDuration.END_OF_NEXT_TURN}
        if timed != {e.effect for e in state.wound_expiries}:
            raise ValueError('untracked next-turn Wound effect requires its chronology')
        for expiry in state.wound_expiries:
            deadline = expiry.deadline_round_number
            if (deadline < state.round_state.round_number or deadline == state.round_state.round_number
                    and expiry.actor_id in state.round_state.completed_turn_entity_ids):
                raise ValueError('due Wound expiry must complete at its target turn end before scheduling')


def _project_round(state: NpcRosterCastingState, combat: CombatRoundState, spatial: SpatialBattleState) -> NpcRosterCastingState:
    champion = state.champion_attack
    if champion is not None:
        champion = replace(champion, round_state=combat)
    return replace(state, round_state=combat, spatial_state=spatial, champion_attack=champion)


def _same_round(actual: CombatRoundState, expected: CombatRoundState) -> bool:
    return (isinstance(actual, CombatRoundState) and all(isinstance(s, CombatSide) for s in actual.side_order)
            and actual == expected)


@dataclass(frozen=True, slots=True)
class NpcRosterTurnStartRequest:
    id: str
    state: NpcRosterCastingState
    actor_id: str
    declaration: CombatActionDeclaration

    def __post_init__(self) -> None:
        _identifier(self.id)
        _identifier(self.actor_id)
        _validate_phase_source(self.state)
        if not isinstance(self.declaration, CombatActionDeclaration):
            raise TypeError('turn start requires a typed action declaration')
        supported = (
            CombatActionDeclaration(CombatActionKind.ATTACK), CombatActionDeclaration(CombatActionKind.RECOVER),
            CombatActionDeclaration(CombatActionKind.MANOEUVRE, manoeuvre=ManoeuvreKind.RUN),
            CombatActionDeclaration(CombatActionKind.IMPROVISE, improvise_kind=ImproviseKind.SPELL,
                                    improvise_approach_id='lore:battle-magic'),
        )
        if self.declaration not in supported:
            raise ValueError('unsupported declaration for the first magic scheduling boundary')
        combat = self.state.round_state
        actor = self.state.roster.participant(self.actor_id)
        if self.actor_id in _inactive_ids(self.state):
            raise ValueError('dead or defeated actor cannot start a turn')
        if combat.active_turn is not None or combat.round_complete:
            raise ValueError('turn start requires an idle incomplete round')
        if self.actor_id in (*combat.completed_turn_entity_ids, *combat.excluded_turn_entity_ids):
            raise ValueError('actor has already completed or been excluded this round')
        if actor.state.side is not combat.next_side:
            raise ValueError('actor must belong to the current side')


@dataclass(frozen=True, slots=True)
class NpcRosterTurnStartResult:
    source: NpcRosterTurnStartRequest
    start: CombatTurnStartResult
    slot: CombatActionSlotResult

    def __post_init__(self) -> None:
        if (not isinstance(self.source, NpcRosterTurnStartRequest) or not isinstance(self.start, CombatTurnStartResult)
                or not isinstance(self.slot, CombatActionSlotResult)):
            raise TypeError('turn result requires typed full source/start/slot')
        source = self.source
        actor = source.state.roster.participant(source.actor_id)
        turn = CombatTurnState(source.actor_id, actor.state.side)
        started = replace(source.state.round_state, active_turn=turn)
        reserved = CombatActionSlot(1, source.declaration, ActionSlotGrant.STANDARD)
        expected = replace(started, active_turn=replace(turn, action_slots=(reserved,)))
        if (self.start.request_id != source.id + ':start' or self.start.turn != turn
                or not _same_round(self.start.state, started) or self.start.applied_rule_ids != _TURN_RULES
                or self.slot.request_id != source.id + ':slot' or self.slot.slot != reserved
                or not _same_round(self.slot.state, expected) or self.slot.applied_rule_ids != (ACTION_BUDGET_RULE_ID,)):
            raise ValueError('start/slot results differ from the complete bound transition')

    @property
    def state(self) -> NpcRosterCastingState:
        return _project_round(self.source.state, self.slot.state, self.source.state.spatial_state)


@dataclass(frozen=True, slots=True)
class NpcRosterRoundAdvanceRequest:
    id: str
    state: NpcRosterCastingState

    def __post_init__(self) -> None:
        _identifier(self.id)
        _validate_phase_source(self.state)
        if self.state.round_state.active_turn is not None or not self.state.round_state.round_complete:
            raise ValueError('advance requires a completed round without active turn')
        if len(_inactive_ids(self.state)) == len(self.state.roster.participants):
            raise ValueError('no living actor remains to enter another round')


@dataclass(frozen=True, slots=True)
class NpcRosterRoundAdvanceResult:
    source: NpcRosterRoundAdvanceRequest
    combat: CombatRoundAdvanceResult
    spatial: SpatialBattleState

    def __post_init__(self) -> None:
        if (not isinstance(self.source, NpcRosterRoundAdvanceRequest) or not isinstance(self.combat, CombatRoundAdvanceResult)
                or not isinstance(self.spatial, SpatialBattleState)):
            raise TypeError('advance result requires typed full source/combat/spatial')
        old = self.source.state
        expected = CombatRoundState(old.round_state.round_number + 1, old.roster.turn_participants,
                                    old.round_state.side_order)
        spatial = replace(old.spatial_state, round_number=old.spatial_state.round_number + 1,
                          gave_ground_entity_ids=(), free_move_used_entity_ids=(), difficult_terrain_tested_entity_ids=())
        if (self.combat.request_id != self.source.id or not _same_round(self.combat.state, expected)
                or self.combat.applied_rule_ids != _TURN_RULES or self.spatial != spatial):
            raise ValueError('round/spatial results differ from the complete bound advance')

    @property
    def state(self) -> NpcRosterCastingState:
        old = self.source.state
        combat = replace(self.combat.state, excluded_turn_entity_ids=_inactive_ids(old))
        return _project_round(old, combat, self.spatial)
