"""Battlefield Musician sources and receipts, PG1.4 III73/V107/114/116/123.

The encounter owner supplies actual actor, audience, acoustic and priority
witnesses. This boundary pays a declared action or records a free signal; it
does not install inspiration or decide its lifetime (ADR-0141 C17).
"""
from dataclasses import dataclass, field, replace
from enum import Enum

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import AcquiredTalent, TalentLoreFact
from towr.domain.test_models import (
    DiceModifier, InitialTestRoll, QualityModifier, RerollLock, RerollTrace,
    RollTrace, SuccessModifier, TestProfile, TestQuality, TestRequest, TestResult,
    _expected_initial_roll_parameters,
)
from towr.domain.tool_inventory_models import ToolKind, ToolUse
from towr.domain.turn_models import (
    ActionExecutionReceipt, ActionSlotGrant, CombatActionDeclaration,
    CombatActionKind, CombatActionSlot, CombatRoundState, CombatSide,
    CombatTurnParticipant, CombatTurnState, ImproviseKind,
)


BATTLEFIELD_MUSICIAN_RULE_ID = 'RULE-TALENT-002:battlefield-musician'
BATTLEFIELD_MUSICIAN_SIGNAL_RULE_ID = BATTLEFIELD_MUSICIAN_RULE_ID + ':signal'


def _identifier(value):
    if type(value) is not str or not value.strip():
        raise TypeError('Battlefield Musician requires exact nonempty identifiers')


def _conditions(value):
    if (type(value) is not ConditionState or type(value.conditions) is not frozenset
            or any(type(condition) is not Condition for condition in value.conditions)):
        raise TypeError('Battlefield Musician requires exact immutable Conditions')
    replace(value)


def _participant(value):
    if type(value) is not CombatTurnParticipant or type(value.side) is not CombatSide:
        raise TypeError('musician audience requires exact typed participant witnesses')
    _identifier(value.entity_id)
    replace(value)


def _declaration(value):
    if (type(value) is not CombatActionDeclaration
            or type(value.kind) is not CombatActionKind
            or type(value.improvise_produces_attack) is not bool
            or value.improvise_kind is not None and type(value.improvise_kind) is not ImproviseKind):
        raise TypeError('musician declaration must retain exact enum/bool types')
    if value.improvise_approach_id is not None:
        _identifier(value.improvise_approach_id)
    replace(value)


def _slot(value):
    if (type(value) is not CombatActionSlot or type(value.index) is not int
            or type(value.grant) is not ActionSlotGrant):
        raise TypeError('musician source requires exact declared action slots')
    _declaration(value.declaration)
    if value.grant_rule_id is not None:
        _identifier(value.grant_rule_id)
    if value.execution is not None:
        receipt = value.execution
        if type(receipt) is not ActionExecutionReceipt:
            raise TypeError('musician clock requires exact execution receipts')
        for name in ('id', 'executor_rule_id', 'source_request_id', 'result_request_id', 'actor_id'):
            _identifier(getattr(receipt, name))
        if type(receipt.round_number) is not int or type(receipt.slot_index) is not int:
            raise TypeError('musician receipt clock requires exact integers')
        _declaration(receipt.declaration)
        replace(receipt)
    replace(value)


def _round(value):
    if type(value) is not CombatRoundState or type(value.round_number) is not int:
        raise TypeError('Battlefield Musician requires the exact actual round clock')
    for name in ('participants', 'side_order', 'completed_turn_entity_ids', 'excluded_turn_entity_ids'):
        if type(getattr(value, name)) is not tuple:
            raise TypeError('musician clock collections require canonical tuples')
    for participant in value.participants:
        _participant(participant)
    if any(type(side) is not CombatSide for side in value.side_order):
        raise TypeError('musician clock requires exact typed side order')
    for actor_id in (*value.completed_turn_entity_ids, *value.excluded_turn_entity_ids):
        _identifier(actor_id)
    turn = value.active_turn
    if type(turn) is not CombatTurnState or type(turn.action_slots) is not tuple:
        raise TypeError('Battlefield Musician requires an actual active turn')
    _identifier(turn.actor_id)
    if type(turn.side) is not CombatSide:
        raise TypeError('musician turn requires its exact typed side')
    for slot in turn.action_slots:
        _slot(slot)
    replace(turn)
    replace(value)


