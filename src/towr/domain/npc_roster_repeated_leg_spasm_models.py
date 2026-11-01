"""Source-bound second Leg Spasm stand (ADR-0052), without runner admission.

PG1.4 Rules pp116,122-123 / Wounds Table p190; GM1.1 Champions p92.
Two explicit witnesses prove old cause removal and one new rolled Wound9.
"""
from dataclasses import dataclass, replace

from towr.domain.attack_models import AttackOutcome, ImpactOutcome, MissConsequence
from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    CharacterInjuryState, CharacterWoundType, WoundConditionEffect,
    WoundEffectDuration, WoundEntryId, WoundRecordOrigin, WoundRestriction,
    WoundRestrictionEffect,
)
from towr.domain.movement_models import (
    FreeMoveProneRemovalRequest, FreeMoveProneRemovalResult, ProneRemovalTargetKind,
)
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandResult
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_roster_turn_models import (
    NpcRosterTurnStartRequest, NpcRosterTurnStartResult, _identifier, _validate_phase_source,
)
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest, NpcWoundTurnEndResult
from towr.domain.test_models import InitialTestRoll, RollTrace, TestQuality, TestRequest, TestResult
from towr.domain.turn_models import (
    ACTION_BUDGET_RULE_ID, ActionSlotGrant, CombatActionSlot, CombatActionSlotResult,
    CombatSide, CombatTurnEndResult, CombatTurnStartResult, CombatTurnState,
)
from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleOutcome


def _readmit(value):
    """Run an explicit model's own pure admission, without repairing its source."""
    if replace(value) != value:
        raise ValueError('repeated stand source would require normalization')


def _injury(injury: CharacterInjuryState) -> None:
    if not isinstance(injury, CharacterInjuryState):
        raise TypeError('repeated stand requires CharacterInjuryState')
    _readmit(injury)
    if type(injury.dead) is not bool:
        raise TypeError('injury dead flag must be a strict boolean')
    _readmit(injury.conditions)
    if not all(isinstance(c, Condition) for c in injury.conditions.conditions):
        raise TypeError('Conditions must retain typed enum values')
    for wound in injury.wounds:
        _readmit(wound)
        if (type(wound.sequence) is not int or type(wound.table_total) is not int
                or any(type(v) is not int for v in wound.roll_values)):
            raise TypeError('Wound provenance requires strict integers')
    for effect in injury.active_wound_effects:
        _readmit(effect)
        if type(effect.wound_sequence) is not int:
            raise TypeError('Wound effect sequence must be a strict integer')


def _owner(state: NpcRosterCastingState) -> None:
    _validate_phase_source(state)
    _readmit(state)
    _readmit(state.roster)
    _readmit(state.wizard)
    _readmit(state.wizard.caster)
    _readmit(state.wizard.magic_state)
    combat = state.round_state
    _readmit(combat)
    if type(combat.round_number) is not int or not all(isinstance(s, CombatSide) for s in combat.side_order):
        raise TypeError('round requires a strict number and typed sides')
    for participant in combat.participants:
        _readmit(participant)
    if combat.active_turn is not None:
        _readmit(combat.active_turn)
        for slot in combat.active_turn.action_slots:
            _readmit(slot)
            _readmit(slot.declaration)
            if type(slot.index) is not int:
                raise TypeError('action slot index must be a strict integer')
    _readmit(state.spatial_state)
    if type(state.spatial_state.round_number) is not int:
        raise TypeError('spatial round must be a strict integer')
    for participant in state.roster.participants:
        _readmit(participant)
        _readmit(participant.definition)
        _readmit(participant.state)
        for flag in ('wields_weapon', 'holds_shield'):
            if type(getattr(participant.state, flag)) is not bool:
                raise TypeError('participant facts require strict booleans')
        if isinstance(participant.state.injury, CharacterInjuryState):
            _injury(participant.state.injury)
        else:
            _readmit(participant.state.injury)
    champion = state.champion_attack
    if champion is None or state.minion_attack is None:
        raise ValueError('repeated stand requires both bound child owners')
    _readmit(champion)
    _readmit(state.minion_attack)
    _readmit(champion.daily_wounds)
    for receipt in champion.daily_wounds.receipts:
        _readmit(receipt)
        _readmit(receipt.wound)
        if (type(receipt.wound.sequence) is not int or type(receipt.wound.table_total) is not int
                or any(type(v) is not int for v in receipt.wound.roll_values)):
            raise TypeError('daily Wound provenance requires strict integers')
    for receipt in state.wound_turn_end_receipts:
        _readmit(receipt)
        if type(receipt.round_number) is not int:
            raise TypeError('end receipt round must be a strict integer')
    if state.wound_expiries or any(r.expired_sources or r.expired_attack_ids for r in state.wound_turn_end_receipts):
        raise ValueError('repeated stand excludes timed Wound histories')


