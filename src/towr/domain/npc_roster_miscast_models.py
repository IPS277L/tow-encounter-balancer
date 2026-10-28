"""Explicit decline and source-bound prepared/rolled Miscast owners (ADR-0045).

PG1.4 Magic in the Old World / Interrupted Casting and Miscasts pp156-159.
Preparation loses Casting progress; the single table roll retains the Pool.
"""
from dataclasses import dataclass, fields, replace
from enum import Enum
from typing import cast

from towr.domain.action_execution_models import SkippedCastingTestAfterActionResult
from towr.domain.magic_models import (
    MiscastPoolIncreaseRequest, MiscastPoolIncreaseSourceKind, MiscastPoolOutcome,
    MiscastPoolResolutionResult, MiscastPreparationRequest, MiscastPreparationResult, MiscastRollRequest,
    MiscastRollResult, MiscastTableEffectRequest, MiscastTableEntry, MiscastTableEntryId,
)
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.turn_models import ActionSlotGrant


class NpcRosterMiscastPolicy(str, Enum):
    DECLINE_CAST_BEFORE_MISCAST = 'decline_cast_before_miscast'


@dataclass(frozen=True, slots=True)
class NpcRosterMiscastFacts:
    all_combatants_in_roster: bool
    no_external_short_range_creatures: bool
    unmounted_combatants_only: bool
    no_effect_immunities: bool
    no_cross_zone_close: bool

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if not isinstance(value, bool):
                raise TypeError(f'{field.name} must be an explicit bool')
            if not value:
                raise ValueError(f'{field.name} must be confirmed for this Miscast scope')


@dataclass(frozen=True, slots=True)
class NpcRosterMiscastPreparationRequest:
    id: str
    state: NpcRosterCastingState
    policy: NpcRosterMiscastPolicy
    facts: NpcRosterMiscastFacts

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            raise TypeError('Miscast preparation ID must be a string')
        if not self.id.strip():
            raise ValueError('Miscast preparation ID must not be blank')
        if not isinstance(self.state, NpcRosterCastingState):
            raise TypeError('Miscast preparation requires the full roster state')
        if not isinstance(self.policy, NpcRosterMiscastPolicy):
            raise TypeError('Miscast preparation requires an explicit typed policy')
        if self.policy is not NpcRosterMiscastPolicy.DECLINE_CAST_BEFORE_MISCAST:
            raise ValueError('this Miscast boundary supports only explicit decline')
        if not isinstance(self.facts, NpcRosterMiscastFacts):
            raise TypeError('Miscast preparation requires typed scope facts')
        old = self.state
        if (old.pending_miscast_continuation is not None or old.pending_minion_attack is not None
                or old.pending_movement is not None
                or old.champion_attack is not None and old.champion_attack.pending is not None):
            raise ValueError('another mandatory continuation blocks Miscast preparation')
        if (old.pending_miscast is None) == (old.pending_interruption is None):
            raise ValueError('Miscast preparation requires exactly one raw pending origin')
        wizard = old.wizard
        if old.roster.participant(wizard.actor_id).state.injury.dead:
            raise ValueError('a dead Wizard cannot prepare this Miscast')
        turn = old.round_state.active_turn
        if (turn is None or turn.actor_id != wizard.actor_id or len(turn.action_slots) != 1
                or turn.action_slots[0].grant is not ActionSlotGrant.STANDARD
                or not turn.action_slots[0].executed):
            raise ValueError('Miscast preparation requires the Wizard completed standard action')
        receipt = turn.action_slots[0].execution
        if not old.consumed_execution_ids or old.consumed_execution_ids[-1] != receipt.id:
            raise ValueError('Miscast origin must own the latest consumed execution receipt')
        pending = old.pending_miscast
        if pending is not None:
            if (pending.source.actor_id != wizard.actor_id or pending.source.caster != wizard.caster
                    or pending.round_state != old.casting_round_state
                    or pending.spatial_state != old.casting_spatial_state
                    or pending.magic_state != wizard.magic_state
                    or pending.execution.slot != turn.action_slots[0]
                    or pending.source.id != receipt.id):
                raise ValueError('Casting Miscast origin differs from current live/receipt context')
        else:
            _validate_interruption_origin(old)
        roll = self.origin_roll_request
        if (roll is None or roll.target_id != wizard.actor_id or roll.bonus_dice != 0
                or roll.pool_dice_count != wizard.magic_state.miscast_dice
                or roll.pool_dice_count <= wizard.caster.wizard_level):
            raise ValueError('Miscast origin requires the complete current unprepared triggered Pool')

    @property
    def origin_roll_request(self) -> MiscastRollRequest:
        old = self.state
        if old.pending_miscast is not None:
            roll = old.pending_miscast.pending_miscast
        elif old.pending_interruption is not None:
            roll = old.pending_interruption.miscast_pool.roll_request
        else:
            raise ValueError('Miscast preparation has no raw pending origin')
        if roll is None:
            raise ValueError('Miscast origin must retain its complete roll request')
        return roll

    @property
    def preparation_request(self) -> MiscastPreparationRequest:
        return MiscastPreparationRequest(self.id, self.origin_roll_request,
                                         self.state.wizard.magic_state, spell_to_cast=None)


