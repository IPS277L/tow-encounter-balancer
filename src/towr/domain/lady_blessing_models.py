"""Blessing resource accounting, PG1.4 III74/77, independent of prayer timing.

This module records receipts already authorised by an encounter owner. It
does not authorise prayer, infer oath fulfilment, negate injuries, spend Fate
or open runtime admission. Prayer timing is owned by the action consumer.
"""
from dataclasses import dataclass, field, replace
from enum import Enum

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import AcquiredTalent


def _id(value):
    if type(value) is not str or not value.strip():
        raise TypeError('a blessing receipt requires an exact nonempty identifier')


def _ids(values):
    if type(values) is not tuple:
        raise TypeError('blessing history requires an exact ordered tuple')
    for value in values:
        _id(value)
    if len(set(values)) != len(values):
        raise ValueError('blessing history cannot repeat a receipt')


class LadyBlessingLoss(str, Enum):
    BROKEN = 'broken'
    OATH_BREACH = 'oath_breach'


class OathDecisionKind(str, Enum):
    BREACH = 'breach'
    PENANCE_APPROVED = 'penance_approved'


@dataclass(frozen=True, slots=True)
class LadyOathDecision:
    id: str
    actor_id: str
    kind: OathDecisionKind

    def __post_init__(self):
        _id(self.id)
        _id(self.actor_id)
        if type(self.kind) is not OathDecisionKind:
            raise TypeError('oath decisions require an exact typed GM decision')


@dataclass(frozen=True, slots=True)
class LadyBlessingState:
    actor_id: str
    talent: AcquiredTalent
    battle_id: str
    prayers: tuple[str, ...] = ()
    negated_wound_id: str | None = None
    loss: LadyBlessingLoss | None = None
    oath_decisions: tuple[LadyOathDecision, ...] = ()
    previous_battle_ids: tuple[str, ...] = field(default=(), kw_only=True)

    def __post_init__(self):
        _id(self.actor_id)
        _id(self.battle_id)
        if type(self.talent) is not AcquiredTalent:
            raise TypeError('blessing accounting requires its complete acquired Talent')
        replace(self.talent)
        if self.talent.id is not TalentId.BLESSINGS_OF_THE_LADY:
            raise ValueError('another Talent cannot supply the Lady blessing resource')
        _ids(self.prayers)
        _ids(self.previous_battle_ids)
        if self.battle_id in self.previous_battle_ids:
            raise ValueError('a completed battle cannot refresh its blessing resource')
        if self.negated_wound_id is not None:
            _id(self.negated_wound_id)
            if not self.prayers:
                raise ValueError('a Wound cannot consume a blessing that was never received')
        if self.loss is not None:
            if type(self.loss) is not LadyBlessingLoss:
                raise TypeError('a blessing loss requires its exact typed cause')
            if not self.prayers:
                raise ValueError('an unreceived blessing cannot have a loss receipt')
        if type(self.oath_decisions) is not tuple:
            raise TypeError('GM decisions require their exact ordered history')
        seen, barred = set(), False
        for decision in self.oath_decisions:
            if type(decision) is not LadyOathDecision:
                raise TypeError('GM oath history requires exact typed decisions')
            replace(decision)
            if decision.actor_id != self.actor_id or decision.id in seen:
                raise ValueError('GM decisions cannot change owner or repeat a source')
            seen.add(decision.id)
            if decision.kind is OathDecisionKind.PENANCE_APPROVED and not barred:
                raise ValueError('penance approval requires an actual preceding breach')
            barred = decision.kind is OathDecisionKind.BREACH
        if self.loss is LadyBlessingLoss.OATH_BREACH and not self.oath_decisions:
            raise ValueError('oath loss requires its actual GM history')

    @property
    def oath_barred(self):
        return bool(self.oath_decisions and self.oath_decisions[-1].kind is OathDecisionKind.BREACH)

    @property
    def available(self):
        return bool(self.prayers and self.negated_wound_id is None
            and self.loss is None and not self.oath_barred)


def _state(state):
    if type(state) is not LadyBlessingState:
        raise TypeError('blessing accounting requires its exact typed current state')
    replace(state)


def record_lady_prayer(state, prayer_receipt_id):
    """Record an independently authorised prayer; never decide its timing here.

    PG74 limits Wound negation once per battle, not the number of prayers.
    Re-prayer therefore preserves the spent resource even after a lost grant.
    """
    _state(state)
    _id(prayer_receipt_id)
    if state.oath_barred:
        raise ValueError('another prayer requires GM-approved amends for the breach')
    return replace(state, prayers=(*state.prayers, prayer_receipt_id), loss=None)


def record_lady_wound_negation(state, wound_id):
    """Consume a bound owner's actual cancellation receipt, without changing HP."""
    _state(state)
    _id(wound_id)
    if not state.available:
        raise ValueError('no unused active blessing remains for this battle')
    return replace(state, negated_wound_id=wound_id)


def record_lady_broken_gain(state, actor_id, before, after):
    _state(state)
    _id(actor_id)
    if actor_id != state.actor_id:
        raise ValueError('Broken witness belongs to another actor')
    for conditions in (before, after):
        if type(conditions) is not ConditionState:
            raise TypeError('Broken loss needs the actual typed Condition transition')
        replace(conditions)
    if before.has(Condition.BROKEN) or not after.has(Condition.BROKEN):
        raise ValueError('a blessing loss requires a new actual Broken condition')
    return replace(state, loss=LadyBlessingLoss.BROKEN) if state.prayers else state


def record_lady_oath_decision(state, decision):
    _state(state)
    if type(decision) is not LadyOathDecision:
        raise TypeError('an oath judgment requires its explicit typed GM source')
    replace(decision)
    loss = (LadyBlessingLoss.OATH_BREACH if state.prayers else None) if (
        decision.kind is OathDecisionKind.BREACH) else state.loss
    return replace(state, oath_decisions=(*state.oath_decisions, decision), loss=loss)


def begin_lady_blessing_battle(state, battle_id):
    """Reset battle expenditure; oath ineligibility survives until GM amends."""
    _state(state)
    _id(battle_id)
    return LadyBlessingState(state.actor_id, state.talent, battle_id,
        oath_decisions=state.oath_decisions, previous_battle_ids=(*state.previous_battle_ids,state.battle_id))