def _prefix(previous: tuple, current: tuple) -> bool:
    return current[:len(previous)] == previous


def _anchors(state: NpcRosterCastingState) -> tuple:
    return (tuple((p.state.actor_id, p.definition, p.state.side) for p in state.roster.participants),
            state.wizard.actor_id, state.wizard.caster,
            state.spatial_state.graph, state.spatial_state.placements,
            state.champion_attack.daily_wounds.day_id, state.champion_attack.daily_wounds.target_id)


def _normal_test(request: TestRequest, result: TestResult) -> None:
    """Admit the two unchanged normal Tests of this narrow stationary Attack."""
    if not isinstance(request, TestRequest) or not isinstance(result, TestResult) or not isinstance(result.trace, RollTrace):
        raise TypeError('Attack witness requires typed Test requests/results/traces')
    _readmit(request.profile)
    _readmit(request)
    for modifier in request.dice_modifiers:
        _readmit(modifier)
    if request.quality_modifiers or request.success_modifiers or request.reroll_locks:
        raise ValueError('repeated stand Attack witness requires unchanged normal Tests')
    trace = result.trace
    InitialTestRoll(request, trace.base_dice, trace.pool_cap, trace.regular_dice_delta,
        trace.cap_bypassing_dice, trace.dice_before_minimum, trace.rolled_dice,
        trace.threshold, trace.minimum_die_rule_applied, trace.initial_values)
    if (type(trace.initial_values) is not tuple or type(trace.final_values) is not tuple
            or any(type(v) is not int or not 1 <= v <= 10 for v in trace.final_values)
            or any(type(v) is not int for v in (trace.rolled_successes, trace.success_delta, trace.successes))):
        raise TypeError('Test witness must retain strict dice and success counts')
    successes = sum(v <= trace.threshold for v in trace.initial_values)
    if (trace.request_id != request.id or trace.quality is not TestQuality.NORMAL
            or trace.rerolls != () or trace.final_values != trace.initial_values
            or (trace.rolled_successes, trace.success_delta, trace.successes) != (successes, 0, successes)
            or trace.applied_rule_ids != tuple(m.rule_id for m in request.dice_modifiers)):
        raise ValueError('Attack witness differs from its complete normal Test trace')


def _attack_witness(result: NpcRosterChampionAttackResult, actor_id: str) -> None:
    if not isinstance(result, NpcRosterChampionAttackResult):
        raise TypeError('repeated stand requires an outer bound Champion attack witness')
    _owner(result.source.state)
    attack = result.attack
    context = result.source.attack.stationary_wounds
    if context is None:
        raise ValueError('new Wound requires its full stationary pre-Attack context')
    context.validate_source(result.source.state, actor_id)
    prepared = attack.source.preparation
    _readmit(prepared.npc_attack.source_request.snapshot)
    _readmit(prepared.npc_attack.selected_profile)
    _readmit(prepared.npc_attack.source_request)
    _readmit(prepared.npc_attack.attack)
    _readmit(prepared.npc_attack)
    _readmit(prepared.protection.source_request)
    _readmit(prepared.protection.attack)
    _readmit(prepared.protection)
    _readmit(prepared)
    _readmit(attack.source.execution.kernel_request)
    _readmit(attack.source.execution)
    raw_attack = attack.execution.resolution.attack
    kernel_attack = attack.source.execution.kernel_request.attack
    _normal_test(kernel_attack.attacker_test, raw_attack.attacker_test)
    if kernel_attack.defender_test is not None:
        _normal_test(kernel_attack.defender_test, raw_attack.defender_test)
    if (not isinstance(raw_attack.outcome, AttackOutcome) or not isinstance(raw_attack.impact, ImpactOutcome)
            or not isinstance(raw_attack.miss_consequence, MissConsequence)
            or type(raw_attack.tie_break_applied) is not bool
            or type(raw_attack.success_margin) is not int):
        raise TypeError('Attack witness requires typed outcomes and strict trace fields')
    _readmit(attack.source)
    _readmit(result.source)
    _readmit(attack.execution)
    _readmit(attack)
    _readmit(result)
    completion = attack.completion
    if (completion is None or completion.outcome is not CharacterWoundLifecycleOutcome.ACCEPTED
            or attack.pending_follow_ups or attack.execution.target_id != actor_id):
        raise ValueError('repeated stand requires one accepted completed attack on the owner')
    roll = completion.source_request.roll
    table_roll = roll.wound_result.table_roll
    _readmit(table_roll.entry)
    _readmit(table_roll)
    if (type(table_roll.dice) is not int or type(table_roll.total) is not int
            or any(type(v) is not int for v in table_roll.values)):
        raise TypeError('new Wound roll must preserve strict d10 provenance')
    _readmit(roll.source_request.wound)
    _readmit(roll.source_request)
    _readmit(roll)
    _readmit(completion.source_request)
    _readmit(completion)
    if (roll.wound_result.subject_type is not CharacterWoundType.CHAMPION
            or roll.wound_result.wound_accepted is not True or roll.near_miss_eligible is not False
            or completion.wound_effect is None or completion.wound_effect.follow_ups
            or completion.wound_effect.request.entry_id is not WoundEntryId.LEG_SPASM):
        raise ValueError('new attack must complete a canonical Champion Leg Spasm')
    _readmit(completion.wound_effect.request)
    _readmit(completion.daily_registration.source_request)
    _readmit(completion.daily_registration)