def _validate_interruption_origin(state: NpcRosterCastingState) -> None:
    """Validate the recorded action-sourced increase without replaying it."""
    raw, wizard = state.pending_interruption, state.wizard
    action = state.round_state.active_turn.action_slots[0].execution
    identifier, rule, pool_rule = action.id + ':skipped-casting', 'RULE-MAGIC-004:skipped-casting-test', 'RULE-MAGIC-004:miscast-pool'
    magic = wizard.magic_state
    previous_pool = magic.miscast_dice - 1
    if magic.casting_lore_id is None or previous_pool > wizard.caster.wizard_level:
        raise ValueError('interruption must originate in an active, not already triggered Casting')
    expected = SkippedCastingTestAfterActionResult(
        identifier, wizard.actor_id, action,
        MiscastPoolIncreaseRequest(identifier + ':increase', wizard.actor_id, 1,
            MiscastPoolIncreaseSourceKind.ACTION, action.id, rule, rule),
        MiscastPoolResolutionResult(identifier + ':miscast-pool', wizard.actor_id, magic, previous_pool, 1,
            MiscastPoolOutcome.MISCAST_TRIGGERED,
            MiscastRollRequest(identifier + ':miscast-pool', identifier + ':increase', wizard.actor_id,
                               magic.miscast_dice, rule_id=pool_rule), (rule, pool_rule)),
        magic, state.consumed_execution_ids[:-1], state.consumed_execution_ids, (rule, pool_rule))
    if raw != expected:
        raise ValueError('interruption Miscast origin differs from the complete action/magic/history proof')


@dataclass(frozen=True, slots=True)
class NpcRosterMiscastPreparationResult:
    source: NpcRosterMiscastPreparationRequest
    preparation: MiscastPreparationResult

    def __post_init__(self) -> None:
        if not isinstance(self.source, NpcRosterMiscastPreparationRequest) or not isinstance(self.preparation, MiscastPreparationResult):
            raise TypeError('bound preparation result requires typed source and K1 preparation')
        request = self.source.preparation_request
        expected = MiscastPreparationResult(
            request.id, request.source.target_id,
            replace(request.state, casting_successes=0, casting_lore_id=None, latest_casting_roll_successes=0),
            request.state.casting_successes,
            (replace(request.source, resolution_id=request.id + ':roll', bonus_dice=0),), (request.rule_id,))
        if type(self.preparation.previous_casting_successes) is not int or self.preparation != expected:
            raise ValueError('K1 preparation differs from the full declined Miscast transition')

    @property
    def roll_request(self) -> MiscastRollRequest:
        # __post_init__ proves exactly one MiscastRollRequest, never a spell.
        return cast(MiscastRollRequest, self.preparation.follow_ups[0])

    @property
    def state(self) -> NpcRosterCastingState:
        old = self.source.state
        return replace(old, wizard=replace(old.wizard, magic_state=self.preparation.state),
                       pending_miscast=None, pending_interruption=None, pending_miscast_continuation=self)


