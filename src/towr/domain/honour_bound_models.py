"""Honour Bound activation and session resource, PG1.4 III77/V111.

The owner binds actual oath-fulfilling Tests and GM context. Preparation does
not execute a Test, invent successes or grant Fate to an NPC. Unmitigated
Success emits the existing constrained effect with a real spend, never a burn.
"""
from dataclasses import dataclass, field, replace

from towr.domain.fate_models import (
    FateSessionState, FateSpendKind, FateSpendRecord, FateRefreshRecord, FateBurnRecord,
    FateUnmitigatedSuccessEffectRequest, _fate_spend_funding, _fate_spend_rule_ids,
)
from towr.domain.fate_unmitigated_success_models import _validate_completed_test
from towr.domain.lady_blessing_models import LadyOathDecision, OathDecisionKind, _id, _ids
from towr.domain.oath_context_models import OathBattleContext
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import AcquiredTalent
from towr.domain.test_models import (
    DiceModifier, InitialTestRoll, InlineProfile, QualityModifier, QualityModifierSource,
    RerollLock, RollTrace, SuccessModifier, TestProfile, TestQuality, TestRequest, TestResult,
)


HONOUR_BOUND_GLORIOUS_RULE_ID = 'RULE-TALENT-002:honour-bound-glorious'
HONOUR_BOUND_UNMITIGATED_RULE_ID = 'RULE-TALENT-002:honour-bound-unmitigated'


@dataclass(frozen=True, slots=True)
class HonourBoundState:
    actor_id: str
    talent: AcquiredTalent
    session_id: str
    activation_id: str | None = None
    oath_decisions: tuple[LadyOathDecision, ...] = ()
    previous_session_ids: tuple[str, ...] = field(default=(), kw_only=True)

    def __post_init__(self):
        _id(self.actor_id)
        _id(self.session_id)
        if type(self.talent) is not AcquiredTalent:
            raise TypeError('Honour Bound requires its complete exact acquisition source')
        replace(self.talent)
        if self.talent.id is not TalentId.HONOUR_BOUND:
            raise ValueError('another Talent cannot grant an Honour Bound activation')
        if self.activation_id is not None:
            _id(self.activation_id)
        _ids(self.previous_session_ids)
        if self.session_id in self.previous_session_ids:
            raise ValueError('a previous session cannot refresh Honour Bound')
        if type(self.oath_decisions) is not tuple:
            raise TypeError('Honour Bound retains the exact ordered GM decision history')
        seen, barred = set(), False
        for decision in self.oath_decisions:
            if type(decision) is not LadyOathDecision:
                raise TypeError('Honour Bound requires actual typed GM oath decisions')
            replace(decision)
            if decision.actor_id != self.actor_id or decision.id in seen:
                raise ValueError('Honour Bound decisions cannot change owner or repeat a source')
            if decision.kind is OathDecisionKind.PENANCE_APPROVED and not barred:
                raise ValueError('GM penance requires a preceding actual oath breach')
            seen.add(decision.id)
            barred = decision.kind is OathDecisionKind.BREACH

    @property
    def oath_barred(self):
        return bool(self.oath_decisions and self.oath_decisions[-1].kind is OathDecisionKind.BREACH)

    @property
    def available(self):
        return self.activation_id is None and not self.oath_barred


def _state(state):
    if type(state) is not HonourBoundState:
        raise TypeError('Honour Bound requires its exact current session state')
    replace(state)


def _context(state, context, *, activating=False):
    _state(state)
    if type(context) is not OathBattleContext:
        raise TypeError('Honour Bound needs its actual typed GM oath context')
    replace(context)
    if context.oath_id != state.talent.acquisitions[0].choice.oath_id:
        raise ValueError('Honour Bound context replaced the actual acquired oath')
    if activating and (not state.available or context.honour_bound_used_this_session
            or not context.combat_tests_fulfil_oath_confirmed):
        raise ValueError('Honour Bound activation requires an unused lawful oath-fulfilling Test')