@dataclass(frozen=True, slots=True)
class BattlefieldMusicianSource:
    actor_id: str
    talent: AcquiredTalent
    tool_use: ToolUse
    music_lore: TalentLoreFact
    fellowship: int
    leadership: int

    def __post_init__(self):
        _identifier(self.actor_id)
        if type(self.talent) is not AcquiredTalent:
            raise TypeError('Battlefield Musician requires its actual acquired Talent')
        replace(self.talent)
        if self.talent.id is not TalentId.BATTLEFIELD_MUSICIAN:
            raise ValueError('another Talent cannot authorize Battlefield Musician')
        if type(self.tool_use) is not ToolUse:
            raise TypeError('Battlefield Musician requires the actual physical ToolUse')
        replace(self.tool_use)
        if (self.tool_use.actor_id != self.actor_id
                or self.tool_use.kind is not ToolKind.MUSICIANS_GEAR):
            raise ValueError('musician gear must be held and used by this actual musician')
        if type(self.music_lore) is not TalentLoreFact:
            raise TypeError('playing Trade Tools requires its actual Music Lore fact')
        replace(self.music_lore)
        if self.music_lore.id != 'music' or self.music_lore.magic:
            raise ValueError('playing musician gear requires nonmagical Music Lore')
        if type(self.fellowship) is not int or type(self.leadership) is not int:
            raise TypeError('Fellowship and Leadership require exact integer ratings')
        TestProfile(self.fellowship, self.leadership)


@dataclass(frozen=True, slots=True)
class BattlefieldMusicianListener:
    actor_id: str
    side: CombatSide
    alive: bool
    conditions: ConditionState
    range_band: RangedWeaponRange
    can_hear: bool

    def __post_init__(self):
        _identifier(self.actor_id)
        if type(self.side) is not CombatSide or type(self.range_band) is not RangedWeaponRange:
            raise TypeError('musician listeners require exact side and distance witnesses')
        if type(self.alive) is not bool or type(self.can_hear) is not bool:
            raise TypeError('listener life and acoustic facts require exact booleans')
        _conditions(self.conditions)


def _context(round_state, source, actor_conditions, listeners, audience_participants):
    _round(round_state)
    if type(source) is not BattlefieldMusicianSource:
        raise TypeError('Battlefield Musician requires its complete typed source')
    replace(source)
    _conditions(actor_conditions)
    if actor_conditions.has(Condition.DEFENCELESS):
        raise ValueError('Defenceless musicians cannot perform actions or incidental music signals')
    if round_state.active_turn.actor_id != source.actor_id:
        raise ValueError('Battlefield Musician requires this musician\'s actual active turn')
    if type(audience_participants) is not tuple:
        raise TypeError('supplemental audience requires an exact participant tuple')
    roster = {participant.entity_id: participant.side for participant in round_state.participants}
    for participant in audience_participants:
        _participant(participant)
        if participant.entity_id in roster:
            raise ValueError('audience witnesses cannot duplicate or alias actual clock participants')
        roster[participant.entity_id] = participant.side
    if type(listeners) is not tuple:
        raise TypeError('musician listener priority requires an exact ordered tuple')
    ids = set()
    for listener in listeners:
        if type(listener) is not BattlefieldMusicianListener:
            raise TypeError('musician listener priority requires exact typed witnesses')
        replace(listener)
        if listener.actor_id in ids:
            raise ValueError('musician listeners must retain distinct actual actor identities')
        ids.add(listener.actor_id)
        if roster.get(listener.actor_id) is not listener.side:
            raise ValueError('musician listener side must match its actual roster participant')


def _heard_listeners(round_state, source, listeners, *, inspiration):
    return tuple(listener for listener in listeners
        if listener.actor_id != source.actor_id
        and listener.side is round_state.active_turn.side
        and listener.alive and listener.can_hear
        and not listener.conditions.has(Condition.DEAFENED)
        and (not inspiration or listener.range_band in (
            RangedWeaponRange.CLOSE, RangedWeaponRange.SHORT, RangedWeaponRange.MEDIUM)))


