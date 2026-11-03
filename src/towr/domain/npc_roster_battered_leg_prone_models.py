"""Source-bound free self-stand after failed Battered Leg Endurance.

PG1.4 Rules / Free Actions p116, Conditions pp122-123, Wounds Table p190/5.
The Wound and completed Test remain; only their removable Prone is consumed.
"""
from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition
from towr.domain.injury_models import CharacterInjuryState, WoundConditionEffect, WoundEffectDuration
from towr.domain.movement_models import FreeMoveProneRemovalRequest, FreeMoveProneRemovalResult, ProneRemovalTargetKind
from towr.domain.npc_roster_battered_leg_models import (
    NpcBatteredLegCompletionWitness, _owner, _readmit, require_battered_leg_completion,
)
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_roster_turn_models import _identifier, _validate_phase_source
from towr.domain.turn_models import ActionSlotGrant


@dataclass(frozen=True, slots=True)
class NpcRosterBatteredLegProneStandRequest:
    id: str
    state: NpcRosterCastingState
    actor_id: str
    actor_has_enemy_in_close_range: bool

    def __post_init__(self) -> None:
        _identifier(self.id)
        _identifier(self.actor_id)
        if type(self.actor_has_enemy_in_close_range) is not bool:
            raise TypeError('Battered Leg self-stand requires an explicit Close enemy boolean')
        if self.actor_has_enemy_in_close_range:
            raise ValueError('an enemy in Close Range prevents Battered Leg self-stand')
        _owner(self.state)
        _validate_phase_source(self.state)
        state = self.state
        if self.actor_id != state.wizard.actor_id:
            raise ValueError('Battered Leg self-stand requires the owner Wizard')
        turn = state.round_state.active_turn
        if (turn is None or turn.actor_id != self.actor_id or len(turn.action_slots) != 1
                or turn.action_slots[0].grant is not ActionSlotGrant.STANDARD
                or turn.action_slots[0].executed):
            raise ValueError('Battered Leg self-stand requires one active unexecuted standard slot')
        if self.actor_id in state.spatial_state.free_move_used_entity_ids:
            raise ValueError('Battered Leg self-stand requires unused free movement')
        receipt = state.battered_leg_receipt
        if not isinstance(receipt, NpcBatteredLegCompletionWitness):
            raise ValueError('Battered Leg self-stand requires its full Endurance witness')
        if receipt.prone_stand is not None:
            raise ValueError('Battered Leg self-stand was already consumed')
        require_battered_leg_completion(state)
        injury = state.roster.participant(self.actor_id).state.injury
        expected_effect = WoundConditionEffect(1, Condition.PRONE, WoundEffectDuration.UNTIL_REMOVED)
        if (receipt.endurance.test_result.succeeded or not isinstance(injury, CharacterInjuryState)
                or injury.dead or injury.conditions.conditions != frozenset((Condition.PRONE,))
                or injury.active_wound_effects != (expected_effect,)):
            raise ValueError('Battered Leg self-stand requires only its failed-Test sourced Prone')
        self.stand_request

    @property
    def stand_request(self) -> FreeMoveProneRemovalRequest:
        return FreeMoveProneRemovalRequest(
            self.id, self.state.round_state, self.state.spatial_state, self.actor_id,
            ProneRemovalTargetKind.SELF, self.actor_id,
            self.state.roster.participant(self.actor_id).state.injury.conditions,
            None, self.actor_has_enemy_in_close_range)


@dataclass(frozen=True, slots=True)
class NpcRosterBatteredLegProneStandResult:
    source: NpcRosterBatteredLegProneStandRequest
    stand: FreeMoveProneRemovalResult

    def __post_init__(self) -> None:
        if not isinstance(self.source, NpcRosterBatteredLegProneStandRequest):
            raise TypeError('Battered Leg self-stand requires its typed full source')
        _readmit(self.source)
        if not isinstance(self.stand, FreeMoveProneRemovalResult):
            raise TypeError('Battered Leg self-stand requires its typed K1 result')
        _readmit(self.stand)
        stand = self.stand
        for clock in (stand.round_state, stand.previous_state, stand.state):
            if type(clock.round_number) is not int:
                raise TypeError('self-stand clocks must retain strict integers')
            _readmit(clock)
        for conditions in (stand.previous_target_conditions, stand.target_conditions):
            if (type(conditions.conditions) is not frozenset
                    or not all(isinstance(c, Condition) for c in conditions.conditions)):
                raise TypeError('self-stand Conditions must retain their typed frozenset')
            _readmit(conditions)
        request = self.source.stand_request
        expected = FreeMoveProneRemovalResult(
            request.id, request.rule_id, request.round_state, request.actor_id,
            ProneRemovalTargetKind.SELF, request.target_id, None, False,
            request.target_conditions, request.target_conditions.without_condition(Condition.PRONE),
            request.state, replace(request.state, free_move_used_entity_ids=(
                *request.state.free_move_used_entity_ids, request.actor_id)),
            (request.rule_id, 'RULE-COMBAT-014:free-movement'))
        if (stand != expected or stand.target_kind is not ProneRemovalTargetKind.SELF
                or stand.target_in_close_range is not None
                or stand.actor_has_enemy_in_close_range is not False):
            raise ValueError('Battered Leg self-stand differs from its exact source and free move')

    @property
    def completed_injury(self) -> CharacterInjuryState:
        injury = self.source.state.roster.participant(self.source.actor_id).state.injury
        return replace(injury, conditions=self.stand.target_conditions, active_wound_effects=())

    @property
    def state(self) -> NpcRosterCastingState:
        _readmit(self)
        old = self.source.state
        roster = NpcRoster(tuple(replace(p, state=replace(p.state, injury=self.completed_injury))
                                 if p.state.actor_id == self.source.actor_id else p
                                 for p in old.roster.participants))
        return replace(old, roster=roster, spatial_state=self.stand.state,
            champion_attack=replace(old.champion_attack, roster=roster),
            minion_attack=None if old.minion_attack is None else replace(old.minion_attack, roster=roster),
            battered_leg_receipt=replace(old.battered_leg_receipt, prone_stand=self))