def initial_honour_bound_state(actor_id, talent, session_id, context):
    state = HonourBoundState(actor_id, talent, session_id)
    _context(state, context)
    if context.honour_bound_used_this_session:
        state = replace(state, activation_id='external-use:' + context.gm_confirmation_id)
    if not context.in_good_standing_confirmed:
        state = record_honour_bound_oath_decision(state, LadyOathDecision(
            context.gm_confirmation_id + ':initial-breach', actor_id, OathDecisionKind.BREACH))
    return state


def record_honour_bound_oath_decision(state, decision):
    _state(state)
    if type(decision) is not LadyOathDecision:
        raise TypeError('Honour Bound requires its explicit typed GM decision')
    replace(decision)
    return replace(state, oath_decisions=(*state.oath_decisions, decision))


def begin_honour_bound_session(state, session_id):
    """Only a genuinely new session refreshes use; oath breaches persist."""
    _state(state)
    _id(session_id)
    return HonourBoundState(state.actor_id, state.talent, session_id,
        oath_decisions=state.oath_decisions,
        previous_session_ids=(*state.previous_session_ids, state.session_id))


def _test(test):
    if type(test) is not TestRequest:
        raise TypeError('Honour Bound must retain the actual exact Test request')
    _id(test.id)
    if type(test.profile) not in (TestProfile, InlineProfile):
        raise TypeError('Honour Bound requires the actual exact Test profile')
    replace(test.profile)
    for name, kind in (('dice_modifiers', DiceModifier), ('quality_modifiers', QualityModifier),
            ('success_modifiers', SuccessModifier), ('reroll_locks', RerollLock)):
        values = getattr(test, name)
        if type(values) is not tuple or any(type(value) is not kind for value in values):
            raise TypeError('Honour Bound retains exact immutable Test modifiers')
        for value in values:
            replace(value)
    replace(test)


@dataclass(frozen=True, slots=True)
class HonourBoundGloriousRequest:
    id: str
    state: HonourBoundState
    context: OathBattleContext
    test: TestRequest

    def __post_init__(self):
        _id(self.id)
        _context(self.state, self.context, activating=True)
        _test(self.test)
        if any(value.rule_id == HONOUR_BOUND_GLORIOUS_RULE_ID
                for value in self.test.quality_modifiers):
            raise ValueError('Honour Bound cannot prepare the same activation twice')


def _glorious_values(request):
    if type(request) is not HonourBoundGloriousRequest:
        raise TypeError('Honour Bound Glorious requires its exact complete request')
    replace(request)
    modifier = QualityModifier(HONOUR_BOUND_GLORIOUS_RULE_ID, TestQuality.GLORIOUS,
        QualityModifierSource.TALENT, request.id)
    return replace(request.state, activation_id=request.id), replace(request.test,
        quality_modifiers=(*request.test.quality_modifiers, modifier))


@dataclass(frozen=True, slots=True)
class HonourBoundGloriousResult:
    source_request: HonourBoundGloriousRequest
    state: HonourBoundState
    test: TestRequest
    applied_rule_ids: tuple[str, ...] = (HONOUR_BOUND_GLORIOUS_RULE_ID,)

    def __post_init__(self):
        expected = _glorious_values(self.source_request)
        _state(self.state)
        _test(self.test)
        if ((self.state, self.test) != expected or type(self.applied_rule_ids) is not tuple
                or self.applied_rule_ids != (HONOUR_BOUND_GLORIOUS_RULE_ID,)):
            raise ValueError('Honour Bound Glorious changed its activation, session or Test source')


def activate_honour_bound_glorious(request):
    return HonourBoundGloriousResult(request, *_glorious_values(request))


