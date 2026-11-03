"""Bounded Battered Leg witnesses (ADR-0059), with no RNG or battle ownership."""

from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import (
    CharacterInjuryState,
    WoundConditionEffect,
    WoundEffectDuration,
    WoundEffectRequest,
    WoundEffectResult,
    WoundEnduranceFailure,
    WoundEnduranceTestRequest,
    WoundEnduranceTestResult,
    WoundEntryId,
    WoundRecord,
    WoundRestrictionEffect,
)
from towr.domain.test_models import (
    Characteristic,
    InitialTestRoll,
    InlineProfile,
    RollTrace,
    Skill,
    TestProfile,
    TestQuality,
    TestRequest,
    TestResult,
)


_RULE_ID = "RULE-WOUND-TABLE:battered_leg"


def _require_id(value: str, label: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    if not value.strip():
        raise ValueError(f"{label} must not be empty")


def _state_structure(state: CharacterInjuryState) -> None:
    if not isinstance(state, CharacterInjuryState):
        raise TypeError("injury_state must be a CharacterInjuryState")
    if type(state.dead) is not bool:
        raise TypeError("injury dead flag must be a boolean")
    if not isinstance(state.conditions, ConditionState):
        raise TypeError("injury Conditions must be a ConditionState")
    if type(state.conditions.conditions) is not frozenset:
        raise TypeError("injury Conditions must retain a frozenset")
    replace(state.conditions)
    if type(state.wounds) is not tuple or type(state.active_wound_effects) is not tuple:
        raise TypeError("injury sequences must retain tuples")
    for wound in state.wounds:
        if not isinstance(wound, WoundRecord) or type(wound.roll_values) is not tuple:
            raise TypeError("Wound records must retain typed rolls")
        replace(wound)
    for effect in state.active_wound_effects:
        if not isinstance(effect, (WoundConditionEffect, WoundRestrictionEffect)):
            raise TypeError("injury requires typed Wound effects")
        replace(effect)
    replace(state)


def _injury(state: CharacterInjuryState) -> None:
    _state_structure(state)
    if state.dead:
        raise ValueError("Battered Leg requires a living character")
    if state.conditions.conditions or state.active_wound_effects:
        raise ValueError("Battered Leg first slice excludes existing Conditions/effects")
    if len(state.wounds) != 1 or not isinstance(state.wounds[0], WoundRecord):
        raise ValueError("Battered Leg first slice requires exactly one Wound")
    wound = state.wounds[0]
    expected = WoundRecord(1, WoundEntryId.BATTERED_LEG, 5, (5,), effect_resolved=True)
    if wound != expected:
        raise ValueError("Battered Leg requires resolved untreated unhealed rolled5")


def _test(request: TestRequest) -> None:
    if not isinstance(request, TestRequest):
        raise TypeError("endurance_test must be a TestRequest")
    if not isinstance(request.profile, (TestProfile, InlineProfile)):
        raise TypeError("Endurance requires an authored Test profile")
    replace(request.profile)
    for name in ("dice_modifiers", "quality_modifiers", "success_modifiers", "reroll_locks"):
        values = getattr(request, name)
        if type(values) is not tuple:
            raise TypeError("Endurance Test sequences must retain tuples")
        if values:
            raise ValueError("Battered Leg first slice requires an unmodified normal Test")
    replace(request)


def _normal_test_result(request: TestRequest, result: TestResult) -> None:
    if not isinstance(result, TestResult) or not isinstance(result.trace, RollTrace):
        raise TypeError("Endurance requires a typed TestResult and RollTrace")
    trace = result.trace
    for name in ("initial_values", "final_values", "rerolls", "applied_rule_ids"):
        if type(getattr(trace, name)) is not tuple:
            raise TypeError("Test trace sequences must retain tuples")
    initial = InitialTestRoll(
        request, trace.base_dice, trace.pool_cap, trace.regular_dice_delta,
        trace.cap_bypassing_dice, trace.dice_before_minimum, trace.rolled_dice,
        trace.threshold, trace.minimum_die_rule_applied, trace.initial_values,
    )
    successes = sum(value <= initial.threshold for value in initial.initial_values)
    counts = (trace.rolled_successes, trace.success_delta, trace.successes)
    if any(type(value) is not int for value in counts):
        raise TypeError("Test success counts must be strict integers")
    if (
        trace.request_id != request.id
        or trace.quality is not TestQuality.NORMAL
        or trace.rerolls
        or trace.final_values != initial.initial_values
        or any(type(value) is not int for value in trace.final_values)
        or counts != (successes, 0, successes)
        or trace.applied_rule_ids
    ):
        raise ValueError("Endurance trace is incompatible with the authored Test parameters")


@dataclass(frozen=True, slots=True)
class BatteredLegEnduranceTestRequest:
    id: str
    actor_id: str
    injury_state: CharacterInjuryState
    wound_effect: WoundEffectResult
    wound_test: WoundEnduranceTestRequest
    endurance_test: TestRequest
    unmounted: bool
    skill: Skill = Skill.ENDURANCE
    characteristic: Characteristic = Characteristic.TOUGHNESS

    def __post_init__(self) -> None:
        _require_id(self.id, "Battered Leg test request id")
        _require_id(self.actor_id, "actor_id")
        if type(self.unmounted) is not bool:
            raise TypeError("unmounted must be an explicit boolean")
        if not self.unmounted:
            raise ValueError("mounted Prone/dismount requires a separate consumer")
        if not isinstance(self.skill, Skill) or not isinstance(self.characteristic, Characteristic):
            raise TypeError("skill and characteristic must be typed")
        if self.skill is not Skill.ENDURANCE:
            raise ValueError("Battered Leg requires an Endurance Test")
        _injury(self.injury_state)
        _test(self.endurance_test)
        if not isinstance(self.wound_effect, WoundEffectResult):
            raise TypeError("wound_effect must be a WoundEffectResult witness")
        effect = self.wound_effect
        if not isinstance(effect.request, WoundEffectRequest):
            raise TypeError("Wound effect must retain its typed source request")
        replace(effect.request)
        _injury(effect.state)
        if not isinstance(self.wound_test, WoundEnduranceTestRequest):
            raise TypeError("wound_test must be a WoundEnduranceTestRequest")
        replace(self.wound_test)
        expected = WoundEnduranceTestRequest(
            f"{effect.request.id}:endurance", 1, WoundEntryId.BATTERED_LEG,
            WoundEnduranceFailure.FALL_PRONE, _RULE_ID,
        )
        if type(effect.follow_ups) is not tuple:
            raise TypeError("Wound effect follow-ups must retain a tuple")
        for follow_up in effect.follow_ups:
            if not isinstance(follow_up, WoundEnduranceTestRequest):
                raise TypeError("Battered Leg requires a typed Endurance follow-up")
            replace(follow_up)
        if (
            effect.request.wound_sequence != 1
            or effect.request.entry_id is not WoundEntryId.BATTERED_LEG
            or effect.request.rule_id != _RULE_ID
            or effect.state != self.injury_state
            or type(effect.follow_ups) is not tuple
            or effect.follow_ups != (expected,)
            or type(effect.applied_rule_ids) is not tuple
            or effect.applied_rule_ids != (_RULE_ID,)
            or self.wound_test != expected
            or self.endurance_test.id != expected.test_id
        ):
            raise ValueError("Battered Leg source, follow-up and Test must match exactly")


@dataclass(frozen=True, slots=True)
class BatteredLegEnduranceTestResult:
    request: BatteredLegEnduranceTestRequest
    test_result: TestResult
    wound_result: WoundEnduranceTestResult

    def __post_init__(self) -> None:
        if not isinstance(self.request, BatteredLegEnduranceTestRequest):
            raise TypeError("request must be a BatteredLegEnduranceTestRequest")
        replace(self.request)
        _normal_test_result(self.request.endurance_test, self.test_result)
        if not isinstance(self.wound_result, WoundEnduranceTestResult):
            raise TypeError("wound_result must be a WoundEnduranceTestResult")
        wound = self.wound_result
        if not isinstance(wound.request, WoundEnduranceTestRequest):
            raise TypeError("Wound result must retain its typed follow-up")
        replace(wound.request)
        if (
            wound.request != self.request.wound_test
            or wound.succeeded is not self.test_result.succeeded
            or type(wound.follow_ups) is not tuple
            or wound.follow_ups
        ):
            raise ValueError("Battered Leg Wound result differs from its completed Test")
        state = wound.state
        _state_structure(state)
        if self.test_result.succeeded:
            _injury(state)
            if state != self.request.injury_state:
                raise ValueError("successful Test must preserve the injury state")
            return
        expected = CharacterInjuryState(
            wounds=self.request.injury_state.wounds,
            conditions=ConditionState(frozenset((Condition.PRONE,))),
            active_wound_effects=(WoundConditionEffect(
                1, Condition.PRONE, WoundEffectDuration.UNTIL_REMOVED,
            ),),
        )
        if state != expected or state.dead is not False:
            raise ValueError("failed Test result must apply only sourced Prone")