@dataclass(frozen=True, slots=True)
class NpcRosterMiscastRollRequest:
    id: str
    state: NpcRosterCastingState

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            raise TypeError('Miscast roll ID must be a string')
        if not self.id.strip():
            raise ValueError('Miscast roll ID must not be blank')
        if not isinstance(self.state, NpcRosterCastingState):
            raise TypeError('Miscast roll requires the full roster state')
        if not isinstance(self.state.pending_miscast_continuation, NpcRosterMiscastPreparationResult):
            raise ValueError('Miscast roll requires the prepared pending, never a raw or rolled origin')
        if self.id != self.roll_request.resolution_id:
            raise ValueError('Miscast roll ID must match the canonical prepared roll request')

    @property
    def roll_request(self) -> MiscastRollRequest:
        prefix = self.state.pending_miscast_continuation
        if not isinstance(prefix, NpcRosterMiscastPreparationResult):
            raise ValueError('Miscast roll requires its prepared pending')
        return prefix.roll_request


@dataclass(frozen=True, slots=True)
class NpcRosterMiscastRollResult:
    source: NpcRosterMiscastRollRequest
    roll: MiscastRollResult

    def __post_init__(self) -> None:
        if not isinstance(self.source, NpcRosterMiscastRollRequest) or not isinstance(self.roll, MiscastRollResult):
            raise TypeError('bound roll result requires typed source and K1 roll')
        request, roll = self.source.roll_request, self.roll
        values = roll.roll_values
        if (not isinstance(values, tuple) or len(values) != request.dice_count
                or any(type(value) is not int or not 1 <= value <= 10 for value in values)
                or type(roll.total) is not int or roll.total != sum(values)):
            raise ValueError('Miscast roll must retain the exact count, strict d10 values and sum')
        if not isinstance(roll.entry, MiscastTableEntry) or not roll.entry.includes(roll.total):
            raise ValueError('Miscast entry must include the recorded table total')
        wind = MiscastTableEntry(MiscastTableEntryId.UNNATURAL_WIND, 21, 22)
        if (roll.total in (21, 22) or roll.entry.id is MiscastTableEntryId.UNNATURAL_WIND) and roll.entry != wind:
            raise ValueError('Miscast totals 21/22 require exactly the canonical Unnatural Wind entry')
        rule = f'RULE-MISCAST-TABLE:{roll.entry.id.value}'
        expected_effect = MiscastTableEffectRequest(
            request.resolution_id + ':effect', request.resolution_id, request.target_id,
            roll.entry, values, roll.total, request.pool_dice_count, request.bonus_dice, rule)
        expected = MiscastRollResult(
            request.resolution_id, request.target_id, self.source.state.wizard.magic_state,
            values, roll.total, roll.entry, expected_effect, (request.rule_id, rule))
        if not isinstance(roll.effect_request, MiscastTableEffectRequest) or roll != expected:
            raise ValueError('K1 roll differs from the complete prepared source/magic/effect trace')

    @property
    def effect_request(self) -> MiscastTableEffectRequest:
        return self.roll.effect_request

    @property
    def state(self) -> NpcRosterCastingState:
        return replace(self.source.state, pending_miscast_continuation=self)


def validate_npc_miscast_continuation_context(state: NpcRosterCastingState) -> None:
    """Bind the pending owner without recursively constructing prefix.state."""
    prefix = state.pending_miscast_continuation
    if not isinstance(prefix, (NpcRosterMiscastPreparationResult, NpcRosterMiscastRollResult)):
        raise TypeError('Miscast pending requires its full typed preparation or roll result')
    old = prefix.source.state
    for field in fields(state):
        if field.name == 'pending_miscast_continuation':
            continue
        if isinstance(prefix, NpcRosterMiscastPreparationResult) and field.name == 'wizard':
            expected = replace(old.wizard, magic_state=prefix.preparation.state)
        elif isinstance(prefix, NpcRosterMiscastPreparationResult) and field.name in ('pending_miscast', 'pending_interruption'):
            expected = None
        else:
            expected = getattr(old, field.name)
        if getattr(state, field.name) != expected:
            raise ValueError(f'Miscast pending has stale full context: {field.name}')