def _fate(state):
    if type(state) is not FateSessionState:
        raise TypeError('Honour Bound spending requires the actual player Fate state')
    _id(state.actor_id)
    _id(state.session_id)
    _ids(state.resource_event_ids)
    for name, kind in (('spends', FateSpendRecord), ('refreshes', FateRefreshRecord), ('burns', FateBurnRecord)):
        values = getattr(state, name)
        if type(values) is not tuple or any(type(value) is not kind for value in values):
            raise TypeError('Honour Bound preserves exact immutable Fate records')
        for value in values:
            replace(value)
    replace(state)


@dataclass(frozen=True, slots=True)
class HonourBoundUnmitigatedRequest:
    id: str
    state: HonourBoundState
    context: OathBattleContext
    fate_state: FateSessionState
    test: TestRequest
    gm_scope_agreement_id: str
    initial_roll: InitialTestRoll | None = None
    final_result: TestResult | None = None

    def __post_init__(self):
        _id(self.id)
        _context(self.state, self.context, activating=True)
        _test(self.test)
        _fate(self.fate_state)
        _id(self.gm_scope_agreement_id)
        if (self.fate_state.actor_id != self.state.actor_id
                or self.fate_state.session_id != self.state.session_id):
            raise ValueError('Honour Bound cannot spend another actor or session\'s Fate')
        if not self.fate_state.can_spend:
            raise ValueError('Honour Bound Unmitigated Success requires an available Fate spend')
        if self.id + ':fate-spend' in {
                *self.fate_state.resource_event_ids, *(record.id for record in self.fate_state.spends)}:
            raise ValueError('Honour Bound Fate expenditure source was already used')
        if any(record.kind is FateSpendKind.HONOUR_BOUND_UNMITIGATED_SUCCESS
                and record.subject_id == self.test.id for record in self.fate_state.spends):
            raise ValueError('Honour Bound cannot spend twice on the same Test')
        if (self.initial_roll is None) == (self.final_result is None):
            raise ValueError('Honour Bound requires exactly one actual initial or completed Test witness')
        if self.initial_roll is not None:
            if type(self.initial_roll) is not InitialTestRoll or type(self.initial_roll.initial_values) is not tuple:
                raise TypeError('Honour Bound requires its exact actual immutable initial roll')
            replace(self.initial_roll)
            if self.initial_roll.request != self.test:
                raise ValueError('Honour Bound initial roll belongs to another actual Test')
        else:
            if type(self.final_result) is not TestResult or type(self.final_result.trace) is not RollTrace:
                raise TypeError('Honour Bound requires its actual exact completed Test')
            trace = self.final_result.trace
            for name in ('base_dice', 'pool_cap', 'regular_dice_delta', 'cap_bypassing_dice',
                    'dice_before_minimum', 'rolled_dice', 'threshold'):
                if type(getattr(trace, name)) is not int:
                    raise TypeError('Honour Bound retains exact completed Test pool parameters')
            if (type(trace.minimum_die_rule_applied) is not bool
                    or any(type(getattr(trace, name)) is not tuple
                        for name in ('initial_values', 'final_values', 'rerolls', 'applied_rule_ids'))):
                raise TypeError('Honour Bound retains exact immutable completed Test evidence')
            _validate_completed_test(_effect(self), self.final_result)


def _effect(request):
    return FateUnmitigatedSuccessEffectRequest(request.id + ':effect', request.id,
        request.state.session_id, request.state.actor_id, request.test, request.initial_roll,
        request.gm_scope_agreement_id)


def _unmitigated_values(request):
    if type(request) is not HonourBoundUnmitigatedRequest:
        raise TypeError('Honour Bound Unmitigated Success requires its exact complete source')
    replace(request)
    spend = FateSpendRecord(request.id + ':fate-spend', request.fate_state.session_id,
        request.state.actor_id, FateSpendKind.HONOUR_BOUND_UNMITIGATED_SUCCESS,
        request.test.id, HONOUR_BOUND_UNMITIGATED_RULE_ID, _fate_spend_funding(request.fate_state))
    return (replace(request.state, activation_id=request.id),
        replace(request.fate_state, spends=(*request.fate_state.spends, spend)), spend, _effect(request))