def _scheduled_source(attack: NpcRosterChampionAttackResult, current: NpcRosterCastingState, actor_id: str) -> None:
    """Compare one exact end-attacker/start-owner delta using pure models only."""
    after = attack.state
    _owner(after)
    combat = after.round_state
    attacker = attack.attack.execution.actor_id
    if (actor_id in combat.completed_turn_entity_ids or combat.round_number != current.round_state.round_number
            or len(current.wound_turn_end_receipts) != len(after.wound_turn_end_receipts) + 1):
        raise ValueError('repeated stand requires immediate end-attacker/start-owner chronology')
    receipt = current.wound_turn_end_receipts[-1]
    end_request = NpcWoundTurnEndRequest(receipt.id, after, attacker)
    ended = replace(combat, active_turn=None,
                    completed_turn_entity_ids=(*combat.completed_turn_entity_ids, attacker))
    end = NpcWoundTurnEndResult(end_request, CombatTurnEndResult(
        receipt.id, ended, combat.active_turn, ended.next_side, ended.round_complete,
        ('RULE-COMBAT-001:rounds-sides-turns',)))
    declaration = current.round_state.active_turn.action_slots[0].declaration
    start_request = NpcRosterTurnStartRequest('repeated-stand:source-check', end.state, actor_id, declaration)
    turn = CombatTurnState(actor_id, end.state.roster.participant(actor_id).state.side)
    started = replace(ended, active_turn=turn)
    slot = CombatActionSlot(1, declaration, ActionSlotGrant.STANDARD)
    reserved = replace(started, active_turn=replace(turn, action_slots=(slot,)))
    start = NpcRosterTurnStartResult(start_request,
        CombatTurnStartResult(start_request.id + ':start', started, turn, ('RULE-COMBAT-001:rounds-sides-turns',)),
        CombatActionSlotResult(start_request.id + ':slot', reserved, slot, (ACTION_BUDGET_RULE_ID,)))
    if current != start.state:
        raise ValueError('current owner differs from the complete end-attacker/start-owner transition')


