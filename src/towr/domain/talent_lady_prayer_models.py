"""Paid Lady prayer, PG1.4 III74; own first actual turn, ADR-0141 C18.

The encounter owner binds the complete TurnStart prefix and acquired source.
No round-number shortcut, inferred pre-battle prayer or Fate is introduced.
"""
from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.lady_blessing_models import (
    LadyBlessingState, _id, _state, record_lady_prayer,
)
from towr.domain.turn_models import (
    ActionExecutionReceipt, ActionSlotGrant, CombatActionDeclaration,
    CombatActionKind, CombatActionSlot, CombatRoundState, CombatTurnStartResult,
    CombatSide, CombatTurnParticipant, CombatTurnState, ImproviseKind,
)


LADY_PRAYER_RULE_ID = 'RULE-TALENT-002:lady-prayer'


def lady_prayer_declaration() -> CombatActionDeclaration:
    return CombatActionDeclaration(CombatActionKind.IMPROVISE,
        improvise_kind=ImproviseKind.ABILITY, improvise_approach_id=LADY_PRAYER_RULE_ID)


def _clock(clock):
    if type(clock) is not CombatRoundState or type(clock.round_number) is not int:
        raise TypeError('Lady prayer requires the actual exact round clock')
    if type(clock.active_turn) is not CombatTurnState:
        raise TypeError('Lady prayer requires an actual active turn')
    turn = clock.active_turn
    _id(turn.actor_id)
    if type(turn.side) is not CombatSide:
        raise TypeError('Lady prayer retains its exact acting side')
    for name in ('participants', 'side_order', 'completed_turn_entity_ids', 'excluded_turn_entity_ids'):
        if type(getattr(clock, name)) is not tuple:
            raise TypeError('Lady prayer retains immutable clock histories')
    for participant in clock.participants:
        if type(participant) is not CombatTurnParticipant or type(participant.side) is not CombatSide:
            raise TypeError('Lady prayer retains exact typed clock participants')
        replace(participant)
    if any(type(side) is not CombatSide for side in clock.side_order):
        raise TypeError('Lady prayer retains exact side order')
    if type(turn.action_slots) is not tuple:
        raise TypeError('Lady prayer retains immutable action slots')
    for slot in turn.action_slots:
        if (type(slot) is not CombatActionSlot or type(slot.index) is not int
                or type(slot.grant) is not ActionSlotGrant):
            raise TypeError('Lady prayer retains exact typed action slots')
        if (type(slot.declaration) is not CombatActionDeclaration
                or type(slot.declaration.improvise_produces_attack) is not bool):
            raise TypeError('Lady prayer retains its exact typed declaration')
        replace(slot.declaration)
        if slot.execution is not None:
            execution = slot.execution
            if (type(execution) is not ActionExecutionReceipt or type(execution.round_number) is not int
                    or type(execution.slot_index) is not int):
                raise TypeError('Lady prayer retains exact typed prior action receipts')
            if type(execution.declaration) is not CombatActionDeclaration:
                raise TypeError('Lady prayer retains its actual prior declaration')
            replace(execution.declaration)
            replace(execution)
        replace(slot)
    replace(turn)
    replace(clock)


def _first_own_turn(clock, actor, starts):
    _clock(clock)
    if type(starts) is not tuple or not starts:
        raise TypeError('Lady prayer needs its complete immutable TurnStart prefix')
    seen_ids, seen_turns = set(), set()
    previous_round = 0
    for start in starts:
        if type(start) is not CombatTurnStartResult:
            raise TypeError('Lady prayer needs exact actual TurnStart receipts')
        _id(start.request_id)
        if type(start.applied_rule_ids) is not tuple:
            raise TypeError('Lady prayer retains actual immutable TurnStart rules')
        for rule in start.applied_rule_ids:
            _id(rule)
        _clock(start.state)
        if (start.state.active_turn != start.turn or start.turn.action_slots
                or start.state.round_number < previous_round):
            raise ValueError('Lady prayer TurnStart changed its actual clock or chronology')
        key = (start.state.round_number, start.turn.actor_id)
        if start.request_id in seen_ids or key in seen_turns:
            raise ValueError('Lady prayer cannot replay or alias an actual TurnStart')
        seen_ids.add(start.request_id)
        seen_turns.add(key)
        previous_round = start.state.round_number
    current = starts[-1]
    if (clock.active_turn.actor_id != actor or current.turn.actor_id != actor
            or replace(clock, active_turn=current.turn) != current.state):
        raise ValueError('Lady prayer prefix must end at this actor\'s current actual turn')
    if sum(start.turn.actor_id == actor for start in starts) != 1:
        raise ValueError('Lady prayer window closes after the first own actual turn')