@dataclass(frozen=True, slots=True)
class HonourBoundUnmitigatedResult:
    source_request: HonourBoundUnmitigatedRequest
    state: HonourBoundState
    fate_state: FateSessionState
    spend: FateSpendRecord
    effect: FateUnmitigatedSuccessEffectRequest
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self):
        expected = _unmitigated_values(self.source_request)
        _state(self.state)
        _fate(self.fate_state)
        if type(self.spend) is not FateSpendRecord or type(self.effect) is not FateUnmitigatedSuccessEffectRequest:
            raise TypeError('Honour Bound preserves its actual spend and constrained success effect')
        replace(self.spend)
        replace(self.effect)
        _test(self.effect.test)
        if type(self.effect.maximum_wounds_inflicted) is not int:
            raise TypeError('Unmitigated Success preserves its exact one-Wound limit')
        if ((self.state, self.fate_state, self.spend, self.effect) != expected
                or type(self.applied_rule_ids) is not tuple
                or self.applied_rule_ids != _fate_spend_rule_ids(self.source_request.fate_state,
                    HONOUR_BOUND_UNMITIGATED_RULE_ID)):
            raise ValueError('Honour Bound Unmitigated Success changed its activation or Fate source')


def activate_honour_bound_unmitigated(request):
    return HonourBoundUnmitigatedResult(request, *_unmitigated_values(request),
        _fate_spend_rule_ids(request.fate_state, HONOUR_BOUND_UNMITIGATED_RULE_ID))


@dataclass(frozen=True, slots=True)
class HonourBoundOutcomeGrant:
    """C20 explicit GM maximum for one real final Test, not invented dice.

    Numeric progress cannot exceed all successes in the actual rolled pool
    plus the same flat modifiers. Its categorical outcome is Total Success;
    attack legality and the single-Wound limit remain with their owners.
    """
    activation: HonourBoundUnmitigatedResult
    raw_test: TestResult
    maximum_successes: int = field(init=False)

    def __post_init__(self):
        if type(self.activation) is not HonourBoundUnmitigatedResult:
            raise TypeError('Honour Bound outcome requires its actual paid Unmitigated activation')
        replace(self.activation)
        source = self.activation.source_request
        if source.context.unmitigated_success_scope_confirmed is not True:
            raise ValueError('Honour Bound maximum outcome requires explicit GM scope confirmation')
        if type(self.raw_test) is not TestResult or self.raw_test.honour_bound is not None:
            raise TypeError('Honour Bound retains exactly one unmodified raw completed Test')
        replace(self.raw_test)
        if source.final_result is None or source.final_result != self.raw_test:
            raise ValueError('Honour Bound outcome requires the activation\'s actual final Test witness')
        _validate_completed_test(self.activation.effect,self.raw_test)
        object.__setattr__(self,'maximum_successes',max(0,
            self.raw_test.trace.rolled_dice+self.raw_test.trace.success_delta))


def grant_honour_bound_outcome(activation):
    if type(activation) is not HonourBoundUnmitigatedResult:
        raise TypeError('Honour Bound outcome requires its exact completed activation')
    replace(activation)
    raw = activation.source_request.final_result
    if raw is None:
        raise ValueError('an initial-only activation cannot manufacture a completed Test trace')
    grant = HonourBoundOutcomeGrant(activation,raw)
    return TestResult(raw.trace,honour_bound=grant)


def validate_honour_bound_test_source(request,result,*,actor_id=None):
    """Readmit an optional grant and bind it to the consumer's actual Test."""
    if type(result) is not TestResult:
        raise TypeError('Honour Bound Test source validation requires the actual Test result')
    if result.honour_bound is not None:
        replace(result)
        if result.honour_bound.activation.source_request.test != request:
            raise ValueError('Honour Bound outcome changed the actual prepared Test source')
        if actor_id is not None and result.honour_bound.activation.state.actor_id != actor_id:
            raise ValueError('Honour Bound outcome belongs to another actual actor')