@dataclass(frozen=True, slots=True)
class NpcRosterRepeatedLegSpasmStandRequest:
    id: str
    state: NpcRosterCastingState
    actor_id: str
    actor_has_enemy_in_close_range: bool
    underlying_cause_allows_removal: bool
    previous_stand: NpcRosterLegSpasmStandResult
    wound_attack: NpcRosterChampionAttackResult

    def __post_init__(self) -> None:
        _identifier(self.id)
        _identifier(self.actor_id)
        for flag in ('actor_has_enemy_in_close_range', 'underlying_cause_allows_removal'):
            if type(getattr(self, flag)) is not bool:
                raise TypeError('repeated stand facts must be strict booleans')
        if self.actor_has_enemy_in_close_range or not self.underlying_cause_allows_removal:
            raise ValueError('repeated stand requires no enemy Close and a removable underlying cause')
        _owner(self.state)
        if self.actor_id != self.state.wizard.actor_id:
            raise ValueError('repeated stand requires the owner Wizard')
        turn = self.state.round_state.active_turn
        if (turn is None or turn.actor_id != self.actor_id or len(turn.action_slots) != 1
                or turn.action_slots[0].grant is not ActionSlotGrant.STANDARD or turn.action_slots[0].executed
                or self.actor_id in self.state.spatial_state.free_move_used_entity_ids):
            raise ValueError('repeated stand requires an unused free move and unexecuted standard slot')
        if not isinstance(self.previous_stand, NpcRosterLegSpasmStandResult):
            raise TypeError('repeated stand requires exactly one prior stand48 witness')
        prior = self.previous_stand
        _owner(prior.source.state)
        _readmit(prior.source)
        _readmit(prior.stand)
        _readmit(prior)
        if prior.source.actor_id != self.actor_id:
            raise ValueError('prior stand belongs to another actor')
        old = prior.state
        _attack_witness(self.wound_attack, self.actor_id)
        before_attack = self.wound_attack.source.state
        if (_anchors(old) != _anchors(before_attack)
                or old.roster.participant(self.actor_id).state.injury != before_attack.roster.participant(self.actor_id).state.injury
                or old.champion_attack.daily_wounds != before_attack.champion_attack.daily_wounds
                or old.champion_attack.consumed_wound_roll_ids != before_attack.champion_attack.consumed_wound_roll_ids
                or not _prefix(old.consumed_execution_ids, before_attack.consumed_execution_ids)
                or not _prefix(old.champion_attack.consumed_execution_ids, before_attack.champion_attack.consumed_execution_ids)
                or before_attack.round_state.round_number <= old.round_state.round_number):
            raise ValueError('new attack loses the exact previous stand anchors or Wound histories')
        injury = self.state.roster.participant(self.actor_id).state.injury
        previous_injury = old.roster.participant(self.actor_id).state.injury
        if (injury.dead or injury.conditions.conditions - {Condition.PRONE, Condition.STAGGERED}
                or not injury.conditions.has(Condition.PRONE)
                or len(injury.wounds) != len(previous_injury.wounds) + 1
                or injury.wounds[:-1] != previous_injury.wounds):
            raise ValueError('repeated stand requires exactly one new Prone Leg Spasm')
        wound = injury.wounds[-1]
        if (wound.entry_id is not WoundEntryId.LEG_SPASM or wound.table_total != 9
                or wound.origin is not WoundRecordOrigin.TABLE_ROLL or not wound.effect_resolved
                or wound.treated or wound.healed):
            raise ValueError('new Wound must be canonical resolved untreated rolled Leg Spasm9')
        expected = (*previous_injury.active_wound_effects, self.removed_effects[0], WoundRestrictionEffect(
            wound.sequence, WoundRestriction.MOVEMENT_IS_DIFFICULT_TERRAIN, WoundEffectDuration.UNTIL_TREATED))
        if injury.active_wound_effects != expected:
            raise ValueError('repeated stand requires exact old terrain and new Prone/terrain causes')
        _scheduled_source(self.wound_attack, self.state, self.actor_id)

    @property
    def removed_effects(self) -> tuple[WoundConditionEffect, ...]:
        wound = self.state.roster.participant(self.actor_id).state.injury.wounds[-1]
        return (WoundConditionEffect(wound.sequence, Condition.PRONE, WoundEffectDuration.UNTIL_REMOVED),)

    @property
    def stand_request(self) -> FreeMoveProneRemovalRequest:
        return FreeMoveProneRemovalRequest(self.id, self.state.round_state, self.state.spatial_state,
            self.actor_id, ProneRemovalTargetKind.SELF, self.actor_id,
            self.state.roster.participant(self.actor_id).state.injury.conditions, None, False)


@dataclass(frozen=True, slots=True)
class NpcRosterRepeatedLegSpasmStandResult:
    source: NpcRosterRepeatedLegSpasmStandRequest
    stand: FreeMoveProneRemovalResult

    def __post_init__(self) -> None:
        if (not isinstance(self.source, NpcRosterRepeatedLegSpasmStandRequest)
                or not isinstance(self.stand, FreeMoveProneRemovalResult)):
            raise TypeError('repeated stand result requires typed source and K1 result')
        _readmit(self.source)
        _readmit(self.stand)
        request = self.source.stand_request
        expected = FreeMoveProneRemovalResult(request.id, request.rule_id, request.round_state,
            request.actor_id, ProneRemovalTargetKind.SELF, request.target_id, None, False,
            request.target_conditions, request.target_conditions.without_condition(Condition.PRONE),
            request.state, replace(request.state, free_move_used_entity_ids=(
                *request.state.free_move_used_entity_ids, request.actor_id)),
            (request.rule_id, 'RULE-COMBAT-014:free-movement'))
        if (self.stand != expected or self.stand.target_kind is not ProneRemovalTargetKind.SELF
                or self.stand.actor_has_enemy_in_close_range is not False
                or self.stand.target_in_close_range is not None):
            raise ValueError('repeated stand differs from the exact K1 transition')

    @property
    def removed_effects(self) -> tuple[WoundConditionEffect, ...]:
        return self.source.removed_effects

    @property
    def state(self) -> NpcRosterCastingState:
        old = self.source.state
        actor = old.roster.participant(self.source.actor_id)
        injury = replace(actor.state.injury, conditions=self.stand.target_conditions,
            active_wound_effects=tuple(e for e in actor.state.injury.active_wound_effects if e not in self.removed_effects))
        roster = NpcRoster(tuple(replace(p, state=replace(p.state, injury=injury))
            if p.state.actor_id == self.source.actor_id else p for p in old.roster.participants))
        return replace(old, roster=roster, spatial_state=self.stand.state,
            champion_attack=replace(old.champion_attack, roster=roster),
            minion_attack=replace(old.minion_attack, roster=roster))