@dataclass(frozen=True, slots=True)
class LadyPrayerActionRequest:
    id: str
    blessing: LadyBlessingState
    round_state: CombatRoundState
    turn_starts: tuple[CombatTurnStartResult, ...]
    actor_conditions: ConditionState
    slot_index: int

    def __post_init__(self):
        _id(self.id)
        _state(self.blessing)
        _first_own_turn(self.round_state, self.blessing.actor_id, self.turn_starts)
        if (type(self.actor_conditions) is not ConditionState
                or type(self.actor_conditions.conditions) is not frozenset
                or any(type(value) is not Condition for value in self.actor_conditions.conditions)):
            raise TypeError('Lady prayer requires actual exact immutable Conditions')
        replace(self.actor_conditions)
        if self.actor_conditions.has(Condition.DEFENCELESS) or self.actor_conditions.has(Condition.BROKEN):
            raise ValueError('Defenceless or compulsory fleeing cannot take a prayer action')
        if self.blessing.oath_barred:
            raise ValueError('Lady prayer requires GM-approved amends after a breach')
        if type(self.slot_index) is not int:
            raise TypeError('Lady prayer slot requires an exact integer')
        slots = self.round_state.active_turn.action_slots
        if self.slot_index not in (1, 2) or self.slot_index > len(slots):
            raise ValueError('Lady prayer must execute its actual reserved ordinary slot')
        slot = slots[self.slot_index - 1]
        if (slot.declaration != lady_prayer_declaration()
                or slot.grant not in (ActionSlotGrant.STANDARD, ActionSlotGrant.FATE)
                or slot.executed or any(not previous.executed for previous in slots[:self.slot_index - 1])):
            raise ValueError('Lady prayer must execute the declared unused ordinary action in order')


def _prayer_values(request):
    if type(request) is not LadyPrayerActionRequest:
        raise TypeError('Lady prayer requires its exact complete request')
    replace(request)
    turn = request.round_state.active_turn
    slot = turn.action_slots[request.slot_index - 1]
    receipt = ActionExecutionReceipt(request.id, LADY_PRAYER_RULE_ID,
        request.id, request.id, request.blessing.actor_id,
        request.round_state.round_number, request.slot_index, slot.declaration)
    executed = replace(slot, execution=receipt)
    slots = tuple(executed if value.index == executed.index else value for value in turn.action_slots)
    clock = replace(request.round_state, active_turn=replace(turn, action_slots=slots))
    return record_lady_prayer(request.blessing, request.id), clock, executed


@dataclass(frozen=True, slots=True)
class LadyPrayerActionResult:
    source_request: LadyPrayerActionRequest
    blessing: LadyBlessingState
    round_state: CombatRoundState
    slot: CombatActionSlot
    applied_rule_ids: tuple[str, ...] = (LADY_PRAYER_RULE_ID,)

    def __post_init__(self):
        expected = _prayer_values(self.source_request)
        _state(self.blessing)
        _clock(self.round_state)
        if (type(self.slot) is not CombatActionSlot
                or type(self.applied_rule_ids) is not tuple
                or (self.blessing, self.round_state, self.slot) != expected
                or self.applied_rule_ids != (LADY_PRAYER_RULE_ID,)):
            raise ValueError('Lady prayer result replaced its action, clock or blessing source')


def execute_lady_prayer(request: LadyPrayerActionRequest) -> LadyPrayerActionResult:
    """No Test/RNG: pay exactly the reserved action and record the blessing."""
    return LadyPrayerActionResult(request, *_prayer_values(request))