def _test(request):
    if type(request) is not TestRequest or type(request.profile) is not TestProfile:
        raise TypeError('musician Leadership requires its exact Fellowship/Leadership Test')
    _identifier(request.id)
    if type(request.profile.characteristic) is not int or type(request.profile.skill) is not int:
        raise TypeError('musician Test ratings require exact integers')
    replace(request.profile)
    for name, kind in (('dice_modifiers', DiceModifier), ('quality_modifiers', QualityModifier),
            ('success_modifiers', SuccessModifier), ('reroll_locks', RerollLock)):
        values = getattr(request, name)
        if type(values) is not tuple or any(type(item) is not kind for item in values):
            raise TypeError('musician Test modifiers require canonical typed tuples')
        for item in values:
            _identifier(item.rule_id)
            replace(item)
            if kind is DiceModifier and type(item.bypasses_pool_cap) is not bool:
                raise TypeError('musician dice cap bypass requires an exact boolean')
    replace(request)


def _completed_test(request, result):
    """Admit recorded final rolls without RNG or replacing reroll decisions."""
    _test(request)
    if type(result) is not TestResult or type(result.trace) is not RollTrace:
        raise TypeError('musician completion requires the complete actual Test and trace')
    trace = result.trace
    _identifier(trace.request_id)
    for name in ('base_dice', 'pool_cap', 'regular_dice_delta', 'cap_bypassing_dice',
            'dice_before_minimum', 'rolled_dice', 'threshold', 'rolled_successes', 'success_delta', 'successes'):
        if type(getattr(trace, name)) is not int:
            raise TypeError('musician Test counters require exact integers')
    if type(trace.minimum_die_rule_applied) is not bool or type(trace.quality) is not TestQuality:
        raise TypeError('musician Test flag and quality require exact types')
    for name in ('initial_values', 'final_values', 'rerolls', 'applied_rule_ids'):
        if type(getattr(trace, name)) is not tuple:
            raise TypeError('musician completed Test collections require exact tuples')
    for value in (*trace.initial_values, *trace.final_values):
        if type(value) is not int or not 1 <= value <= 10:
            raise ValueError('musician Test requires actual recorded d10 values')
    parameters = _expected_initial_roll_parameters(request)
    InitialTestRoll(request, *parameters, trace.initial_values)
    qualities = {item.quality for item in request.quality_modifiers}
    quality = next(iter(qualities)) if len(qualities) == 1 else TestQuality.NORMAL
    locked = {item.value for item in request.reroll_locks}
    eligible = tuple(index for index, value in enumerate(trace.initial_values)
        if value not in locked and (value <= parameters[6] if quality is TestQuality.GRIM else value > parameters[6]))
    for reroll in trace.rerolls:
        if type(reroll) is not RerollTrace or any(type(value) is not int
                for value in (reroll.index, reroll.original, reroll.replacement)):
            raise TypeError('musician rerolls require exact recorded coordinates and values')
    indices = tuple(item.index for item in trace.rerolls)
    if (indices != tuple(sorted(set(indices))) or quality is TestQuality.NORMAL and indices
            or quality is TestQuality.GRIM and indices != eligible
            or quality is TestQuality.GLORIOUS and not set(indices) <= set(eligible)):
        raise ValueError('musician final Test changed legal quality or reroll choices')
    final = list(trace.initial_values)
    for reroll in trace.rerolls:
        if reroll.original != final[reroll.index] or not 1 <= reroll.replacement <= 10:
            raise ValueError('musician reroll changed an actual original or replacement die')
        final[reroll.index] = reroll.replacement
    for rule_id in trace.applied_rule_ids:
        _identifier(rule_id)
    successes = sum(value <= parameters[6] for value in final)
    delta = sum(item.amount for item in request.success_modifiers)
    rules = tuple(item.rule_id for name in ('dice_modifiers', 'quality_modifiers',
        'success_modifiers', 'reroll_locks') for item in getattr(request, name))
    expected = RollTrace(request.id, *parameters, quality, trace.initial_values,
        trace.rerolls, tuple(final), successes, delta, max(0, successes + delta), rules)
    if trace != expected:
        raise ValueError('musician final Test differs from its complete actual source')


