"""Typed consequence of the Endurance Test prompted by Critically Injured."""
from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import CharacterInjuryState
from towr.domain.test_models import RollTrace, TestQuality, TestResult


def _identifier(value: str, name: str) -> None:
    if type(value) is not str or not value.strip():
        raise TypeError(f'{name} must be a nonempty string')


def _injury(state: CharacterInjuryState) -> None:
    if type(state) is not CharacterInjuryState:
        raise TypeError('critical injury requires character injury state')
    if type(state.dead) is not bool:
        raise TypeError('critical injury death must be a bool')
    if type(state.wounds) is not tuple or type(state.active_wound_effects) is not tuple:
        raise TypeError('critical injury source collections must be canonical tuples')
    replace(state)
    if type(state.conditions) is not ConditionState or type(state.conditions.conditions) is not frozenset:
        raise TypeError('critical injury requires canonical Conditions')
    replace(state.conditions)
    for wound in state.wounds:
        replace(wound)
    for effect in state.active_wound_effects:
        replace(effect)


@dataclass(frozen=True, slots=True)
class CriticalInjuryTestRequest:
    id: str
    actor_id: str
    state: CharacterInjuryState
    test_id: str

    def __post_init__(self) -> None:
        for name in ('id','actor_id','test_id'):
            _identifier(getattr(self,name),name)
        _injury(self.state)
        if self.state.dead or not self.state.conditions.has(Condition.CRITICALLY_INJURED):
            raise ValueError('only a living Critically Injured character makes this Test')


def critical_injury_state_after_test(
    request: CriticalInjuryTestRequest,
    test: TestResult,
) -> CharacterInjuryState:
    """Apply PG123's consequence; the caller binds the actual Endurance profile.

    This consumer does not roll, spend Fate, consume a next-Test restriction,
    create a Wound, or advance the clock. Orchestration owns those phases.
    """
    if type(request) is not CriticalInjuryTestRequest:
        raise TypeError('critical injury requires its typed source request')
    replace(request)
    if type(test) is not TestResult or type(test.trace) is not RollTrace:
        raise TypeError('critical injury requires its actual Test result')
    trace = test.trace
    if type(trace.request_id) is not str or trace.request_id != request.test_id:
        raise ValueError('critical Endurance Test belongs to another source')
    for name in ('base_dice','pool_cap','regular_dice_delta','cap_bypassing_dice',
                 'dice_before_minimum','rolled_dice','threshold','rolled_successes',
                 'success_delta','successes'):
        if type(getattr(trace,name)) is not int:
            raise TypeError('critical Endurance Test counters must be integers')
    if type(trace.minimum_die_rule_applied) is not bool or type(trace.quality) is not TestQuality:
        raise TypeError('critical Endurance Test flags must retain canonical types')
    if trace.successes < 0 or trace.rolled_successes < 0:
        raise ValueError('critical Endurance Test successes must be nonnegative')
    if trace.successes != max(0,trace.rolled_successes+trace.success_delta):
        raise ValueError('critical Endurance Test success total is inconsistent')
    if test.succeeded:
        return request.state
    if request.state.conditions.has(Condition.DEFENCELESS):
        return replace(request.state,dead=True)
    return replace(request.state,
        conditions=request.state.conditions.with_condition(Condition.DEFENCELESS))


@dataclass(frozen=True, slots=True)
class CriticalInjuryTestResult:
    source_request: CriticalInjuryTestRequest
    test: TestResult
    state: CharacterInjuryState

    def __post_init__(self) -> None:
        _injury(self.state)
        expected = critical_injury_state_after_test(self.source_request,self.test)
        if self.state != expected:
            raise ValueError('critical Endurance result changed unrelated injury state')