@dataclass(frozen=True, slots=True)
class BattlefieldMusicianActionRequest:
    id: str
    round_state: CombatRoundState
    source: BattlefieldMusicianSource
    actor_conditions: ConditionState
    slot_index: int
    leadership_test: TestRequest
    listeners: tuple[BattlefieldMusicianListener, ...]
    audience_participants: tuple[CombatTurnParticipant, ...] = field(default=(), kw_only=True)

    def __post_init__(self):
        _identifier(self.id)
        _context(self.round_state, self.source, self.actor_conditions,
            self.listeners, self.audience_participants)
        _test(self.leadership_test)
        if self.leadership_test.profile != TestProfile(self.source.fellowship, self.source.leadership):
            raise ValueError('Leadership Test must use this musician\'s actual Fellowship and Leadership')
        if type(self.slot_index) is not int:
            raise TypeError('musician action slot requires an exact integer')
        turn = self.round_state.active_turn
        if self.slot_index not in (1, 2) or self.slot_index > len(turn.action_slots):
            raise ValueError('musician action requires its actually reserved ordinary slot')
        slot = turn.action_slots[self.slot_index - 1]
        expected = CombatActionDeclaration(CombatActionKind.IMPROVISE,
            improvise_kind=ImproviseKind.ABILITY,
            improvise_approach_id=BATTLEFIELD_MUSICIAN_RULE_ID)
        if (slot.declaration != expected or slot.grant not in (ActionSlotGrant.STANDARD, ActionSlotGrant.FATE)
                or slot.executed or any(not item.executed for item in turn.action_slots[:self.slot_index - 1])):
            raise ValueError('musician action must execute its unused declared ordinary Ability slot in order')
        if self.actor_conditions.has(Condition.DEFENCELESS):
            raise ValueError('Defenceless musicians cannot take the Leadership action')

    @property
    def actor_id(self) -> str:
        return self.source.actor_id


def _action_values(request, result):
    if type(request) is not BattlefieldMusicianActionRequest:
        raise TypeError('musician action requires its exact typed complete request')
    replace(request)
    _completed_test(request.leadership_test, result)
    from towr.domain.honour_bound_models import validate_honour_bound_test_source
    validate_honour_bound_test_source(request.leadership_test,result,actor_id=request.actor_id)
    selected = _heard_listeners(request.round_state, request.source, request.listeners,
        inspiration=True)[:result.effective_successes]
    turn = request.round_state.active_turn
    previous_slot = turn.action_slots[request.slot_index - 1]
    receipt = ActionExecutionReceipt(request.id, BATTLEFIELD_MUSICIAN_RULE_ID,
        request.id, result.trace.request_id, request.actor_id,
        request.round_state.round_number, request.slot_index, previous_slot.declaration)
    slot = replace(previous_slot, execution=receipt)
    slots = tuple(slot if item.index == slot.index else item for item in turn.action_slots)
    updated = replace(request.round_state, active_turn=replace(turn, action_slots=slots))
    rules = tuple(dict.fromkeys((BATTLEFIELD_MUSICIAN_RULE_ID, *result.trace.applied_rule_ids)))
    return selected, slot, updated, rules


@dataclass(frozen=True, slots=True)
class BattlefieldMusicianActionResult:
    request_id: str
    source_request: BattlefieldMusicianActionRequest
    test_result: TestResult
    selected_listeners: tuple[BattlefieldMusicianListener, ...]
    previous_round_state: CombatRoundState
    round_state: CombatRoundState
    slot: CombatActionSlot
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self):
        _identifier(self.request_id)
        selected, slot, updated, rules = _action_values(self.source_request, self.test_result)
        _round(self.previous_round_state)
        _round(self.round_state)
        if (type(self.slot) is not CombatActionSlot or type(self.selected_listeners) is not tuple
                or type(self.applied_rule_ids) is not tuple):
            raise TypeError('musician result requires its exact slot, listener and rule receipts')
        _slot(self.slot)
        for rule_id in self.applied_rule_ids:
            _identifier(rule_id)
        for listener in self.selected_listeners:
            if type(listener) is not BattlefieldMusicianListener:
                raise TypeError('musician result recipients require exact listener witnesses')
            replace(listener)
        if (self.request_id != self.source_request.id
                or self.previous_round_state != self.source_request.round_state
                or (self.selected_listeners, self.slot, self.round_state, self.applied_rule_ids)
                != (selected, slot, updated, rules)):
            raise ValueError('musician action result differs from its complete source, Test or slot receipt')

    @property
    def beneficiary_ids(self) -> tuple[str, ...]:
        return tuple(listener.actor_id for listener in self.selected_listeners)


class BattlefieldMusicianSignalKind(str, Enum):
    PRESENCE = 'presence'
    RETREAT = 'retreat'


@dataclass(frozen=True, slots=True)
class BattlefieldMusicianSignalReceipt:
    id: str
    source: BattlefieldMusicianSource
    round_state: CombatRoundState
    actor_conditions: ConditionState
    kind: BattlefieldMusicianSignalKind
    listeners: tuple[BattlefieldMusicianListener, ...]
    heard_actor_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]
    audience_participants: tuple[CombatTurnParticipant, ...] = field(default=(), kw_only=True)

    def __post_init__(self):
        _identifier(self.id)
        _context(self.round_state, self.source, self.actor_conditions,
            self.listeners, self.audience_participants)
        if type(self.kind) is not BattlefieldMusicianSignalKind:
            raise TypeError('musician signal requires its exact presence or retreat selection')
        if type(self.heard_actor_ids) is not tuple or type(self.applied_rule_ids) is not tuple:
            raise TypeError('musician signal requires exact heard-actor and rule tuples')
        for actor_id in self.heard_actor_ids:
            _identifier(actor_id)
        for rule_id in self.applied_rule_ids:
            _identifier(rule_id)
        expected = tuple(listener.actor_id for listener in _heard_listeners(
            self.round_state, self.source, self.listeners, inspiration=False))
        if (self.heard_actor_ids != expected
                or self.applied_rule_ids != (BATTLEFIELD_MUSICIAN_SIGNAL_RULE_ID,)):
            raise ValueError('musician signal changed its actual hearing or source rule')

    @property
    def source_turn(self) -> tuple[str, int]:
        return self.source.actor_id, self.round_state.round_number


@dataclass(frozen=True, slots=True)
class BattlefieldMusicianSignalRequest:
    id: str
    round_state: CombatRoundState
    source: BattlefieldMusicianSource
    actor_conditions: ConditionState
    kind: BattlefieldMusicianSignalKind
    listeners: tuple[BattlefieldMusicianListener, ...]
    previous_receipts: tuple[BattlefieldMusicianSignalReceipt, ...] = ()
    audience_participants: tuple[CombatTurnParticipant, ...] = field(default=(), kw_only=True)

    def __post_init__(self):
        _identifier(self.id)
        _context(self.round_state, self.source, self.actor_conditions,
            self.listeners, self.audience_participants)
        if type(self.kind) is not BattlefieldMusicianSignalKind:
            raise TypeError('musician signal requires its exact typed selection')
        if type(self.previous_receipts) is not tuple:
            raise TypeError('musician prior signals require an exact receipt tuple')
        ids, turns = set(), set()
        for receipt in self.previous_receipts:
            if type(receipt) is not BattlefieldMusicianSignalReceipt:
                raise TypeError('musician prior signals require exact complete receipts')
            replace(receipt)
            if receipt.id in ids or receipt.source_turn in turns:
                raise ValueError('musician prior signal receipts cannot duplicate IDs or source turns')
            ids.add(receipt.id)
            turns.add(receipt.source_turn)
        if self.id in ids or (self.source.actor_id, self.round_state.round_number) in turns:
            raise ValueError('a musician can issue only one selected signal on its actual source turn')


@dataclass(frozen=True, slots=True)
class BattlefieldMusicianSignalResult:
    source_request: BattlefieldMusicianSignalRequest
    receipt: BattlefieldMusicianSignalReceipt
    receipts: tuple[BattlefieldMusicianSignalReceipt, ...]

    def __post_init__(self):
        if (type(self.source_request) is not BattlefieldMusicianSignalRequest
                or type(self.receipt) is not BattlefieldMusicianSignalReceipt
                or type(self.receipts) is not tuple):
            raise TypeError('musician signal result requires exact request and receipt sources')
        request = self.source_request
        replace(request)
        replace(self.receipt)
        for receipt in self.receipts:
            if type(receipt) is not BattlefieldMusicianSignalReceipt:
                raise TypeError('musician signal result bank requires exact complete receipts')
            replace(receipt)
        expected = BattlefieldMusicianSignalReceipt(request.id, request.source,
            request.round_state, request.actor_conditions, request.kind, request.listeners,
            tuple(listener.actor_id for listener in _heard_listeners(request.round_state,
                request.source, request.listeners, inspiration=False)),
            (BATTLEFIELD_MUSICIAN_SIGNAL_RULE_ID,), audience_participants=request.audience_participants)
        if self.receipt != expected or self.receipts != (*request.previous_receipts, self.receipt):
            raise ValueError('musician signal result must append exactly its actual incidental receipt')
